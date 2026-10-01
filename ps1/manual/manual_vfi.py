import numpy as np

beta, sigma, labor, kmin = 0.96, 1.5, 1.0, 0.0
z, alpha, delta, K0 = 1.0, 0.36, 0.10, 5.0
eps = np.array([0.8, 1.2])
P = np.array([[0.5, 0.5], [0.5, 0.5]])
S, N, kmax = 2, 100, 20.0
L = 0.5 * eps[0] * labor + 0.5 * eps[1] * labor
w = (1.0 - alpha) * z * (K0 / L) ** alpha
r = alpha * z * (K0 / L) ** (alpha - 1.0) - delta
k = np.linspace(kmin, kmax, N)
state_k = np.tile(k, S)
state_eps = np.repeat(eps, N)
resources = (1.0 + r) * state_k + w * state_eps * labor
C = resources[:, None] - k[None, :]
R = np.full((N * S, N), -np.inf)
feasible = C > 0.0
R[feasible] = C[feasible] ** (1.0 - sigma) / (1.0 - sigma)
V, tol = np.zeros((N, S)), 1.0e-10
for it in range(1, 10001):
    B = R + np.kron(beta * (P @ V.T), np.ones((N, 1)))
    g = np.argmax(B, axis=1)
    Vnew = B[np.arange(N * S), g].reshape((N, S), order="F")
    metric = np.max(np.abs(Vnew - V) / (np.abs(V) + 1.0))
    V = Vnew
    if metric <= tol:
        break
else:
    raise RuntimeError("VFI did not converge")
B = R + np.kron(beta * (P @ V.T), np.ones((N, 1)))
g = np.argmax(B, axis=1)
G = g.reshape((N, S), order="F")
Q = np.zeros((N * S, N * S))
rows, shock = np.arange(N * S), np.repeat(np.arange(S), N)
for sp in range(S):
    Q[rows, sp * N + g] = P[shock, sp]
pi = np.ones(N * S) / (N * S)
for pit in range(1, 1000001):
    pinew = Q.T @ pi
    if np.max(np.abs(pinew - pi)) <= 1.0e-14:
        break
    pi = pinew
else:
    raise RuntimeError("Power iteration did not converge")
pi = pinew / pinew.sum()
print(f"iterations: {it}")
print(f"V range: [{V.min():.12g}, {V.max():.12g}]")
print(f"mean assets: {pi @ state_k:.12g}")
np.savez("manual/manual_vfi_output.npz", V=V, policy=G, pi=pi)
