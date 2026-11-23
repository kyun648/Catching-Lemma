import pytest

from catching_lemma.engine import DFA, NFA
from catching_lemma.stages import grade, load_stages

STAGES = load_stages()
DFA_STAGES = [s for s in STAGES if s.chapter == "dfa"]
NFA_STAGES = [s for s in STAGES if s.chapter == "nfa"]


def test_stages_exist():
    assert len(DFA_STAGES) >= 3
    assert len(NFA_STAGES) >= 3


def test_stage_ids_unique():
    ids = [s.id for s in STAGES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_reference_is_valid(stage):
    errors = [i.message for i in stage.reference.validate() if i.level == "error"]
    assert errors == []
    assert stage.reference.alphabet == stage.alphabet


@pytest.mark.parametrize("stage", DFA_STAGES, ids=lambda s: s.id)
def test_dfa_reference_is_complete(stage):
    assert isinstance(stage.reference, DFA)
    assert stage.reference.validate() == []


@pytest.mark.parametrize("stage", NFA_STAGES, ids=lambda s: s.id)
def test_nfa_reference_is_nfa(stage):
    assert isinstance(stage.reference, NFA)


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_description_examples_match_reference(stage):
    """설명에 적은 예시 문자열이 정답 기계의 판정과 맞는지 확인한다."""
    assert stage.examples_accept or stage.examples_reject
    for word in stage.examples_accept:
        assert stage.reference.accepts(word), f"{word!r}는 받아들여야 함"
    for word in stage.examples_reject:
        assert not stage.reference.accepts(word), f"{word!r}는 거부해야 함"


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.id)
def test_reference_grades_itself_correct(stage):
    result = grade(stage, stage.reference)
    assert result.correct


def test_wrong_dfa_answer_gives_counterexample():
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


def test_wrong_nfa_answer_gives_counterexample():
    stage = next(s for s in STAGES if s.id == "nfa-01")
    # "마지막 글자가 a"로 잘못 이해한 설계
    wrong = NFA.from_dict(
        {
            "type": "nfa",
            "states": ["q0", "q1"],
            "alphabet": ["a", "b"],
            "start": "q0",
            "accept": ["q1"],
            "transitions": {"q0": {"a": ["q0", "q1"], "b": ["q0"]}},
        }
    )
    result = grade(stage, wrong)
    assert not result.correct
    assert result.counterexample == "a"  # 마지막 글자는 a지만 끝에서 두 번째 글자가 없음
    assert result.expected is False


def test_dfa_answer_accepted_in_nfa_stage():
    """NFA 스테이지에 DFA로 답해도 같은 언어면 정답이다 (DFA는 NFA의 특수한 경우)."""
    stage = next(s for s in STAGES if s.id == "nfa-01")
    assert grade(stage, stage.reference_dfa).correct


def test_too_large_nfa_is_not_graded():
    stage = next(s for s in STAGES if s.id == "nfa-01")
    n = 12  # 끝에서 12번째 글자가 a: 바꾼 DFA는 상태 2^12개
    transitions = {"q0": {"a": ["q0", "q1"], "b": ["q0"]}}
    for i in range(1, n):
        transitions[f"q{i}"] = {"a": [f"q{i + 1}"], "b": [f"q{i + 1}"]}
    big = NFA(states=[f"q{i}" for i in range(n + 1)], alphabet=["a", "b"], start="q0",
              accept={f"q{n}"}, transitions=transitions)
    result = grade(stage, big)
    assert result.too_large
    assert not result.correct
    assert result.counterexample is None
