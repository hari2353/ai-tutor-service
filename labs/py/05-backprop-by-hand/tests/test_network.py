"""Lab 05 tests. Every analytic gradient is checked against a numerical
finite-difference gradient -- that comparison is the whole point of this lab.
"""
import numpy as np
import pytest

EPS = 1e-5
ATOL = 1e-4
RTOL = 1e-3


def _numerical_gradient(net, param_name: str, X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Central-difference numerical gradient of net.loss(net.forward(X), y)
    with respect to a single parameter array, using ONLY forward() and loss()
    -- never backward(). This is the ground truth backward() is checked against."""
    param = getattr(net, param_name)
    grad = np.zeros_like(param, dtype=np.float64)
    it = np.nditer(param, flags=["multi_index"])
    while not it.finished:
        idx = it.multi_index
        original = param[idx]

        param[idx] = original + EPS
        loss_plus = net.loss(net.forward(X), y)

        param[idx] = original - EPS
        loss_minus = net.loss(net.forward(X), y)

        param[idx] = original
        grad[idx] = (loss_plus - loss_minus) / (2 * EPS)
        it.iternext()
    return grad


def _small_problem(seed=0, n=5, d_in=3, d_out=2):
    rng = np.random.RandomState(seed)
    X = rng.randn(n, d_in)
    y = rng.randn(n, d_out)
    return X, y


# ------------------------------------------------------------------ forward shape / determinism
def test_forward_output_shape(N):
    net = N.TwoLayerNet(d_in=3, d_hidden=4, d_out=2, seed=0)
    X, _ = _small_problem()
    y_hat = net.forward(X)
    assert y_hat.shape == (5, 2)


def test_forward_is_deterministic_given_same_weights(N):
    net = N.TwoLayerNet(d_in=3, d_hidden=4, d_out=2, seed=0)
    X, _ = _small_problem()
    out1 = net.forward(X)
    out2 = net.forward(X)
    assert np.allclose(out1, out2)


def test_loss_is_mean_squared_error(N):
    net = N.TwoLayerNet(d_in=2, d_hidden=3, d_out=1, seed=0)
    y_hat = np.array([[1.0], [2.0]])
    y = np.array([[0.0], [0.0]])
    assert net.loss(y_hat, y) == pytest.approx(2.5)  # mean(1^2, 2^2) = 2.5


# ------------------------------------------------------------------ gradient checks
def test_gradient_check_W2(N):
    net = N.TwoLayerNet(d_in=3, d_hidden=4, d_out=2, seed=1)
    X, y = _small_problem(seed=1)
    y_hat = net.forward(X)
    analytic = net.backward(y_hat, y)["W2"]
    numeric = _numerical_gradient(net, "W2", X, y)
    assert np.allclose(analytic, numeric, atol=ATOL, rtol=RTOL)


def test_gradient_check_b2(N):
    net = N.TwoLayerNet(d_in=3, d_hidden=4, d_out=2, seed=1)
    X, y = _small_problem(seed=1)
    y_hat = net.forward(X)
    analytic = net.backward(y_hat, y)["b2"]
    numeric = _numerical_gradient(net, "b2", X, y)
    assert np.allclose(analytic, numeric, atol=ATOL, rtol=RTOL)


def test_gradient_check_W1(N):
    net = N.TwoLayerNet(d_in=3, d_hidden=4, d_out=2, seed=1)
    X, y = _small_problem(seed=1)
    y_hat = net.forward(X)
    analytic = net.backward(y_hat, y)["W1"]
    numeric = _numerical_gradient(net, "W1", X, y)
    assert np.allclose(analytic, numeric, atol=ATOL, rtol=RTOL)


def test_gradient_check_b1(N):
    net = N.TwoLayerNet(d_in=3, d_hidden=4, d_out=2, seed=1)
    X, y = _small_problem(seed=1)
    y_hat = net.forward(X)
    analytic = net.backward(y_hat, y)["b1"]
    numeric = _numerical_gradient(net, "b1", X, y)
    assert np.allclose(analytic, numeric, atol=ATOL, rtol=RTOL)


def test_gradient_check_holds_for_a_second_random_problem(N):
    """Guard against a gradient check that only happens to pass for one seed."""
    net = N.TwoLayerNet(d_in=4, d_hidden=6, d_out=3, seed=7)
    X, y = _small_problem(seed=7, n=8, d_in=4, d_out=3)
    y_hat = net.forward(X)
    analytic = net.backward(y_hat, y)
    for name in ["W1", "b1", "W2", "b2"]:
        numeric = _numerical_gradient(net, name, X, y)
        assert np.allclose(analytic[name], numeric, atol=ATOL, rtol=RTOL), f"{name} gradient mismatch"


def test_gradient_check_single_sample(N):
    """N=1 edge case -- the mean-over-elements normalization must still be right."""
    net = N.TwoLayerNet(d_in=2, d_hidden=3, d_out=1, seed=3)
    X, y = _small_problem(seed=3, n=1, d_in=2, d_out=1)
    y_hat = net.forward(X)
    analytic = net.backward(y_hat, y)
    for name in ["W1", "b1", "W2", "b2"]:
        numeric = _numerical_gradient(net, name, X, y)
        assert np.allclose(analytic[name], numeric, atol=ATOL, rtol=RTOL), f"{name} gradient mismatch"


# ------------------------------------------------------------------ step / update
def test_step_moves_parameters_in_descent_direction(N):
    net = N.TwoLayerNet(d_in=3, d_hidden=4, d_out=2, seed=1)
    X, y = _small_problem(seed=1)
    y_hat = net.forward(X)
    loss_before = net.loss(y_hat, y)
    grads = net.backward(y_hat, y)
    net.step(grads, lr=0.01)
    loss_after = net.loss(net.forward(X), y)
    assert loss_after < loss_before


# ------------------------------------------------------------------ training loop
def test_training_loop_reduces_loss_on_seeded_problem(N):
    rng = np.random.RandomState(0)
    n = 60
    X = rng.randn(n, 2)
    y = (np.sin(X[:, 0]) + 0.5 * X[:, 1] ** 2).reshape(n, 1)

    net = N.TwoLayerNet(d_in=2, d_hidden=16, d_out=1, seed=1)
    losses = N.train(net, X, y, epochs=300, lr=0.1)

    assert len(losses) == 300
    assert losses[-1] < losses[0] * 0.5, f"loss barely moved: {losses[0]} -> {losses[-1]}"


def test_training_loss_trend_is_mostly_decreasing(N):
    rng = np.random.RandomState(0)
    n = 60
    X = rng.randn(n, 2)
    y = (np.sin(X[:, 0]) + 0.5 * X[:, 1] ** 2).reshape(n, 1)

    net = N.TwoLayerNet(d_in=2, d_hidden=16, d_out=1, seed=1)
    losses = N.train(net, X, y, epochs=300, lr=0.1)

    # compare 10-epoch windows at the start vs the end -- must have dropped substantially
    early = np.mean(losses[:10])
    late = np.mean(losses[-10:])
    assert late < early * 0.5
