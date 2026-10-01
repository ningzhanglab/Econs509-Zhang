"""Invariant-distribution methods and explicit roundoff diagnostics from spec.md."""
from time import perf_counter

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import eigs, spsolve


def finish_distribution(Q, raw):
    raw = np.asarray(raw, dtype=np.float64)
    if not np.isfinite(raw).all() or raw.sum() == 0:
        raise RuntimeError("Distribution is nonfinite or has zero sum")
    normalized = raw / raw.sum()
    raw_minimum = float(normalized.min())
    if raw_minimum < -1e-14:
        raise RuntimeError(f"Invalid negative probability: {raw_minimum}")
    negative = normalized < 0
    correction_mass = float(-normalized[negative].sum())
    corrected = normalized.copy()
    if negative.any():
        corrected[negative] = 0
        corrected /= corrected.sum()
    residual = float(np.max(np.abs(Q.T @ corrected - corrected)))
    marginal = corrected.reshape((-1, 2), order="F").sum(axis=0)
    if (not np.isfinite(corrected).all() or np.any(corrected < 0)
            or abs(corrected.sum() - 1) > 1e-10 or residual > 1e-10
            or np.max(np.abs(marginal - 0.5)) > 1e-10):
        raise RuntimeError(f"Distribution check failed: residual={residual}, marginals={marginal}")
    return corrected, {"raw_minimum": raw_minimum, "correction_mass": correction_mass,
                       "raw_sum": float(raw.sum()), "sum": float(corrected.sum()),
                       "stationarity_residual": residual, "shock_marginals": marginal.tolist()}


class PowerIteration:
    def __init__(self, Q):
        started = perf_counter()
        self.Q = Q
        self.pi = np.ones(Q.shape[0], dtype=np.float64) / Q.shape[0]
        self.updates = 0
        self.seconds = 0.0
        self.done = False
        self.last_difference = None
        self.result = None
        self.seconds = perf_counter() - started

    def advance(self, budget_seconds=110):
        started = perf_counter()
        while not self.done and self.updates < 100000:
            new = self.Q.T @ self.pi
            self.last_difference = float(np.max(np.abs(new - self.pi)))
            self.pi = new
            self.updates += 1
            if self.last_difference <= 1e-12:
                self.done = True
                pi, metadata = finish_distribution(self.Q, self.pi)
                self.result = {"pi": pi, "metadata": {**metadata, "method": "power",
                               "updates": self.updates, "update_tolerance": 1e-12,
                               "update_cap": 100000, "last_difference": self.last_difference}}
            elif perf_counter() - started >= budget_seconds:
                break
        self.seconds += perf_counter() - started
        if not self.done and self.updates >= 100000:
            raise RuntimeError("Power iteration reached the 100000-update cap")
        if self.done:
            self.result["metadata"]["seconds"] = self.seconds
        return self.done

    def save_checkpoint(self, path):
        np.savez_compressed(path, pi=self.pi, updates=self.updates, seconds=self.seconds)

    @classmethod
    def load_checkpoint(cls, Q, path):
        state = cls(Q)
        with np.load(path, allow_pickle=False) as data:
            state.pi = data["pi"].copy()
            if state.pi.shape != (Q.shape[0],):
                raise ValueError("Power checkpoint dimension mismatch")
            state.updates = int(data["updates"])
            state.seconds = float(data["seconds"])
        return state


def invariant(Q, method, budget_seconds=110, checkpoint=None):
    """Return None after saving an unfinished power slice, otherwise a checked result."""
    if method == "power":
        state = (PowerIteration.load_checkpoint(Q, checkpoint)
                 if checkpoint is not None and checkpoint.exists() else PowerIteration(Q))
        if not state.advance(budget_seconds):
            if checkpoint is None:
                raise RuntimeError("Power iteration needs a checkpoint path to continue")
            state.save_checkpoint(checkpoint)
            return None
        return state.result
    started = perf_counter()
    extra = {}
    if method == "eigen":
        values, vectors = eigs(Q.T, k=1, sigma=1 - 1e-10, which="LM",
                              v0=np.ones(Q.shape[0]) / np.sqrt(Q.shape[0]),
                              tol=1e-12, maxiter=100000)
        eigen_distance = float(abs(values[0] - 1))
        imaginary = float(np.max(np.abs(vectors[:, 0].imag)))
        if eigen_distance > 1e-10 or imaginary > 1e-10:
            raise RuntimeError(f"Eigenvector diagnostics failed: {eigen_distance}, {imaginary}")
        raw = vectors[:, 0].real
        extra = {"eigenvalue_real": float(values[0].real),
                 "eigenvalue_imaginary": float(values[0].imag),
                 "eigenvalue_distance": eigen_distance, "eigenvector_imaginary_maximum": imaginary,
                 "shift": 1 - 1e-10, "tolerance": 1e-12, "maxiter": 100000}
    elif method == "direct":
        rhs = np.zeros(Q.shape[0])
        rhs[-1] = 1
        if sparse.issparse(Q):
            A = (sparse.eye(Q.shape[0], format="csr") - Q.T).tolil()
            A[-1, :] = np.ones(Q.shape[0])
            raw = spsolve(A.tocsr(), rhs)
        else:
            A = np.eye(Q.shape[0]) - Q.T
            A[-1, :] = 1
            raw = np.linalg.solve(A, rhs)
    else:
        raise ValueError(method)
    pi, metadata = finish_distribution(Q, raw)
    return {"pi": pi, "metadata": {**metadata, **extra, "method": method,
                                   "seconds": perf_counter() - started}}
