"""화면(app.py)과 엔진 사이의 창구.

화면은 이 모듈만 쓰고, 모든 입력과 출력은 JSON으로 바꿀 수 있는 값(dict, list, str, int, bool, None)이다.
엔진 객체(DFA, NFA)와 결과 dataclass는 이 모듈 밖으로 나가지 않는다.
그래서 엔진 내부 구조를 바꿔도 여기서 돌려주는 형식만 지키면 화면은 고치지 않아도 된다.

기계(machine)는 엔진 문서에 적힌 오토마타 JSON 형식이다. "type"이 "nfa"면 NFA, 없거나 "dfa"면 DFA로 본다.
"""

from __future__ import annotations

from dataclasses import asdict

from .diagram import to_dot
from .engine import LAMBDA, MAX_DFA_STATES, NFA, TooManyStatesError, automaton_from_dict
from .stages import Stage, grade as _grade, load_stages

__all__ = [
    "LAMBDA",
    "MAX_DFA_STATES",
    "list_stages",
    "normalize",
    "validate",
    "is_valid",
    "run",
    "grade",
    "to_dfa",
    "diagram",
]


def _stage_info(stage: Stage) -> dict:
    return {
        "id": stage.id,
        "chapter": stage.chapter,
        "title": stage.title,
        "description": stage.description,
        "hint": stage.hint,
        "alphabet": list(stage.alphabet),
    }


def _find_stage(stage_id: str) -> Stage:
    for stage in load_stages():
        if stage.id == stage_id:
            return stage
    raise KeyError(f"스테이지 '{stage_id}'를 찾을 수 없어요.")


def list_stages(chapter: str) -> list[dict]:
    """챕터의 스테이지 목록. 정답 기계와 예시 문자열은 화면에 보내지 않는다."""
    return [_stage_info(s) for s in load_stages(chapter)]


def normalize(machine: dict) -> dict:
    """같은 설계면 같은 dict가 되도록 정리한다 (종료 상태와 NFA 도착 상태를 정렬).

    채점 뒤에 설계가 바뀌었는지 비교할 때 쓴다.
    """
    return automaton_from_dict(machine).to_dict()


def validate(machine: dict) -> list[dict]:
    """설계 문제 목록: [{"level": "error" | "warning", "message": str}]"""
    return [{"level": i.level, "message": i.message} for i in automaton_from_dict(machine).validate()]


def is_valid(machine: dict) -> bool:
    """error가 없으면 True. 채점과 실행은 이 값이 True일 때만 한다."""
    return automaton_from_dict(machine).is_valid()


def run(machine: dict, word: str) -> dict:
    """문자열 하나를 실행한다.

    {"type": "dfa", "accepted": bool, "trace": ["q0", "q1", None]}
        DFA: 지나간 상태 목록. 빠진 전이를 만나면 마지막이 None(죽은 상태)이다.
    {"type": "nfa", "accepted": bool, "trace": [["q0"], ["q0", "q1"], []]}
        NFA: 글자를 하나씩 읽을 때마다의 활성 상태 목록 (정렬됨). 빈 목록은 ∅이다.
    """
    automaton = automaton_from_dict(machine)
    result = automaton.run(word)
    if isinstance(automaton, NFA):
        return {
            "type": "nfa",
            "accepted": result.accepted,
            "trace": [sorted(states) for states in result.steps],
        }
    return {"type": "dfa", "accepted": result.accepted, "trace": list(result.path)}


def grade(stage_id: str, machine: dict) -> dict:
    """정답 기계와 비교한 채점 결과. 호출 전에 is_valid(machine)를 확인할 것.

    {"correct": bool, "counterexample": str | None, "expected": bool | None,
     "used_states": int | None, "optimal_states": int | None, "too_large": bool}

    too_large가 True면 NFA를 DFA로 바꾸다가 상태가 MAX_DFA_STATES개를 넘어서 채점하지 못한 것이다.
    """
    return asdict(_grade(_find_stage(stage_id), automaton_from_dict(machine)))


def to_dfa(machine: dict) -> dict | None:
    """NFA를 부분집합 구성으로 바꾼 DFA. DFA를 넣으면 그대로 돌려준다.

    바꾼 DFA의 상태가 MAX_DFA_STATES개를 넘으면 None을 돌려준다.
    """
    automaton = automaton_from_dict(machine)
    if isinstance(automaton, NFA):
        try:
            automaton = automaton.to_dfa()
        except TooManyStatesError:
            return None
    return automaton.to_dict()


def diagram(machine: dict, counterexample: str | None = None) -> str:
    """Graphviz DOT 문자열.

    counterexample을 주면 DFA는 그 문자열을 실행한 경로를, NFA는 끝까지 읽은 뒤 남은 상태를 강조한다.
    강조는 실행할 수 있는(error가 없는) 설계에서만 한다.
    """
    automaton = automaton_from_dict(machine)
    if counterexample is None or not automaton.is_valid():
        return to_dot(automaton)
    result = automaton.run(counterexample)
    if isinstance(automaton, NFA):
        return to_dot(automaton, highlight_states=result.steps[-1])
    return to_dot(automaton, highlight_path=result.path)
