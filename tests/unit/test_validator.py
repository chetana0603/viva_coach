from app.question_authoring.validator import validate_mcq

MATERIAL = ("Normalization organizes tables to reduce redundancy and prevent insertion, "
            "update and deletion anomalies in a relational database schema.")


def _base():
    return {"question": "Which problem does normalization mainly prevent in a database?",
            "options": ["Data anomalies", "Slow internet", "Weak passwords", "UI bugs"],
            "answer": 0}


def test_good_question_passes():
    assert validate_mcq(_base(), MATERIAL) == []


def test_fewer_than_four_options_fails():
    mcq = _base()
    mcq["options"] = ["A", "B"]
    assert any("four options" in p for p in validate_mcq(mcq, MATERIAL))


def test_answer_out_of_range_fails():
    mcq = _base()
    mcq["answer"] = 9
    assert any("not one of the options" in p for p in validate_mcq(mcq, MATERIAL))


def test_passage_reference_fails():
    mcq = _base()
    mcq["question"] = "According to the above passage, what does normalization prevent?"
    assert any("passage" in p for p in validate_mcq(mcq, MATERIAL))


def test_duplicate_is_rejected():
    mcq = _base()
    problems = validate_mcq(mcq, MATERIAL, previous_questions=[mcq["question"]])
    assert any("duplicate" in p.lower() for p in problems)
