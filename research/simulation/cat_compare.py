"""
E2b - Does EAP-driven level selection measure ability better than the +/-1 staircase?

Policies (20 primary items, levels 0..5, same bank model as simulate.py):
  staircase      : platform rule (level +/- 1)
  eap_select     : next level = level whose mean difficulty is closest to current EAP
Both with and without remediation. Outcome: RMSE and bias of the final EAP estimate
against true theta, and mean highest level reached.
"""
import json

import numpy as np

from simulate import GRID, PRIOR

B0, STEP = None, None


def run(theta, policy, remediation, rng, bl, item_sd=0.3, n_primary=20, max_level=5):
    n = len(theta)
    level = np.zeros(n, int)
    logpost = np.tile(np.log(PRIOR), (n, 1))
    hi = np.zeros(n, int)

    def answer(lvl):
        b = bl[lvl] + rng.normal(0, item_sd, n)
        return rng.random(n) < 1 / (1 + np.exp(-(theta - b)))

    def update(lvl, c, mask):
        p = 1 / (1 + np.exp(-(GRID[None, :] - bl[lvl][:, None])))
        ll = np.where(c[:, None], np.log(p), np.log1p(-p))
        return logpost + ll * mask[:, None]

    def eap_now(lp):
        w = np.exp(lp - lp.max(1, keepdims=True))
        return (w * GRID).sum(1) / w.sum(1)

    for _ in range(n_primary):
        c = answer(level)
        hi = np.maximum(hi, level)
        logpost = update(level, c, np.ones(n, bool))
        nxt = np.clip(level + np.where(c, 1, -1), 0, max_level)
        if remediation:
            miss = ~c
            rl = np.maximum(0, level - 1)
            c2 = answer(rl)
            logpost = update(rl, c2, miss)
            nxt = np.where(miss, np.clip(rl + np.where(c2, 1, -1), 0, max_level), nxt)
        if policy == "eap_select":
            est = eap_now(logpost)
            nxt = np.abs(bl[None, :] - est[:, None]).argmin(1)
        level = nxt
    est = eap_now(logpost)
    return est, hi


if __name__ == "__main__":
    cal = json.load(open("sim_results.json"))["calibration"]
    bl = cal["b0"] + cal["step"] * np.arange(6)
    rng = np.random.default_rng(7)
    theta = rng.normal(0, 1, 30000)
    res = {}
    for policy in ("staircase", "eap_select"):
        for remediation in (False, True):
            est, hi = run(theta, policy, remediation, rng, bl)
            key = f"{policy}{'+remediation' if remediation else ''}"
            res[key] = {"rmse": round(float(np.sqrt(((est - theta) ** 2).mean())), 3),
                        "bias": round(float((est - theta).mean()), 3),
                        "corr": round(float(np.corrcoef(est, theta)[0, 1]), 3),
                        "mean_highest_level": round(float(hi.mean()), 2)}
            print(key, res[key])
    json.dump(res, open("cat_results.json", "w"), indent=2)
