"""화면(app.py)과 엔진 사이의 창구.

화면은 이 모듈만 쓰고, 모든 입력과 출력은 JSON으로 바꿀 수 있는 값(dict, list, str, int, bool, None)이다.
엔진 객체(DFA, NFA)와 결과 dataclass는 이 모듈 밖으로 나가지 않는다.
그래서 엔진 내부 구조를 바꿔도 여기서 돌려주는 형식만 지키면 화면은 고치지 않아도 된다.

기계(machine)는 엔진 문서에 적힌 오토마타 JSON 형식이다. "type"이 "nfa"면 NFA, 없거나 "dfa"면 DFA로 본다.
"""

from __future__ import annotations

import random
from dataclasses import asdict

from .diagram import to_dot
from .engine import LAMBDA, MAX_DFA_STATES, NFA, TooManyStatesError, automaton_from_dict
from .engine.pumping import (
    SMASH_VALUES,
    TemplateError,
    WordTooLongError,
    analyze_splits,
    best_receives,
    build_proof,
    choose_defense,
    choose_receive,
    computer_smash,
    expand_template,
    max_receive_length,
    mistake_rate,
    parse_template,
    pump,
    split_error,
)
from .stages import PumpingStage, Stage, grade as _grade, load_pumping_stages, load_stages

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
    "SMASH_VALUES",
    "MAX_SERVE",
    "list_pumping_stages",
    "pumping_receive",
    "pumping_defend",
    "pumping_smash",
    "pumping_analysis",
    "pumping_proof",
    "pumping_mistake_rate",
    "pumping_computer_receive",
    "pumping_computer_smash",
    "pumping_best_receive",
    "pumping_reveal",
]

MAX_SERVE = 8  # 막는 쪽에서 서브할 수 있는 가장 큰 m (컴퓨터가 리시브 후보를 모두 검사하는 시간 때문)


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


# ---------- 펌핑 게임 ----------
#
# 펌핑 게임은 탁구 4구 랠리로 진행한다. 플레이어는 깨는 쪽(Lemma에 반박)과 막는 쪽(Lemma 편) 중 하나를 고른다.
#
#   깨는 쪽                                           막는 쪽
#   1구 서브: Lemma가 m (스테이지의 m_values 순서)     1구 서브: 플레이어가 m (1 ~ MAX_SERVE)
#   2구 리시브: 플레이어가 w → pumping_receive         2구 리시브: 컴퓨터가 w → pumping_computer_receive
#   3구 수비: Lemma가 분할 → pumping_defend            3구 수비: 플레이어가 분할
#   4구 스매시: 플레이어가 i → pumping_smash           4구 스매시: 컴퓨터가 i → pumping_computer_smash
#
# 컴퓨터는 포인트가 진행될수록 실수를 덜 한다 (pumping_mistake_rate).
# 포인트가 끝나면 pumping_analysis로 모든 수비 코스를, 막는 쪽은 pumping_best_receive로 컴퓨터의 최선 리시브를 보여준다.
# 경기가 끝나면 pumping_reveal로 정규 언어인지 알려주고, 깨는 쪽이 이기면 pumping_proof로 증명문을 만든다.


def _find_pumping_stage(stage_id: str) -> PumpingStage:
    for stage in load_pumping_stages():
        if stage.id == stage_id:
            return stage
    raise KeyError(f"스테이지 '{stage_id}'를 찾을 수 없어요.")


def list_pumping_stages() -> list[dict]:
    """펌핑 게임 스테이지 목록. 언어의 조건식, 정규 언어인지, 예시 문자열, 이기는 w 예시는 보내지 않는다."""
    return [
        {
            "id": s.id,
            "chapter": s.chapter,
            "title": s.title,
            "description": s.description,
            "hint": s.hint,
            "hint_defend": s.hint_defend,
            "notation": s.notation,
            "alphabet": s.language.alphabet,
            "m_values": list(s.m_values),
        }
        for s in load_pumping_stages()
    ]


def pumping_receive(stage_id: str, template: str, m: int) -> dict:
    """리시브(w 템플릿)를 m에 대해 펼치고 규칙을 확인한다.

    {"ok": True, "word": "aaabbb", "error": None, "kind": None}
    {"ok": False, "word": str | None, "error": "화면에 보여줄 이유",
     "kind": "bad_m" | "parse" | "too_long" | "too_short" | "not_in_language"}

    w가 max_receive_length(m)보다 길면 펌핑한 문자열이 판정 상한을 넘을 수 있어서 too_long으로 돌려보낸다.
    길이는 문자열을 만들기 전에 계산한다.
    """
    stage = _find_pumping_stage(stage_id)
    if error := _m_error(m):
        return {"ok": False, "word": None, "error": error, "kind": "bad_m"}
    if not isinstance(template, str):
        return {"ok": False, "word": None, "error": "w는 문자열로 적어주세요.", "kind": "parse"}
    try:
        word = expand_template(parse_template(template, stage.language.alphabet), m,
                               max_length=max_receive_length(m))
    except WordTooLongError as e:
        return {"ok": False, "word": None, "error": str(e), "kind": "too_long"}
    except TemplateError as e:
        return {"ok": False, "word": None, "error": str(e), "kind": "parse"}
    if len(word) < m:
        return {"ok": False, "word": word, "kind": "too_short",
                "error": f"w의 길이({len(word)})가 m({m})보다 짧아요. 펌핑 보조정리는 |w| ≥ m인 w에만 적용돼요."}
    if not stage.language.contains(word):
        return {"ok": False, "word": word, "kind": "not_in_language",
                "error": "w가 L에 속하지 않아요. 리시브는 L 안의 문자열로 해야 해요."}
    return {"ok": True, "word": word, "error": None, "kind": None}


# ---------- 입력 확인 ----------
#
# 펌핑 api는 받은 값을 스스로 확인하고, 문제가 있으면 예외 대신 {"ok": False, "error": ...}를 돌려준다.
# 화면이 확인을 빠뜨려도 앱이 멈추지 않게 하기 위해서다. (스테이지 id가 없는 경우만 KeyError를 낸다.)

MAX_PUMPING_LENGTH = 20  # api가 받는 m의 상한. 리시브 길이 상한(200 - 4m)이 충분히 남도록 정했다.


def _m_error(m) -> str | None:
    if not isinstance(m, int) or isinstance(m, bool) or not 1 <= m <= MAX_PUMPING_LENGTH:
        return f"m은 1부터 {MAX_PUMPING_LENGTH}까지의 정수여야 해요."
    return None


def _word_error(stage: PumpingStage, word, m: int) -> str | None:
    """리시브로 쓸 수 있는 w인지: m이 올바르고, |w| ≥ m, 길이 상한 이하, L에 속함."""
    if error := _m_error(m):
        return error
    if not isinstance(word, str):
        return "w는 문자열이어야 해요."
    if len(word) < m:
        return f"w의 길이({len(word)})가 m({m})보다 짧아요."
    if len(word) > max_receive_length(m):
        return f"w가 너무 길어요. m = {m}일 때 w는 {max_receive_length(m)}글자 이하여야 해요."
    if any(ch not in stage.language.alphabet for ch in word):
        return "w에 이 언어의 글자가 아닌 것이 있어요."
    if not stage.language.contains(word):
        return "w가 L에 속하지 않아요."
    return None


def _split_check(word: str, m: int, start, end) -> str | None:
    if not isinstance(start, int) or not isinstance(end, int) or isinstance(start, bool) or isinstance(end, bool):
        return "분할 위치는 정수여야 해요."
    return split_error(word, m, start, end)


def _split_dict(word: str, start: int, end: int) -> dict:
    return {"start": start, "end": end, "x": word[:start], "y": word[start:end], "z": word[end:]}


def pumping_mistake_rate(point: int) -> float:
    """컴퓨터의 실수 확률. point는 0부터 센다 (1포인트 0.4 → 2포인트 0.3 → 3포인트 0.2 → 이후 0.1)."""
    return mistake_rate(max(0, point) if isinstance(point, int) else 0)


def pumping_defend(stage_id: str, word: str, m: int, seed: int | None = None, point: int = 0) -> dict:
    """Lemma의 수비(분할).

    {"ok": True, "error": None, "start": int, "end": int, "x": str, "y": str, "z": str, "mode": "tough" | "random"}
    {"ok": False, "error": "이유", "start": None, "end": None, "x": None, "y": None, "z": None, "mode": None}
    mode가 "random"이면 가장 까다로운 코스 대신 아무 코스나 고른 것이다 (확률은 pumping_mistake_rate(point)).
    어떤 i가 통하는지는 보내지 않는다.
    """
    stage = _find_pumping_stage(stage_id)
    if error := _word_error(stage, word, m):
        return {"ok": False, "error": error, "start": None, "end": None, "x": None, "y": None, "z": None,
                "mode": None}
    split, mode = choose_defense(
        analyze_splits(stage.language, word, m), random.Random(seed), random_rate=pumping_mistake_rate(point)
    )
    return {"ok": True, "error": None, **_split_dict(word, split.start, split.end), "mode": mode}


def pumping_smash(stage_id: str, word: str, m: int, start: int, end: int, i: int) -> dict:
    """스매시: xyⁱz가 L에 속하는지. in_language가 False면 득점이다.

    {"ok": True, "error": None, "pumped": str, "in_language": bool}
    {"ok": False, "error": "이유", "pumped": None, "in_language": None}
    i는 SMASH_VALUES 안에서만 고를 수 있다.
    """
    stage = _find_pumping_stage(stage_id)
    error = _word_error(stage, word, m) or _split_check(word, m, start, end)
    # bool(True == 1)이나 1.0 같은 값이 i로 들어오지 않도록 정수 타입을 먼저 확인한다.
    if error is None and (type(i) is not int or i not in SMASH_VALUES):
        error = f"i는 {', '.join(map(str, SMASH_VALUES))} 중에서 골라야 해요."
    if error:
        return {"ok": False, "error": error, "pumped": None, "in_language": None}
    pumped = pump(word, start, end, i)
    return {"ok": True, "error": None, "pumped": pumped, "in_language": stage.language.contains(pumped)}


def pumping_analysis(stage_id: str, word: str, m: int) -> dict:
    """모든 수비 코스와 각 코스에서 통하는 스매시.

    {"ok": True, "error": None, "splits": [{"start", "end", "x", "y", "z", "breaking": [i, ...]}],
     "total": int, "beaten": int}
    {"ok": False, "error": "이유", "splits": [], "total": 0, "beaten": 0}
    beaten은 통하는 i가 하나라도 있는 코스 수다. beaten < total이면 막는 쪽이 막을 수 있는 코스가 있다.
    """
    stage = _find_pumping_stage(stage_id)
    if error := _word_error(stage, word, m):
        return {"ok": False, "error": error, "splits": [], "total": 0, "beaten": 0}
    splits = [
        {**_split_dict(word, s.start, s.end), "breaking": list(s.breaking)}
        for s in analyze_splits(stage.language, word, m)
    ]
    return {"ok": True, "error": None, "splits": splits, "total": len(splits),
            "beaten": sum(1 for s in splits if s["breaking"])}


def pumping_proof(stage_id: str, template: str) -> dict:
    """경기 기록(w 템플릿)을 증명문으로 정리한다. 스테이지의 모든 m으로 확인한다.

    {"available": bool, "text": str | None (마크다운, LaTeX 포함), "reason": str | None,
     "smash": int | None, "checked_m": [int] | None}
    """
    stage = _find_pumping_stage(stage_id)
    if not isinstance(template, str):
        return {"available": False, "text": None, "reason": "w는 문자열로 적어주세요.", "smash": None,
                "checked_m": None}
    return asdict(build_proof(stage.language, stage.condition_text, template, stage.m_values))


# ---------- 펌핑 게임: 막는 쪽 ----------


def _serve_error(m) -> str | None:
    if not isinstance(m, int) or isinstance(m, bool) or not 1 <= m <= MAX_SERVE:
        return f"m은 1부터 {MAX_SERVE}까지 고를 수 있어요."
    return None


def pumping_computer_receive(stage_id: str, m: int, point: int = 0, seed: int | None = None) -> dict:
    """막는 쪽 게임에서 컴퓨터의 리시브(w).

    {"ok": True, "word": str, "mode": "best" | "mistake", "error": None}
    {"ok": False, "word": None, "mode": None, "error": "화면에 보여줄 이유"}
    mode가 "mistake"면 최선보다 약한 w를 고른 것이다 (확률은 pumping_mistake_rate(point)).
    """
    stage = _find_pumping_stage(stage_id)
    if error := _serve_error(m):
        return {"ok": False, "word": None, "mode": None, "error": error}
    choice = choose_receive(stage.language, m, random.Random(seed), pumping_mistake_rate(point))
    if choice is None:
        return {"ok": False, "word": None, "mode": None, "error": f"m = {m}일 때 고를 수 있는 w가 없어요."}
    return {"ok": True, "word": choice.word, "mode": choice.mode, "error": None}


def pumping_computer_smash(stage_id: str, word: str, m: int, start: int, end: int) -> dict:
    """막는 쪽 게임에서 플레이어의 수비(분할)에 대한 컴퓨터의 스매시.

    {"ok": False, "error": "이유 (분할 규칙 위반 등)", "i": None, "pumped": None, "in_language": None}
    {"ok": True, "error": None, "i": int | None, "pumped": str | None, "in_language": bool}
    i가 None이면 컴퓨터가 SMASH_VALUES의 어떤 i로도 L 밖으로 보내지 못한 것이다 (막는 쪽 득점).
    이때 pumped는 None, in_language는 True다.
    """
    stage = _find_pumping_stage(stage_id)
    error = _serve_error(m) or _word_error(stage, word, m) or _split_check(word, m, start, end)
    if error:
        return {"ok": False, "error": error, "i": None, "pumped": None, "in_language": None}
    i = computer_smash(stage.language, word, start, end)
    if i is None:
        return {"ok": True, "error": None, "i": None, "pumped": None, "in_language": True}
    return {"ok": True, "error": None, "i": i, "pumped": pump(word, start, end, i), "in_language": False}


def pumping_best_receive(stage_id: str, m: int) -> dict:
    """이 m에서 어떤 수비도 뚫는 리시브(w)들. 포인트가 끝난 뒤 막는 쪽에 보여준다.

    {"ok": True, "error": None, "winning_words": [str, ...] (짧은 것부터 최대 3개), "winning_count": int, "total": int}
    {"ok": False, "error": "이유", "winning_words": [], "winning_count": 0, "total": 0}
    winning_count가 0이면 이 m에서는 막는 쪽이 어떤 w도 막을 수 있다.
    """
    stage = _find_pumping_stage(stage_id)
    if error := _serve_error(m):
        return {"ok": False, "error": error, "winning_words": [], "winning_count": 0, "total": 0}
    winning, total = best_receives(stage.language, m)
    return {"ok": True, "error": None, "winning_words": winning[:3], "winning_count": len(winning), "total": total}


def pumping_reveal(stage_id: str) -> dict:
    """경기가 끝난 뒤에만 부른다: {"regular": bool}"""
    return {"regular": _find_pumping_stage(stage_id).regular}
