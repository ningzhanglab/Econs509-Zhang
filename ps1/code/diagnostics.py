"""Euler residuals, support statistics, and OLS accuracy scaling from spec.md."""
import numpy as np


def distribution_statistics(grid, pi):
    marginal = pi.reshape((len(grid), 2), order="F").sum(axis=1)
    support = marginal > 1e-12
    return {"mean_assets": float(np.dot(grid, marginal)),
            "top_node_mass": float(marginal[-1]),
            "support_endpoint": float(grid[support][-1]) if support.any() else None,
            "support_share": float(support.mean()), "support_count": int(support.sum())}


def euler(model, G, pi):
    c = model.consumption(G)
    # c[G[n,s],sp] evaluates the next-period policy at next assets and shock.
    next_c = c[G, :]
    expectation = np.sum(next_c ** (-model.sigma) * model.P[None, :, :], axis=2)
    cEE = (model.beta * (1 + model.r) * expectation) ** (-1 / model.sigma)
    E = np.abs(1 - cEE / c)
    slack = G > 0
    upper = G == model.N - 1
    joint = pi.reshape((model.N, 2), order="F")
    mass = float(joint[slack].sum())
    supported = slack & (joint > 1e-12)
    reasons = {}
    stats = {"slack_count": int(slack.sum()), "slack_mass": mass,
             "upper_choice_count": int(upper.sum()),
             "weighted_maximum_convention": "max_A(q*E), q=pi/sum_A(pi)"}
    for key, operation in (("maximum", np.max), ("mean", np.mean)):
        stats[key] = float(operation(E[slack])) if slack.any() else None
        if not slack.any():
            reasons[key] = "No slack states"
    stats["weighted_mean"] = float(np.sum(joint[slack] * E[slack]) / mass) if mass > 0 else None
    stats["weighted_maximum"] = float(np.max(joint[slack] * E[slack] / mass)) if mass > 0 else None
    if mass == 0:
        reasons.update({key: "Zero slack-state probability mass" for key in ("weighted_mean", "weighted_maximum")})
    stats["supported_maximum"] = float(E[supported].max()) if supported.any() else None
    if not supported.any():
        reasons["supported_maximum"] = "No slack states with probability above 1e-12"
    stats["unavailable_reasons"] = reasons
    return {"consumption": c, "next_consumption": next_c, "cEE": cEE, "E": E,
            "slack": slack, "upper": upper, "statistics": stats}


def accuracy_scaling(grids, errors):
    h = np.array([np.max(np.diff(grid)) for grid in grids], dtype=np.float64)
    errors = np.array([np.nan if error is None else error for error in errors])
    valid = np.isfinite(h) & (h > 0) & np.isfinite(errors) & (errors > 0)
    if len(np.unique(h[valid])) < 2:
        return {"intercept": None, "slope": None, "reason": "Fewer than two distinct positive finite step sizes",
                "h": h.tolist(), "used_indices": np.flatnonzero(valid).tolist()}
    design = np.column_stack((np.ones(valid.sum()), np.log(h[valid])))
    intercept, slope = np.linalg.lstsq(design, np.log(errors[valid]), rcond=None)[0]
    return {"intercept": float(intercept), "slope": float(slope), "h": h.tolist(),
            "used_indices": np.flatnonzero(valid).tolist(), "reason": None}
