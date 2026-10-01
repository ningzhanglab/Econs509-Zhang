# PS1: discrete-state household problem

This folder contains the student's specification (`spec.md`), registered checks (`tests.md`), independent manual reference (`manual/`), prompts and append-only log, Python implementation (`code/`), and numerical results (`results/`). The task and definitions are in `spec.md`. JSON summaries and NPZ arrays provide the numerical evidence; tables are complete LaTeX tabular environments and Markdown, and figures are available as PDF and PNG. The student is the author of record and handles Git and the report.

## Regenerate

From this folder, using the prescribed existing environment:

```sh
"/Users/ning/Documents/Python/.venv/bin/python" code/run_all.py
```

Equivalently, with that environment active: `python code/run_all.py`.
This command regenerates validation stages 2–3 and parts (a)–(h), including early comparisons, using `code/selected_settings.json`, then verifies a second clean scratch regeneration. No new choices are requested. Computational runs are split into bounded subprocess calls with saved solver/power state, counters, and elapsed time; continuations occur automatically. If interrupted, repeat the command with `--resume`. No packages are installed. Scratch work stays inside this assignment folder and is removed on successful completion.

Recorded choices: modified_howard, power, sparse (CSR), k_max=5, exp_log, N=5000. Prices remain fixed at K0=5; no market-clearing solve is performed. Final evidence: `results/stage4/summary.json`, `tests.json`, `reproduction.json`; part-(h) diagnostics and plots are in `results/stage4/h/`.

## Running environment

Python 3.13.14. Versions read from the running interpreter's package metadata, in pip-freeze format (numerical and plotting packages used):

```text
numpy==2.5.2
scipy==1.18.0
matplotlib==3.11.1
contourpy==1.3.3
cycler==0.12.1
fonttools==4.63.0
kiwisolver==1.5.0
packaging==26.3
pillow==12.3.0
pyparsing==3.3.2
python-dateutil==2.9.0.post0
six==1.17.0
```

## Measured runtimes

| Part or shared construction | Seconds |
| --- | ---: |
| a: five solvers | 104.322666 |
| a: shared utility construction | 0.020563 |
| a: optional singular-value diagnostics | 0.021835 |
| b: three dense distributions | 0.349666 |
| bc: common dense-Q construction | 0.002323 |
| c: three sparse distributions | 0.014462 |
| c: common CSR conversion | 0.012338 |
| d: recorded choice | 0.000000 |
| e: trial compute sum | 0.461246 |
| f: trial compute sum | 0.158909 |
| g: trial compute sum | 2.390224 |
| h: analysis | 1.891807 |

Part (a) is the sum of the five solver times; initial utility construction and optional singular-value diagnostics are separate. Parts (b) and (c) sum their three distribution times, with common dense-Q construction and CSR conversion separate. Part (d) records the student's choices and has no numerical run. Parts (e), (f), and (g) sum utility construction, selected solver, selected Q construction, and selected distribution time over their trials; output/checkpoint/test/plot overhead is excluded. Part (h) reuses the selected part-(g) solution and reports analysis wall time including final checks, tables, figures, and utility reconstruction for validation. The README is regenerated whenever its run results/runtimes change; scratch reproduction times are recorded separately in `reproduction.json`.

## Verification and limitations

Status: passed. Applicable numerical checks and the independent OLS check pass; the final report distinguishes expected truncated-range rejections from failures. Fixed-step gradient and Adam reached 20,000 passes and remain unconverged. Range trials k_max=1 and 2 were rejected; accepted-grid parameters/tolerances were never altered to improve a check. At N=100 the single flagged upper-bound choice is retained, with top mass below the registered threshold. The specified conditioning expression and computed condition numbers are both reported in the numerical theory table; their theoretical interpretation is the student's work. Running times and binary bytes may differ across reproductions. The student's independent verification and report are still separate work; the agent stops before the Stage-4 commit.
