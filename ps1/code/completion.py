"""Final evidence, README generation, bounded regeneration, and clean scratch check."""
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from outputs import write_json
from tests.checks import CheckFailure
from tests.experiments import complete_outputs, read, reproduction


def environment():
    names = ("numpy", "scipy", "matplotlib", "contourpy", "cycler", "fonttools", "kiwisolver",
             "packaging", "pillow", "pyparsing", "python-dateutil", "six")
    return {"python": platform.python_version(), "interpreter": sys.executable,
            "packages": {name: importlib.metadata.version(name) for name in names}}


def write_readme(root, summary, env):
    runtimes = summary["part_runtimes"]
    rows = [f"| {key} | {value:.6f} |" for key, value in runtimes.items()]
    packages = "\n".join(f"{name}=={version}" for name, version in env["packages"].items())
    choices = summary["selected_settings"]
    text = f"""# PS1: discrete-state household problem

This folder contains the student's specification (`spec.md`), registered checks (`tests.md`), independent manual reference (`manual/`), prompts and append-only log, Python implementation (`code/`), and numerical results (`results/`). The task and definitions are in `spec.md`. JSON summaries and NPZ arrays provide the numerical evidence; tables are complete LaTeX tabular environments and Markdown, and figures are available as PDF and PNG. The student is the author of record and handles Git and the report.

## Regenerate

From this folder, using the prescribed existing environment:

```sh
"/Users/ning/Documents/Python/.venv/bin/python" code/run_all.py
```

Equivalently, with that environment active: `python code/run_all.py`.
This command regenerates validation stages 2–3 and parts (a)–(h), including early comparisons, using `code/selected_settings.json`, then verifies a second clean scratch regeneration. No new choices are requested. Computational runs are split into bounded subprocess calls with saved solver/power state, counters, and elapsed time; continuations occur automatically. If interrupted, repeat the command with `--resume`. No packages are installed. Scratch work stays inside this assignment folder and is removed on successful completion.

Recorded choices: {choices['solver']}, {choices['distribution_method']}, {choices['representation']} (CSR), k_max={choices['k_max']}, {choices['grid_kind']}, N={choices['N']}. Prices remain fixed at K0=5; no market-clearing solve is performed. Final evidence: `results/stage4/summary.json`, `tests.json`, `reproduction.json`; part-(h) diagnostics and plots are in `results/stage4/h/`.

## Running environment

Python {env['python']}. Versions read from the running interpreter's package metadata, in pip-freeze format (numerical and plotting packages used):

```text
{packages}
```

## Measured runtimes

| Part or shared construction | Seconds |
| --- | ---: |
{chr(10).join(rows)}

Part (a) is the sum of the five solver times; initial utility construction and optional singular-value diagnostics are separate. Parts (b) and (c) sum their three distribution times, with common dense-Q construction and CSR conversion separate. Part (d) records the student's choices and has no numerical run. Parts (e), (f), and (g) sum utility construction, selected solver, selected Q construction, and selected distribution time over their trials; output/checkpoint/test/plot overhead is excluded. Part (h) reuses the selected part-(g) solution and reports analysis wall time including final checks, tables, figures, and utility reconstruction for validation. The README is regenerated whenever its run results/runtimes change; scratch reproduction times are recorded separately in `reproduction.json`.

## Verification and limitations

Status: {summary['status']}. Applicable numerical checks and the independent OLS check pass; the final report distinguishes expected truncated-range rejections from failures. Fixed-step gradient and Adam reached 20,000 passes and remain unconverged. Range trials k_max=1 and 2 were rejected; accepted-grid parameters/tolerances were never altered to improve a check. At N=100 the single flagged upper-bound choice is retained, with top mass below the registered threshold. The specified conditioning expression and computed condition numbers are both reported in the numerical theory table; their theoretical interpretation is the student's work. Running times and binary bytes may differ across reproductions. The student's independent verification and report are still separate work; the agent stops before the Stage-4 commit.
"""
    (root/"README.md").write_text(text)


def finalize(root, reproduction_record=None):
    root = Path(root)
    choices = read(root/"code/selected_settings.json")
    abc = read(root/"results/stage4/abc/summary.json")
    parts = {part: read(root/f"results/stage4/{part}/summary.json") for part in ("e", "f", "g", "h")}
    checks = []
    for source in ("stage3/tests.json", "stage4/abc/tests.json", "stage4/e/summary.json",
                   "stage4/f/tests.json", "stage4/g/tests.json", "stage4/h/tests.json"):
        checks.extend({**check, "source": source} for check in read(root/f"results/{source}")["checks"])
    if any(not c["passed"] and not c.get("expected_trial_rejection") for c in checks):
        raise CheckFailure("Final evidence includes an unresolved applicable failure")
    env = environment()
    write_json(root/"results/stage4/environment.json", env)
    times = abc["runtimes"]
    runtimes = {"a: five solvers": times["a_solver_seconds"],
                "a: shared utility construction": times["utility_construction_seconds"],
                "a: optional singular-value diagnostics": times["a_optional_singular_seconds"],
                "b: three dense distributions": times["b_distribution_seconds"],
                "bc: common dense-Q construction": times["dense_construction_seconds"],
                "c: three sparse distributions": times["c_distribution_seconds"],
                "c: common CSR conversion": times["csr_conversion_seconds"], "d: recorded choice": 0.,
                **{f"{p}: trial compute sum": parts[p]["compute_seconds"] for p in ("e", "f", "g")},
                "h: analysis": parts["h"]["analysis_seconds"]}
    status = "passed" if reproduction_record is not None else "awaiting_reproduction"
    report = {"status": status, "checks": checks, "check_records": len(checks),
              "passed_records": sum(c["passed"] for c in checks),
              "expected_range_rejections": sum(not c["passed"] for c in checks),
              "independent_scaling_check": parts["h"]["scaling_check"]}
    summary = {"status": status, "parts_complete": list("abcdefgh"), "selected_settings": choices,
               "part_runtimes": runtimes, "final_euler_statistics": parts["h"]["euler_statistics"],
               "accuracy_scaling": parts["h"]["scaling"], "check_records": report["check_records"],
               "passed_records": report["passed_records"], "expected_range_rejections": report["expected_range_rejections"],
               "capped_unconverged": {k: v for k, v in abc["solvers"].items() if not v["converged"]},
               "rejected_ranges": parts["e"]["rejected_ranges"],
               "agent": {"name": "Codex", "model": "GPT-6", "exact_build": "not exposed"},
               "stop": "Await student's manual Stage-4 commit; independent verification and report remain the student's work"}
    write_json(root/"results/stage4/summary.json", summary)
    write_json(root/"results/stage4/tests.json", report)
    write_readme(root, summary, env)
    structure = complete_outputs(root)
    report["test_11"] = {"complete_outputs": structure, "reproduction": reproduction_record}
    summary["test_11"] = "passed" if reproduction_record is not None else "complete outputs passed; clean reproduction pending"
    if reproduction_record is not None:
        write_json(root/"results/stage4/reproduction.json", reproduction_record)
    write_json(root/"results/stage4/tests.json", report)
    write_json(root/"results/stage4/summary.json", summary)
    return summary


def regenerate(root, slice_seconds=50., resume=False):
    """One command, bounded numerical subprocesses; all student decisions pre-recorded."""
    from experiments import fingerprint
    choices = read(root/"code/selected_settings.json")
    if any(v is None for v in choices.values()):
        raise RuntimeError("Complete regeneration requires all recorded student choices")
    state_path = root/"results/.regeneration.json"
    code_hash = fingerprint(root)
    commands = [("2", None), ("3", None), ("4", "abc"), ("4", "e"), ("4", "f"), ("4", "g"), ("4", "h")]
    if resume and state_path.exists():
        state = read(state_path)
        if state["code_sha256"] != code_hash or state["choices"] != choices:
            raise RuntimeError("Code/choices changed since regeneration checkpoint")
    else:
        state = {"code_sha256": code_hash, "choices": choices, "step": 0, "resume_step": False, "slices": []}
    while state["step"] < len(commands):
        stage, part = commands[state["step"]]
        command = [sys.executable, str(root/"code/run_all.py"), "--stage", stage,
                   "--slice-seconds", str(slice_seconds)]
        if part:
            command += ["--part", part]
        if state["resume_step"]:
            command.append("--resume")
        write_json(state_path, state)
        print(f"Regeneration: stage {stage}, part {part or 'validation'}, bounded call", flush=True)
        result = subprocess.run(command, cwd=root)
        state["slices"].append({"stage": stage, "part": part, "exit_code": result.returncode})
        if result.returncode == 75:
            state["resume_step"] = True
        elif result.returncode == 0:
            state["step"] += 1
            state["resume_step"] = False
        else:
            write_json(state_path, state)
            raise CheckFailure(f"Regeneration stopped at stage {stage}, part {part}, exit {result.returncode}")
        write_json(state_path, state)
    return state


def check_reproduction(root, slice_seconds=50.):
    """Never copy results into scratch; keep failed evidence for diagnosis."""
    scratch = Path(tempfile.mkdtemp(prefix=".reproduction-", dir=root))
    for name in ("code", "tests"):
        shutil.copytree(root/name, scratch/name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("spec.md", "tests.md", "AGENTS.md"):
        shutil.copy2(root/name, scratch/name)
    (scratch/"manual").mkdir()
    # The manual data is copied solely for its registered kernel comparison.
    shutil.copy2(root/"manual/kernel_output.npz", scratch/"manual/kernel_output.npz")
    if (scratch/"results").exists():
        raise RuntimeError("Scratch unexpectedly contains generated results")
    print("Clean reproduction: scratch starts without results; regenerate all parts using recorded choices.", flush=True)
    command = [sys.executable, str(scratch/"code/run_all.py"), "--numerical-only",
               "--slice-seconds", str(slice_seconds)]
    result = subprocess.run(command, cwd=scratch)
    if result.returncode != 0:
        raise CheckFailure(f"Clean reproduction failed, exit {result.returncode}; retained {scratch.name}")
    record = reproduction(root, scratch)
    record["scratch_part_runtimes"] = read(scratch/"results/stage4/summary.json")["part_runtimes"]
    state = read(scratch/"results/.regeneration.json")
    record["bounded_calls"] = state["slices"]
    finalize(root, record)
    shutil.rmtree(scratch)
    print(f"Test 11 passed: {record['arrays_checked']} arrays, {record['exact_policy_arrays']} exact policies, "
          f"{record['json_numbers_checked']} JSON numbers; max tolerance ratio={record['maximum_tolerance_ratio']:.12g}", flush=True)
    return record
