from catching_lemma.engine import DFA, find_counterexample, minimal_state_count


def even_a() -> DFA:
    return DFA.from_dict(
        {
            "states": ["e", "o"],
            "alphabet": ["a", "b"],
            "start": "e",
            "accept": ["e"],
            "transitions": {"e": {"a": "o", "b": "e"}, "o": {"a": "e", "b": "o"}},
        }
    )


def test_accepts():
    dfa = even_a()
    assert dfa.accepts("")
    assert dfa.accepts("abab")
    assert not dfa.accepts("a")
    assert not dfa.accepts("aab" + "a")


def test_missing_transition_is_reject_and_warning():
    dfa = DFA.from_dict(
        {
            "states": ["q0", "q1"],
            "alphabet": ["a", "b"],
            "start": "q0",
            "accept": ["q1"],
            "transitions": {"q0": {"a": "q1"}},
        }
    )
    run = dfa.run("ab")
    assert not run.accepted
    assert run.path == ["q0", "q1", None]
    assert run.stuck_at == 1
    issues = dfa.validate()
    assert dfa.is_valid()
    assert sum(i.level == "warning" for i in issues) == 3  # q0-b, q1-a, q1-b


def test_validate_errors():
    dfa = DFA.from_dict(
        {
            "states": ["q0"],
            "alphabet": ["a", "bb"],
            "start": "nope",
            "accept": ["q9"],
            "transitions": {"q0": {"a": "zz"}},
        }
    )
    messages = [i.message for i in dfa.validate() if i.level == "error"]
    assert len(messages) == 4  # 두 글자 기호, 시작 상태 없음, 없는 종료 상태, 없는 도착 상태
    assert not dfa.is_valid()


def test_counterexample_none_for_equivalent():
    # 상태 이름과 개수가 달라도 같은 언어면 반례가 없어야 한다.
    bigger = DFA.from_dict(
        {
            "states": ["e1", "o1", "e2", "o2"],
            "alphabet": ["a", "b"],
            "start": "e1",
            "accept": ["e1", "e2"],
            "transitions": {
                "e1": {"a": "o1", "b": "e2"},
                "e2": {"a": "o2", "b": "e1"},
                "o1": {"a": "e2", "b": "o2"},
                "o2": {"a": "e1", "b": "o1"},
            },
        }
    )
    assert find_counterexample(bigger, even_a()) is None


def test_counterexample_is_shortest():
    # 모든 문자열을 받아들이는 기계 vs a 짝수 → 가장 짧은 반례는 "a"
    everything = DFA.from_dict(
        {
            "states": ["q"],
            "alphabet": ["a", "b"],
            "start": "q",
            "accept": ["q"],
            "transitions": {"q": {"a": "q", "b": "q"}},
        }
    )
    assert find_counterexample(everything, even_a()) == "a"


def test_counterexample_empty_string():
    nothing = DFA.from_dict(
        {"states": ["q"], "alphabet": ["a", "b"], "start": "q", "accept": [], "transitions": {}}
    )
    assert find_counterexample(nothing, even_a()) == ""


def test_minimal_state_count():
    assert minimal_state_count(even_a()) == 2
    # 빠진 전이가 있으면 죽은 상태 1개가 더해진다: "정확히 a 하나" → q0, q1, dead
    only_a = DFA.from_dict(
        {
            "states": ["q0", "q1"],
            "alphabet": ["a", "b"],
            "start": "q0",
            "accept": ["q1"],
            "transitions": {"q0": {"a": "q1"}},
        }
    )
    assert minimal_state_count(only_a) == 3
    assert only_a.completed_state_count() == 3


def test_minimal_merges_equivalent_states():
    bigger = DFA.from_dict(
        {
            "states": ["e1", "o1", "e2", "o2"],
            "alphabet": ["a", "b"],
            "start": "e1",
            "accept": ["e1", "e2"],
            "transitions": {
                "e1": {"a": "o1", "b": "e2"},
                "e2": {"a": "o2", "b": "e1"},
                "o1": {"a": "e2", "b": "o2"},
                "o2": {"a": "e1", "b": "o1"},
            },
        }
    )
    assert bigger.completed_state_count() == 4
    assert minimal_state_count(bigger) == 2


def test_round_trip_dict():
    dfa = even_a()
    assert DFA.from_dict(dfa.to_dict()).to_dict() == dfa.to_dict()
