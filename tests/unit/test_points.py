from app.exam_engine.scoring_service import (POINTS_CORRECT, POINTS_REMEDIAL,
                                             award_points, points_summary)


def rec(correct, remedial=False):
    return {"is_correct": correct, "is_remedial": remedial}


def test_award_points():
    assert award_points(True, False) == POINTS_CORRECT
    assert award_points(True, True) == POINTS_REMEDIAL
    assert award_points(False, False) == 0.0
    assert award_points(False, True) == 0.0


def test_primary_percent_ignores_remedials():
    records = [rec(True)] * 15 + [rec(False)] * 5 + [rec(True, True)] * 3
    s = points_summary(records)
    assert s["primary_total"] == 20
    assert s["primary_percent"] == 75.0


def test_recovery_credit_is_quarter_point():
    records = [rec(True)] * 15 + [rec(False)] * 5 + [rec(True, True)] * 3
    s = points_summary(records)
    assert s["recovery_points"] == 0.75
    assert s["credited_percent"] == 78.8


def test_pre_test_scores_identically_under_both_measures():
    """A test with no remediation must score the same either way, or the
    pre/post comparison would be measuring the mechanic, not learning."""
    records = [rec(True)] * 12 + [rec(False)] * 8
    s = points_summary(records)
    assert s["primary_percent"] == s["credited_percent"] == 60.0


def test_remediation_cannot_inflate_a_perfect_run():
    s = points_summary([rec(True)] * 10)
    assert s["credited_percent"] == 100.0


def test_all_wrong_all_recovered_caps_at_quarter():
    s = points_summary([rec(False)] * 10 + [rec(True, True)] * 10)
    assert s["primary_percent"] == 0.0
    assert s["credited_percent"] == 25.0


def test_empty_records():
    s = points_summary([])
    assert s["primary_percent"] == 0.0 and s["credited_percent"] == 0.0
