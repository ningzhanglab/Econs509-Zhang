# Prompt 01: Run Question 2(a)–(h)

## Task

Run the experiments specified in `spec.md`, in order, and complete stage 4. Report numerical evidence, counting iterations as specified. I will select the methods and grid settings and write the reasons and report explanations.

## Context

Start in `ps1/`; read the agent file, `spec.md`, `tests.md`, and `log.md`. Confirm stages 2–3 are recorded, applicable tests pass, and this prompt was committed before the run. Report missing definitions or revised inputs requiring renewed verification. Propose a short plan and wait for approval before large changes.

## Constraints

Use the specified parameters, settings, timing rules, and test criteria. Do not modify my files or make choices on my behalf. An applicable test failure stops dependent work. Report capped gradient runs and truncated trial ranges accurately. For long runs, save checkpoints preserving state, counters, and elapsed time. Append a dated log entry at each decision pause and session end.

I handle Git manually in GitHub Desktop. Do not stage, commit, push, or tag. At the stage-4 boundary, provide the changed-file list, measured Summary/Description text, and accurate agent attribution, then stop for my manual commit. Read-only Git history and status checks are allowed.

## Experiments and required pauses

1. **(a) Four solvers.** At `N = 1000`, use a uniform grid on `[0,20]`. Starting from zero, run VFI, Howard, modified Howard, fixed-step gradient descent, and Adam. Report iterations, running time, metric at exit, and convergence status. Save gradient traces and the numerical diagnostics for the theory discussion specified in `spec.md`.

2. **(b) Dense distribution.** Use the converged Howard reference policy. Run the three specified distribution methods with dense `Q`. Save running times, distributions, maximum pairwise differences, and correctness checks.

3. **(c) Sparse distribution.** Convert the same `Q` to CSR and repeat part (b). Save the same evidence and dense–sparse differences. **STOP after (c):** present the comparisons and await my solver, distribution-method, and matrix-representation choices. Do not run (e) on a provisional choice. Record the decisions in the log and `code/selected_settings.json`.

4. **(d) Method choice.** Record my selection from converged, verified methods. From (e) onward, use only the selected methods.

5. **(e) Range.** Run the upper-bound candidates in the specification. For each range, report top-node mass, upper support endpoint, share of grid points in the support, and running time. **STOP after (e):** await and record my range choice.

6. **(f) Nonuniform grid.** At the selected range and fixed `N`, compare the uniform and specified exp-log grids. Save values, policies, distributions, running time, and accuracy diagnostics. **STOP after (f):** await and record my grid choice.

7. **(g) Grid number.** With the selected methods, range, and grid, solve at `N = 100,500,1000,2000,5000`. Save every solution and plot value functions, policy functions, and joint distributions for both shocks. **STOP after (g):** await and record my final `N` choice.

8. **(h) Accuracy.** At my selected `N`, plot the specified Euler residual at every slack state and report unweighted and weighted summaries. Use all five saved solutions for the log-log error-versus-grid-step plot and fitted slopes. Run and report final policy, consumption, and distribution tests and all other applicable checks. Do not impose a predetermined accuracy conclusion.

## Output format

Save outputs according to `spec.md`: JSON summaries, NPZ arrays, complete LaTeX tables and Markdown tables, and PDF/PNG figures. Keep selected settings outside `results/`. Ensure `python code/run_all.py` regenerates all required outputs, including early comparisons, without new choices. Complete the stage-4 reproduction check and write the README with actual versions and measured runtimes.

## Success criteria

All experiments and applicable tests are complete, all four choices are recorded, and outputs reproduce. Provide the stage-4 commit information: measured results, agent attribution, selected settings, output paths, test outcomes, capped runs, rejected ranges, and limitations. **STOP for my manual commit**; record its hash only after confirmation. My independent verification and report follow. The report check requires a separate committed prompt.
