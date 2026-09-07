// Package k8soperator holds the shared type definitions for Lab 03: the
// fictional Greeting CRD, the simulated cluster, and the reconciler contract.
//
// The Reconciler implementation lives in two sibling packages — starter/
// (stub, fails tests) and solution/ (reference, passes tests) — both also
// named package k8soperator, mirroring real operators where the controller
// package imports its API types package. The root test files (external test
// package k8soperator_test) switch between them with build tags:
//
//	go test ./...                 → starter selected  → tests FAIL on assertions
//	go test -tags solution ./...   → solution selected → tests PASS
package k8soperator

import (
	"context"
	"sync"
)

// ---------------------------------------------------------------------------
// The CRD: Greeting
// ---------------------------------------------------------------------------

// GreetingSpec is the desired state the human asked for.
type GreetingSpec struct {
	// MessageTemplate is the pod template — e.g. "Hello, %s!" — that the
	// greeting's worker pods render on every request.
	MessageTemplate string
	// Replicas is how many identical greeting pods the cluster should run.
	// Zero is valid (scale to zero). Negative is invalid.
	Replicas int
}

// GreetingStatus is the observed state the controller writes back.
// In real Kubernetes this is a separate subresource with its own RBAC.
type GreetingStatus struct {
	ReadyReplicas int
	Conditions    []string // e.g. "Synced", "Invalid"
}

// Greeting is the custom resource: Spec is what the user wants, Status is
// what the cluster actually has.
type Greeting struct {
	Name   string
	Spec   GreetingSpec
	Status GreetingStatus
}

// ---------------------------------------------------------------------------
// The managed object: a fictional Deployment
// ---------------------------------------------------------------------------

// Deployment is a stripped-down Deployment: the thing the controller owns
// and reconciles toward the spec.
type Deployment struct {
	Name     string
	Replicas int
	Template string
	OwnerRef string // the Greeting name; real k8s uses ownerReferences with UIDs
}

// ---------------------------------------------------------------------------
// The simulated cluster
// ---------------------------------------------------------------------------

// ClusterState is an in-memory stand-in for the API server + etcd: maps of
// Greeting CRs and Deployment-like objects, guarded by a mutex because the
// tests exercise concurrency (multiple reconciles racing). It is also the
// informer cache in this simulation: every read is a "cache read".
type ClusterState struct {
	mu          sync.Mutex
	greetings   map[string]Greeting
	deployments map[string]Deployment
	writeCount  int
}

// NewClusterState returns an empty cluster, optionally seeded with greetings.
func NewClusterState(greetings ...Greeting) *ClusterState {
	c := &ClusterState{
		greetings:   make(map[string]Greeting),
		deployments: make(map[string]Deployment),
	}
	for _, g := range greetings {
		c.greetings[g.Name] = g
	}
	return c
}

// GetGreeting returns the CR and whether it exists. Like an informer cache
// read, it does not count as a write.
func (c *ClusterState) GetGreeting(name string) (Greeting, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	g, ok := c.greetings[name]
	return g, ok
}

// SetGreeting writes a Greeting CR back (spec or status update).
// Counts as a write — the idempotency test watches this counter.
func (c *ClusterState) SetGreeting(g Greeting) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.greetings[g.Name] = g
	c.writeCount++
}

// GetDeployment returns the deployment and whether it exists.
func (c *ClusterState) GetDeployment(name string) (Deployment, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	d, ok := c.deployments[name]
	return d, ok
}

// CreateOrUpdateDeployment applies desired state over whatever is there:
// create if missing, overwrite if drifted. Counts as a write.
func (c *ClusterState) CreateOrUpdateDeployment(d Deployment) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.deployments[d.Name] = d
	c.writeCount++
}

// ScaleDeployment is how a human (or HPA) manually changes replicas on the
// cluster without going through the controller — used to inject drift.
// Counts as a write.
func (c *ClusterState) ScaleDeployment(name string, replicas int) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if d, ok := c.deployments[name]; ok {
		d.Replicas = replicas
		c.deployments[name] = d
		c.writeCount++
	}
}

// WriteCount reports how many writes have hit the cluster. The idempotency
// test reconciles twice and asserts this did not move the second time.
func (c *ClusterState) WriteCount() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.writeCount
}

// ---------------------------------------------------------------------------
// The reconciler contract
// ---------------------------------------------------------------------------

// Result mirrors controller-runtime's ctrl.Result: Requeue/RequeueAfter are
// how you tell the loop to come back without a watch event.
type Result struct {
	Requeue      bool
	RequeueAfter int // simulated duration units; 0 = not set
}

// Reconciler is the interface every controller implements. controller-runtime
// calls this once per (workqueue) key, with a deadline-bearing ctx.
type Reconciler interface {
	// Reconcile takes a context, the object name (the workqueue key), and the
	// cluster. It reads current state, compares to desired, applies the diff,
	// and returns. It must be idempotent: the same input state must produce
	// the same output state, and a no-op reconcile must not write.
	Reconcile(ctx context.Context, name string, cluster *ClusterState) (Result, error)
}
