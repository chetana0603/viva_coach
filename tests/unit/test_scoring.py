from app.core import scoring


def _record(level, correct, rt=5.0):
    return {"type": "mcq", "concept": "X", "level": level, "is_correct": correct,
            "response_time": rt, "integrity_flags": []}


def test_readiness_between_0_and_100():
    for records in ([_record(0, False)] * 10, [_record(5, True)] * 10):
        score = scoring.compute_readiness(records)["score"]
        assert 0 <= score <= 100


def test_no_data_is_zero():
    assert scoring.compute_readiness([])["score"] == 0


def test_higher_levels_score_higher():
    low = scoring.compute_readiness([_record(0, True)] * 5)["score"]
    high = scoring.compute_readiness([_record(5, True)] * 5)["score"]
    assert high > low


def test_integrity_penalty_is_capped_at_15():
    flagged = [dict(_record(3, True), integrity_flags=["f1", "f2", "f3"]) for _ in range(10)]
    clean = [_record(3, True) for _ in range(10)]
    diff = scoring.compute_readiness(clean)["score"] - scoring.compute_readiness(flagged)["score"]
    assert diff <= 15
