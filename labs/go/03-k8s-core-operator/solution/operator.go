// Package k8soperator implements the REFERENCE SOLUTION for Lab 03: the
// reconcile loop for a fictional Greeting CRD, level-triggered and idempotent.
package k8soperator

import (
	"context"

	k8soperator "tutor/labs/k8soperator"
)

// Reconciler holds reconciler state. Nothing needed for this simulation.
type Reconciler struct{}

// NewReconciler is the constructor the tests use (both starter and solution
// packages export the same symbol via build tags).
func NewReconciler() *Reconciler { return &Reconciler{} }

// Reconcile drives the cluster toward the desired state of one Greeting CR.
// Level-triggered: it looks at current state, compares with desired state,
// and applies only the difference. It never reacts to "events" — it reacts
// to state. That is what makes it safe to run twice, or a hundred times.
func (r *Reconciler) Reconcile(ctx context.Context, name string, cluster *k8soperator.ClusterState) (k8soperator.Result, error) {
	// 1. Fetch the Greeting CR. Not found -> the CR was deleted; owned
	//    deployments are garbage-collected via ownerReferences, so there is
	//    nothing for us to do. No error, no requeue: erroring here would
	//    hot-loop the workqueue on a deleted object.
	g, ok := cluster.GetGreeting(name)
	if !ok {
		return k8soperator.Result{}, nil
	}

	// 2. Validate the spec before touching the cluster. An invalid spec must
	//    not produce a Deployment with a negative replica count — and must
	//    not requeue: requeueing on invalid input is a busy loop.
	if g.Spec.Replicas < 0 {
		if g.Status.ReadyReplicas != 0 || !hasCondition(g.Status.Conditions, "Invalid") {
			g.Status.ReadyReplicas = 0
			g.Status.Conditions = appendUnique(g.Status.Conditions, "Invalid")
			cluster.SetGreeting(g)
		}
		return k8soperator.Result{}, nil
	}

	// 3. Fetch the owned Deployment and reconcile toward desired state.
	desired := k8soperator.Deployment{
		Name:     deploymentName(name),
		Replicas: g.Spec.Replicas,
		Template: g.Spec.MessageTemplate,
		OwnerRef: name,
	}

	current, ok := cluster.GetDeployment(desired.Name)
	drifted := !ok || current.Replicas != desired.Replicas || current.Template != desired.Template
	if drifted {
		cluster.CreateOrUpdateDeployment(desired)
	}

	// 4. Update status. In this simulation the Deployment is instantly ready,
	//    so ReadyReplicas == Replicas. In a real cluster you would read the
	//    Deployment's status.readyReplicas and requeue until it converges.
	//    (Still: write only if something actually changed — writing identical
	//    status is a write, and writes bump resourceVersion.)
	if g.Status.ReadyReplicas != desired.Replicas || !hasCondition(g.Status.Conditions, "Synced") {
		g.Status.ReadyReplicas = desired.Replicas
		g.Status.Conditions = appendUnique(g.Status.Conditions, "Synced")
		cluster.SetGreeting(g)
	}

	// 5. Done. Empty result: no requeue — the watch will wake us if anything
	//    changes. Idempotent: a second call with the same state writes nothing.
	return k8soperator.Result{}, nil
}

// deploymentName derives the owned object's name from the CR, the way real
// controllers conventionally do (e.g. `<crd>-<name>`).
func deploymentName(greetingName string) string {
	return "greeting-" + greetingName
}

func hasCondition(conds []string, want string) bool {
	for _, c := range conds {
		if c == want {
			return true
		}
	}
	return false
}

func appendUnique(conds []string, want string) []string {
	if hasCondition(conds, want) {
		return conds
	}
	return append(conds, want)
}
