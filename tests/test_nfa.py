import pytest

from catching_lemma.engine import (
    DFA,
    LAMBDA,
    NFA,
    TooManyStatesError,
    find_counterexample,
    minimal_state_count,
)


def second_last_a() -> NFA:
    return NFA.from_dict(
        {
            "type": "nfa",
            "states": ["q0", "q1", "q2"],
            "alphabet": ["a", "b"],
            "start": "q0",
            "accept": ["q2"],
            "transitions": {"q0": {"a": ["q0", "q1"], "b": ["q0"]}, "q1": {"a": ["q2"], "b": ["q2"]}},
        }
    )


def a_star_b_star() -> NFA:
    return NFA.from_dict(
        {
            "type": "nfa",
            "states": ["qa", "qb"],
            "alphabet": ["a", "b"],
            "start": "qa",
            "accept": ["qb"],
            "transitions": {"qa": {"a": ["qa"], LAMBDA: ["qb"]}, "qb": {"b": ["qb"]}},
        }
    )


def test_accepts_with_nondeterminism():
    nfa = second_last_a()
    assert nfa.accepts("ab")
    assert nfa.accepts("bab")
    assert not nfa.accepts("abb")
    assert not nfa.accepts("")


def test_run_tracks_state_sets():
    run = second_last_a().run("ab")
    assert run.steps == [frozenset({"q0"}), frozenset({"q0", "q1"}), frozenset({"q0", "q2"})]
    assert run.accepted


def test_lambda_closure_and_acceptance():
    nfa = a_star_b_star()
    assert nfa.lambda_closure({"qa"}) == frozenset({"qa", "qb"})
    assert nfa.accepts("")  # 시작 상태의 λ-closure에 종료 상태가 있음
    assert nfa.accepts("aabbb")
    assert not nfa.accepts("ba")
    # b를 읽은 뒤 a가 오면 활성 상태가 사라진다
    assert nfa.run("ba").steps[-1] == frozenset()


def test_lambda_cycle_does_not_loop_forever():
    nfa = NFA.from_dict(
        {
            "type": "nfa",
            "states": ["p", "q"],
            "alphabet": ["a"],
            "start": "p",
            "accept": ["q"],
            "transitions": {"p": {LAMBDA: ["q"]}, "q": {LAMBDA: ["p"]}},
        }
    )
    assert nfa.lambda_closure({"p"}) == frozenset({"p", "q"})
    assert nfa.accepts("")
    assert not nfa.accepts("a")


def test_subset_construction_matches_nfa():
    nfa = second_last_a()
    dfa = nfa.to_dfa()
    assert dfa.is_valid()
    for word in ["", "a", "b", "aa", "ab", "ba", "bb", "aab", "abb", "bab", "aaaa", "abab"]:
        assert dfa.accepts(word) == nfa.accepts(word), word
    # "끝에서 두 번째 글자가 a"는 NFA 3개 상태, 최소 DFA 4개 상태
    assert minimal_state_count(dfa) == 4


def test_subset_construction_state_names():
    dfa = second_last_a().to_dfa()
    assert dfa.start == "{q0}"
    assert "{q0,q1}" in dfa.states


def test_nfa_and_dfa_equivalence_via_counterexample():
    # a*b*를 DFA로 직접 만든 것과 NFA는 같은 언어
    dfa = DFA.from_dict(
        {
            "states": ["A", "B"],
            "alphabet": ["a", "b"],
            "start": "A",
            "accept": ["A", "B"],
            "transitions": {"A": {"a": "A", "b": "B"}, "B": {"b": "B"}},
        }
    )
    assert find_counterexample(a_star_b_star().to_dfa(), dfa) is None


def test_validate_errors():
    nfa = NFA.from_dict(
        {
            "type": "nfa",
            "states": ["q0"],
            "alphabet": ["a"],
            "start": "q0",
            "accept": ["q0"],
            "transitions": {"q0": {"a": ["zz"], "c": ["q0"]}},
        }
    )
    messages = [i.message for i in nfa.validate() if i.level == "error"]
    assert len(messages) == 2  # 없는 상태로 가는 전이, 알파벳에 없는 기호
    assert not nfa.is_valid()


def test_missing_transitions_are_not_warned():
    issues = second_last_a().validate()
    assert issues == []


def test_state_names_with_reserved_chars_are_errors():
    """부분집합 이름 "{x,y}"가 겹치지 않도록 상태 이름에 쉼표와 중괄호를 막는다.

    막지 않으면 {x, y}와 {"x,y"}가 둘 다 "{x,y}"가 되어, NFA는 "a"를 거부하는데 바꾼 DFA는 받아들인다.
    """
    nfa = NFA.from_dict(
        {
            "type": "nfa",
            "states": ["s", "x", "y", "x,y"],
            "alphabet": ["a", "b"],
            "start": "s",
            "accept": ["x,y"],
            "transitions": {"s": {"a": ["x", "y"], "b": ["x,y"]}},
        }
    )
    assert not nfa.is_valid()
    assert any("x,y" in i.message for i in nfa.validate() if i.level == "error")
    for name in ["{q0}", "q{", "a}"]:
        assert not NFA.from_dict({**second_last_a().to_dict(), "states": ["q0", "q1", "q2", name]}).is_valid()


def test_subset_construction_stops_at_limit():
    nfa = second_last_a()
    with pytest.raises(TooManyStatesError):
        nfa.to_dfa(max_states=3)  # 실제로는 상태 4개가 필요하다
    assert len(nfa.to_dfa(max_states=4).states) == 4
