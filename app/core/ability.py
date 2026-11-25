"""
ability.py
----------
Model-based ability estimate for an adaptive attempt.

Why this exists
    Level-based summaries ("highest level reached", level-weighted accuracy) depend on
    the route the adaptive engine took, not only on what the student knows. In the
    post-test, remediation after a wrong answer changes that route (a correct remedial
    returns the student to the level they missed), so those summaries can rise with no
    learning at all. A simulation of this engine (research/simulation) showed
    "highest level" rising by ~0.3 levels from remediation alone.

    A likelihood-based estimate does not have this problem: the questions a student is
    routed to depend only on answers already observed, so the routing can be ignored
    when estimating ability (the same reason computerised adaptive tests can be scored
    fairly). Remedial answers are real evidence and are included; in simulation this
    lowered the estimation error from 0.44 to 0.37 logits.

Model
    Rasch: P(correct | theta, level) = 1 / (1 + exp(-(theta - b[level]))).
    b[level] are level difficulties on the logit scale. The defaults are evenly spaced;
    they can be re-estimated from response data once enough attempts exist.
    Estimate: EAP (posterior mean) on a grid with a standard-normal prior.

Pure Python - no numpy - so it runs inside the web app unchanged.
"""

import math

# Default level difficulties (levels 0..5), centred on 0. Override per subject when
# calibrated difficulties are available.
DEFAULT_DIFFICULTY = {0: -1.5, 1: -0.9, 2: -0.3, 3: 0.3, 4: 0.9, 5: 1.5}

_GRID = [-4.0 + i * 0.05 for i in range(161)]          # -4 .. +4 logits
_PRIOR = [math.exp(-0.5 * t * t) for t in _GRID]


def _p(theta, b):
    return 1.0 / (1.0 + math.exp(-(theta - b)))


def estimate_ability(records, difficulty=None, include_remedial=True):
    """
    EAP ability from MCQ records (dicts with 'level', 'is_correct', optional
    'is_remedial'). Returns theta (logits), its posterior SD, a 0-100 display score
    (the probability of answering a mid-difficulty question correctly), and the
    number of responses used.
    """
    difficulty = difficulty or DEFAULT_DIFFICULTY
    used = [r for r in records
            if r.get("type", "mcq") == "mcq"
            and r.get("is_correct") is not None
            and (include_remedial or not r.get("is_remedial"))]
    if not used:
        return {"theta": 0.0, "se": 1.0, "score": 50, "n": 0}

    log_post = [math.log(p) for p in _PRIOR]
    for r in used:
        b = difficulty.get(int(r.get("level", 0)), 0.0)
        correct = bool(r.get("is_correct"))
        for i, t in enumerate(_GRID):
            p = _p(t, b)
            log_post[i] += math.log(p if correct else 1.0 - p)

    m = max(log_post)
    w = [math.exp(v - m) for v in log_post]
    z = sum(w)
    theta = sum(t * wi for t, wi in zip(_GRID, w)) / z
    var = sum((t - theta) ** 2 * wi for t, wi in zip(_GRID, w)) / z
    mid = sum(difficulty.values()) / len(difficulty)
    return {
        "theta": round(theta, 3),
        "se": round(math.sqrt(var), 3),
        "score": round(100 * _p(theta, mid)),
        "n": len(used),
    }


def highest_correct_level(records):
    """Highest level answered correctly on a primary question (0 if none)."""
    levels = [int(r.get("level", 0)) for r in records
              if r.get("is_correct") and not r.get("is_remedial")]
    return max(levels, default=0)
