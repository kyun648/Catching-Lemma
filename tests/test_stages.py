import pytest

from catching_lemma.engine import DFA
from catching_lemma.stages import grade, load_stages

STAGES = load_stages("dfa")


def test_stages_exist():
    assert len(STAGES) >= 3


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_reference_is_valid_and_complete(stage):
    issues = stage.reference.validate()
    assert issues == [], [i.message for i in issues]
    assert stage.reference.alphabet == stage.alphabet


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_reference_grades_itself_correct(stage):
    result = grade(stage, stage.reference)
    assert result.correct
    assert result.used_states >= result.optimal_states


def test_wrong_answer_gives_counterexample():
    stage = next(s for s in STAGES if s.id == "dfa-01")
    # "a로 시작"만 확인하고 끝 글자를 무시하는 틀린 설계
    wrong = DFA.from_dict(
        {
            "states": ["s", "ok"],
            "alphabet": ["a", "b"],
            "start": "s",
            "accept": ["ok"],
            "transitions": {"s": {"a": "ok"}, "ok": {"a": "ok", "b": "ok"}},
        }
    )
    result = grade(stage, wrong)
    assert not result.correct
    assert result.counterexample == "a"  # a로 시작하지만 b로 끝나지 않음 → 거부해야 함
    assert result.expected is False
