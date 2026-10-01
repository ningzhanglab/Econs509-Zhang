"""Independent checks from tests.md. A failed applicable check stops the suite."""
from itertools import combinations
import numpy as np


class CheckFailure(RuntimeError):
    pass


def outcome(test_id, passed, **measurements):
    result = {"test_id": test_id, "passed": bool(passed), **measurements}
    if not passed:
        raise CheckFailure(str(result))
    return result


def reference_schema(path):
    with np.load(path, allow_pickle=False) as ref:
        required = {"V": (100, 2), "G": (100, 2), "pi": (200,), "iterations": ()}
        for key, shape in required.items():
            if key not in ref or ref[key].shape != shape:
                raise CheckFailure(f"Manual reference missing/invalid {key}: expected {shape}")
        if not np.issubdtype(ref["G"].dtype, np.integer):
            raise CheckFailure("Manual policy indices must be integers")
        if np.any((ref["G"] < 0) | (ref["G"] >= 100)):
            raise CheckFailure("Manual policy indices outside [0,99]")
        if not all(np.isfinite(ref[key]).all() for key in required):
            raise CheckFailure("Nonfinite manual reference")
        if not np.issubdtype(ref["iterations"].dtype, np.integer) or ref["iterations"] < 1:
            raise CheckFailure("Manual iterations must be a positive integer scalar")
        return {key: ref[key].copy() for key in required}


def kernel(solution, reference_path):
    ref = reference_schema(reference_path)
    difference = float(np.max(np.abs(solution["V"] - ref["V"])))
    mismatches = int(np.count_nonzero(solution["G"] != ref["G"]))
    return outcome(1, difference <= 1e-8 and mismatches == 0,
                   value_difference=difference, policy_mismatches=mismatches,
                   agent_outer_passes=solution["metadata"]["outer_passes"],
                   manual_outer_passes=int(ref["iterations"]))


def monotone(G):
    violations = np.argwhere(np.diff(G, axis=0) < 0).tolist()
    return outcome(2, not violations, violation_count=len(violations),
                   violations_lower_node_and_shock=violations)


def consumption(model, G, saved):
    valid = (G.shape == (model.N, 2) and np.issubdtype(G.dtype, np.integer)
             and np.all((G >= 0) & (G < model.N)))
    if not valid:
        return outcome(3, False, valid_policy_indices=False)
    recomputed = np.empty_like(saved)
    for n in range(model.N):
        for s in range(2):
            recomputed[n, s] = ((1 + model.r) * model.grid[n]
                                + model.w * model.efficiency[s] * model.labor
                                - model.grid[G[n, s]])
    difference = float(np.max(np.abs(saved - recomputed)))
    location = np.unravel_index(np.argmin(saved), saved.shape)
    return outcome(3, np.isfinite(saved).all() and np.all(saved > 0) and difference <= 1e-12,
                   valid_policy_indices=True, minimum=float(np.min(saved)),
                   minimum_state=[int(v) for v in location], budget_difference=difference)


def normalization(pi):
    total = float(np.sum(pi))
    deviation = abs(total - 1)
    return outcome(4, np.isfinite(pi).all() and deviation <= 1e-10,
                   total=total, deviation=deviation)


def nonnegative(pi, metadata):
    return outcome(5, metadata["raw_minimum"] >= -1e-14 and np.all(pi >= 0),
                   raw_minimum=metadata["raw_minimum"],
                   correction_mass=metadata["correction_mass"],
                   saved_minimum=float(np.min(pi)))


def top_mass(pi, N):
    mass = float(pi.reshape((N, 2), order="F")[-1].sum())
    return outcome(6, mass <= 1e-12, top_node_mass=mass)


def transition(model, G, dense, sparse):
    expected = np.zeros((2 * model.N, 2 * model.N))
    for s in range(2):
        for n in range(model.N):
            for sp in range(2):
                expected[s * model.N + n, sp * model.N + int(G[n, s])] = model.P[s, sp]
    sparse_array = sparse.toarray()
    error = float(np.max(np.abs(dense - expected)))
    representation_error = float(np.max(np.abs(dense - sparse_array)))
    row_error = max(float(np.max(np.abs(dense.sum(axis=1) - 1))),
                    float(np.max(np.abs(sparse_array.sum(axis=1) - 1))))
    return outcome(7, dense.shape == expected.shape and sparse.shape == expected.shape
                   and np.all(dense >= 0) and np.all(sparse_array >= 0)
                   and error <= 1e-12 and row_error <= 1e-12 and representation_error <= 1e-12,
                   shape=list(dense.shape), policy_entry_error=error,
                   row_sum_error=row_error, representation_error=representation_error)


def transition_selected(model, G, Q):
    """Test 7 on only the selected representation; construct no companion matrix."""
    from scipy import sparse
    shape_valid = Q.shape == (model.M, model.M)
    if not shape_valid:
        return outcome(7, False, shape=list(Q.shape))
    is_sparse = sparse.issparse(Q)
    stored = Q.data if is_sparse else Q
    minimum = min(0.0, float(np.min(stored))) if np.size(stored) else 0.0
    row_error = float(np.max(np.abs(np.asarray(Q.sum(axis=1)).ravel() - 1)))
    entry_error = 0.0
    for s in range(2):
        for n in range(model.N):
            row = s * model.N + n
            expected = {sp * model.N + int(G[n, s]): model.P[s, sp] for sp in range(2)}
            if is_sparse:
                start, end = Q.indptr[row:row + 2]
                actual = {}
                for col, probability in zip(Q.indices[start:end], Q.data[start:end]):
                    actual[int(col)] = actual.get(int(col), 0.0) + float(probability)
            else:
                actual = {int(col): float(Q[row, col]) for col in np.flatnonzero(Q[row])}
            for col in set(actual) | set(expected):
                entry_error = max(entry_error, abs(actual.get(col, 0.0) - expected.get(col, 0.0)))
    return outcome(7, minimum >= 0 and row_error <= 1e-12 and entry_error <= 1e-12,
                   shape=list(Q.shape), representation="CSR" if is_sparse else "dense",
                   minimum_entry=minimum, row_sum_error=row_error, policy_entry_error=entry_error)


def range_top_mass(pi, N):
    """Test 6 rejects truncated trial ranges; accepted-grid failures remain binding."""
    mass = float(pi.reshape((N, 2), order="F")[-1].sum())
    eligible = mass <= 1e-12
    return {"test_id": 6, "passed": bool(eligible), "top_node_mass": mass,
            "range_status": "eligible" if eligible else "rejected_truncated",
            "expected_trial_rejection": not bool(eligible)}


def stationarity(Q, pi, N):
    residual = float(np.max(np.abs(Q.T @ pi - pi)))
    marginal = pi.reshape((N, 2), order="F").sum(axis=0)
    error = float(np.max(np.abs(marginal - np.array([0.5, 0.5]))))
    return outcome(8, residual <= 1e-10 and error <= 1e-10,
                   stationarity_residual=residual, shock_marginals=marginal.tolist(),
                   shock_marginal_error=error)


def distribution_agreement(distributions):
    pairs = [(float(np.max(np.abs(distributions[a]["pi"] - distributions[b]["pi"]))), a, b)
             for a, b in combinations(distributions, 2)]
    largest, a, b = max(pairs)
    return outcome(8, largest <= 1e-8, largest_pair=[a, b], maximum_difference=largest)


def bellman(model, solutions):
    V = np.arange(model.N, dtype=np.float64)[:, None] ** 2 / (model.N - 1) ** 2
    V = V + 0.2 * np.arange(2)[None, :]
    expected = np.full_like(V, -np.inf)
    expected_G = np.zeros(V.shape, dtype=np.int64)
    for s in range(2):
        for n in range(model.N):
            for choice in range(model.N):
                c = ((1 + model.r) * model.grid[n]
                     + model.w * model.efficiency[s] * model.labor - model.grid[choice])
                if c > 0:
                    value = c ** (1 - model.sigma) / (1 - model.sigma)
                    value += model.beta * sum(model.P[s, sp] * V[choice, sp] for sp in range(2))
                    if value > expected[n, s]:
                        expected[n, s], expected_G[n, s] = value, choice
    actual, G = model.bellman(V.ravel(order="F"))
    error = float(np.max(np.abs(actual - expected.ravel(order="F"))))
    scale = 1e-12 * max(1, float(np.max(np.abs(expected))))
    mismatch = int(np.count_nonzero(G.reshape(V.shape, order="F") != expected_G))
    outcomes = [outcome(9, error <= scale and mismatch == 0,
                        operator_error=error, tolerance=scale, policy_mismatches=mismatch)]
    return outcomes + stopping(model, solutions)


def stopping(model, solutions):
    """Saved-value and settings portion of test 9, also for capped baseline runs."""
    outcomes = []
    for name, solution in solutions.items():
        meta = solution["metadata"]
        x = solution["V"].ravel(order="F")
        Tx, greedy = model.bellman(x)
        metric = float(np.max(np.abs(Tx - x) / (np.abs(x) + 1)))
        difference = abs(metric - meta["exit_metric"])
        required = name in ("vfi", "howard", "modified_howard", "kernel_vfi")
        converged = metric <= meta["tolerance"]
        counts_valid = (1 <= meta["outer_passes"] <= meta["outer_pass_cap"]
                        and meta["updates"] in (meta["outer_passes"] - 1, meta["outer_passes"]))
        inner_valid = meta["inner_steps"] == (20 * meta["updates"] if name == "modified_howard" else 0)
        method = "vfi" if name == "kernel_vfi" else name
        caps = {"vfi": 10000, "howard": 1000, "modified_howard": 10000,
                "gradient": 20000, "adam": 20000}
        settings_valid = (meta["method"] == method and meta["outer_pass_cap"] == caps[method]
                          and meta["tolerance"] == (1e-10 if name == "kernel_vfi" else 1e-8)
                          and meta["initial_value"] == "zero"
                          and meta["modified_howard_steps_per_update"] == 20
                          and meta["gradient_step"] == 0.0005
                          and meta["adam_learning_rate"] == 0.1
                          and meta["adam_moment_decay"] == [0.9, 0.999]
                          and meta["adam_epsilon"] == 1e-8)
        trace_valid = True
        if method in ("gradient", "adam"):
            trace = solution["trace"]
            trace_valid = (trace.shape == (meta["outer_passes"] + 1, 4)
                           and np.array_equal(trace[:-1, 0], np.arange(1, meta["outer_passes"] + 1))
                           and np.all(trace[:-1, 3] == 0) and trace[-1, 3] == 1
                           and abs(trace[-1, 1] - metric) <= 1e-12
                           and abs(trace[-1, 2] - float(np.dot(x - Tx, x - Tx) / 2))
                           <= 1e-12 * max(1, float(np.dot(x - Tx, x - Tx) / 2)))
        outcomes.append(outcome(9, difference <= 1e-12 and counts_valid and inner_valid
                                and settings_valid and trace_valid
                                and meta["converged"] == converged and (converged or not required)
                                and np.array_equal(greedy, solution["G"].ravel(order="F")),
                                method=name, exit_metric=metric, metric_difference=difference,
                                outer_passes=meta["outer_passes"], updates=meta["updates"],
                                inner_steps=meta["inner_steps"], converged=converged))
    return outcomes


def baseline_policy_checks(model, solution, pi, distribution_metadata, dense, csr, diagnostics):
    """Applicable tests 2–10 for one converged baseline policy."""
    yield monotone(solution["G"])
    yield consumption(model, solution["G"], solution["consumption"])
    yield normalization(pi)
    yield nonnegative(pi, distribution_metadata)
    yield top_mass(pi, model.N)
    yield transition(model, solution["G"], dense, csr)
    yield stationarity(csr, pi, model.N)
    yield euler(model, solution["G"], pi, diagnostics)


def euler(model, G, pi, saved):
    c = np.empty((model.N, 2))
    E = np.empty_like(c)
    next_c = np.empty((model.N, 2, 2))
    for n in range(model.N):
        for s in range(2):
            c[n, s] = ((1 + model.r) * model.grid[n] + model.w * model.efficiency[s]
                       * model.labor - model.grid[G[n, s]])
            expectation = 0.0
            for sp in range(2):
                gp = int(G[n, s])
                cn = ((1 + model.r) * model.grid[gp] + model.w * model.efficiency[sp]
                      * model.labor - model.grid[G[gp, sp]])
                next_c[n, s, sp] = cn
                expectation += model.P[s, sp] * cn ** (-model.sigma)
            cee = (model.beta * (1 + model.r) * expectation) ** (-1 / model.sigma)
            E[n, s] = abs(1 - cee / c[n, s])
    points = [(0, 0), (50, 1), (99, 0)]
    measurements = []
    valid = True
    for n, s in points:
        difference = float(abs(E[n, s] - saved["E"][n, s]))
        valid &= difference <= 1e-12 * max(1, abs(E[n, s]))
        valid &= abs(c[n, s] - saved["consumption"][n, s]) <= 1e-12 * max(1, abs(c[n, s]))
        valid &= np.all(np.abs(next_c[n, s] - saved["next_consumption"][n, s])
                        <= 1e-12 * np.maximum(1, np.abs(next_c[n, s])))
        measurements.append({"state": [n, s], "residual": float(E[n, s]), "difference": difference})
    mask = G > 0
    upper = G == model.N - 1
    joint = pi.reshape((model.N, 2), order="F")
    weight = float(joint[mask].sum())
    supported = mask & (joint > 1e-12)
    expected = {
        "maximum": float(E[mask].max()) if mask.any() else None,
        "mean": float(E[mask].mean()) if mask.any() else None,
        "weighted_mean": float(np.sum(joint[mask] * E[mask]) / weight) if weight > 0 else None,
        "weighted_maximum": float(np.max(joint[mask] * E[mask] / weight)) if weight > 0 else None,
        "supported_maximum": float(E[supported].max()) if supported.any() else None,
        "slack_mass": weight, "slack_count": int(mask.sum()), "upper_choice_count": int(upper.sum()),
    }
    differences = {}
    for key, value in expected.items():
        actual = saved["statistics"][key]
        if value is None:
            valid &= actual is None and bool(saved["statistics"]["unavailable_reasons"].get(key))
            differences[key] = None
        else:
            difference = float(abs(value - actual)) if actual is not None else float("inf")
            valid &= difference <= 1e-12 * max(1, abs(value))
            differences[key] = difference
    valid &= np.array_equal(mask, saved["slack"]) and np.array_equal(upper, saved["upper"])
    return outcome(10, valid, scalar_checks=measurements, summary_differences=differences,
                   expected_statistics=expected)


def run_validation(model, solutions, distributions, dense, sparse, diagnostics, reference):
    """Run tests 1–10 in order; driver saves completed checks on a failure."""
    yield kernel(solutions["kernel_vfi"], reference)
    ref = solutions["howard"]
    yield monotone(ref["G"])
    yield consumption(model, ref["G"], ref["consumption"])
    for name, dist in distributions.items():
        yield {**normalization(dist["pi"]), "distribution": name}
    for name, dist in distributions.items():
        yield {**nonnegative(dist["pi"], dist["metadata"]), "distribution": name}
    yield top_mass(distributions["sparse_power"]["pi"], model.N)
    yield transition(model, ref["G"], dense, sparse)
    for name, dist in distributions.items():
        Q = dense if name.startswith("dense") else sparse
        yield {**stationarity(Q, dist["pi"], model.N), "distribution": name}
    yield distribution_agreement(distributions)
    yield from bellman(model, solutions)
    yield euler(model, ref["G"], distributions["sparse_power"]["pi"], diagnostics)


def experiment_checks_pending():
    return {"test_id": 11, "status": "pending", "reason": "Stage-4 experiments and choices do not yet exist"}
