# PS1: Discrete State Dynamic Programming

## 1. Task

Solve the Huggett household problem in Question 2 using discrete state dynamic programming. Compare the four solver families and three invariant-distribution methods, investigate the asset grid, and assess policy accuracy using Euler-equation residuals. Hold prices fixed at the off-equilibrium values implied by `K0 = 5`; do not solve for market-clearing capital. I will select the methods, range, grid, and number of points from the numerical comparisons.

## 2. Context

### 2.1 Model and parameters

The household solves

$$
v(k,s)=\max_{k'\in\mathcal K,\;k'\ge0,\;c>0}
\left\{\frac{c^{1-\sigma}}{1-\sigma}
+\beta\sum_{s'=1}^2P_{ss'}v(k',s')\right\},
\qquad c=(1+r^0)k+w^0\epsilon_s\bar l-k'.
$$

Use `beta = 0.96`, `sigma = 1.5`, `labor = 1`, `k_min = 0`, `z = 1`, `alpha = 0.36`, `delta = 0.1`, and `K0 = 5`. State 1 has efficiency 0.8 and state 2 has efficiency 1.2. The row-stochastic shock matrix and its stationary probabilities are

$$
P=\begin{pmatrix}0.5&0.5\\0.5&0.5\end{pmatrix},
\qquad \pi^{shock}=(0.5,0.5).
$$

The production function is `Y = z K^alpha L^(1-alpha)`. Compute prices at full precision from

$$
L^*=\sum_s\pi_s^{shock}\epsilon_s\bar l=1,\qquad
w^0=(1-\alpha)z(K^0/L^*)^\alpha,\qquad
r^0=\alpha z(K^0/L^*)^{\alpha-1}-\delta.
$$

### 2.2 Vector formulation

Let `S = 2`, `M = NS`, and `m(n,s) = (s-1)N+n` in mathematical indexing. Stack columns using NumPy `order="F"` and use zero-based indices in Python. Define the value function `V` and policy indices `G` as `N × S` matrices, the stacked value vector `x = V(:)` as an `M`-vector, and the `M × N` utility matrix `R` by

$$
R[m(n,s),n']=u((1+r^0)k_n+w^0\epsilon_s\bar l-k_{n'}),
$$

Here `u(c) = c^(1-sigma)/(1-sigma)` for `c > 0`; set `R = -infinity` otherwise. Define

$$
T(x)=\max_{\mathrm{columns}}[R+\beta(PV^\top)\otimes\mathbf1_N],
\quad G(:)=\arg\max_{\mathrm{columns}}[R+\beta(PV^\top)\otimes\mathbf1_N].
$$

Break exact ties by selecting the smallest index. The asset policy is `g(k_n,s) = k_{G(n,s)}`. For a given policy, define the `M × M` transition matrix and chosen utility vector as

$$
Q_G[m(n,s),m(n',s')]=P_{ss'}\mathbf1\{n'=G(n,s)\},
\qquad R_G^*[m(n,s)]=R[m(n,s),G(n,s)].
$$

### 2.3 Household solvers

Start with a zero value function. At each outer pass, compute the greedy policy and percentage-change metric

$$
d(x)=\max_m\frac{|T(x)_m-x_m|}{|x_m|+1}.
$$

Stop when `d <= 1e-8`, returning the current `x` and its greedy policy. Each outer pass checks the current values and performs at most one update; include the terminating pass in the count. Report outer passes, updates, running time in seconds, and the metric recomputed on saved values. Solver time includes policy and matrix calculations and convergence checks, but excludes initial utility-matrix construction, which is reported separately. Use float64.

| Method | Update if not converged | Outer-pass cap |
|---|---|---:|
| Value function iteration | `x_j = T(x_{j-1})` | 10,000 |
| Howard improvement | Solve `(I-beta Q_j)x_j = R_j*` with sparse `spsolve` | 1,000 |
| Modified Howard improvement | `B_0 = T(x_{j-1})`; `B_h = R_j* + beta Q_j B_{h-1}` for `h = 1,...,20`; `x_j = B_20` | 10,000 |
| Fixed-step gradient descent | `x_j = x_{j-1} - eta h_j`, `eta = 0.0005` | 20,000 |
| Adam | Bias-corrected moment update below, learning rate 0.1 | 20,000 |

For both gradient runs, define `F(x) = x-T(x)`, `L(x) = ||F(x)||_2^2/2`, and `h_j = (I-beta Q_j)^T F(x_{j-1})`. Recompute the greedy policy each pass. The fixed step is conservative: at the baseline `M = 2000`, `||I-beta Q||_2 <= 1+beta sqrt(M)` gives a squared norm bound below 2,000. Retain this step even if convergence is slow; do not substitute line search.

Adam starts with zero moments and uses elementwise operations:

$$
a_j=0.9a_{j-1}+0.1h_j,\quad b_j=0.999b_{j-1}+0.001h_j^2,
\quad \hat a_j=\frac{a_j}{1-0.9^j},\quad\hat b_j=\frac{b_j}{1-0.999^j},
\quad x_j=x_{j-1}-0.1\frac{\hat a_j}{\sqrt{\hat b_j}+10^{-8}}.
$$

Report modified-Howard inner steps separately. For gradient traces, save the pass number, `d`, and `L` at each pass and at the saved exit values. Save the greedy policy corresponding to the returned values. Retain capped gradient runs and label them unconverged unless the saved-value metric passes. Additional exit diagnostics do not count as outer passes or updates. Use the Bellman criterion rather than the size of the update.

### 2.4 Invariant distribution

The invariant distribution is a column vector `pi` satisfying `Q^T pi = pi`, `sum(pi) = 1`, and `pi >= 0`. Use the converged Howard policy as the common reference for parts (b)–(c); stop if that solve fails. Compare the following methods:

1. **Power iteration:** start from `ones(M)/M`, update `pi_new = Q^T pi`, and return `pi_new` when `||pi_new-pi||_infinity <= 1e-12`; cap at 100,000 updates.
2. **Inverse iteration/eigenvector method:** call `scipy.sparse.linalg.eigs(Q.T, k=1, sigma=1-1e-10, which="LM", v0=ones(M)/sqrt(M), tol=1e-12, maxiter=100000)`. Require eigenvalue distance from one and imaginary parts of the returned eigenvector at most `1e-10`. Take the real part and divide by its nonzero sum.
3. **Direct solution:** replace the last row of `I-Q^T` with ones, and solve with right-hand side zero except its last entry one. Use `numpy.linalg.solve` for dense matrices and `spsolve` for sparse matrices.

Keep `Q` dense in (b) and convert the same matrix to CSR in (c). Include equation setup and normalization in each method's running time. Exclude common `Q` construction and conversion, and report them separately. A power-iteration cap, unsuccessful eigenvalue solve, or failed distribution check stops dependent work. Record negative roundoff before correction. Only entries in `[-1e-14,0)` may be set to zero, followed by normalization and renewed checks. Do not take absolute values to conceal an invalid distribution.

### 2.5 Grids, experiments, and statistics

Uniform grids include endpoints: `k_n = k_max (n-1)/(N-1)`. Parts (a)–(d) use `N = 1000` and `[0,20]`.

| Part | What to run and report |
|---|---|
| (a) | Run all five solver variants; tabulate iterations, time, exit metric, and convergence status. Save gradient traces. |
| (b)–(c) | Compare three distribution methods, first dense then sparse; report times and maximum pairwise sup-norm differences within each group and across representations. |
| (d) | Stop after (c) for my solver and distribution-method/representation choices. |
| (e) | With selected methods and `N = 1000`, test uniform ranges with `k_max = 1, 2, 5, 10, 20, 40`; report top mass, support endpoint, support share, and time. Stop for my range choice. |
| (f) | At selected range and `N = 1000`, compare uniform and exp-log grids. Save values, policies, distributions, times, and Euler diagnostics. Stop for my grid choice. |
| (g) | Use selected methods/range/grid at `N = 100, 500, 1000, 2000, 5000`; save and plot values, policies, and joint distributions for both shocks. Stop for my `N` choice. |
| (h) | Report selected-grid Euler residuals, five-grid accuracy scaling, and final tests. |

The nonuniform grid is `k_n = exp[(n-1)log(k_max+1)/(N-1)]-1`, with endpoints set exactly to zero and `k_max`. From (e) onward, use only my selected solver and distribution method. My choices will be limited to methods that converged and passed the applicable checks.

Let `p_n = sum_s pi(n,s)`. Mean assets are `sum_n k_n p_n`, and top-node mass is `p_N`. Define numerical support as `{n: p_n > 1e-12}`; its upper endpoint is the largest asset in that set, and its share of grid points is the number of supported nodes divided by `N`. Plot probability masses, not densities. Report and reject truncated trial ranges without silently changing the grid.

For part (a), report the contraction prediction `log(1e-8)/log(beta)` and observed VFI count. The prediction is about 451 for an eight-order error reduction, not an exact count for the relative metric. Report Howard and modified-Howard counts and the Hessian condition-number bound `1/(1-beta)^2 = 625`. If feasible, compute extreme singular values of `J = I-beta Q` at zero values and at the Howard solution. Distinguish `cond(J)` from `cond(J^T J) = cond(J)^2`. I will write the theoretical interpretation.

### 2.6 Euler-equation residual

For continuous choices with a slack artificial upper bound, the Euler condition is `c^(-sigma) >= beta(1+r0) E[c_next^(-sigma)]`, with equality when the borrowing constraint is also slack. An upper-bound choice may reverse this inequality and indicate truncation. The borrowing-constraint condition will be derived separately in my manual work.

Using the discrete policy, define

$$
c_{n,s}=(1+r^0)k_n+w^0\epsilon_s\bar l-k_{G(n,s)},
\quad c^{next}_{n,s,s'}=(1+r^0)k_{G(n,s)}+w^0\epsilon_{s'}\bar l-k_{G(G(n,s),s')}.
$$

$$
c^{EE}_{n,s}=[\beta(1+r^0)\sum_{s'}P_{ss'}(c^{next}_{n,s,s'})^{-\sigma}]^{-1/\sigma},
\qquad E_{n,s}=|1-c^{EE}_{n,s}/c_{n,s}|.
$$

Evaluate the residual at every slack state `A = {(n,s): G(n,s)>0}` in zero-based indexing, and flag upper-bound choices. Report `max_A E`, the arithmetic mean on `A`, and the conditional weighted mean `sum_A q E`, where `q = pi/sum_A pi`. Define the weighted maximum as `max_A(q E)` and state this convention explicitly. Also report the unweighted maximum over slack states with `pi > 1e-12`. For an empty set or `sum_A pi = 0`, report the affected statistic as unavailable with its reason.

Plot residuals against assets at my selected `N`. Across all five part-(g) solutions, plot unweighted mean and maximum errors against `h = max(diff(k_grid))` on log-log axes. Fit `log(error) = intercept + slope*log(h)` by ordinary least squares separately for each summary, using positive finite pairs. Report a slope as unavailable if fewer than two distinct step sizes remain. Do not impose zero residuals or a predetermined slope.

### 2.7 Validation before experiments

For stages 2–3, use the Question 2 model on `N = 100` uniform `[0,20]`. Compare the manual kernel with plain VFI from zero at relative tolerance `1e-10`, using the current-iterate exit and counting conventions above. The manual reference `manual/kernel_output.npz` must contain `V` and zero-based `G` of shape `(100,2)`, a column-stacked `pi` vector of shape `(200,)`, and scalar `iterations` recording the outer-pass count. Its power iteration uses `1e-12`, cap 100,000, and returns the updated iterate. Do not overwrite the reference.

Run the remaining correctness checks on this grid using the converged Howard reference at tolerance `1e-8`; validate VFI and modified Howard on the same grid. Full comparison tables, gradient cap runs, final-grid checks, and reproduction belong to stage 4 and remain pending beforehand.

## 3. Constraints

Use Python scripts, NumPy, SciPy, and Matplotlib; fix any random seed at zero. Follow the assignment's agent-instructions file. I handle Git manually in GitHub Desktop: do not stage, commit, push, tag, or rewrite history. Provide measured commit summaries and accurate agent attribution, then stop at each commit boundary for my confirmation. Read-only Git history and status checks are allowed.

Do not change model parameters, grids, tolerances, tests, or student-owned files to make a test pass. Report missing definitions or failures and stop. Read `manual/` only for the kernel test. Keep the log append-only and preserve Git history. Split runs longer than about three minutes, saving state and counters between calls. I will write the manual work, make the choices, state the reasons, and write the report.

## 4. Output format

Place the implementation in `code/` and checks in `tests/`. The command `python code/run_all.py` must regenerate all experiment outputs in `results/`, including early comparisons. Store my choices in `code/selected_settings.json`, outside generated outputs.

Save grids, values, zero-based policy indices, consumption, distributions, and Euler residuals as NPZ; save settings, counts, times, metrics, statistics, and test results as JSON. Write each table as a complete LaTeX `tabular` and a Markdown table in `results/tables.md`; save each figure as PDF and PNG. The stage-4 README must state the folder contents, reproduction command, actual Python/package versions in `pip freeze` format, and runtimes.

## 5. Success criteria

All applicable tests pass, parts (a)–(h) and their outputs are complete, and my four choices are recorded. Capped runs and rejected ranges are reported accurately, and clean reproduction regenerates the numerical results.

At stages 2, 3, and 4, provide separate changed-file lists, measured commit summaries, and accurate agent attribution; I will make and push each commit manually. Append dated log entries distinguishing results verified by running from claims. Before the final report and stage-5 commit, I will independently verify the manual-kernel comparison and at least one other check.
