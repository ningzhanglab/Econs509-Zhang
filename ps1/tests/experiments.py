"""Independent complete-output, scaling, and clean-reproduction checks (test 11)."""
import json
from pathlib import Path

import numpy as np

from tests.checks import CheckFailure, outcome

NODES = [100, 500, 1000, 2000, 5000]
RANGES = [1, 2, 5, 10, 20, 40]
METHODS = ["vfi", "howard", "modified_howard", "gradient", "adam"]
TIMING_KEYS = {"seconds", "timings", "runtimes", "compute_seconds", "analysis_seconds",
               "utility_seconds", "resume_utility_construction_seconds", "runtime_convention",
               "transition_construction_seconds", "transition_conversion_seconds",
               "dense_construction_seconds", "csr_conversion_seconds", "code_sha256"}


def read(path):
    return json.loads(Path(path).read_text())


def scaling(grids, summaries, fits):
    """Check OLS independently with centered covariance, not the production lstsq."""
    h = np.array([max(np.diff(grid)) for grid in grids])
    measurements = {}
    for key in ("mean", "maximum"):
        errors = np.array([np.nan if s[key] is None else s[key] for s in summaries])
        valid = np.isfinite(h) & (h > 0) & np.isfinite(errors) & (errors > 0)
        fit = fits[key]
        if len(np.unique(h[valid])) < 2:
            if fit["slope"] is not None or fit["intercept"] is not None or not fit["reason"]:
                raise CheckFailure("Unavailable scaling fit not reported correctly")
            measurements[key] = {"unavailable": True}
            continue
        x, y = np.log(h[valid]), np.log(errors[valid])
        slope = float(np.dot(x-x.mean(), y-y.mean()) / np.dot(x-x.mean(), x-x.mean()))
        intercept = float(y.mean() - slope*x.mean())
        differences = {"slope": abs(slope-fit["slope"]), "intercept": abs(intercept-fit["intercept"])}
        if (not np.array_equal(np.flatnonzero(valid), fit["used_indices"])
                or not np.array_equal(h, fit["h"])
                or any(differences[k] > 1e-12*max(1, abs(v)) for k, v in
                       (("slope", slope), ("intercept", intercept)))):
            raise CheckFailure(f"Independent scaling-fit mismatch: {key}, {differences}")
        measurements[key] = {"slope": slope, "intercept": intercept, "differences": differences}
    return {"name": "independent_scaling_fit", "passed": True, "measurements": measurements}


def expected_artifacts():
    paths = {"tables.md"}
    paths.update(f"{name}.tex" for name in (
        "validation_solvers", "validation_distributions", "part_a_solvers", "parts_bc_distributions",
        "parts_bc_agreement", "part_a_theory_diagnostics", "part_e_ranges", "part_f_grids", "part_g_nodes",
        "part_h_accuracy", "part_h_scaling"))
    for name in ("vfi", "howard", "modified_howard"):
        paths.update(f"stage2/{name}.{ext}" for ext in ("json", "npz"))
    paths.add("stage2/summary.json")
    paths.add("stage3/tests.json")
    for name in ("kernel_vfi", "howard_reference"):
        paths.update(f"stage3/{name}.{ext}" for ext in ("json", "npz"))
    for part in ("stage3", "stage4/abc"):
        paths.update(f"{part}/transition_{rep}.npz" for rep in ("dense", "sparse"))
        for rep in ("dense", "sparse"):
            for method in ("power", "eigen", "direct"):
                paths.update(f"{part}/{rep}_{method}.{ext}" for ext in ("json", "npz"))
    for name in METHODS:
        paths.update(f"stage4/abc/{name}.{ext}" for ext in ("json", "npz"))
    paths.update(f"stage4/abc/{name}.json" for name in ("manifest", "summary", "tests", "theory", "transition"))
    for part in ("e", "f", "g"):
        paths.update(f"stage4/{part}/{name}.json" for name in ("manifest", "summary"))
    paths.update(f"stage4/{part}/tests.json" for part in ("f", "g", "h"))
    cases = [f"e/kmax_{n}" for n in RANGES] + [f"f/{kind}" for kind in ("uniform", "exp_log")]
    cases += [f"g/N_{n}" for n in NODES]
    for case in cases:
        paths.update(f"stage4/{case}/{name}.{ext}" for name in ("solution", "distribution", "transition")
                     for ext in ("json", "npz"))
        paths.update(f"stage4/{case}/{name}.json" for name in ("utility", "summary", "tests"))
    paths.update(f"stage4/h/{name}.{ext}" for name in ("selected_solution",) for ext in ("json", "npz"))
    paths.add("stage4/h/summary.json")
    figures = {"abc": ["part_a_gradient_traces"],
               "f": ["part_f_values_policies_masses", "part_f_euler_comparison"],
               "g": ["part_g_values", "part_g_policies", "part_g_joint_masses"],
               "h": ["part_h_euler_residuals", "part_h_accuracy_scaling"]}
    for part, names in figures.items():
        paths.update(f"stage4/{part}/{name}.{ext}" for name in names for ext in ("pdf", "png"))
    paths.update(f"stage4/{name}.json" for name in ("environment", "summary", "tests"))
    return sorted(paths)


def complete_outputs(root):
    root = Path(root)
    results = root / "results"
    missing = [p for p in expected_artifacts() if not (results/p).is_file() or (results/p).stat().st_size == 0]
    if missing:
        raise CheckFailure(f"Missing/empty required outputs: {missing}")
    choices = read(root/"code/selected_settings.json")
    if (choices["N"] not in NODES or choices["k_max"] not in RANGES
            or choices["grid_kind"] not in ("uniform", "exp_log") or any(v is None for v in choices.values())):
        raise CheckFailure("Missing/invalid recorded choices")
    g = read(results/"stage4/g/summary.json")
    if g["node_counts"] != NODES or [t["settings"]["N"] for t in g["trials"]] != NODES:
        raise CheckFailure("Part-(g) node counts differ from specification")
    parameters = {"beta": .96, "sigma": 1.5, "labor": 1., "k_min": 0., "z": 1., "alpha": .36,
                  "delta": .1, "K0": 5., "efficiency": [.8, 1.2], "P": [[.5, .5], [.5, .5]],
                  "shock_stationary": [.5, .5], "seed": 0, "dtype": "float64", "stack_order": "F"}
    solutions = list(results.glob("stage2/*.json")) + list(results.glob("stage3/*.json"))
    solutions += list(results.glob("stage4/abc/*.json")) + list(results.glob("stage4/[efg]/*/solution.json"))
    solutions += [results/"stage4/h/selected_solution.json"]
    checked_solutions = 0
    for path in solutions:
        meta = read(path)
        if "initial_value" not in meta:
            continue
        settings = meta["settings"]
        if any(settings[k] != v for k, v in parameters.items()):
            raise CheckFailure(f"Specified parameter mismatch: {path}")
        if settings["w"] != .64*5**.36 or settings["r"] != .36*5**(-.64)-.1 or settings["L"] != 1.:
            raise CheckFailure(f"Price mismatch: {path}")
        N, upper, kind = settings["N"], settings["k_max"], settings["grid_kind"]
        fraction = np.arange(N, dtype=np.float64)/(N-1)
        grid = upper*fraction if kind == "uniform" else np.exp(fraction*np.log(upper+1))-1
        grid[0], grid[-1] = 0., upper
        relative = path.relative_to(results).as_posix()
        if relative.startswith(("stage2/", "stage3/")) and (N, upper, kind) != (100, 20., "uniform"):
            raise CheckFailure(f"Validation grid mismatch: {path}")
        if relative.startswith("stage4/abc/") and (N, upper, kind) != (1000, 20., "uniform"):
            raise CheckFailure(f"Baseline grid mismatch: {path}")
        if relative.startswith("stage4/e/") and (N != 1000 or kind != "uniform" or upper not in RANGES):
            raise CheckFailure(f"Range-trial grid mismatch: {path}")
        if relative.startswith("stage4/f/") and (N != 1000 or upper != choices["k_max"]):
            raise CheckFailure(f"Grid-comparison setting mismatch: {path}")
        if relative.startswith(("stage4/g/", "stage4/h/")) and (upper != choices["k_max"] or kind != choices["grid_kind"]):
            raise CheckFailure(f"Selected setting mismatch: {path}")
        if relative.startswith("stage4/h/") and N != choices["N"]:
            raise CheckFailure("Final N differs from recorded choice")
        expected_tol = 1e-10 if path.stem == "kernel_vfi" else 1e-8
        caps = {"vfi": 10000, "howard": 1000, "modified_howard": 10000, "gradient": 20000, "adam": 20000}
        if (meta["tolerance"] != expected_tol or meta["outer_pass_cap"] != caps[meta["method"]]
                or meta["initial_value"] != "zero" or not np.isfinite(meta["seconds"]) or meta["seconds"] < 0):
            raise CheckFailure(f"Solver setting/timing mismatch: {path}")
        if relative.startswith("stage4/") and not relative.startswith("stage4/abc/") and meta["method"] != choices["solver"]:
            raise CheckFailure(f"Unselected solver used: {path}")
        with np.load(path.with_suffix(".npz"), allow_pickle=False) as arrays:
            if not np.array_equal(arrays["grid"], grid) or arrays["V"].shape != (N, 2) or arrays["G"].shape != (N, 2):
                raise CheckFailure(f"Saved-grid/value/policy shape mismatch: {path}")
            if arrays["V"].dtype != np.float64 or not np.issubdtype(arrays["G"].dtype, np.integer):
                raise CheckFailure(f"Saved dtype mismatch: {path}")
            if relative.startswith("stage4/") and meta["converged"]:
                for key in ("pi", "E", "cEE", "slack", "upper", "next_consumption"):
                    if key not in arrays:
                        raise CheckFailure(f"Missing saved diagnostics {key}: {path}")
        checked_solutions += 1
    e = read(results/"stage4/e/summary.json")
    if e["ranges"] != RANGES or choices["k_max"] not in e["eligible_ranges"]:
        raise CheckFailure("Range trials/selected range invalid")
    for part in ("abc", "e", "f", "g", "h"):
        for path in (results/f"stage4/{part}").rglob("*distribution.json"):
            meta = read(path)
            if part != "abc" and meta["method"] != choices["distribution_method"]:
                raise CheckFailure(f"Unselected distribution method: {path}")
        for path in (results/f"stage4/{part}").rglob("transition.json"):
            if part in ("e", "f", "g") and read(path)["representation"] != choices["representation"]:
                raise CheckFailure(f"Unselected representation: {path}")
    markdown = (results/"tables.md").read_text()
    for path in results.glob("*.tex"):
        table = path.read_text()
        if not table.startswith(r"\begin{tabular}{") or not table.rstrip().endswith(r"\end{tabular}"):
            raise CheckFailure(f"Incomplete tabular: {path}")
        if len(table.splitlines()) < 5:
            raise CheckFailure(f"Empty table: {path}")
    if markdown.count("\n| ---") != len(list(results.glob("*.tex"))):
        raise CheckFailure("Markdown and LaTeX table counts differ")
    for path in results.rglob("*.pdf"):
        if path.read_bytes()[:5] != b"%PDF-" or not path.with_suffix(".png").is_file():
            raise CheckFailure(f"Invalid/missing paired figure: {path}")
    for path in results.rglob("*.png"):
        if path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n" or not path.with_suffix(".pdf").is_file():
            raise CheckFailure(f"Invalid/missing paired figure: {path}")
    env = read(results/"stage4/environment.json")
    summary = read(results/"stage4/summary.json")
    report = read(results/"stage4/tests.json")
    if summary["selected_settings"] != choices or report["status"] not in ("passed", "awaiting_reproduction"):
        raise CheckFailure("Final summary/settings/check status inconsistent")
    if any(not c["passed"] and c.get("range_status") != "rejected_truncated" for c in report["checks"]):
        raise CheckFailure("Unresolved applicable test failure")
    readme = (root/"README.md").read_text()
    if env["python"] not in readme or "python code/run_all.py" not in readme:
        raise CheckFailure("README lacks interpreter version or regeneration command")
    if any(f"{name}=={version}" not in readme for name, version in env["packages"].items()):
        raise CheckFailure("README package versions differ from running environment record")
    for key, value in summary["part_runtimes"].items():
        if not np.isfinite(value) or value < 0 or f"{value:.6f}" not in readme:
            raise CheckFailure(f"README missing measured runtime: {key}")
    return outcome(11, True, scope="complete outputs (clean reproduction still separate)",
                   required_artifact_count=len(expected_artifacts()), solution_count=checked_solutions,
                   table_count=len(list(results.glob("*.tex"))), figure_pairs=len(list(results.rglob("*.pdf"))),
                   node_counts=NODES, selected_settings=choices)


def reproduction(reference, scratch):
    """Elementwise registered tolerance, exact discrete policies; ignore measured times."""
    ref, new = Path(reference)/"results", Path(scratch)/"results"
    required = expected_artifacts()
    max_error = 0.
    max_ratio = 0.
    location = None
    arrays_checked = json_numbers = policies = 0

    def numeric(a, b, name, exact=False):
        nonlocal max_error, max_ratio, location
        a, b = np.asarray(a), np.asarray(b)
        if a.shape != b.shape:
            raise CheckFailure(f"Reproduction shape mismatch: {name}")
        if exact or a.dtype.kind not in "fciu":
            if not np.array_equal(a, b):
                raise CheckFailure(f"Reproduction discrete/non-numeric mismatch: {name}")
            return
        if not np.isfinite(a).all() or not np.isfinite(b).all():
            raise CheckFailure(f"Nonfinite reproduced numeric output: {name}")
        if a.size == 0:
            return
        diff = np.abs(b-a)
        ratio = diff/(1e-8*np.maximum(1, np.abs(a)))
        error, scaled = float(diff.max()), float(ratio.max())
        max_error = max(max_error, error)
        if scaled > max_ratio:
            max_ratio, location = scaled, name
        if scaled > 1:
            raise CheckFailure(f"Reproduction numeric mismatch: {name}; error={error}, tolerance ratio={scaled}")

    def compare_json(a, b, name):
        nonlocal json_numbers
        if isinstance(a, dict):
            if not isinstance(b, dict):
                raise CheckFailure(f"Reproduction JSON type mismatch: {name}")
            for key in a:
                if key in TIMING_KEYS:
                    continue
                if key not in b:
                    raise CheckFailure(f"Reproduction missing JSON key: {name}/{key}")
                compare_json(a[key], b[key], f"{name}/{key}")
        elif isinstance(a, list):
            if not isinstance(b, list) or len(a) != len(b):
                raise CheckFailure(f"Reproduction list mismatch: {name}")
            for i, (av, bv) in enumerate(zip(a, b)):
                compare_json(av, bv, f"{name}/{i}")
        elif isinstance(a, (int, float)) and not isinstance(a, bool):
            numeric(a, b, name)
            json_numbers += 1
        elif a != b:
            raise CheckFailure(f"Reproduction JSON mismatch: {name}: {a!r} != {b!r}")

    for relative in required:
        a, b = ref/relative, new/relative
        if relative.endswith(".npz"):
            with np.load(a, allow_pickle=False) as aa, np.load(b, allow_pickle=False) as bb:
                if set(aa.files) != set(bb.files):
                    raise CheckFailure(f"Reproduction NPZ fields differ: {relative}")
                for key in aa.files:
                    numeric(aa[key], bb[key], f"{relative}/{key}", exact=key in ("G", "slack", "upper", "indices", "indptr", "shape"))
                    arrays_checked += 1
                    policies += key == "G"
        elif relative.endswith(".json"):
            # Final verification/provenance is freshly computed by each run. Compare the
            # underlying per-part numerical records instead of copying reference evidence.
            if relative not in ("stage4/tests.json", "stage4/summary.json"):
                compare_json(read(a), read(b), relative)
    independent = complete_outputs(scratch)
    child = read(new/"stage4/tests.json")
    return outcome(11, True, scope="clean reproduction", scratch_started_without_results=True,
                   arrays_checked=arrays_checked, json_numbers_checked=json_numbers,
                   exact_policy_arrays=policies, policy_mismatches=0, maximum_absolute_difference=max_error,
                   maximum_tolerance_ratio=max_ratio, largest_scaled_difference_location=location,
                   tolerance="elementwise 1e-8*max(1,abs(reference)); discrete policies exact",
                   scratch_check_records=len(child["checks"]), scratch_passed=sum(c["passed"] for c in child["checks"]),
                   scratch_expected_range_rejections=sum(not c["passed"] for c in child["checks"]),
                   scratch_complete_outputs=independent)
