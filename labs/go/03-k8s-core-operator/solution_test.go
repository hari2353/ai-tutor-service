//go:build solution

// Selects the SOLUTION implementation: NewReconciler from solution/. Compiled
// only under `go test -tags solution ./...` (PASSES).
package k8soperator_test

import (
	solution "tutor/labs/k8soperator/solution"

	k8soperator "tutor/labs/k8soperator"
)

var newReconciler func() k8soperator.Reconciler = func() k8soperator.Reconciler {
	return solution.NewReconciler()
}
