from app.core.ability import estimate_ability, highest_correct_level


def _r(level, correct, remedial=False):
    return {"type": "mcq", "level": level, "is_correct": correct, "is_remedial": remedial}


def test_no_data_returns_prior():
    out = estimate_ability([])
    assert out["n"] == 0 and out["theta"] == 0.0


def test_more_correct_means_higher_ability():
    weak = estimate_ability([_r(2, False)] * 10)
    strong = estimate_ability([_r(2, True)] * 10)
    assert strong["theta"] > weak["theta"]


def test_correct_at_harder_level_counts_more():
    easy = estimate_ability([_r(0, True), _r(0, False)] * 5)
    hard = estimate_ability([_r(5, True), _r(5, False)] * 5)
    assert hard["theta"] > easy["theta"]


def test_uncertainty_shrinks_with_more_answers():
    few = estimate_ability([_r(3, True), _r(3, False)])
    many = estimate_ability([_r(3, True), _r(3, False)] * 10)
    assert many["se"] < few["se"]


def test_remedial_can_be_excluded():
    recs = [_r(3, True)] * 5 + [_r(1, False, remedial=True)] * 5
    with_rem = estimate_ability(recs)
    without = estimate_ability(recs, include_remedial=False)
    assert without["n"] == 5 and with_rem["n"] == 10


def test_score_is_bounded():
    for recs in ([_r(5, True)] * 30, [_r(0, False)] * 30):
        assert 0 <= estimate_ability(recs)["score"] <= 100


def test_highest_correct_ignores_wrong_and_remedial():
    recs = [_r(4, False), _r(2, True), _r(5, True, remedial=True)]
    assert highest_correct_level(recs) == 2
