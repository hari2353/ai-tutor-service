"""Lab 05 -- a 2-layer network, forward and backward passes derived by hand.

Architecture: Linear(d_in -> d_hidden) -> tanh -> Linear(d_hidden -> d_out) -> MSE loss.
Every analytic gradient here is checked against numerical finite-difference
gradients by the test suite -- that comparison IS the point of this lab.
"""
from __future__ import annotations

import numpy as np


class TwoLayerNet:
    def __init__(self, d_in: int, d_hidden: int, d_out: int, seed: int = 0) -> None:
        rng = np.random.RandomState(seed)
        self.W1 = rng.randn(d_in, d_hidden) * 0.5
        self.b1 = np.zeros(d_hidden)
        self.W2 = rng.randn(d_hidden, d_out) * 0.5
        self.b2 = np.zeros(d_out)
        self.cache: dict = {}

    def params(self) -> dict[str, np.ndarray]:
        return {"W1": self.W1, "b1": self.b1, "W2": self.W2, "b2": self.b2}

    # ------------------------------------------------------------------ forward
    def forward(self, X: np.ndarray) -> np.ndarray:
        """X: (N, d_in) -> y_hat: (N, d_out).

        z1 = X @ W1 + b1
        a1 = tanh(z1)
        z2 = a1 @ W2 + b2
        y_hat = z2   (linear output -- this is a regression head)
        """
        z1 = X @ self.W1 + self.b1
        a1 = np.tanh(z1)
        z2 = a1 @ self.W2 + self.b2
        self.cache = {"X": X, "z1": z1, "a1": a1, "z2": z2}
        return z2

    # ------------------------------------------------------------------ loss
    def loss(self, y_hat: np.ndarray, y: np.ndarray) -> float:
        """Mean squared error over every element (batch x d_out)."""
        return float(np.mean((y_hat - y) ** 2))

    # ------------------------------------------------------------------ backward
    def backward(self, y_hat: np.ndarray, y: np.ndarray) -> dict[str, np.ndarray]:
        """Manual chain rule, MSE -> linear2 -> tanh -> linear1.

        loss = mean((y_hat - y)^2) over all N*d_out elements
        dL/dy_hat = 2*(y_hat - y) / (N*d_out)

        z2 = a1 @ W2 + b2
          dL/dW2 = a1.T @ dL/dz2
          dL/db2 = sum(dL/dz2, axis=0)
          dL/da1 = dL/dz2 @ W2.T

        a1 = tanh(z1)  =>  da1/dz1 = 1 - tanh(z1)^2
          dL/dz1 = dL/da1 * (1 - tanh(z1)^2)

        z1 = X @ W1 + b1
          dL/dW1 = X.T @ dL/dz1
          dL/db1 = sum(dL/dz1, axis=0)
        """
        X, z1, a1 = self.cache["X"], self.cache["z1"], self.cache["a1"]
        N = y_hat.size  # total scalar elements the mean was taken over

        dy_hat = 2.0 * (y_hat - y) / N          # dL/dz2, since y_hat = z2 exactly

        dW2 = a1.T @ dy_hat
        db2 = dy_hat.sum(axis=0)

        da1 = dy_hat @ self.W2.T
        dz1 = da1 * (1.0 - np.tanh(z1) ** 2)

        dW1 = X.T @ dz1
        db1 = dz1.sum(axis=0)

        return {"W1": dW1, "b1": db1, "W2": dW2, "b2": db2}

    # ------------------------------------------------------------------ update
    def step(self, grads: dict[str, np.ndarray], lr: float) -> None:
        self.W1 -= lr * grads["W1"]
        self.b1 -= lr * grads["b1"]
        self.W2 -= lr * grads["W2"]
        self.b2 -= lr * grads["b2"]


def train(net: TwoLayerNet, X: np.ndarray, y: np.ndarray, epochs: int, lr: float) -> list[float]:
    """One full training loop: forward, loss, backward, update, repeat."""
    losses = []
    for _ in range(epochs):
        y_hat = net.forward(X)
        l = net.loss(y_hat, y)
        losses.append(l)
        grads = net.backward(y_hat, y)
        net.step(grads, lr)
    return losses
