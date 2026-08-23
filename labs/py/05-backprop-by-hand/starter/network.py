"""Lab 05 -- a 2-layer network, forward and backward passes derived by hand.
Fill in every TODO. Tests define done.

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

        TODO(step 1):
          z1 = X @ W1 + b1
          a1 = tanh(z1)
          z2 = a1 @ W2 + b2
          y_hat = z2   (linear output -- this is a regression head)

        Cache X, z1, a1 (self.cache = {...}) -- backward() needs them and must
        not recompute the forward pass.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------ loss
    def loss(self, y_hat: np.ndarray, y: np.ndarray) -> float:
        """TODO(step 2): mean squared error over EVERY element (batch x d_out),
        i.e. np.mean((y_hat - y) ** 2) -- not summed, not averaged only over
        the batch axis. backward()'s normalization constant depends on this."""
        raise NotImplementedError

    # ------------------------------------------------------------------ backward
    def backward(self, y_hat: np.ndarray, y: np.ndarray) -> dict[str, np.ndarray]:
        """Manual chain rule, MSE -> linear2 -> tanh -> linear1.

        TODO(step 3) -- derive and implement, in order:
          loss = mean((y_hat - y)^2) over all N*d_out elements
          dL/dy_hat = 2*(y_hat - y) / (N*d_out)      # N*d_out = y_hat.size

          z2 = a1 @ W2 + b2   (y_hat IS z2, so dL/dz2 == dL/dy_hat)
            dL/dW2 = a1.T @ dL/dz2
            dL/db2 = sum(dL/dz2, axis=0)
            dL/da1 = dL/dz2 @ W2.T

          a1 = tanh(z1)  =>  da1/dz1 = 1 - tanh(z1)^2
            dL/dz1 = dL/da1 * (1 - tanh(z1)^2)

          z1 = X @ W1 + b1
            dL/dW1 = X.T @ dL/dz1
            dL/db1 = sum(dL/dz1, axis=0)

        Return {"W1": dW1, "b1": db1, "W2": dW2, "b2": db2}. Read X, z1, a1
        back out of self.cache (set by forward()) -- do not recompute them.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------ update
    def step(self, grads: dict[str, np.ndarray], lr: float) -> None:
        """TODO(step 4): plain SGD -- subtract lr * grad from each parameter."""
        raise NotImplementedError


def train(net: TwoLayerNet, X: np.ndarray, y: np.ndarray, epochs: int, lr: float) -> list[float]:
    """TODO(step 5): one full training loop -- for each epoch: forward, compute
    loss (record it), backward, step. Return the list of per-epoch losses."""
    raise NotImplementedError
