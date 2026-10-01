"""Question 2 experiments: resumable comparisons and binding student-choice gates."""
import hashlib
import json
from itertools import combinations
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import LinearOperator, splu, svds

from model import Model
from distributions import invariant
from diagnostics import accuracy_scaling, distribution_statistics, euler
from outputs import plotting, save_figure, save_solution, write_json, write_tables
from tests.checks import (CheckFailure, baseline_policy_checks, consumption, distribution_agreement,
                          euler as check_euler, monotone, nonnegative, normalization, range_top_mass,
                          stationarity, stopping, transition_selected)

METHODS = ("vfi", "howard", "modified_howard", "gradient", "adam")
DISTRIBUTIONS = ("power", "eigen", "direct")


def fingerprint(root):
    digest = hashlib.sha256()
    for folder in ("code", "tests"):
        for path in sorted((root / folder).glob("*.py")):
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def read_distribution(directory, name):
    with np.load(directory / f"{name}.npz", allow_pickle=False) as saved:
        pi = saved["pi"].copy()
    return {"pi": pi, "metadata": json.loads((directory / f"{name}.json").read_text())}


def read_diagnostics(directory, name):
    with np.load(directory / f"{name}.npz", allow_pickle=False) as saved:
        result = {key: saved[key].copy() for key in
                  ("consumption", "E", "cEE", "slack", "upper", "next_consumption")}
    result["statistics"] = json.loads((directory / f"{name}.json").read_text())["euler_statistics"]
    return result


def largest_difference(distributions):
    pairs = [(float(np.max(np.abs(distributions[a]["pi"] - distributions[b]["pi"]))), a, b)
             for a, b in combinations(distributions, 2)]
    difference, a, b = max(pairs)
    return {"maximum_difference": difference, "largest_pair": [a, b]}


def singular_values(model, G, budget_seconds=25):
    """Extreme singular values; estimate the smallest using the largest of J inverse."""
    started = perf_counter()
    deadline = started + budget_seconds
    Q = model.transition(G)
    J = sparse.eye(model.M, format="csc") - model.beta * Q.tocsc()
    settings = {"method": "svds largest of J and J_inverse; sigma_min=1/sigma_max(J_inverse)",
                "solver": "arpack", "k": 1, "which": "LM", "tol": 0.0,
                "optional_time_budget_seconds": budget_seconds,
                "initial_vector": "ones(M)/sqrt(M)"}
    try:
        factor = splu(J)

        def bounded(operation):
            def apply(vector):
                if perf_counter() >= deadline:
                    raise TimeoutError("Optional singular-value diagnostic exceeded its time budget")
                return operation(vector)
            return apply

        operator = LinearOperator(J.shape, dtype=np.float64,
                                  matvec=bounded(lambda v: J @ v),
                                  rmatvec=bounded(lambda v: J.T @ v))
        inverse = LinearOperator(J.shape, dtype=np.float64,
                                 matvec=bounded(lambda v: factor.solve(v)),
                                 rmatvec=bounded(lambda v: factor.solve(v, trans="T")))
        v0 = np.ones(model.M) / np.sqrt(model.M)
        maximum = float(svds(operator, k=1, which="LM", v0=v0,
                             tol=0, return_singular_vectors=False)[0])
        inverse_maximum = float(svds(inverse, k=1, which="LM", v0=v0,
                                     tol=0, return_singular_vectors=False)[0])
        minimum = 1 / inverse_maximum
        condition = maximum / minimum
        return {"status": "computed", "sigma_min": minimum, "sigma_max": maximum,
                "condition_J": condition, "condition_JtJ": condition ** 2,
                "seconds": perf_counter() - started, "settings": settings}
    except Exception as unavailable:
        # This diagnostic is optional under spec.md; no registered criterion is relaxed.
        return {"status": "unavailable", "reason": str(unavailable),
                "seconds": perf_counter() - started, "settings": settings}


def solver_rows(solutions):
    return [[name, r["metadata"]["outer_passes"], r["metadata"]["updates"],
             r["metadata"]["inner_steps"], f"{r['metadata']['seconds']:.6f}",
             f"{r['metadata']['exit_metric']:.12g}", r["metadata"]["status"]]
            for name, r in solutions.items()]


def distribution_rows(distributions):
    return [[name, f"{r['metadata']['seconds']:.6f}", r["metadata"].get("updates", "n/a"),
             f"{r['metadata']['raw_minimum']:.12g}", f"{r['metadata']['correction_mass']:.12g}",
             f"{r['metadata']['stationarity_residual']:.12g}"] for name, r in distributions.items()]


def tables(root, solutions, distributions, differences, theory, extra=()):
    headers = ["Method", "Passes", "Updates", "Inner steps", "Seconds", "Exit metric", "Status"]
    collection = []
    previous = {name: {"metadata": json.loads((root / "results" / "stage2" / f"{name}.json").read_text())}
                for name in METHODS[:3]}
    collection.append(("validation_solvers", "Stage-2 validation solvers (N=100, uniform [0,20])",
                       headers, solver_rows(previous)))
    previous_dists = {f"{representation}_{method}": read_distribution(root / "results" / "stage3", f"{representation}_{method}")
                      for representation in ("dense", "sparse") for method in DISTRIBUTIONS}
    collection.append(("validation_distributions", "Stage-3 invariant distributions",
                       ["Method", "Seconds", "Raw minimum", "Correction mass", "Stationarity"],
                       [[row[0], row[1], *row[3:]] for row in distribution_rows(previous_dists)]))
    collection.append(("part_a_solvers", "Part (a): baseline solvers, N=1000 uniform [0,20]",
                       headers, solver_rows(solutions)))
    collection.append(("parts_bc_distributions", "Parts (b)–(c): common Howard policy",
                       ["Method", "Seconds", "Power updates", "Raw minimum", "Correction mass", "Stationarity"],
                       distribution_rows(distributions)))
    collection.append(("parts_bc_agreement", "Parts (b)–(c): distribution differences",
                       ["Comparison", "Maximum difference", "Pair"],
                       [[group, f"{entry['maximum_difference']:.12g}", ", ".join(entry["largest_pair"])]
                        for group, entry in differences.items()]))
    rows = [["Contraction expression", f"{theory['contraction_prediction']:.12g}"],
            ["Observed VFI outer passes", theory["observed_vfi_passes"]],
            ["Specified 1/(1-beta)^2 expression", f"{theory['specified_hessian_expression']:.12g}"]]
    for label, values in theory["singular_values"].items():
        if values["status"] == "computed":
            rows.extend([[f"{label}: {key}", f"{values[key]:.12g}"]
                         for key in ("sigma_min", "sigma_max", "condition_J", "condition_JtJ")])
        else:
            rows.append([f"{label}: singular values", "unavailable"])
    collection.append(("part_a_theory_diagnostics", "Part (a): numerical theory diagnostics", ["Quantity", "Value"], rows))
    write_tables(root / "results", collection + list(extra))


def gradient_figures(directory, solutions):
    plt = plotting()
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for name in ("gradient", "adam"):
        trace = solutions[name]["trace"]
        passes = trace[trace[:, 3] == 0]
        axes[0].semilogy(passes[:, 0], passes[:, 1], label=name)
        axes[1].semilogy(passes[:, 0], passes[:, 2], label=name)
    axes[0].axhline(1e-8, color="black", linestyle="--", linewidth=1, label="Bellman tolerance")
    axes[0].set_ylabel("Relative Bellman metric d")
    axes[1].set_ylabel("Loss L = ||x − T(x)||² / 2")
    for ax in axes:
        ax.set_xlabel("Outer pass")
        ax.legend()
        ax.grid(alpha=0.25)
    save_figure(fig, directory, "part_a_gradient_traces")
    plt.close(fig)


def run_abc(root, deadline, resume, solve_one, load_solution, pause):
    directory = root / "results" / "stage4" / "abc"
    directory.mkdir(parents=True, exist_ok=True)
    checkpoints = directory / "checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    model = Model(1000, 20.0, "uniform")
    manifest_path = directory / "manifest.json"
    code_hash = fingerprint(root)
    if resume and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["code_sha256"] != code_hash:
            raise RuntimeError("Code changed since this experiment checkpoint; restart instead of resuming")
        manifest["resume_utility_construction_seconds"].append(model.utility_seconds)
    else:
        manifest = {"settings": model.settings(), "code_sha256": code_hash,
                    "resume_utility_construction_seconds": [], "status": "running"}
    write_json(manifest_path, manifest)
    solutions = {}
    for method in METHODS:
        solutions[method] = solve_one(model, method, method, 1e-8, directory, deadline, resume)
    solutions = {name: load_solution(directory, name, model) for name in METHODS}
    checks = []

    def record(check, **context):
        checks.append({**check, **context})
        write_json(directory / "tests.json", {"status": "running", "checks": checks})

    try:
        for check in stopping(model, solutions):
            record(check, part="a")
        if not solutions["howard"]["metadata"]["converged"]:
            raise CheckFailure("Howard reference did not converge")
        # The common dense matrix and conversion are built once and loaded on continuation.
        if resume and (directory / "transition.json").exists():
            with np.load(directory / "transition_dense.npz", allow_pickle=False) as saved:
                dense = saved["Q"].copy()
            csr = sparse.load_npz(directory / "transition_sparse.npz")
            transition_times = json.loads((directory / "transition.json").read_text())
        else:
            started = perf_counter()
            dense = model.transition(solutions["howard"]["G"], "dense")
            construction = perf_counter() - started
            started = perf_counter()
            csr = sparse.csr_matrix(dense)
            conversion = perf_counter() - started
            transition_times = {"dense_construction_seconds": construction, "csr_conversion_seconds": conversion}
            np.savez_compressed(directory / "transition_dense.npz", Q=dense)
            sparse.save_npz(directory / "transition_sparse.npz", csr)
            write_json(directory / "transition.json", transition_times)
        distributions = {}
        for representation, Q in (("dense", dense), ("sparse", csr)):
            for method in DISTRIBUTIONS:
                name = f"{representation}_{method}"
                if deadline - perf_counter() <= 1:
                    raise pause(f"Stopped before {name}; resume required")
                if resume and (directory / f"{name}.json").exists():
                    result = read_distribution(directory, name)
                else:
                    checkpoint = checkpoints / f"{name}.npz"
                    if not resume and checkpoint.exists():
                        checkpoint.unlink()
                    result = invariant(Q, method, max(0.1, deadline - perf_counter() - 1), checkpoint)
                    if result is None:
                        raise pause(f"Power checkpoint saved for {name}")
                    np.savez_compressed(directory / f"{name}.npz", pi=result["pi"])
                    write_json(directory / f"{name}.json", result["metadata"])
                    if checkpoint.exists():
                        checkpoint.unlink()
                    print(f"{name}: {result['metadata']['seconds']:.6f}s, "
                          f"stationarity={result['metadata']['stationarity_residual']:.12g}", flush=True)
                distributions[name] = result
                for check in (normalization(result["pi"]), nonnegative(result["pi"], result["metadata"]),
                              stationarity(Q, result["pi"], model.N)):
                    record(check, distribution=name, part="b" if representation == "dense" else "c")
        distributions = {name: read_distribution(directory, name) for name in distributions}
        record(distribution_agreement(distributions), part="bc")
        differences = {representation: largest_difference({k: v for k, v in distributions.items() if k.startswith(representation)})
                       for representation in ("dense", "sparse")}
        cross = [(float(np.max(np.abs(a["pi"] - b["pi"]))), an, bn)
                 for an, a in distributions.items() if an.startswith("dense")
                 for bn, b in distributions.items() if bn.startswith("sparse")]
        difference, a, b = max(cross)
        differences["across_representations"] = {"maximum_difference": difference, "largest_pair": [a, b]}
        differences["all_six"] = largest_difference(distributions)
        common_distribution = distributions["sparse_power"]
        policy_agreement = {}
        for name, solution in solutions.items():
            if not solution["metadata"]["converged"]:
                continue
            mismatch = int(np.count_nonzero(solution["G"] != solutions["howard"]["G"]))
            policy_agreement[name] = mismatch
            if mismatch == 0:
                own_dense, own_csr, own_distribution = dense, csr, common_distribution
            else:
                own_dense = model.transition(solution["G"], "dense")
                own_csr = sparse.csr_matrix(own_dense)
                if deadline - perf_counter() <= 1:
                    raise pause(f"Policy checks for {name} require continuation")
                checkpoint = checkpoints / f"{name}_policy_distribution.npz"
                own_distribution = invariant(own_csr, "power", max(0.1, deadline - perf_counter() - 1), checkpoint)
                if own_distribution is None:
                    raise pause(f"Policy-distribution checkpoint saved for {name}")
            pi = own_distribution["pi"]
            diagnostics = euler(model, solution["G"], pi)
            save_solution(directory, name, model, solution, pi, diagnostics)
            diagnostics = read_diagnostics(directory, name)
            for check in baseline_policy_checks(model, solution, pi, own_distribution["metadata"],
                                                 own_dense, own_csr, diagnostics):
                record(check, solver=name, part="a")
        write_json(directory / "tests.json", {"status": "passed", "checks": checks,
                                               "pending": "Test 11 and later experiments"})
    except CheckFailure as failure:
        write_json(directory / "tests.json", {"status": "failed", "checks": checks, "failure": str(failure)})
        raise
    theory_path = directory / "theory.json"
    if resume and theory_path.exists():
        theory = json.loads(theory_path.read_text())
    else:
        theory = {"contraction_prediction": float(np.log(1e-8) / np.log(model.beta)),
                  "observed_vfi_passes": solutions["vfi"]["metadata"]["outer_passes"],
                  "specified_hessian_expression": float(1 / (1 - model.beta) ** 2),
                  "singular_values": {}}
    for name, policy in (("zero_values", model.bellman(np.zeros(model.M))[1]),
                         ("howard_solution", solutions["howard"]["G"])):
        if name not in theory["singular_values"]:
            if deadline - perf_counter() < 26:
                write_json(theory_path, theory)
                raise pause(f"Singular-value diagnostics for {name} require continuation")
            theory["singular_values"][name] = singular_values(model, policy)
            write_json(theory_path, theory)
    tables(root, solutions, distributions, differences, theory)
    gradient_figures(directory, solutions)
    runtimes = {"a_solver_seconds": sum(r["metadata"]["seconds"] for r in solutions.values()),
                "utility_construction_seconds": manifest["settings"]["utility_seconds"],
                "a_optional_singular_seconds": sum(v["seconds"] for v in theory["singular_values"].values()),
                "b_distribution_seconds": sum(v["metadata"]["seconds"] for k, v in distributions.items() if k.startswith("dense")),
                "c_distribution_seconds": sum(v["metadata"]["seconds"] for k, v in distributions.items() if k.startswith("sparse")),
                **transition_times}
    eligible = {"solvers": [name for name, r in solutions.items() if r["metadata"]["converged"]],
                "distribution_methods": list(DISTRIBUTIONS), "representations": ["dense", "sparse"]}
    summary = {"status": "awaiting_method_choice", "parts_complete": ["a", "b", "c"],
               "settings": manifest["settings"], "solvers": {k: v["metadata"] for k, v in solutions.items()},
               "distributions": {k: v["metadata"] for k, v in distributions.items()},
               "distribution_differences": differences, "policy_mismatches_vs_howard": policy_agreement,
               "distribution_statistics": distribution_statistics(model.grid, common_distribution["pi"]),
               "theory": theory, "runtimes": runtimes, "tests": "passed",
               "check_records": len(checks), "eligible_choices": eligible,
               "pending": ["method choice", "e", "f", "g", "h", "test 11", "README", "stage-4 manual commit"]}
    write_json(directory / "summary.json", summary)
    manifest["status"] = "awaiting_method_choice"
    write_json(manifest_path, manifest)
    print(json.dumps(summary, indent=2), flush=True)
    print("STOP after (c): await solver, distribution method, and representation choices.", flush=True)


def validate_selected_methods(root, settings):
    summary = json.loads((root / "results" / "stage4" / "abc" / "summary.json").read_text())
    if summary["tests"] != "passed":
        raise RuntimeError("Parts (a)–(c) have not passed their applicable checks")
    eligible = summary["eligible_choices"]
    for key, group in (("solver", "solvers"), ("distribution_method", "distribution_methods"),
                       ("representation", "representations")):
        if settings[key] not in eligible[group]:
            raise RuntimeError(f"Missing or ineligible student selection: {key}")


def selected_policy_checks(model, solution, distribution, Q, diagnostics, trial=False):
    """Use only the selected method/representation from (e) onward."""
    yield monotone(solution["G"])
    yield consumption(model, solution["G"], solution["consumption"])
    yield normalization(distribution["pi"])
    yield nonnegative(distribution["pi"], distribution["metadata"])
    if trial:
        yield range_top_mass(distribution["pi"], model.N)
    else:
        from tests.checks import top_mass
        yield top_mass(distribution["pi"], model.N)
    yield transition_selected(model, solution["G"], Q)
    yield stationarity(Q, distribution["pi"], model.N)
    yield from stopping(model, {solution["metadata"]["method"]: solution})
    yield check_euler(model, solution["G"], distribution["pi"], diagnostics)


def range_table(trials):
    return ("part_e_ranges", "Part (e): uniform range trials, N=1000; selected methods",
            ["k_max", "Top mass", "Support endpoint", "Support share", "Compute seconds", "Range status"],
            [[trial["k_max"], f"{trial['statistics']['top_node_mass']:.12g}",
              f"{trial['statistics']['support_endpoint']:.12g}", f"{trial['statistics']['support_share']:.6f}",
              f"{trial['timings']['compute_seconds']:.6f}", trial["range_status"]] for trial in trials])


def preserve_abc_tables(root, extra):
    directory = root / "results" / "stage4" / "abc"
    summary = json.loads((directory / "summary.json").read_text())
    solutions = {name: {"metadata": metadata} for name, metadata in summary["solvers"].items()}
    distributions = {name: read_distribution(directory, name) for name in summary["distributions"]}
    tables(root, solutions, distributions, summary["distribution_differences"], summary["theory"], extra)


def run_e(root, deadline, resume, solve_one, load_solution, pause, settings):
    """All six range trials, then a binding k_max-choice gate."""
    validate_selected_methods(root, settings)
    directory = root / "results" / "stage4" / "e"
    directory.mkdir(parents=True, exist_ok=True)
    methods = {key: settings[key] for key in ("solver", "distribution_method", "representation")}
    manifest_path = directory / "manifest.json"
    code_hash = fingerprint(root)
    if resume and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["code_sha256"] != code_hash or manifest["selected_methods"] != methods:
            raise RuntimeError("Code or selected methods changed since the range checkpoint")
    else:
        manifest = {"code_sha256": code_hash, "selected_methods": methods,
                    "ranges": [1, 2, 5, 10, 20, 40], "N": 1000, "grid_kind": "uniform", "status": "running"}
    write_json(manifest_path, manifest)
    trials = []
    all_checks = []
    for k_max in manifest["ranges"]:
        trial_dir = directory / f"kmax_{k_max}"
        trial_dir.mkdir(parents=True, exist_ok=True)
        if resume and (trial_dir / "summary.json").exists():
            trial = json.loads((trial_dir / "summary.json").read_text())
            trials.append(trial)
            all_checks.extend(trial["checks"])
            continue
        if deadline - perf_counter() <= 1:
            raise pause(f"Range k_max={k_max} requires continuation")
        model = Model(1000, float(k_max), "uniform")
        utility_path = trial_dir / "utility.json"
        if not resume or not utility_path.exists():
            write_json(utility_path, {"seconds": model.utility_seconds})
        utility_time = json.loads(utility_path.read_text())["seconds"]
        solution = solve_one(model, methods["solver"], "solution", 1e-8, trial_dir, deadline, resume)
        # Every non-gradient selected solver must meet its saved Bellman criterion.
        if not solution["metadata"]["converged"]:
            raise CheckFailure(f"Selected solver failed at k_max={k_max}")
        transition_path = trial_dir / "transition.npz"
        if resume and transition_path.exists():
            if methods["representation"] == "sparse":
                Q = sparse.load_npz(transition_path)
            else:
                with np.load(transition_path, allow_pickle=False) as saved:
                    Q = saved["Q"].copy()
            transition_time = json.loads((trial_dir / "transition.json").read_text())["seconds"]
        else:
            started = perf_counter()
            Q = model.transition(solution["G"], methods["representation"])
            transition_time = perf_counter() - started
            if methods["representation"] == "sparse":
                sparse.save_npz(transition_path, Q)
            else:
                np.savez_compressed(transition_path, Q=Q)
            write_json(trial_dir / "transition.json", {"seconds": transition_time,
                        "representation": methods["representation"]})
        if deadline - perf_counter() <= 1:
            raise pause(f"Distribution for k_max={k_max} requires continuation")
        checkpoint = trial_dir / "checkpoints" / "distribution.npz"
        if resume and (trial_dir / "distribution.json").exists():
            distribution = read_distribution(trial_dir, "distribution")
        else:
            if not resume and checkpoint.exists():
                checkpoint.unlink()
            distribution = invariant(Q, methods["distribution_method"],
                                     max(0.1, deadline - perf_counter() - 1), checkpoint)
            if distribution is None:
                raise pause(f"Power checkpoint saved for k_max={k_max}")
            np.savez_compressed(trial_dir / "distribution.npz", pi=distribution["pi"])
            write_json(trial_dir / "distribution.json", distribution["metadata"])
            if checkpoint.exists():
                checkpoint.unlink()
        diagnostics = euler(model, solution["G"], distribution["pi"])
        save_solution(trial_dir, "solution", model, solution, distribution["pi"], diagnostics)
        solution = load_solution(trial_dir, "solution", model)
        distribution = read_distribution(trial_dir, "distribution")
        diagnostics = read_diagnostics(trial_dir, "solution")
        checks = []
        try:
            for check in selected_policy_checks(model, solution, distribution, Q, diagnostics, trial=True):
                checks.append({**check, "k_max": k_max})
        except CheckFailure as failure:
            write_json(trial_dir / "tests.json", {"status": "failed", "checks": checks, "failure": str(failure)})
            raise
        classification = next(check for check in checks if check["test_id"] == 6)
        stats = distribution_statistics(model.grid, distribution["pi"])
        timings = {"utility_seconds": utility_time, "solver_seconds": solution["metadata"]["seconds"],
                   "transition_seconds": transition_time, "distribution_seconds": distribution["metadata"]["seconds"]}
        timings["compute_seconds"] = sum(timings.values())
        trial = {"k_max": k_max, "settings": model.settings(), "selected_methods": methods,
                 "statistics": stats, "timings": timings, "solver": solution["metadata"],
                 "distribution": distribution["metadata"], "range_status": classification["range_status"],
                 "checks": checks, "euler_statistics": diagnostics["statistics"]}
        write_json(trial_dir / "tests.json", {"status": "passed" if classification["passed"] else "passed_with_expected_range_rejection",
                                               "checks": checks})
        write_json(trial_dir / "summary.json", trial)
        trials.append(trial)
        all_checks.extend(checks)
        print(f"k_max={k_max}: top mass={stats['top_node_mass']:.12g}, "
              f"support endpoint={stats['support_endpoint']:.12g}, share={stats['support_share']:.3f}, "
              f"compute={timings['compute_seconds']:.6f}s, {classification['range_status']}", flush=True)
    summary = {"status": "awaiting_range_choice", "part_complete": "e", "selected_methods": methods,
               "N": 1000, "grid_kind": "uniform", "ranges": manifest["ranges"], "trials": trials,
               "eligible_ranges": [t["k_max"] for t in trials if t["range_status"] == "eligible"],
               "rejected_ranges": [t["k_max"] for t in trials if t["range_status"] != "eligible"],
               "checks": all_checks, "compute_seconds": sum(t["timings"]["compute_seconds"] for t in trials),
               "runtime_convention": "utility + solver + selected Q construction + selected distribution; output/checkpoint/check overhead excluded",
               "pending": ["k_max choice", "f", "g", "h", "test 11", "README", "stage-4 manual commit"]}
    write_json(directory / "summary.json", summary)
    manifest["status"] = "awaiting_range_choice"
    write_json(manifest_path, manifest)
    preserve_abc_tables(root, [range_table(trials)])
    print(json.dumps({key: value for key, value in summary.items() if key not in ("trials", "checks")}, indent=2), flush=True)
    print("STOP after (e): await k_max choice. No uniform/exp-log comparison has run.", flush=True)


def validate_selected_range(root, settings):
    validate_selected_methods(root, settings)
    ranges = json.loads((root / "results" / "stage4" / "e" / "summary.json").read_text())
    if settings["k_max"] not in ranges["eligible_ranges"]:
        raise RuntimeError("Missing or ineligible student range selection")
    if any(ranges["selected_methods"][key] != settings[key] for key in ranges["selected_methods"]):
        raise RuntimeError("Selected methods differ from the verified range trials")


def solve_selected_case(model, case_dir, methods, deadline, resume, solve_one, load_solution, pause):
    """Save and check one accepted-grid solution using only the selected methods."""
    case_dir.mkdir(parents=True, exist_ok=True)
    if deadline - perf_counter() <= 1:
        raise pause(f"{case_dir.name} requires continuation")
    utility_path = case_dir / "utility.json"
    if not resume or not utility_path.exists():
        write_json(utility_path, {"seconds": model.utility_seconds})
    utility_time = json.loads(utility_path.read_text())["seconds"]
    solution = solve_one(model, methods["solver"], "solution", 1e-8, case_dir, deadline, resume)
    if not solution["metadata"]["converged"]:
        raise CheckFailure(f"Selected solver failed for {case_dir.name}")
    transition_path = case_dir / "transition.npz"
    if resume and transition_path.exists():
        if methods["representation"] == "sparse":
            Q = sparse.load_npz(transition_path)
        else:
            with np.load(transition_path, allow_pickle=False) as saved:
                Q = saved["Q"].copy()
        transition_time = json.loads((case_dir / "transition.json").read_text())["seconds"]
    else:
        started = perf_counter()
        Q = model.transition(solution["G"], methods["representation"])
        transition_time = perf_counter() - started
        if methods["representation"] == "sparse":
            sparse.save_npz(transition_path, Q)
        else:
            np.savez_compressed(transition_path, Q=Q)
        write_json(case_dir / "transition.json", {"seconds": transition_time,
                                                   "representation": methods["representation"]})
    if deadline - perf_counter() <= 1:
        raise pause(f"Distribution for {case_dir.name} requires continuation")
    checkpoint = case_dir / "checkpoints" / "distribution.npz"
    if resume and (case_dir / "distribution.json").exists():
        distribution = read_distribution(case_dir, "distribution")
    else:
        if not resume and checkpoint.exists():
            checkpoint.unlink()
        distribution = invariant(Q, methods["distribution_method"],
                                 max(0.1, deadline - perf_counter() - 1), checkpoint)
        if distribution is None:
            raise pause(f"Distribution checkpoint saved for {case_dir.name}")
        np.savez_compressed(case_dir / "distribution.npz", pi=distribution["pi"])
        write_json(case_dir / "distribution.json", distribution["metadata"])
        if checkpoint.exists():
            checkpoint.unlink()
    diagnostics = euler(model, solution["G"], distribution["pi"])
    save_solution(case_dir, "solution", model, solution, distribution["pi"], diagnostics)
    solution = load_solution(case_dir, "solution", model)
    distribution = read_distribution(case_dir, "distribution")
    diagnostics = read_diagnostics(case_dir, "solution")
    checks = []
    try:
        for check in selected_policy_checks(model, solution, distribution, Q, diagnostics):
            checks.append({**check, "N": model.N, "grid_kind": model.grid_kind,
                           "k_max": float(model.grid[-1])})
    except CheckFailure as failure:
        write_json(case_dir / "tests.json", {"status": "failed", "checks": checks, "failure": str(failure)})
        raise
    statistics = distribution_statistics(model.grid, distribution["pi"])
    statistics["maximum_grid_step"] = float(np.max(np.diff(model.grid)))
    timings = {"utility_seconds": utility_time, "solver_seconds": solution["metadata"]["seconds"],
               "transition_seconds": transition_time, "distribution_seconds": distribution["metadata"]["seconds"]}
    timings["compute_seconds"] = sum(timings.values())
    result = {"settings": model.settings(), "selected_methods": methods, "statistics": statistics,
              "solver": solution["metadata"], "distribution": distribution["metadata"],
              "euler_statistics": diagnostics["statistics"], "timings": timings, "checks": checks,
              "status": "passed"}
    write_json(case_dir / "tests.json", {"status": "passed", "checks": checks})
    write_json(case_dir / "summary.json", result)
    return result


def grid_comparison_table(comparisons):
    definitions = [
        ("Outer passes", "solver", "outer_passes"), ("Updates", "solver", "updates"),
        ("Inner steps", "solver", "inner_steps"), ("Exit metric", "solver", "exit_metric"),
        ("Solver seconds", "solver", "seconds"), ("Power updates", "distribution", "updates"),
        ("Distribution seconds", "distribution", "seconds"), ("Compute seconds", "timings", "compute_seconds"),
        ("Maximum grid step", "statistics", "maximum_grid_step"), ("Mean assets", "statistics", "mean_assets"),
        ("Top mass", "statistics", "top_node_mass"), ("Support endpoint", "statistics", "support_endpoint"),
        ("Support share", "statistics", "support_share"), ("Slack count", "euler_statistics", "slack_count"),
        ("Slack mass", "euler_statistics", "slack_mass"), ("Upper choices", "euler_statistics", "upper_choice_count"),
        ("Euler maximum", "euler_statistics", "maximum"), ("Euler mean", "euler_statistics", "mean"),
        ("Conditional weighted mean", "euler_statistics", "weighted_mean"),
        ("Weighted maximum: max(qE)", "euler_statistics", "weighted_maximum"),
        ("Supported slack maximum", "euler_statistics", "supported_maximum")]
    rows = []
    for label, group, key in definitions:
        values = [comparisons[kind][group][key] for kind in ("uniform", "exp_log")]
        rows.append([label, *["unavailable" if v is None else f"{v:.12g}" if isinstance(v, float) else v for v in values]])
    return ("part_f_grids", "Part (f): uniform and exp-log, N=1000 at selected range",
            ["Quantity", "Uniform", "Exp-log"], rows)


def grid_comparison_figures(directory, comparisons):
    plt = plotting()
    fig, axes = plt.subplots(2, 3, figsize=(12, 7), layout="constrained")
    residual_fig, residual_axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for kind, label, style in (("uniform", "Uniform", "--"), ("exp_log", "Exp-log", "-")):
        with np.load(directory / kind / "solution.npz", allow_pickle=False) as saved:
            grid, V, G, pi = [saved[key] for key in ("grid", "V", "G", "pi")]
            joint = pi.reshape((len(grid), 2), order="F")
            for s, efficiency in enumerate((0.8, 1.2)):
                axes[s, 0].plot(grid, V[:, s], style, label=label)
                axes[s, 1].plot(grid, grid[G[:, s]], style, label=label)
                axes[s, 2].plot(grid, joint[:, s], style, label=label, linewidth=1)
                mask = saved["slack"][:, s]
                residual_axes[s].plot(grid[mask], saved["E"][mask, s], style, label=label, linewidth=1)
                residual_axes[s].set_title(f"Efficiency {efficiency}: slack states")
                for j, title in enumerate(("Value", "Savings policy", "Joint probability mass")):
                    axes[s, j].set_title(f"{title}, efficiency {efficiency}")
    for ax in axes.flat:
        ax.set_xlabel("Assets")
        ax.grid(alpha=0.2)
        ax.legend()
    for ax in residual_axes:
        ax.set_xlabel("Assets")
        ax.set_ylabel("Euler residual |1 − cEE/c|")
        ax.grid(alpha=0.2)
        ax.legend()
    save_figure(fig, directory, "part_f_values_policies_masses")
    save_figure(residual_fig, directory, "part_f_euler_comparison")
    plt.close(fig)
    plt.close(residual_fig)


def run_f(root, deadline, resume, solve_one, load_solution, pause, settings):
    """Two prescribed grids at N=1000, then a binding grid-choice gate."""
    validate_selected_range(root, settings)
    directory = root / "results" / "stage4" / "f"
    directory.mkdir(parents=True, exist_ok=True)
    methods = {key: settings[key] for key in ("solver", "distribution_method", "representation")}
    manifest_path = directory / "manifest.json"
    code_hash = fingerprint(root)
    if resume and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if (manifest["code_sha256"] != code_hash or manifest["selected_methods"] != methods
                or manifest["k_max"] != settings["k_max"]):
            raise RuntimeError("Code or settings changed since the grid-comparison checkpoint")
    else:
        manifest = {"code_sha256": code_hash, "selected_methods": methods, "k_max": settings["k_max"],
                    "N": 1000, "grids": ["uniform", "exp_log"], "status": "running"}
    write_json(manifest_path, manifest)
    comparisons = {}
    for kind in manifest["grids"]:
        case_dir = directory / kind
        if resume and (case_dir / "summary.json").exists():
            result = json.loads((case_dir / "summary.json").read_text())
        else:
            if deadline - perf_counter() <= 1:
                raise pause(f"Grid {kind} requires continuation")
            model = Model(1000, float(settings["k_max"]), kind)
            result = solve_selected_case(model, case_dir, methods, deadline, resume, solve_one, load_solution, pause)
            print(f"{kind}: compute={result['timings']['compute_seconds']:.6f}s, "
                  f"Euler maximum={result['euler_statistics']['maximum']:.12g}, "
                  f"mean={result['euler_statistics']['mean']:.12g}, "
                  f"weighted mean={result['euler_statistics']['weighted_mean']:.12g}", flush=True)
        comparisons[kind] = result
    checks = [check for result in comparisons.values() for check in result["checks"]]
    summary = {"status": "awaiting_grid_choice", "part_complete": "f", "selected_methods": methods,
               "N": 1000, "k_max": settings["k_max"], "comparisons": comparisons,
               "checks": checks, "compute_seconds": sum(r["timings"]["compute_seconds"] for r in comparisons.values()),
               "weighted_maximum_convention": "max_A(q*E), q=pi/sum_A(pi)",
               "runtime_convention": "utility + solver + selected Q construction + selected distribution",
               "pending": ["grid choice", "g", "h", "test 11", "README", "stage-4 manual commit"]}
    write_json(directory / "summary.json", summary)
    write_json(directory / "tests.json", {"status": "passed", "checks": checks})
    range_summary = json.loads((root / "results" / "stage4" / "e" / "summary.json").read_text())
    preserve_abc_tables(root, [range_table(range_summary["trials"]), grid_comparison_table(comparisons)])
    grid_comparison_figures(directory, comparisons)
    manifest["status"] = "awaiting_grid_choice"
    write_json(manifest_path, manifest)
    print(f"Part (f) complete: {len(checks)} applicable check records passed.", flush=True)
    print("STOP after (f): await uniform or exp-log grid choice. No part-(g) node-count trial has run.", flush=True)


def validate_selected_grid(root, settings):
    validate_selected_range(root, settings)
    comparison = json.loads((root / "results" / "stage4" / "f" / "summary.json").read_text())
    selected = comparison["comparisons"].get(settings["grid_kind"])
    if selected is None or selected["status"] != "passed" or not all(c["passed"] for c in selected["checks"]):
        raise RuntimeError("Missing or unverified student grid selection")
    if (selected["settings"]["k_max"] != settings["k_max"]
            or any(selected["selected_methods"][key] != settings[key] for key in selected["selected_methods"])):
        raise RuntimeError("Selected methods/range differ from the verified grid comparison")


def node_comparison_tables(trials):
    definitions = [
        ("Outer passes", "solver", "outer_passes"), ("Updates", "solver", "updates"),
        ("Inner steps", "solver", "inner_steps"), ("Exit metric", "solver", "exit_metric"),
        ("Utility seconds", "timings", "utility_seconds"), ("Solver seconds", "timings", "solver_seconds"),
        ("CSR construction seconds", "timings", "transition_seconds"),
        ("Power seconds", "timings", "distribution_seconds"), ("Power updates", "distribution", "updates"),
        ("Compute seconds", "timings", "compute_seconds"),
        ("Stationarity residual", "distribution", "stationarity_residual"),
        ("Maximum grid step", "statistics", "maximum_grid_step"), ("Mean assets", "statistics", "mean_assets"),
        ("Top mass", "statistics", "top_node_mass"), ("Support endpoint", "statistics", "support_endpoint"),
        ("Support share", "statistics", "support_share"), ("Slack count", "euler_statistics", "slack_count"),
        ("Slack mass", "euler_statistics", "slack_mass"), ("Upper choices", "euler_statistics", "upper_choice_count"),
        ("Euler maximum", "euler_statistics", "maximum"), ("Euler mean", "euler_statistics", "mean"),
        ("Conditional weighted mean", "euler_statistics", "weighted_mean"),
        ("Weighted maximum: max(qE)", "euler_statistics", "weighted_maximum"),
        ("Supported slack maximum", "euler_statistics", "supported_maximum")]
    rows = []
    for label, group, key in definitions:
        values = [trial[group][key] for trial in trials]
        rows.append([label, *["unavailable" if v is None else f"{v:.12g}" if isinstance(v, float) else v for v in values]])
    return ("part_g_nodes", "Part (g): selected methods, range, and grid across five node counts",
            ["Quantity", *[f"N={t['settings']['N']}" for t in trials]], rows)


def node_comparison_figures(directory, trials):
    plt = plotting()
    figures = [plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained") for _ in range(3)]
    styles = ("--", "-.", ":", "--", "-")
    for trial, style in zip(trials, styles):
        N = trial["settings"]["N"]
        with np.load(directory / f"N_{N}" / "solution.npz", allow_pickle=False) as saved:
            grid, V, G, pi = [saved[key] for key in ("grid", "V", "G", "pi")]
            joint = pi.reshape((N, 2), order="F")
            for s in range(2):
                for (_, axes), values in zip(figures, (V[:, s], grid[G[:, s]], joint[:, s])):
                    axes[s].plot(grid, values, linestyle=style, label=f"N={N}", linewidth=1.1)
    for (fig, axes), name, ylabel in zip(figures,
            ("part_g_values", "part_g_policies", "part_g_joint_masses"),
            ("Value", "Next-period assets", "Joint probability mass")):
        for s, ax in enumerate(axes):
            ax.set_title(f"Efficiency {(0.8, 1.2)[s]}")
            ax.set_xlabel("Assets")
            ax.set_ylabel(ylabel)
            ax.grid(alpha=0.2)
            ax.legend()
        fig.suptitle(f"Part (g): {ylabel.lower()}, {trials[0]['settings']['grid_kind']} grid on [0,{trials[0]['settings']['k_max']:g}]")
        save_figure(fig, directory, name)
        plt.close(fig)


def run_g(root, deadline, resume, solve_one, load_solution, pause, settings):
    """All five specified node counts, then a binding final-N choice gate."""
    validate_selected_grid(root, settings)
    directory = root / "results" / "stage4" / "g"
    directory.mkdir(parents=True, exist_ok=True)
    methods = {key: settings[key] for key in ("solver", "distribution_method", "representation")}
    manifest_path = directory / "manifest.json"
    code_hash = fingerprint(root)
    if resume and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if (manifest["code_sha256"] != code_hash or manifest["selected_methods"] != methods
                or manifest["k_max"] != settings["k_max"] or manifest["grid_kind"] != settings["grid_kind"]):
            raise RuntimeError("Code or settings changed since the node-comparison checkpoint")
    else:
        manifest = {"code_sha256": code_hash, "selected_methods": methods, "k_max": settings["k_max"],
                    "grid_kind": settings["grid_kind"], "node_counts": [100, 500, 1000, 2000, 5000],
                    "status": "running"}
    write_json(manifest_path, manifest)
    trials = []
    for N in manifest["node_counts"]:
        case_dir = directory / f"N_{N}"
        if resume and (case_dir / "summary.json").exists():
            result = json.loads((case_dir / "summary.json").read_text())
        else:
            if deadline - perf_counter() <= 1:
                raise pause(f"N={N} requires continuation")
            model = Model(N, float(settings["k_max"]), settings["grid_kind"])
            result = solve_selected_case(model, case_dir, methods, deadline, resume, solve_one, load_solution, pause)
            del model  # Release the quadratic utility array before building the next grid.
            print(f"N={N}: compute={result['timings']['compute_seconds']:.6f}s, "
                  f"Euler maximum={result['euler_statistics']['maximum']:.12g}, "
                  f"mean={result['euler_statistics']['mean']:.12g}, "
                  f"weighted mean={result['euler_statistics']['weighted_mean']:.12g}", flush=True)
        trials.append(result)
    checks = [check for trial in trials for check in trial["checks"]]
    summary = {"status": "awaiting_N_choice", "part_complete": "g", "selected_methods": methods,
               "k_max": settings["k_max"], "grid_kind": settings["grid_kind"],
               "node_counts": manifest["node_counts"], "trials": trials, "checks": checks,
               "compute_seconds": sum(t["timings"]["compute_seconds"] for t in trials),
               "weighted_maximum_convention": "max_A(q*E), q=pi/sum_A(pi)",
               "runtime_convention": "utility + solver + selected Q construction + selected distribution; output/checkpoint/check overhead excluded",
               "pending": ["final N choice", "h", "test 11", "README", "stage-4 manual commit"]}
    write_json(directory / "summary.json", summary)
    write_json(directory / "tests.json", {"status": "passed", "checks": checks})
    range_summary = json.loads((root / "results" / "stage4" / "e" / "summary.json").read_text())
    grid_summary = json.loads((root / "results" / "stage4" / "f" / "summary.json").read_text())
    preserve_abc_tables(root, [range_table(range_summary["trials"]),
                              grid_comparison_table(grid_summary["comparisons"]), node_comparison_tables(trials)])
    node_comparison_figures(directory, trials)
    manifest["status"] = "awaiting_N_choice"
    write_json(manifest_path, manifest)
    print(f"Part (g) complete: {len(checks)} applicable check records passed.", flush=True)
    print("STOP after (g): await final N choice. No part-(h) accuracy-scaling experiment has run.", flush=True)


def accuracy_tables(statistics, fits):
    keys = ["slack_count", "slack_mass", "upper_choice_count", "maximum", "mean", "weighted_mean",
            "weighted_maximum", "supported_maximum"]
    rows = [[key, "unavailable" if statistics[key] is None else f"{statistics[key]:.12g}"] for key in keys]
    rows += [[f"{key}: reason", value] for key, value in statistics["unavailable_reasons"].items()]
    return [("part_h_accuracy", "Part (h): selected-grid Euler diagnostics; weighted maximum is max(qE)",
             ["Quantity", "Value"], rows),
            ("part_h_scaling", "Part (h): OLS log(error) against log(maximum grid step)",
             ["Error summary", "Intercept", "Slope", "Used grids", "Reason"],
             [[key, "unavailable" if fit["intercept"] is None else f"{fit['intercept']:.12g}",
               "unavailable" if fit["slope"] is None else f"{fit['slope']:.12g}",
               len(fit["used_indices"]), fit["reason"] or "available"] for key, fit in fits.items()])]


def accuracy_figures(directory, arrays, grids, summaries, fits):
    plt = plotting()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    for s, ax in enumerate(axes):
        mask = arrays["slack"][:, s]
        ax.plot(arrays["grid"][mask], arrays["E"][mask, s], linewidth=.6, label="Every slack state")
        upper = arrays["upper"][:, s] & mask
        if upper.any():
            ax.scatter(arrays["grid"][upper], arrays["E"][upper, s], marker="x", color="red", label="Upper-bound choice")
        ax.set_title(f"Efficiency {(0.8, 1.2)[s]}")
        ax.set_xlabel("Assets")
        ax.set_ylabel("Euler residual |1 − cEE/c|")
        ax.grid(alpha=.2)
        ax.legend()
    fig.suptitle(f"Part (h): selected N={len(arrays['grid'])}, Euler residuals at every slack state")
    save_figure(fig, directory, "part_h_euler_residuals")
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    for ax, key in zip(axes, ("mean", "maximum")):
        fit = fits[key]
        h = np.array(fit["h"])
        errors = np.array([np.nan if summary[key] is None else summary[key] for summary in summaries])
        indices = np.array(fit["used_indices"], dtype=int)
        ax.loglog(h[indices], errors[indices], "o", label=f"Unweighted {key}")
        for i in indices:
            ax.annotate(f"N={len(grids[i])}", (h[i], errors[i]), xytext=(4, 4), textcoords="offset points", fontsize=8)
        if fit["slope"] is not None:
            line = np.geomspace(h[indices].min(), h[indices].max(), 100)
            ax.loglog(line, np.exp(fit["intercept"])*line**fit["slope"], "--", label=f"OLS slope={fit['slope']:.4f}")
        ax.set_xlabel("Maximum grid step h")
        ax.set_ylabel(f"Euler {key}")
        ax.margins(x=.18, y=.18)
        ax.grid(alpha=.2, which="both")
        ax.legend()
    fig.suptitle("Part (h): five-grid accuracy scaling")
    save_figure(fig, directory, "part_h_accuracy_scaling")
    plt.close(fig)


def run_h(root, deadline, resume, load_solution, pause, settings):
    """Use the chosen saved solution; recompute final checks and all-five-grid OLS."""
    from tests.experiments import NODES, scaling
    started = perf_counter()
    validate_selected_grid(root, settings)
    g = json.loads((root/"results/stage4/g/summary.json").read_text())
    if g["node_counts"] != NODES or settings["N"] not in NODES:
        raise RuntimeError("Missing five-grid results or invalid final N selection")
    selected = next(t for t in g["trials"] if t["settings"]["N"] == settings["N"])
    if selected["status"] != "passed" or not all(c["passed"] for c in selected["checks"]):
        raise RuntimeError("Final N selection has not passed its applicable checks")
    methods = {key: settings[key] for key in ("solver", "distribution_method", "representation")}
    if selected["selected_methods"] != methods:
        raise RuntimeError("Final methods differ from selected-grid solution")
    if deadline-perf_counter() <= 1:
        raise pause("Part-(h) analysis requires continuation")
    directory = root/"results/stage4/h"
    case_dir = root/f"results/stage4/g/N_{settings['N']}"
    model = Model(settings["N"], float(settings["k_max"]), settings["grid_kind"])
    solution = load_solution(case_dir, "solution", model)
    distribution = read_distribution(case_dir, "distribution")
    if methods["representation"] == "sparse":
        Q = sparse.load_npz(case_dir/"transition.npz")
    else:
        with np.load(case_dir/"transition.npz", allow_pickle=False) as saved:
            Q = saved["Q"].copy()
    diagnostics = euler(model, solution["G"], distribution["pi"])
    save_solution(directory, "selected_solution", model, solution, distribution["pi"], diagnostics)
    solution = load_solution(directory, "selected_solution", model)
    diagnostics = read_diagnostics(directory, "selected_solution")
    checks = []
    try:
        checks = list(selected_policy_checks(model, solution, distribution, Q, diagnostics))
    except CheckFailure as failure:
        write_json(directory/"tests.json", {"status": "failed", "checks": checks, "failure": str(failure)})
        raise
    del model, Q
    grids, summaries = [], []
    for N in NODES:
        with np.load(root/f"results/stage4/g/N_{N}/solution.npz", allow_pickle=False) as saved:
            grids.append(saved["grid"].copy())
        summaries.append(read_diagnostics(root/f"results/stage4/g/N_{N}", "solution")["statistics"])
    fits = {key: accuracy_scaling(grids, [s[key] for s in summaries]) for key in ("mean", "maximum")}
    fit_check = scaling(grids, summaries, fits)
    with np.load(directory/"selected_solution.npz", allow_pickle=False) as saved:
        arrays = {key: saved[key].copy() for key in saved.files}
    accuracy_figures(directory, arrays, grids, summaries, fits)
    range_summary = json.loads((root/"results/stage4/e/summary.json").read_text())
    grid_summary = json.loads((root/"results/stage4/f/summary.json").read_text())
    preserve_abc_tables(root, [range_table(range_summary["trials"]), grid_comparison_table(grid_summary["comparisons"]),
                              node_comparison_tables(g["trials"]), *accuracy_tables(diagnostics["statistics"], fits)])
    elapsed = perf_counter()-started
    summary = {"part_complete": "h", "status": "passed", "selected_settings": settings,
               "solver": solution["metadata"], "distribution": distribution["metadata"],
               "statistics": selected["statistics"], "euler_statistics": diagnostics["statistics"],
               "scaling": fits, "scaling_node_counts": NODES, "scaling_errors": summaries,
               "checks": checks, "scaling_check": fit_check, "analysis_seconds": elapsed,
               "runtime_convention": "analysis wall time including saved-array loading, final checks, table/figure writing, and validation utility reconstruction; selected solve reused from g"}
    write_json(directory/"summary.json", summary)
    write_json(directory/"tests.json", {"status": "passed", "checks": checks, "scaling_check": fit_check})
    print(f"Part (h): {len(checks)} final check records passed; mean slope={fits['mean']['slope']}, "
          f"maximum slope={fits['maximum']['slope']}; analysis={elapsed:.6f}s", flush=True)
