"""Resumable solvers. A pass checks current values, then makes at most one update."""
from time import perf_counter

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve

CAPS = {"vfi": 10000, "howard": 1000, "modified_howard": 10000,
        "gradient": 20000, "adam": 20000}


class Solver:
    def __init__(self, model, method, tolerance=1e-8):
        started = perf_counter()
        if method not in CAPS:
            raise ValueError(method)
        self.model, self.method, self.tolerance = model, method, tolerance
        self.x = np.zeros(model.M, dtype=np.float64)
        self.a = np.zeros_like(self.x)
        self.b = np.zeros_like(self.x)
        self.outer_passes = self.updates = self.inner_steps = 0
        self.seconds = 0.0
        self.trace = []
        self.done = False
        self.exit_metric = None
        self.G = None
        self.seconds = perf_counter() - started

    def advance(self, budget_seconds=110.0):
        """Complete a bounded slice; callers persist state if it is unfinished."""
        started = perf_counter()
        while not self.done:
            Tx, G = self.model.bellman(self.x)
            F = self.x - Tx
            d = float(np.max(np.abs(F) / (np.abs(self.x) + 1)))
            self.outer_passes += 1
            if self.method in ("gradient", "adam"):
                self.trace.append([self.outer_passes, d, float(np.dot(F, F) / 2), 0])
            if d <= self.tolerance:
                self.done = True
            else:
                if self.method == "vfi":
                    self.x = Tx
                else:
                    Q = self.model.transition(G)
                    Rg = self.model.R[np.arange(self.model.M), G]
                    if self.method == "howard":
                        self.x = spsolve(sparse.eye(self.model.M, format="csr") - self.model.beta * Q, Rg)
                    elif self.method == "modified_howard":
                        B = Tx
                        for _ in range(20):
                            B = Rg + self.model.beta * (Q @ B)
                        self.x = B
                        self.inner_steps += 20
                    else:
                        h = F - self.model.beta * (Q.T @ F)
                        if self.method == "gradient":
                            self.x -= 0.0005 * h
                        else:
                            j = self.updates + 1
                            self.a = 0.9 * self.a + 0.1 * h
                            self.b = 0.999 * self.b + 0.001 * h ** 2
                            ahat = self.a / (1 - 0.9 ** j)
                            bhat = self.b / (1 - 0.999 ** j)
                            self.x -= 0.1 * ahat / (np.sqrt(bhat) + 1e-8)
                self.updates += 1
                if self.outer_passes >= CAPS[self.method]:
                    self.done = True
            if not np.isfinite(self.x).all():
                raise RuntimeError(f"Nonfinite values in {self.method} at pass {self.outer_passes}")
            if self.done:
                # Diagnostic on saved values is never an extra pass or update.
                self.exit_metric, self.G = self.model.metric(self.x)
                if self.method in ("gradient", "adam"):
                    exit_T, _ = self.model.bellman(self.x)
                    exit_F = self.x - exit_T
                    self.trace.append([self.outer_passes, self.exit_metric,
                                       float(np.dot(exit_F, exit_F) / 2), 1])
            elif perf_counter() - started >= budget_seconds:
                break
        self.seconds += perf_counter() - started
        return self.done

    def metadata(self):
        return {"method": self.method, "tolerance": self.tolerance,
                "outer_pass_cap": CAPS[self.method], "outer_passes": self.outer_passes,
                "updates": self.updates, "inner_steps": self.inner_steps, "seconds": self.seconds,
                "exit_metric": self.exit_metric,
                "converged": self.done and self.exit_metric <= self.tolerance,
                "status": ("converged" if self.exit_metric <= self.tolerance else "capped_unconverged")
                if self.done else "checkpointed",
                "modified_howard_steps_per_update": 20, "gradient_step": 0.0005,
                "adam_learning_rate": 0.1, "adam_moment_decay": [0.9, 0.999],
                "adam_epsilon": 1e-8, "initial_value": "zero"}

    def result(self):
        if not self.done:
            raise RuntimeError("Solver not complete")
        return {"V": self.x.reshape((self.model.N, 2), order="F"),
                "G": self.G.reshape((self.model.N, 2), order="F"),
                "consumption": self.model.consumption(self.G),
                "trace": np.asarray(self.trace, dtype=np.float64).reshape((-1, 4)),
                "metadata": self.metadata()}

    def save_checkpoint(self, path):
        np.savez_compressed(path, x=self.x, a=self.a, b=self.b,
                            trace=np.asarray(self.trace, dtype=np.float64).reshape((-1, 4)),
                            method=self.method, tolerance=self.tolerance,
                            outer_passes=self.outer_passes, updates=self.updates,
                            inner_steps=self.inner_steps, seconds=self.seconds,
                            grid=self.model.grid, beta=self.model.beta,
                            P=self.model.P, r=self.model.r, w=self.model.w)

    @classmethod
    def load_checkpoint(cls, model, path):
        with np.load(path, allow_pickle=False) as data:
            if not (np.array_equal(data["grid"], model.grid)
                    and np.array_equal(data["P"], model.P)
                    and float(data["beta"]) == model.beta
                    and float(data["r"]) == model.r and float(data["w"]) == model.w):
                raise ValueError("Checkpoint settings differ from current model")
            solver = cls(model, str(data["method"]), float(data["tolerance"]))
            solver.x, solver.a, solver.b = [data[key].copy() for key in ("x", "a", "b")]
            solver.trace = data["trace"].tolist()
            for key in ("outer_passes", "updates", "inner_steps"):
                setattr(solver, key, int(data[key]))
            solver.seconds = float(data["seconds"])
        return solver
