"""
Per-answer re-analysis of the pilot (study group 'Test1').

1. Calibrate Rasch level difficulties b[0..5] from all 764 responses (marginal ML via
   EM on a grid, theta ~ N(0,1) per attempt).
2. Score every attempt with EAP ability (primary only, and primary + remedial).
3. Paired pre/post comparison on ability, with and without students whose attempts
   show the copy -> tab-switch -> answer pattern in the integrity log.
"""
import csv
import collections
import json

import numpy as np
from scipy import stats

R = list(csv.DictReader(open("responses_Test1.csv")))
A = {r["attempt_id"]: r for r in csv.DictReader(open("attempts_Test1.csv"))}
GRID = np.linspace(-5, 5, 201)
PRIOR = stats.norm.pdf(GRID)
PRIOR /= PRIOR.sum()

att_ids = sorted({r["attempt_id"] for r in R}, key=int)
resp = {a: [(int(r["question_level"]), r["is_correct"] == "1", r["is_remedial"] == "1")
            for r in R if r["attempt_id"] == a] for a in att_ids}


def posterior(items, b):
    ll = np.zeros_like(GRID)
    for lv, c, _ in items:
        p = 1 / (1 + np.exp(-(GRID - b[lv])))
        ll += np.log(p if c else 1 - p)
    w = np.exp(ll - ll.max()) * PRIOR
    return w / w.sum()


# --- 1. EM calibration of level difficulties --------------------------------
b = np.linspace(-1.5, 1.5, 6)
for it in range(200):
    num = collections.defaultdict(float)     # expected correct per level
    info = collections.defaultdict(list)
    posts = {a: posterior(resp[a], b) for a in att_ids}
    newb = b.copy()
    for lv in range(6):
        # Newton step on b[lv] using expected log-likelihood
        g = h = 0.0
        for a in att_ids:
            for l2, c, _ in resp[a]:
                if l2 != lv:
                    continue
                p = 1 / (1 + np.exp(-(GRID - b[lv])))
                g += (posts[a] * (p - c)).sum()
                h += (posts[a] * p * (1 - p)).sum()
        newb[lv] = b[lv] + g / max(h, 1e-9)
    if np.abs(newb - b).max() < 1e-5:
        b = newb
        break
    b = newb
calib = {"level_difficulty": [round(float(x), 3) for x in b], "em_iterations": it + 1}

# Empirical accuracy by level (sanity check of whether levels get harder)
acc_by_level = {}
for lv in range(6):
    xs = [c for a in att_ids for l2, c, rem in resp[a] if l2 == lv and not rem]
    acc_by_level[lv] = {"n": len(xs), "accuracy": round(100 * np.mean(xs), 1)}


# --- 2. EAP per attempt -------------------------------------------------------
def eap(items):
    w = posterior(items, b)
    m = float((w * GRID).sum())
    return m, float(np.sqrt((w * (GRID - m) ** 2).sum()))


score = {}
for a in att_ids:
    at = A[a]
    prim = [x for x in resp[a] if not x[2]]
    score[(at["participant"], at["exam_kind"])] = {
        "attempt_id": int(a),
        "eap_primary": eap(prim)[0],
        "eap_all": eap(resp[a])[0],
        "se_all": eap(resp[a])[1],
        "n_primary": len(prim), "n_all": len(resp[a]),
    }

# --- 3. Integrity pattern -> students ----------------------------------------
FLAGGED_ATTEMPTS = {4, 5, 24, 34, 35}   # repeated copy -> tab_hidden -> return, ~1 per question
flag_students = sorted({A[str(x)]["participant"] for x in FLAGGED_ATTEMPTS if str(x) in A})
flag_map = {x: (A[str(x)]["participant"], A[str(x)]["exam_kind"]) for x in FLAGGED_ATTEMPTS if str(x) in A}

# Gap between finishing the pre-test and starting the post-test
from datetime import datetime
gaps = []
for s in {k[0] for k in score}:
    pre = [a for a in A.values() if a["participant"] == s and a["exam_kind"] == "pre_test"]
    post = [a for a in A.values() if a["participant"] == s and a["exam_kind"] == "post_test"]
    if pre and post:
        g = (datetime.fromisoformat(post[0]["started_at"]) -
             datetime.fromisoformat(pre[0]["submitted_at"])).total_seconds() / 60
        gaps.append(g)


def paired(key, exclude=()):
    ss = sorted(s for s in {k[0] for k in score}
                if (s, "post_test") in score and s not in exclude)
    pre = np.array([score[(s, "pre_test")][key] for s in ss])
    post = np.array([score[(s, "post_test")][key] for s in ss])
    d = post - pre
    return {"n": len(ss), "pre_mean": round(pre.mean(), 3), "post_mean": round(post.mean(), 3),
            "gain_logits": round(d.mean(), 3), "dz": round(d.mean() / d.std(ddof=1), 2),
            "t_p": round(float(stats.ttest_rel(post, pre).pvalue), 4),
            "wilcoxon_p": round(float(stats.wilcoxon(post, pre).pvalue), 4),
            "n_improved": int((d > 0).sum())}


# Same sensitivity for the reported percentage outcomes (from the evaluation export)
ev = [r for r in csv.DictReader(open("eval_final.csv")) if r["post_score_primary"]]


def paired_ev(col_pre, col_post, exclude=()):
    rows = [r for r in ev if r["register_number"].replace("STUDENT", "STUDENT") not in exclude]
    a = np.array([float(r[col_pre]) for r in rows]); c = np.array([float(r[col_post]) for r in rows])
    return {"n": len(rows), "gain": round((c - a).mean(), 2),
            "t_p": round(float(stats.ttest_rel(c, a).pvalue), 4),
            "wilcoxon_p": round(float(stats.wilcoxon(c, a).pvalue), 4)}


out = {
    "calibration": calib,
    "primary_accuracy_by_level": acc_by_level,
    "pre_to_post_gap_minutes": {"median": round(float(np.median(gaps)), 1),
                                "max": round(float(np.max(gaps)), 1)},
    "flagged_attempts": {str(k): v for k, v in flag_map.items()},
    "flagged_students": flag_students,
    "ability_all_responses": paired("eap_all"),
    "ability_primary_only": paired("eap_primary"),
    "ability_all_excluding_flagged": paired("eap_all", flag_students),
    "primary_score_excluding_flagged": paired_ev("pre_score_primary", "post_score_primary", flag_students),
    "readiness_excluding_flagged": paired_ev("pre_readiness", "post_readiness", flag_students),
}
json.dump(out, open("per_answer_results.json", "w"), indent=1)
print(json.dumps(out, indent=1))
