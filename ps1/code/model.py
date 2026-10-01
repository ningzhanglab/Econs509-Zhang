"""Question 2 definitions from spec.md, in float64 and column-stacked order."""
from time import perf_counter

import numpy as np
from scipy import sparse

PARAMETERS = {"beta": 0.96, "sigma": 1.5, "labor": 1.0, "k_min": 0.0,
              "z": 1.0, "alpha": 0.36, "delta": 0.1, "K0": 5.0,
              "efficiency": [0.8, 1.2], "P": [[0.5, 0.5], [0.5, 0.5]],
              "shock_stationary": [0.5, 0.5], "seed": 0}


def asset_grid(N, k_max, kind="uniform"):
    fraction = np.arange(N, dtype=np.float64) / (N - 1)
    if kind == "uniform":
        grid = k_max * fraction
    elif kind == "exp_log":
        grid = np.exp(fraction * np.log(k_max + 1)) - 1
    else:
        raise ValueError(f"Unknown grid: {kind}")
    grid[0], grid[-1] = 0.0, k_max
    return grid


class Model:
    def __init__(self, N=100, k_max=20.0, grid_kind="uniform"):
        self.N, self.M = N, 2 * N
        self.grid_kind = grid_kind
        self.grid = asset_grid(N, k_max, grid_kind)
        self.beta, self.sigma, self.labor = 0.96, 1.5, 1.0
        self.P = np.array(PARAMETERS["P"], dtype=np.float64)
        self.efficiency = np.array(PARAMETERS["efficiency"], dtype=np.float64)
        self.L = float(np.dot(PARAMETERS["shock_stationary"], self.efficiency) * self.labor)
        ratio = PARAMETERS["K0"] / self.L
        self.w = (1 - PARAMETERS["alpha"]) * PARAMETERS["z"] * ratio ** PARAMETERS["alpha"]
        self.r = PARAMETERS["alpha"] * PARAMETERS["z"] * ratio ** (PARAMETERS["alpha"] - 1) - PARAMETERS["delta"]
        started = perf_counter()
        resources = ((1 + self.r) * self.grid[:, None]
                     + self.w * self.efficiency[None, :] * self.labor).ravel(order="F")
        c = resources[:, None] - self.grid[None, :]
        self.R = np.full(c.shape, -np.inf, dtype=np.float64)
        feasible = c > 0
        self.R[feasible] = c[feasible] ** (1 - self.sigma) / (1 - self.sigma)
        self.utility_seconds = perf_counter() - started

    def settings(self):
        return {**PARAMETERS, "N": self.N, "k_max": float(self.grid[-1]),
                "grid_kind": self.grid_kind, "L": self.L, "w": self.w, "r": self.r,
                "utility_seconds": self.utility_seconds, "dtype": "float64", "stack_order": "F"}

    def bellman(self, x):
        V = x.reshape((self.N, 2), order="F")
        continuation = self.P @ V.T
        candidates = self.R + self.beta * np.repeat(continuation, self.N, axis=0)
        G = np.argmax(candidates, axis=1)  # NumPy returns the first exact maximizer.
        return candidates[np.arange(self.M), G], G

    def metric(self, x):
        Tx, G = self.bellman(x)
        return float(np.max(np.abs(Tx - x) / (np.abs(x) + 1))), G

    def transition(self, G, representation="sparse"):
        policy = np.asarray(G).ravel(order="F")
        rows = np.repeat(np.arange(self.M), 2)
        columns = (policy[:, None] + self.N * np.arange(2)[None, :]).ravel()
        probabilities = np.repeat(self.P, self.N, axis=0).ravel()
        if representation == "dense":
            Q = np.zeros((self.M, self.M), dtype=np.float64)
            Q[rows, columns] = probabilities
            return Q
        if representation == "sparse":
            return sparse.csr_matrix((probabilities, (rows, columns)), shape=(self.M, self.M))
        raise ValueError(representation)

    def consumption(self, G):
        G = np.asarray(G).reshape((self.N, 2), order="F")
        return ((1 + self.r) * self.grid[:, None]
                + self.w * self.efficiency[None, :] * self.labor - self.grid[G])
