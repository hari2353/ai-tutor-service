// Lab 03 test suite — runs against BOTH the starter (default, must FAIL on
// assertions) and the solution (`go test -tags solution ./...`, must PASS).
// The switch is the build-tagged pair starter_test.go / solution_test.go,
// which set `newReconciler` to the starter or solution constructor.
//
// This is an external test package (k8soperator_test) so it can import the
// implementation packages, exactly like a real controller-runtime test imports
// your controller package plus its API types.
package k8soperator_test

import (
	"context"
	"fmt"
	"sync"
	"testing"

	k8soperator "tutor/labs/k8soperator"
)

// reconcile drives one reconcile loop for a named Greeting through whichever
// implementation the build tags selected.
func reconcile(t *testing.T, name string, c *k8soperator.ClusterState) (k8soperator.Result, error) {
	t.Helper()
	return newReconciler().Reconcile(context.Background(), name, c)
}

func greeting(name string, replicas int, template string) k8soperator.Greeting {
	return k8soperator.Greeting{
		Name: name,
		Spec: k8soperator.GreetingSpec{MessageTemplate: template, Replicas: replicas},
	}
}

func deploymentFor(t *testing.T, c *k8soperator.ClusterState, name string) k8soperator.Deployment {
	t.Helper()
	d, ok := c.GetDeployment(name)
	if !ok {
		t.Fatalf("deployment %q not found", name)
	}
	return d
}

func conditionsContain(conds []string, want string) bool {
	for _, c := range conds {
		if c == want {
			return true
		}
	}
	return false
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

// TestReconcileCreatesMissingDeployment: the core loop — a Greeting exists,
// its deployment does not; one reconcile must create it with the spec's
// replicas and template, owned by the greeting.
func TestReconcileCreatesMissingDeployment(t *testing.T) {
	c := k8soperator.NewClusterState(greeting("hello", 3, "Hello, %s!"))
	res, err := reconcile(t, "hello", c)
	if err != nil {
		t.Fatalf("Reconcile returned error: %v", err)
	}
	if res.Requeue {
		t.Errorf("Reconcile should not request a requeue on success, got %+v", res)
	}
	d := deploymentFor(t, c, "greeting-hello")
	if d.Replicas != 3 {
		t.Errorf("deployment Replicas = %d, want 3", d.Replicas)
	}
	if d.Template != "Hello, %s!" {
		t.Errorf("deployment Template = %q, want %q", d.Template, "Hello, %s!")
	}
	if d.OwnerRef != "hello" {
		t.Errorf("deployment OwnerRef = %q, want %q", d.OwnerRef, "hello")
	}
}

// TestReconcileCorrectsReplicasDrift: someone scaled the deployment out from
// under us (5 replicas on the cluster, 3 in the spec). Reconcile notices the
// level difference and corrects it.
func TestReconcileCorrectsReplicasDrift(t *testing.T) {
	c := k8soperator.NewClusterState(greeting("hello", 3, "Hello, %s!"))
	if _, err := reconcile(t, "hello", c); err != nil {
		t.Fatalf("initial reconcile failed: %v", err)
	}
	c.ScaleDeployment("greeting-hello", 5) // manual drift injection
	if _, err := reconcile(t, "hello", c); err != nil {
		t.Fatalf("drift reconcile failed: %v", err)
	}
	d := deploymentFor(t, c, "greeting-hello")
	if d.Replicas != 3 {
		t.Errorf("after drift correction Replicas = %d, want 3", d.Replicas)
	}
}

// TestReconcileCorrectsTemplateDrift: pod template changed (e.g. new message).
// Same level-triggered comparison, different field.
func TestReconcileCorrectsTemplateDrift(t *testing.T) {
	c := k8soperator.NewClusterState(greeting("hello", 3, "Hello, %s!"))
	if _, err := reconcile(t, "hello", c); err != nil {
		t.Fatalf("initial reconcile failed: %v", err)
	}
	c.SetGreeting(greeting("hello", 3, "Howdy, %s!")) // spec change: new template
	if _, err := reconcile(t, "hello", c); err != nil {
		t.Fatalf("template-drift reconcile failed: %v", err)
	}
	d := deploymentFor(t, c, "greeting-hello")
	if d.Template != "Howdy, %s!" {
		t.Errorf("after template drift correction Template = %q, want %q", d.Template, "Howdy, %s!")
	}
}

// TestMissingCRIsNoOp: the workqueue hands us a key whose CR was deleted.
// Deletion is handled by garbage collection via ownerRefs — the correct
// response is no error, no requeue, and zero writes.
func TestMissingCRIsNoOp(t *testing.T) {
	c := k8soperator.NewClusterState() // empty cluster
	before := c.WriteCount()
	res, err := reconcile(t, "ghost", c)
	if err != nil {
		t.Fatalf("Reconcile on missing CR must not error, got %v", err)
	}
	if res.Requeue {
		t.Errorf("Reconcile on missing CR must not requeue, got %+v", res)
	}
	if after := c.WriteCount(); after != before {
		t.Errorf("Reconcile on missing CR must not write: WriteCount %d -> %d", before, after)
	}
}

// TestStatusUpdatedWithSyncedCondition: after a successful reconcile the CR's
// status reports ReadyReplicas and carries the "Synced" condition.
func TestStatusUpdatedWithSyncedCondition(t *testing.T) {
	c := k8soperator.NewClusterState(greeting("hello", 3, "Hello, %s!"))
	if _, err := reconcile(t, "hello", c); err != nil {
		t.Fatalf("Reconcile failed: %v", err)
	}
	g, ok := c.GetGreeting("hello")
	if !ok {
		t.Fatal("greeting disappeared from cluster")
	}
	if g.Status.ReadyReplicas != 3 {
		t.Errorf("Status.ReadyReplicas = %d, want 3", g.Status.ReadyReplicas)
	}
	if !conditionsContain(g.Status.Conditions, "Synced") {
		t.Errorf("Status.Conditions = %v, want to contain %q", g.Status.Conditions, "Synced")
	}
}

// TestIdempotencyNoWritesOnSecondReconcile: the heart of level-triggered
// design — an immediate second reconcile finds the world already as the spec
// wants it and must write nothing. (If this fails you are "edge-triggered".)
func TestIdempotencyNoWritesOnSecondReconcile(t *testing.T) {
	c := k8soperator.NewClusterState(greeting("hello", 3, "Hello, %s!"))
	if _, err := reconcile(t, "hello", c); err != nil {
		t.Fatalf("first reconcile failed: %v", err)
	}
	after1 := c.WriteCount()
	if _, err := reconcile(t, "hello", c); err != nil {
		t.Fatalf("second reconcile failed: %v", err)
	}
	if after2 := c.WriteCount(); after2 != after1 {
		t.Errorf("second reconcile wrote to the cluster: WriteCount %d -> %d (must be idempotent)", after1, after2)
	}
}

// TestDriftRestoredAfterExternalChange: external change + reconcile = spec
// wins. Proves the loop is self-healing rather than event-driven: we don't
// care WHO changed the deployment, only what state it is in now.
func TestDriftRestoredAfterExternalChange(t *testing.T) {
	c := k8soperator.NewClusterState(greeting("hello", 3, "Hello, %s!"))
	if _, err := reconcile(t, "hello", c); err != nil {
		t.Fatalf("initial reconcile failed: %v", err)
	}
	c.ScaleDeployment("greeting-hello", 99) // a human with kubectl
	res, err := reconcile(t, "hello", c)
	if err != nil {
		t.Fatalf("reconcile after external change failed: %v", err)
	}
	if res.Requeue {
		t.Errorf("successful convergence should not requeue, got %+v", res)
	}
	if d := deploymentFor(t, c, "greeting-hello"); d.Replicas != 3 {
		t.Errorf("external change was not corrected: Replicas = %d, want 3", d.Replicas)
	}
	g, _ := c.GetGreeting("hello")
	if g.Status.ReadyReplicas != 3 {
		t.Errorf("Status.ReadyReplicas = %d after correction, want 3", g.Status.ReadyReplicas)
	}
}

// TestScaleToZero: Replicas 0 is a valid spec — the controller must drive
// the deployment to zero replicas, not skip it.
func TestScaleToZero(t *testing.T) {
	c := k8soperator.NewClusterState(greeting("sleepy", 0, "zzz %s"))
	if _, err := reconcile(t, "sleepy", c); err != nil {
		t.Fatalf("Reconcile with Replicas=0 failed: %v", err)
	}
	d := deploymentFor(t, c, "greeting-sleepy")
	if d.Replicas != 0 {
		t.Errorf("deployment Replicas = %d, want 0", d.Replicas)
	}
	g, _ := c.GetGreeting("sleepy")
	if g.Status.ReadyReplicas != 0 {
		t.Errorf("Status.ReadyReplicas = %d, want 0", g.Status.ReadyReplicas)
	}
	if !conditionsContain(g.Status.Conditions, "Synced") {
		t.Errorf("Status.Conditions = %v, want to contain %q", g.Status.Conditions, "Synced")
	}
}

// TestScaleToZeroAfterScalingUp: a deployment at 5 driven to spec 0 — the
// controller must be able to shrink, not only grow.
func TestScaleToZeroAfterScalingUp(t *testing.T) {
	c := k8soperator.NewClusterState(greeting("sleepy", 5, "zzz %s"))
	if _, err := reconcile(t, "sleepy", c); err != nil {
		t.Fatalf("initial reconcile failed: %v", err)
	}
	c.SetGreeting(greeting("sleepy", 0, "zzz %s"))
	if _, err := reconcile(t, "sleepy", c); err != nil {
		t.Fatalf("scale-to-zero reconcile failed: %v", err)
	}
	if d := deploymentFor(t, c, "greeting-sleepy"); d.Replicas != 0 {
		t.Errorf("deployment Replicas = %d after scale-to-zero, want 0", d.Replicas)
	}
}

// TestMultipleGreetingsIndependent: two CRs, two deployments, no cross-talk.
// Mirrors the real property that each workqueue key is reconciled in
// isolation.
func TestMultipleGreetingsIndependent(t *testing.T) {
	c := k8soperator.NewClusterState(
		greeting("hello", 3, "Hello, %s!"),
		greeting("bye", 1, "Bye, %s!"),
	)
	for _, name := range []string{"hello", "bye"} {
		if _, err := reconcile(t, name, c); err != nil {
			t.Fatalf("reconcile %s failed: %v", name, err)
		}
	}
	h := deploymentFor(t, c, "greeting-hello")
	b := deploymentFor(t, c, "greeting-bye")
	if h.Replicas != 3 || h.Template != "Hello, %s!" || h.OwnerRef != "hello" {
		t.Errorf("hello deployment wrong: %+v", h)
	}
	if b.Replicas != 1 || b.Template != "Bye, %s!" || b.OwnerRef != "bye" {
		t.Errorf("bye deployment wrong: %+v", b)
	}
}

// TestInvalidSpecNoDeployment: negative Replicas is invalid. The controller
// must NOT create a deployment, must NOT report Synced, and must surface the
// invalidity as a condition instead of hot-looping on an API error.
func TestInvalidSpecNoDeployment(t *testing.T) {
	c := k8soperator.NewClusterState(greeting("broken", -2, "Hello, %s!"))
	res, err := reconcile(t, "broken", c)
	if err != nil {
		t.Fatalf("invalid spec should not error (it must not hot-loop), got %v", err)
	}
	if res.Requeue {
		t.Errorf("invalid spec should not requeue (that would hot-loop), got %+v", res)
	}
	if _, ok := c.GetDeployment("greeting-broken"); ok {
		t.Error("deployment must not be created for an invalid spec")
	}
	g, _ := c.GetGreeting("broken")
	if !conditionsContain(g.Status.Conditions, "Invalid") {
		t.Errorf("Status.Conditions = %v, want to contain %q", g.Status.Conditions, "Invalid")
	}
	if conditionsContain(g.Status.Conditions, "Synced") {
		t.Error("invalid spec must not be marked Synced")
	}
	if g.Status.ReadyReplicas != 0 {
		t.Errorf("Status.ReadyReplicas = %d for invalid spec, want 0", g.Status.ReadyReplicas)
	}
}

// TestInvalidSpecRecovers: fixing the spec (a human edits the CR) must fully
// converge on the next reconcile — Invalid is cleared, Synced is set, the
// deployment appears.
func TestInvalidSpecRecovers(t *testing.T) {
	c := k8soperator.NewClusterState(greeting("broken", -2, "Hello, %s!"))
	if _, err := reconcile(t, "broken", c); err != nil {
		t.Fatalf("invalid reconcile failed: %v", err)
	}
	c.SetGreeting(greeting("broken", 2, "Hello, %s!")) // the human fixes the CR
	if _, err := reconcile(t, "broken", c); err != nil {
		t.Fatalf("recovery reconcile failed: %v", err)
	}
	d := deploymentFor(t, c, "greeting-broken")
	if d.Replicas != 2 {
		t.Errorf("after recovery Replicas = %d, want 2", d.Replicas)
	}
	g, _ := c.GetGreeting("broken")
	if conditionsContain(g.Status.Conditions, "Invalid") {
		t.Errorf("Invalid condition must be cleared on recovery, got %v", g.Status.Conditions)
	}
	if !conditionsContain(g.Status.Conditions, "Synced") {
		t.Errorf("after recovery Conditions = %v, want to contain %q", g.Status.Conditions, "Synced")
	}
}

// TestConcurrentReconcilesAreSafe: ClusterState is shared; concurrent
// reconciles (different names) must be race-free. Run with -race for teeth.
func TestConcurrentReconcilesAreSafe(t *testing.T) {
	names := []string{"a", "b", "c", "d"}
	greetings := make([]k8soperator.Greeting, 0, len(names))
	for i, n := range names {
		greetings = append(greetings, greeting(n, i+1, fmt.Sprintf("msg-%s %%s", n)))
	}
	c := k8soperator.NewClusterState(greetings...)
	var wg sync.WaitGroup
	for _, n := range names {
		wg.Add(1)
		go func(name string) {
			defer wg.Done()
			for i := 0; i < 5; i++ {
				if _, err := newReconciler().Reconcile(context.Background(), name, c); err != nil {
					t.Errorf("concurrent reconcile %s: %v", name, err)
					return
				}
			}
		}(n)
	}
	wg.Wait()
	for _, n := range names {
		if _, ok := c.GetDeployment("greeting-" + n); !ok {
			t.Errorf("missing deployment for %s after concurrent reconciles", n)
		}
	}
}
