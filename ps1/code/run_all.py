"""Stage-aware regeneration driver with explicit experiment decision gates.

python code/run_all.py --stage 2
python code/run_all.py --stage 3  # only after the student's stage-2 commit confirmation
python code/run_all.py --stage 4  # parts (a)–(c), then stop for method choices
python code/run_all.py --stage 4 --part e  # selected methods, then stop for range choice
python code/run_all.py --stage 4 --part f  # selected range, then stop for grid choice
python code/run_all.py --stage 4 --part g  # selected grid, then stop for final N choice
python code/run_all.py --stage 4 --part h  # chosen N: accuracy, final checks, README
python code/run_all.py  # all choices recorded: complete regeneration and scratch check

An unfinished bounded run exits with code 75. Repeat with --resume to continue.
"""
import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np
from scipy import sparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model import Model
from solvers import Solver
from distributions import invariant
from diagnostics import distribution_statistics, euler
from outputs import save_solution, write_json, write_tables
from tests.checks import CheckFailure, experiment_checks_pending, run_validation


class SliceComplete(Exception):
    pass


def load_solution(directory, name, model):
    metadata = json.loads((directory / f"{name}.json").read_text())
    with np.load(directory / f"{name}.npz", allow_pickle=False) as saved:
        result = {key: saved[key].copy() for key in ("V", "G", "consumption", "trace")}
        if not np.array_equal(saved["grid"], model.grid):
            raise RuntimeError("Saved grid differs from validation grid")
    expected = model.settings()
    for key, value in expected.items():
        if key != "utility_seconds" and metadata["settings"][key] != value:
            raise RuntimeError(f"Saved model setting mismatch: {key}")
    result["metadata"] = {key: value for key, value in metadata.items() if key != "settings"}
    return result


def solve_one(model, method, name, tolerance, directory, deadline, resume):
    checkpoints = directory / "checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    checkpoint = checkpoints / f"{name}.npz"
    if resume and (directory / f"{name}.json").exists():
        result = load_solution(directory, name, model)
        if result["metadata"]["method"] != method or result["metadata"]["tolerance"] != tolerance:
            raise RuntimeError("Saved solver settings mismatch")
        return result
    solver = Solver.load_checkpoint(model, checkpoint) if resume and checkpoint.exists() else Solver(model, method, tolerance)
    if solver.method != method or solver.tolerance != tolerance:
        raise RuntimeError("Checkpoint method/tolerance mismatch")
    if deadline - perf_counter() <= 1:
        solver.save_checkpoint(checkpoint)
        raise SliceComplete(f"Saved {name} at pass {solver.outer_passes}")
    if not solver.advance(max(0.1, deadline - perf_counter() - 1)):
        solver.save_checkpoint(checkpoint)
        raise SliceComplete(f"Saved {name} at pass {solver.outer_passes}")
    result = solver.result()
    save_solution(directory, name, model, result)
    if checkpoint.exists():
        checkpoint.unlink()
    meta = result["metadata"]
    print(f"{name}: {meta['outer_passes']} passes, {meta['updates']} updates, "
          f"d={meta['exit_metric']:.12g}, {meta['seconds']:.6f}s, {meta['status']}", flush=True)
    if method in ("vfi", "howard", "modified_howard") and not meta["converged"]:
        raise CheckFailure(f"Required {method} solve failed to converge")
    return result


def solver_table(results):
    return ("validation_solvers", "Stage-2 validation solvers (N=100, uniform [0,20])",
            ["Method", "Passes", "Updates", "Inner steps", "Seconds", "Exit metric", "Status"],
            [[name, s["metadata"]["outer_passes"], s["metadata"]["updates"],
              s["metadata"]["inner_steps"], f"{s['metadata']['seconds']:.6f}",
              f"{s['metadata']['exit_metric']:.12g}", s["metadata"]["status"]]
             for name, s in results.items()])


def stage2(model, deadline, resume):
    directory = ROOT / "results" / "stage2"
    results = {}
    for method in ("vfi", "howard", "modified_howard"):
        results[method] = solve_one(model, method, method, 1e-8, directory, deadline, resume)
    write_tables(ROOT / "results", [solver_table(results)])
    report = {"stage": 2, "settings": model.settings(),
              "solvers": {name: result["metadata"] for name, result in results.items()},
              "tests": [{"test_id": test, "status": "pending", "reason": "Awaiting stage-2 manual commit confirmation"}
                        for test in range(1, 11)] + [experiment_checks_pending()],
              "stage4": "pending", "stop": "Await student's manual stage-2 commit confirmation"}
    write_json(directory / "summary.json", report)
    print("Stage 2 complete. Stop for the student's manual commit.", flush=True)


def stage3(model, deadline, resume):
    directory = ROOT / "results" / "stage3"
    directory.mkdir(parents=True, exist_ok=True)
    solutions = {method: load_solution(ROOT / "results" / "stage2", method, model)
                 for method in ("vfi", "howard", "modified_howard")}
    solutions["kernel_vfi"] = solve_one(model, "vfi", "kernel_vfi", 1e-10, directory, deadline, resume)
    if not solutions["howard"]["metadata"]["converged"]:
        raise CheckFailure("Howard reference has not converged")
    started = perf_counter()
    dense = model.transition(solutions["howard"]["G"], "dense")
    construction_seconds = perf_counter() - started
    started = perf_counter()
    csr = sparse.csr_matrix(dense)
    conversion_seconds = perf_counter() - started
    np.savez_compressed(directory / "transition_dense.npz", Q=dense)
    sparse.save_npz(directory / "transition_sparse.npz", csr)
    distributions = {}
    for representation, Q in (("dense", dense), ("sparse", csr)):
        for method in ("power", "eigen", "direct"):
            name = f"{representation}_{method}"
            checkpoint = directory / "checkpoints" / f"{name}.npz"
            if deadline - perf_counter() <= 1:
                raise SliceComplete(f"Distribution {name} not started; resume required")
            if resume and (directory / f"{name}.json").exists():
                with np.load(directory / f"{name}.npz", allow_pickle=False) as saved:
                    pi = saved["pi"].copy()
                result = {"pi": pi, "metadata": json.loads((directory / f"{name}.json").read_text())}
            else:
                if not resume and checkpoint.exists():
                    checkpoint.unlink()
                result = invariant(Q, method, max(0.1, deadline - perf_counter() - 1), checkpoint)
                if result is None:
                    raise SliceComplete(f"Power checkpoint saved for {name}")
                np.savez_compressed(directory / f"{name}.npz", pi=result["pi"])
                write_json(directory / f"{name}.json", result["metadata"])
                if checkpoint.exists():
                    checkpoint.unlink()
            distributions[name] = result
    pi = distributions["sparse_power"]["pi"]
    diagnostics = euler(model, solutions["howard"]["G"], pi)
    save_solution(directory, "howard_reference", model, solutions["howard"], pi, diagnostics)
    # Check persisted arrays and metadata rather than only the objects used to write them.
    solutions["kernel_vfi"] = load_solution(directory, "kernel_vfi", model)
    with np.load(directory / "howard_reference.npz", allow_pickle=False) as saved:
        diagnostics = {key: saved[key].copy() for key in
                       ("consumption", "next_consumption", "cEE", "E", "slack", "upper")}
    saved_metadata = json.loads((directory / "howard_reference.json").read_text())
    diagnostics["statistics"] = saved_metadata["euler_statistics"]
    for name in distributions:
        with np.load(directory / f"{name}.npz", allow_pickle=False) as saved:
            distributions[name]["pi"] = saved["pi"].copy()
        distributions[name]["metadata"] = json.loads((directory / f"{name}.json").read_text())
    checks = []
    try:
        for check in run_validation(model, solutions, distributions, dense, csr, diagnostics,
                                    ROOT / "manual" / "kernel_output.npz"):
            checks.append(check)
    except CheckFailure as failure:
        write_json(directory / "tests.json", {"status": "failed", "completed": checks, "failure": str(failure)})
        raise
    report = {"stage": 3, "status": "passed", "settings": model.settings(), "checks": checks,
              "transition_construction_seconds": construction_seconds,
              "transition_conversion_seconds": conversion_seconds,
              "distribution_statistics": distribution_statistics(model.grid, pi),
              "euler_statistics": diagnostics["statistics"], "stage4": "pending",
              "pending_checks": [experiment_checks_pending()],
              "stop": "Await student's manual stage-3 commit confirmation"}
    write_json(directory / "tests.json", report)
    distribution_table = ("validation_distributions", "Stage-3 invariant distributions",
                          ["Method", "Seconds", "Raw minimum", "Correction mass", "Stationarity"],
                          [[name, f"{r['metadata']['seconds']:.6f}", f"{r['metadata']['raw_minimum']:.12g}",
                            f"{r['metadata']['correction_mass']:.12g}", f"{r['metadata']['stationarity_residual']:.12g}"]
                           for name, r in distributions.items()])
    write_tables(ROOT / "results", [solver_table({k: v for k, v in solutions.items() if k != "kernel_vfi"}),
                                      distribution_table])
    print(json.dumps(report, indent=2), flush=True)
    print("Stage 3 complete. Stop for the student's manual commit.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, choices=(2, 3, 4), default=4)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--part", choices=("abc", "e", "f", "g", "h", "all"),
                        help="Explicit stage-4 part; otherwise follow the recorded choices")
    parser.add_argument("--check-reproduction", action="store_true",
                        help="Verify existing complete outputs against clean scratch regeneration")
    parser.add_argument("--numerical-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--slice-seconds", type=float, default=50.0,
                        help="Checkpoint wall-time budget per call, between 1 and 110 seconds")
    args = parser.parse_args()
    np.random.seed(0)
    if not 1 <= args.slice_seconds <= 110:
        parser.error("--slice-seconds must be between 1 and 110")
    deadline = perf_counter() + args.slice_seconds
    model = Model(100, 20.0, "uniform") if args.stage < 4 else None
    try:
        if args.check_reproduction:
            from completion import check_reproduction
            check_reproduction(ROOT, args.slice_seconds)
        elif args.stage == 2:
            stage2(model, deadline, args.resume)
        elif args.stage == 3:
            stage3(model, deadline, args.resume)
        else:
            from experiments import run_abc, run_e, run_f, run_g, run_h
            settings = json.loads((ROOT / "code" / "selected_settings.json").read_text())
            part = args.part or ("all" if settings["N"] is not None else
                                 "g" if settings["grid_kind"] is not None else
                                 "f" if settings["k_max"] is not None else
                                 "e" if settings["solver"] is not None else "abc")
            if part == "all":
                from completion import check_reproduction, regenerate
                regenerate(ROOT, args.slice_seconds, args.resume)
                if not args.numerical_only:
                    check_reproduction(ROOT, args.slice_seconds)
                print("Regeneration complete. Stop before the student's manual Stage-4 commit.", flush=True)
            elif part == "abc":
                run_abc(ROOT, deadline, args.resume, solve_one, load_solution, SliceComplete)
            elif part == "e":
                run_e(ROOT, deadline, args.resume, solve_one, load_solution, SliceComplete, settings)
            elif part == "f":
                run_f(ROOT, deadline, args.resume, solve_one, load_solution, SliceComplete, settings)
            elif part == "g":
                run_g(ROOT, deadline, args.resume, solve_one, load_solution, SliceComplete, settings)
            else:
                from completion import finalize
                run_h(ROOT, deadline, args.resume, load_solution, SliceComplete, settings)
                summary = finalize(ROOT)
                print(f"Final checks: {summary['passed_records']} passed, "
                      f"{summary['expected_range_rejections']} expected range rejections; clean reproduction pending.", flush=True)
    except SliceComplete as paused:
        print(f"{paused}. Repeat the same command with --resume.", flush=True)
        return 75
    except (CheckFailure, RuntimeError, ValueError, np.linalg.LinAlgError) as failed:
        write_json(ROOT / "results" / f"stage{args.stage}" / "failure.json",
                   {"status": "failed", "message": str(failed)})
        print(f"STOP: {failed}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
