"""화면과 엔진 사이 창구(catching_lemma.api) 테스트.

- app.py가 api만 쓰는지 (경계 규칙)
- api의 입력과 출력이 모두 JSON으로 바꿀 수 있는 값인지
"""

import ast
import json
from pathlib import Path

import pytest

from catching_lemma import api

APP = Path(__file__).resolve().parent.parent / "app.py"

DFA_WRONG = {  # dfa-01에 대한 틀린 답: "a로 시작"만 확인한다
    "type": "dfa",
    "states": ["s", "x", "a"],
    "alphabet": ["a", "b"],
    "start": "s",
    "accept": ["a"],
    "transitions": {"s": {"a": "a", "b": "x"}, "x": {"a": "x", "b": "x"}, "a": {"a": "a", "b": "a"}},
}

NFA_SECOND_LAST_A = {
    "type": "nfa",
    "states": ["q1", "q0", "q2"],
    "alphabet": ["a", "b"],
    "start": "q0",
    "accept": ["q2"],
    "transitions": {"q0": {"a": ["q1", "q0"], "b": ["q0"]}, "q1": {"a": ["q2"], "b": ["q2"]}},
}


def roundtrips_as_json(value) -> bool:
    return json.loads(json.dumps(value)) == value


# ---------- 경계 규칙 ----------


def test_app_imports_only_api_from_package():
    """app.py는 catching_lemma 패키지에서 api 모듈만 가져온다."""
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    used = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            used += [a.name for a in node.names if a.name.split(".")[0] == "catching_lemma"]
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "catching_lemma":
            if node.module == "catching_lemma":
                used += [f"catching_lemma.{a.name}" for a in node.names]
            else:
                used.append(node.module)
    assert used, "app.py가 catching_lemma.api를 쓰지 않고 있어요"
    assert set(used) == {"catching_lemma.api"}, f"api 말고 다른 모듈을 쓰고 있어요: {sorted(set(used))}"


# ---------- 출력 형식 ----------


def test_list_stages_hides_reference():
    stages = api.list_stages("nfa")
    assert len(stages) >= 3
    assert roundtrips_as_json(stages)
    assert set(stages[0]) == {"id", "chapter", "title", "description", "hint", "alphabet"}


def test_validate_returns_dicts():
    issues = api.validate({"type": "dfa", "states": [], "alphabet": ["a"], "start": "", "accept": []})
    assert roundtrips_as_json(issues)
    assert {"level": "error", "message": "상태가 하나도 없어요."} in issues
    assert not api.is_valid({"type": "dfa", "states": [], "alphabet": ["a"], "start": "", "accept": []})


def test_run_dfa_trace_ends_with_none_when_stuck():
    machine = {"type": "dfa", "states": ["q0"], "alphabet": ["a", "b"], "start": "q0",
               "accept": ["q0"], "transitions": {"q0": {"a": "q0"}}}
    result = api.run(machine, "ab")
    assert result == {"type": "dfa", "accepted": False, "trace": ["q0", "q0", None]}
    assert roundtrips_as_json(result)


def test_run_nfa_trace_is_sorted_lists():
    result = api.run(NFA_SECOND_LAST_A, "ab")
    assert result == {"type": "nfa", "accepted": True, "trace": [["q0"], ["q0", "q1"], ["q0", "q2"]]}
    # abb: q2에서 더 갈 곳이 없어 사라지고 q0만 남는다
    assert api.run(NFA_SECOND_LAST_A, "abb")["trace"] == [["q0"], ["q0", "q1"], ["q0", "q2"], ["q0"]]
    assert roundtrips_as_json(result)


def test_grade_correct_and_wrong():
    wrong = api.grade("dfa-01", DFA_WRONG)
    assert roundtrips_as_json(wrong)
    assert wrong["correct"] is False
    assert wrong["counterexample"] == "a"
    assert wrong["expected"] is False

    right = api.grade("nfa-01", NFA_SECOND_LAST_A)
    assert right == {"correct": True, "counterexample": None, "expected": None,
                     "used_states": 3, "optimal_states": 4}


def test_grade_unknown_stage():
    with pytest.raises(KeyError):
        api.grade("없는-스테이지", DFA_WRONG)


def test_to_dfa_and_normalize():
    dfa = api.to_dfa(NFA_SECOND_LAST_A)
    assert dfa["type"] == "dfa"
    assert dfa["start"] == "{q0}"
    assert roundtrips_as_json(dfa)
    assert api.grade("nfa-01", dfa)["correct"]
    # 도착 상태 순서만 다른 같은 설계는 같은 dict가 된다
    reordered = {**NFA_SECOND_LAST_A, "transitions": {"q0": {"a": ["q0", "q1"], "b": ["q0"]},
                                                      "q1": {"a": ["q2"], "b": ["q2"]}}}
    assert api.normalize(reordered) == api.normalize(NFA_SECOND_LAST_A)


def test_diagram_highlights_counterexample():
    plain = api.diagram(DFA_WRONG)
    highlighted = api.diagram(DFA_WRONG, counterexample="a")
    assert "penwidth=2" not in plain
    assert "penwidth=2" in highlighted

    nfa_highlighted = api.diagram(NFA_SECOND_LAST_A, counterexample="ab")
    assert "style=filled" in nfa_highlighted


def test_diagram_skips_highlight_for_invalid_machine():
    broken = {**DFA_WRONG, "start": ""}
    assert "penwidth=2" not in api.diagram(broken, counterexample="a")
