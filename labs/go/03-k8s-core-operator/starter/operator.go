// Package k8soperator implements the STARTER for Lab 03: a reconciler for a
// fictional Greeting CRD. Stubs return "not implemented" so the lab compiles
// and the tests fail on assertions (never on compile errors) until you build
// the real thing. Replace the Reconcile body with your implementation.
package k8soperator

import (
	"context"
	"errors"

	k8soperator "tutor/labs/k8soperator"
)

var errNotImplemented = errors.New("not implemented")

// NewReconciler is the constructor the tests use (both starter and solution
// packages export the same symbol via build tags).
func NewReconciler() *Reconciler { return &Reconciler{} }

// Reconciler holds your reconciler state; add fields as your design needs
// (clients, caches, counters — in real life it holds the controller-runtime
// client and schemes).
type Reconciler struct{}

// Reconcile drives the cluster toward the desired state of one Greeting CR.
// Follow the loop from the README:
//  1. fetch the Greeting CR (missing -> no error, no requeue)
//  2. validate spec (negative Replicas -> condition "Invalid", no deployment)
//  3. fetch the deployment; if missing or drifted, create-or-update
//  4. update status (ReadyReplicas + condition "Synced")
//  5. return an empty Result
func (r *Reconciler) Reconcile(ctx context.Context, name string, cluster *k8soperator.ClusterState) (k8soperator.Result, error) {
	return k8soperator.Result{}, errNotImplemented
}
