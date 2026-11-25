"""
E2 - Simulation of the viva platform's adaptive engine.

Replicates the platform's rules exactly (app/exam_engine/attempt_service.py,
adaptive_service.py, core/scoring.py):
  * staircase: correct -> level+1, wrong -> level-1, clamped to [0, max_level]
  * pre-test : no remediation
  * post-test: after a WRONG primary answer at level L, one remedial question at
               max(0, L-1) on the same concept; the next primary level is then
               remedial_level +/- 1. Remedials do not count toward question_count.
  * readiness (code): 100*(0.55*W + 0.25*A + 0.20*Lmax/5) on PRIMARY records,
               Lmax = highest level ATTEMPTED
  * readiness (paper Eq.3): same but Lmax = highest level answered CORRECTLY

Simulated learners follow a Rasch model: P(correct) = sigmoid(theta - b),
with item difficulty b = b0 + step*level + N(0, item_sd).

Ability is also estimated by EAP (grid, N(0,1) prior) using the level-mean
difficulties - i.e. what an instructor could compute without per-item calibration.
Because item selection depends only on observed responses, the likelihood-based
estimate is not distorted by the adaptive/remedial routing (ignorability).
"""
import json
import sys

import numpy as np
from scipy import stats

GRID = np.linspace(-5, 5, 201)
PRIOR = stats.norm.pdf(GRID)


def run_tests(theta, remediation, rng, b_levels, item_sd=0.3, n_primary=20,
              max_level=5, start=0):
    """Vectorised over learners. Returns per-learner arrays of responses."""
    n = len(theta)
    level = np.full(n, start)
    max_items = n_primary * 2
    lv = np.full((n, max_items), -1)
    cor = np.zeros((n, max_items), bool)
    rem = np.zeros((n, max_items), bool)
    k = 0
    for _ in range(n_primary):
        b = b_levels[level] + rng.normal(0, item_sd, n)
        c = rng.random(n) < 1 / (1 + np.exp(-(theta - b)))
        lv[:, k], cor[:, k], rem[:, k] = level, c, False
        k += 1
        nxt = np.clip(level + np.where(c, 1, -1), 0, max_level)
        if remediation:
            miss = ~c
            rl = np.maximum(0, level - 1)
            b2 = b_levels[rl] + rng.normal(0, item_sd, n)
            c2 = rng.random(n) < 1 / (1 + np.exp(-(theta - b2)))
            lv[miss, k] = rl[miss]
            cor[miss, k] = c2[miss]
            rem[miss, k] = True
            nxt = np.where(miss, np.clip(rl + np.where(c2, 1, -1), 0, max_level), nxt)
            k += 1
        level = nxt
    return lv[:, :k], cor[:, :k], rem[:, :k]


def metrics(lv, cor, rem, b_levels, max_level=5):
    used = lv >= 0
    prim = used & ~rem
    n_p = prim.sum(1)
    A = (cor & prim).sum(1) / n_p
    w = np.where(prim, lv + 1, 0)
    W = (w * cor).sum(1) / w.sum(1)
    hi_att = np.where(prim, lv, -1).max(1)
    hi_cor = np.where(prim & cor, lv, 0).max(1)
    r_code = np.clip(np.round(100 * (0.55 * W + 0.25 * A + 0.20 * hi_att / max_level)), 0, 100)
    r_paper = np.clip(np.round(100 * (0.55 * W + 0.25 * A + 0.20 * hi_cor / max_level)), 0, 100)
    return {
        "primary_pct": 100 * A,
        "readiness_code": r_code,
        "readiness_paper": r_paper,
        "highest_attempted": hi_att.astype(float),
        "highest_correct": hi_cor.astype(float),
        "eap_primary": eap(lv, cor, prim, b_levels),
        "eap_all": eap(lv, cor, used, b_levels),
    }


def eap(lv, cor, mask, b_levels, chunk=2000):
    """EAP ability on a grid using level-mean difficulties (chunked for memory)."""
    if len(lv) > chunk:
        return np.concatenate([eap(lv[i:i + chunk], cor[i:i + chunk], mask[i:i + chunk],
                                   b_levels, chunk) for i in range(0, len(lv), chunk)])
    b = b_levels[np.clip(lv, 0, len(b_levels) - 1)]              # (n, k)
    p = 1 / (1 + np.exp(-(GRID[None, None, :] - b[:, :, None])))  # (n, k, g)
    ll = np.where(cor[:, :, None], np.log(p), np.log1p(-p))
    ll = (ll * mask[:, :, None]).sum(1)                           # (n, g)
    post = np.exp(ll - ll.max(1, keepdims=True)) * PRIOR
    post /= post.sum(1, keepdims=True)
    return (post * GRID).sum(1)


def study(rng, n, delta, b_levels, theta_mu=0.0, theta_sd=1.0, **kw):
    theta = rng.normal(theta_mu, theta_sd, n)
    pre = metrics(*run_tests(theta, False, rng, b_levels, **kw), b_levels)
    post = metrics(*run_tests(theta + delta, True, rng, b_levels, **kw), b_levels)
    return theta, pre, post


def calibrate(rng, target_pct=49.06, target_hi=4.00):
    """Pick (b0, step, theta_mu) so the simulated PRE-test matches the pilot pre-test."""
    best = None
    for step in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0):
        for b0 in np.arange(-3.0, 0.01, 0.25):
            bl = b0 + step * np.arange(6)
            theta = rng.normal(0, 1, 4000)
            m = metrics(*run_tests(theta, False, rng, bl), bl)
            err = ((m["primary_pct"].mean() - target_pct) / 5) ** 2 + \
                  (m["highest_attempted"].mean() - target_hi) ** 2
            if best is None or err < best[0]:
                best = (err, b0, step, m["primary_pct"].mean(), m["highest_attempted"].mean())
    return best


if __name__ == "__main__":
    rng = np.random.default_rng(2026)
    out = {}

    err, b0, step, pct, hi = calibrate(rng)
    b_levels = b0 + step * np.arange(6)
    b0, step, pct, hi = float(b0), float(step), float(pct), float(hi)
    out["calibration"] = {"b0": b0, "step": step, "sim_pre_pct": round(pct, 2),
                          "sim_pre_highest": round(hi, 2),
                          "pilot_pre_pct": 49.06, "pilot_pre_highest": 4.00}
    print("calibration", out["calibration"])

    keys = ["primary_pct", "readiness_code", "readiness_paper",
            "highest_attempted", "highest_correct", "eap_primary", "eap_all"]

    # (a) Large-sample bias: mean measured gain at each true learning effect
    out["bias"] = {}
    for delta in (0.0, 0.25, 0.5):
        _, pre, post = study(rng, 50000, delta, b_levels)
        out["bias"][str(delta)] = {k: round(float((post[k] - pre[k]).mean()), 3) for k in keys}
        print("delta", delta, out["bias"][str(delta)])

    # (b) False-positive rate at the pilot's n = 16 with ZERO true learning,
    #     and power with a modest true effect - paired t-test, alpha = .05
    for delta, name in ((0.0, "false_positive_rate_n16"), (0.5, "power_n16_delta0.5")):
        reps, hits = 4000, {k: 0 for k in keys}
        for _ in range(reps):
            _, pre, post = study(rng, 16, delta, b_levels)
            for k in keys:
                d = post[k] - pre[k]
                if d.std() == 0:
                    continue
                if stats.ttest_rel(post[k], pre[k]).pvalue < 0.05 and d.mean() > 0:
                    hits[k] += 1
        out[name] = {k: round(hits[k] / reps, 3) for k in keys}
        print(name, out[name])

    # (c) Measurement accuracy of each score: correlation with true theta (pre-test design)
    theta, pre, _ = study(rng, 20000, 0.0, b_levels)
    out["corr_with_true_theta_pre"] = {k: round(float(np.corrcoef(theta, pre[k])[0, 1]), 3)
                                      for k in keys}
    print("corr", out["corr_with_true_theta_pre"])

    # (d) Sensitivity: zero-learning spurious gain across difficulty spacing
    out["sensitivity_zero_learning"] = {}
    for st in (0.5, 0.8, 1.0):
        for mu in (-0.5, 0.0, 0.5):
            bl = b0 + st * np.arange(6)
            _, pre, post = study(rng, 20000, 0.0, bl, theta_mu=mu)
            out["sensitivity_zero_learning"][f"step={st},theta_mu={mu}"] = {
                k: round(float((post[k] - pre[k]).mean()), 3)
                for k in ("readiness_code", "highest_attempted", "primary_pct", "eap_all")}
    json.dump(out, open("sim_results.json", "w"), indent=2)
    print("saved sim_results.json")
