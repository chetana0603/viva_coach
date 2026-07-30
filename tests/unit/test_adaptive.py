from app.exam_engine.adaptive_service import calculate_next_level, nearest_available_level


def test_correct_answer_increases_level():
    assert calculate_next_level(2, True, max_level=5) == 3


def test_wrong_answer_decreases_level():
    assert calculate_next_level(2, False, max_level=5) == 1


def test_level_never_exceeds_ceiling():
    assert calculate_next_level(5, True, max_level=5) == 5
    assert calculate_next_level(3, True, max_level=3) == 3


def test_level_never_falls_below_zero():
    assert calculate_next_level(0, False, max_level=5) == 0


def test_nearest_available_prefers_easier_on_tie():
    assert nearest_available_level(2, [1, 3]) == 1


def test_nearest_available_none_when_empty():
    assert nearest_available_level(2, []) is None
