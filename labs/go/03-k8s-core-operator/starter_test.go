//go:build !solution

// Selects the STARTER implementation: NewReconciler from starter/. Compiled
// by default; `go test ./...` runs the suite against the stub (FAILS).
package k8soperator_test

import (
	starter "tutor/labs/k8soperator/starter"

	k8soperator "tutor/labs/k8soperator"
)

var newReconciler func() k8soperator.Reconciler = func() k8soperator.Reconciler {
	return starter.NewReconciler()
}
