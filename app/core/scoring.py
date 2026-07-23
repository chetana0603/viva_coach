"""
scoring.py
----------
Computes readiness score and all analytics shown in Report Mode:
level-wise accuracy, concept mastery, weak/strong concepts, adaptive movement,
and teacher follow-up material.
"""

from app.core.utils import level_name


def _mcq_records(records):
    return [r for r in records if r.get("type", "mcq") == "mcq"]


def compute_readiness(records):
    """
    Weighted readiness score (0-100).

    Rewards accuracy, reaching higher levels, and consistency; penalizes
    integrity flags slightly. Designed to be interpretable, not a black box.
    """
    mcqs = _mcq_records(records)
    if not mcqs:
        return {
            "score": 0, "label": "No Data",
            "total": 0, "correct": 0, "accuracy": 0.0,
            "highest_level": 0, "avg_response_time": 0.0, "integrity_flags": 0,
        }

    total = len(mcqs)
    correct = sum(1 for r in mcqs if r.get("is_correct"))
    accuracy = correct / total

    highest_level = max((r.get("level", 0) for r in mcqs), default=0)
    # Depth factor: how deep into Levels 0-5 the student reliably answered.
    depth_factor = highest_level / 5.0

    # Level-weighted accuracy: correct answers at higher levels count more.
    weighted_points = sum((r.get("level", 0) + 1) for r in mcqs if r.get("is_correct"))
    max_points = sum((r.get("level", 0) + 1) for r in mcqs)
    weighted_accuracy = weighted_points / max_points if max_points else 0.0

    integrity_flags = sum(len(r.get("integrity_flags", []) or []) for r in records)
    integrity_penalty = min(integrity_flags * 3, 15)  # cap penalty at 15 points

    times = [r.get("response_time") for r in mcqs if r.get("response_time")]
    avg_time = sum(times) / len(times) if times else 0.0

    raw = (0.55 * weighted_accuracy + 0.25 * accuracy + 0.20 * depth_factor) * 100
    score = max(0, min(100, round(raw - integrity_penalty)))

    if score >= 85:
        label = "Ready"
    elif score >= 70:
        label = "Almost Ready"
    elif score >= 50:
        label = "Needs Practice"
    else:
        label = "Not Ready"

    return {
        "score": score,
        "label": label,
        "total": total,
        "correct": correct,
        "accuracy": round(accuracy * 100, 1),
        "highest_level": highest_level,
        "avg_response_time": round(avg_time, 1),
        "integrity_flags": integrity_flags,
    }


def level_accuracy(records):
    """Accuracy per knowledge level (0-5)."""
    mcqs = _mcq_records(records)
    result = {}
    for lvl in range(6):
        lvl_records = [r for r in mcqs if r.get("level") == lvl]
        if lvl_records:
            corr = sum(1 for r in lvl_records if r.get("is_correct"))
            result[lvl] = {
                "name": level_name(lvl),
                "total": len(lvl_records),
                "correct": corr,
                "accuracy": round(corr / len(lvl_records) * 100, 1),
            }
    return result


def concept_mastery(records):
    """Accuracy per concept, sorted, plus strong/weak lists."""
    mcqs = _mcq_records(records)
    by_concept = {}
    for r in mcqs:
        c = r.get("concept", "Unknown")
        by_concept.setdefault(c, {"total": 0, "correct": 0})
        by_concept[c]["total"] += 1
        if r.get("is_correct"):
            by_concept[c]["correct"] += 1

    mastery = []
    for c, d in by_concept.items():
        acc = d["correct"] / d["total"] * 100 if d["total"] else 0
        mastery.append({
            "concept": c,
            "total": d["total"],
            "correct": d["correct"],
            "accuracy": round(acc, 1),
        })
    mastery.sort(key=lambda x: x["accuracy"], reverse=True)

    strong = [m["concept"] for m in mastery if m["accuracy"] >= 70]
    weak = [m["concept"] for m in mastery if m["accuracy"] < 50]
    return {"mastery": mastery, "strong": strong, "weak": weak}


def adaptive_trace(records):
    """Human-readable adaptive level-movement trace."""
    mcqs = _mcq_records(records)
    trace = []
    for r in mcqs:
        frm = r.get("level", 0)
        outcome = "Correct" if r.get("is_correct") else "Wrong"
        nxt = r.get("next_level", frm)
        if r.get("is_correct"):
            arrow = f"Level {frm} -> Correct -> Level {nxt}"
        else:
            arrow = f"Level {frm} -> Wrong -> Remedial Level {nxt}"
        trace.append(arrow)
    return trace


def teacher_followups(records, max_items: int = 5):
    """
    Generate teacher follow-up questions targeting weak concepts.
    Template-based so it works without an LLM; the LLM path can enrich this.
    """
    weak = concept_mastery(records)["weak"]
    followups = []
    templates = [
        "Can you explain {c} in your own words?",
        "Where in your work would {c} actually be used?",
        "What would go wrong if {c} were removed or ignored?",
        "How does {c} relate to the other topics you studied?",
        "Why did you make the choices you did regarding {c}?",
    ]
    for i, concept in enumerate(weak):
        followups.append(templates[i % len(templates)].format(c=concept))
        if len(followups) >= max_items:
            break

    if not followups:
        followups.append("The student covered the material well; probe design trade-offs at Level 5 to confirm depth.")
    return followups


def full_report(records):
    """Assemble the complete analytics payload for Report Mode."""
    readiness = compute_readiness(records)
    return {
        "readiness": readiness,
        "level_accuracy": level_accuracy(records),
        "concept": concept_mastery(records),
        "trace": adaptive_trace(records),
        "followups": teacher_followups(records),
    }
