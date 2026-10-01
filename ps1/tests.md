# PS1: Pre-registered tests

Use the definitions and settings in `spec.md`. At stage 3, run tests 1–10 on the specified validation inputs; tests 2–8 use the converged Howard validation policy/distribution unless stated otherwise. At stage 4, repeat applicable tests 2–10 on converged baseline and selected-method solutions; test 9 also checks capped gradient runs. Test 11 and full experiment checks remain pending until their outputs exist.

Tests 7–8 compare methods and matrix representations only during validation and parts (b)–(c). From (e) onward, check only the selected method's transition matrix and distribution. Report test IDs, measured values, and pass/fail status. A genuine applicable failure stops dependent work. Changes to criteria require my revision and a dated reason in the log.

1. **Kernel test.** Run plain VFI from zero on the manual kernel's `N = 100` uniform `[0,20]` grid at relative Bellman tolerance `1e-10`. Against `manual/kernel_output.npz`, require `max(abs(V_agent-V_manual)) <= 1e-8` and identical zero-based policy indices. Report the value difference, mismatch count, and both iteration counts. Do not overwrite the reference.

2. **Monotone policy.** The savings policy must be nondecreasing in assets for each shock: require `G[n+1,s] >= G[n,s]` at every adjacent pair. Report all violations without sorting or altering the policy.

3. **Positive consumption and feasibility.** Require integer policy indices in `[0,N-1]` and finite, strictly positive consumption at every state. Recompute consumption from the budget and require agreement with saved values within `1e-12`. Report minimum consumption and its state; do not clip consumption.

4. **Distribution sums to one.** Require finite entries and `abs(sum(pi)-1) <= 1e-10`. Report the sum and its deviation from one.

5. **Nonnegative distribution.** Require the normalized raw distribution's minimum to be at least `-1e-14`. Apply only the roundoff corrections specified in `spec.md`. The saved distribution must be nonnegative and pass normalization and stationarity after correction. Report the raw minimum and correction mass.

6. **No top-node mass.** On accepted grids, require `sum_s pi[N-1,s] <= 1e-12`. Report top-node mass for every range trial. Excessive mass rejects the trial; it does not authorize a silent grid change.

7. **Correct transition matrix.** Require shape `(2N,2N)`, nonnegative entries, and maximum row-sum error at most `1e-12`. Each row must send assets to its policy index with next-shock probabilities given by the corresponding row of `P`. Dense and sparse entries must agree within `1e-12`.

8. **Stationarity and distribution-method agreement.** Every computed distribution must pass tests 4–5, satisfy `max(abs(Q.T @ pi-pi)) <= 1e-10`, and have shock marginals within `1e-10` of `(0.5,0.5)`. During validation and parts (b)–(c), require the maximum pairwise difference across the three dense and three sparse solutions for the same policy to be at most `1e-8`. Report the pair with the largest difference.

9. **Bellman operator and stopping rule.** On the validation grid, use `V[n,s] = (n/(N-1))^2 + 0.2s` with zero-based indices. Compare one vectorized Bellman step with an explicit exhaustive search: require value error at most `1e-12*max(1,max(abs(T(V))))` and identical maximizing indices under the specified tie rule. VFI, Howard, and modified Howard must converge within their specified caps; recorded exit metrics must agree with a fresh evaluation within `1e-12`. At stage 4, check the same metric and settings for all five baseline runs. A gradient cap exit is allowed, but a run is converged only if `d <= 1e-8`.

10. **Euler calculation.** Using the validation policy, independently recompute current and next-period consumption and the residual at zero-based states `(0,0)`, `(50,1)`, and `(99,0)`. Require residual agreement within `1e-12*max(1,abs(E_scalar))`. Recompute slack-state masks and all reported summary statistics from saved arrays using the same tolerance scale. Empty sets and zero weight denominators must be reported as unavailable. Discrete residuals need not be zero or decrease at every `N`.

11. **Complete experiments and reproduction (stage 4).** Check specified parameters/grids, all five required part-(g) node counts, tables and figures, JSON/NPZ outputs, final test summary, recorded choices, and README versions/runtimes. In a scratch copy without generated results, `python code/run_all.py` must recreate the outputs without new choices. Require identical discrete policies and elementwise agreement of numerical arrays and statistics within `1e-8*max(1,abs(reference))`. Reproduced outputs must also pass their own stricter tests. Running times and binary file bytes need not match.

The agent's test report is evidence, not my independent verification. After stage 4, I will personally verify the manual-kernel comparison and at least one other independent check, record the measured results in `log.md`, and summarize them in the report.
