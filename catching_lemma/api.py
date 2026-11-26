"""화면(app.py)과 엔진 사이의 창구.

화면은 이 모듈만 쓰고, 모든 입력과 출력은 JSON으로 바꿀 수 있는 값(dict, list, str, int, bool, None)이다.
엔진 객체(DFA, NFA)와 결과 dataclass는 이 모듈 밖으로 나가지 않는다.
그래서 엔진 내부 구조를 바꿔도 여기서 돌려주는 형식만 지키면 화면은 고치지 않아도 된다.

기계(machine)는 엔진 문서에 적힌 오토마타 JSON 형식이다. "type"이 "nfa"면 NFA, 없거나 "dfa"면 DFA로 본다.
"""

from __future__ import annotations

import random
from dataclasses import asdict
from functools import lru_cache

from .diagram import to_dot
from .engine import LAMBDA, MAX_DFA_STATES, NFA, TooManyStatesError, automaton_from_dict
from .engine.pumping import (
    MAX_TEMPLATE_LENGTH,
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
    receive_scores,
    split_error,
)
from .engine.cfl_pumping import (
    analyze_cfl_splits,
    case_key,
    cfl_parts,
    cfl_pump,
    cfl_receive_scores,
    cfl_split_error,
    letter_runs,
    summarize_cases,
)
from .engine.cfl_pumping import cfl_case_report as cfl_case_report_engine
from .engine.cfl_pumping import cfl_computer_smash as cfl_computer_smash_engine
from .stages import MAX_SERVE, PumpingStage, Stage, grade as _grade, load_pumping_stages, load_stages

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
    "cfl_defend",
    "cfl_smash",
    "cfl_analysis",
    "cfl_case_report",
    "cfl_computer_receive",
    "cfl_computer_smash",
    "cfl_best_receive",
    "cfl_reveal",
]

# MAX_SERVE: 막는 쪽에서 서브할 수 있는 m의 최대값 (stages.MAX_SERVE). 스테이지마다 max_serve로 더 낮출 수 있다.


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


def _find_pumping_stage(stage_id: str, chapter: str | None = None) -> PumpingStage:
    """펌핑 스테이지를 찾는다. chapter를 주면 그 장의 스테이지만 찾는다 (다른 장의 엔진으로 계산하지 않도록)."""
    for stage in load_pumping_stages(chapter):
        if stage.id == stage_id:
            return stage
    raise KeyError(f"스테이지 '{stage_id}'를 찾을 수 없어요.")


def list_pumping_stages(chapter: str = "pumping") -> list[dict]:
    """펌핑 게임 스테이지 목록 (chapter: "pumping" 정규, "cfl_pumping" 문맥자유).

    언어의 조건식, 정답(정규/문맥자유 언어인지), 예시 문자열, 이기는 w 예시는 보내지 않는다.
    """
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
            "max_serve": s.max_serve,
        }
        for s in load_pumping_stages(chapter)
    ]


def pumping_receive(stage_id: str, template: str, m: int) -> dict:
    """리시브(w 템플릿)를 m에 대해 펼치고 규칙을 확인한다.

    {"ok": True, "word": "aaabbb", "error": None, "kind": None}
    {"ok": False, "word": str | None, "error": "화면에 보여줄 이유",
     "kind": "bad_m" | "parse" | "too_long" | "too_short" | "not_in_language"}

    w가 max_receive_length(m)보다 길면 펌핑한 문자열이 판정 상한을 넘을 수 있어서 too_long으로 돌려보낸다.
    길이는 문자열을 만들기 전에 계산한다. 정규·문맥자유 두 장에서 같이 쓴다
    (문맥자유 분할도 |vy| ≤ m이라 펌핑한 문자열의 길이가 같은 범위 안에 있다).
    """
    stage = _find_pumping_stage(stage_id)
    # 문맥자유 스테이지는 수비(cfl_defend)와 같은 m 상한을 쓴다. 리시브만 통과하고 수비에서 거부되는 m이 없게 하기 위해서다.
    error = _cfl_m_error(m, stage) if stage.chapter == "cfl_pumping" else _m_error(m)
    if error:
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
    stage = _find_pumping_stage(stage_id, "pumping")
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
    stage = _find_pumping_stage(stage_id, "pumping")
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
    stage = _find_pumping_stage(stage_id, "pumping")
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
    stage = _find_pumping_stage(stage_id, "pumping")
    if not isinstance(template, str):
        return {"available": False, "text": None, "reason": "w는 문자열로 적어주세요.", "smash": None,
                "checked_m": None}
    return asdict(build_proof(stage.language, stage.condition_text, template, stage.m_values))


# ---------- 펌핑 게임: 막는 쪽 ----------


def _serve_error(m, stage: PumpingStage) -> str | None:
    """막는 쪽 서브(m) 확인. 스테이지의 max_serve까지 고를 수 있다."""
    if not isinstance(m, int) or isinstance(m, bool) or not 1 <= m <= stage.max_serve:
        return f"m은 1부터 {stage.max_serve}까지 고를 수 있어요."
    return None


@lru_cache(maxsize=128)
def _receive_scores(stage_id: str, m: int):
    """(스테이지, m)마다 후보 w의 점수를 한 번만 계산한다.

    컴퓨터의 리시브와 포인트 뒤 '최선의 리시브' 안내가 같은 계산을 쓰고, 같은 m을 다시 서브하면 바로 돌려준다.
    결과는 바뀌지 않는 tuple이라 여러 세션이 같이 써도 안전하다. m은 _serve_error로 확인한 뒤에만 넘긴다.
    """
    return receive_scores(_find_pumping_stage(stage_id, "pumping").language, m)


def pumping_computer_receive(stage_id: str, m: int, point: int = 0, seed: int | None = None) -> dict:
    """막는 쪽 게임에서 컴퓨터의 리시브(w).

    {"ok": True, "word": str, "mode": "best" | "mistake", "error": None}
    {"ok": False, "word": None, "mode": None, "error": "화면에 보여줄 이유"}
    mode가 "mistake"면 최선보다 약한 w를 고른 것이다 (확률은 pumping_mistake_rate(point)).
    """
    stage = _find_pumping_stage(stage_id, "pumping")
    if error := _serve_error(m, stage):
        return {"ok": False, "word": None, "mode": None, "error": error}
    choice = choose_receive(
        stage.language, m, random.Random(seed), pumping_mistake_rate(point), scores=_receive_scores(stage_id, m)
    )
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
    stage = _find_pumping_stage(stage_id, "pumping")
    error = _serve_error(m, stage) or _word_error(stage, word, m) or _split_check(word, m, start, end)
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
    stage = _find_pumping_stage(stage_id, "pumping")
    if error := _serve_error(m, stage):
        return {"ok": False, "error": error, "winning_words": [], "winning_count": 0, "total": 0}
    winning, total = best_receives(stage.language, m, scores=_receive_scores(stage_id, m))
    return {"ok": True, "error": None, "winning_words": winning[:3], "winning_count": len(winning), "total": total}


def pumping_reveal(stage_id: str) -> dict:
    """경기가 끝난 뒤에만 부른다: {"regular": bool}"""
    return {"regular": _find_pumping_stage(stage_id, "pumping").regular}


# ---------- 문맥자유 펌핑 게임 ----------
#
# 진행은 정규 펌핑 게임과 같고 분할만 w = uvxyz (|vxy| ≤ m, |vy| ≥ 1)로 바뀐다.
# 분할은 경계 위치 네 개 cuts = [p1, p2, p3, p4]로 주고받는다: u = w[:p1], v = w[p1:p2], x = w[p2:p3], y = w[p3:p4], z = w[p4:]
#
#   깨는 쪽                                         막는 쪽
#   1구 서브: Lemma가 m (m_values)                  1구 서브: 플레이어가 m (1 ~ 스테이지의 max_serve)
#   2구 리시브: 플레이어가 w → pumping_receive       2구 리시브: 컴퓨터가 w → cfl_computer_receive
#   3구 수비: Lemma가 분할 → cfl_defend              3구 수비: 플레이어가 분할
#   4구 스매시: 플레이어가 i → cfl_smash             4구 스매시: 컴퓨터가 i → cfl_computer_smash
#
# m은 1 ~ cfl_max_m(스테이지)만 받는다 (정규 게임의 20보다 작다. 문맥자유 분할 계산은 m³에 비례해서).
# 포인트가 끝나면 cfl_analysis로 모든 수비 코스를 경우(v, y가 어느 글자 블록에 있는가)별로 묶어 보여준다.
# 경기가 끝나면 cfl_reveal로 문맥자유 언어인지 알려주고, 깨는 쪽이 이기면 cfl_case_report로 경우별 정리 표를 만든다.


def _cuts_dict(word: str, cuts) -> dict:
    u, v, x, y, z = cfl_parts(word, tuple(cuts))
    return {"cuts": list(cuts), "u": u, "v": v, "x": x, "y": y, "z": z}


_NO_CUTS = {"cuts": None, "u": None, "v": None, "x": None, "y": None, "z": None}


def cfl_max_m(stage: PumpingStage) -> int:
    """문맥자유 api가 받는 m의 상한: 깨는 쪽에서 Lemma가 서브하는 m(m_values)과 막는 쪽 서브(1 ~ max_serve)를 모두 덮는 값.

    정규 게임은 분할 수가 m²에 비례해서 m = 20(MAX_PUMPING_LENGTH)도 금방 끝나지만, 문맥자유 게임은 |w| × m³에
    비례해서 m = 20이면 수비 계산에 15초가 걸린다. 그래서 화면에서 쓰는 범위까지만 받는다.
    m_values에 든 값만 받으면 안 된다: 막는 쪽에서 1, 2, 8처럼 m_values 밖의 m을 서브해도 포인트 뒤 cfl_analysis가 그 m으로 불린다.
    """
    return max(stage.max_serve, max(stage.m_values))


def _cfl_m_error(m, stage: PumpingStage) -> str | None:
    if not isinstance(m, int) or isinstance(m, bool) or not 1 <= m <= cfl_max_m(stage):
        return f"m은 1부터 {cfl_max_m(stage)}까지의 정수여야 해요."
    return None


CFL_SPLIT_CACHE_SIZE = 8  # 분석 결과 하나가 최대 약 3.4MB(168글자 w, m = 8, 분할 약 25,000개)라 상한을 작게 둔다


@lru_cache(maxsize=CFL_SPLIT_CACHE_SIZE)
def _cfl_splits(stage_id: str, word: str, m: int):
    """(스테이지, w, m)의 모든 분할 분석. 입력 확인 뒤에만 부른다.

    같은 포인트 안에서 Lemma의 수비(cfl_defend)와 포인트 뒤 분석(cfl_analysis)이 같은 결과를 쓰려는 용도라
    오래 들고 있을 필요가 없다. 키에 사용자가 입력한 w가 들어가므로 상한을 작게 둬서 메모리가 쌓이지 않게 한다
    (최악 약 27MB). 다른 사람의 요청으로 밀려나도 다시 계산할 뿐 결과는 같다.
    """
    return tuple(analyze_cfl_splits(_find_pumping_stage(stage_id, "cfl_pumping").language, word, m))


def cfl_defend(stage_id: str, word: str, m: int, seed: int | None = None, point: int = 0) -> dict:
    """Lemma의 수비(분할 uvxyz).

    {"ok": True, "error": None, "cuts": [p1, p2, p3, p4], "u", "v", "x", "y", "z": str, "mode": "tough" | "random"}
    {"ok": False, "error": "이유", "cuts": None, ..., "mode": None}
    """
    stage = _find_pumping_stage(stage_id, "cfl_pumping")
    if error := _cfl_m_error(m, stage) or _word_error(stage, word, m):
        return {"ok": False, "error": error, **_NO_CUTS, "mode": None}
    split, mode = choose_defense(
        list(_cfl_splits(stage_id, word, m)), random.Random(seed), random_rate=pumping_mistake_rate(point)
    )
    return {"ok": True, "error": None, **_cuts_dict(word, split.cuts), "mode": mode}


def cfl_smash(stage_id: str, word: str, m: int, cuts, i: int) -> dict:
    """스매시: uvⁱxyⁱz가 L에 속하는지. in_language가 False면 득점이다.

    {"ok": True, "error": None, "pumped": str, "in_language": bool}
    {"ok": False, "error": "이유", "pumped": None, "in_language": None}
    """
    stage = _find_pumping_stage(stage_id, "cfl_pumping")
    error = _cfl_m_error(m, stage) or _word_error(stage, word, m) or cfl_split_error(word, m, cuts)
    if error is None and (type(i) is not int or i not in SMASH_VALUES):
        error = f"i는 {', '.join(map(str, SMASH_VALUES))} 중에서 골라야 해요."
    if error:
        return {"ok": False, "error": error, "pumped": None, "in_language": None}
    pumped = cfl_pump(word, tuple(cuts), i)
    return {"ok": True, "error": None, "pumped": pumped, "in_language": stage.language.contains(pumped)}


def cfl_analysis(stage_id: str, word: str, m: int) -> dict:
    """모든 수비 코스와, 그것을 경우별로 묶은 표.

    {"ok": True, "error": None,
     "splits": [{"cuts", "u", "v", "x", "y", "z", "breaking": [i, ...], "case": 경우 번호}],
     "cases": [{"label": str, "total": int, "blockable": int, "common_i": [i, ...], "example": {"cuts", "u", ...}}],
     "total": int, "beaten": int}
    {"ok": False, "error": "이유", "splits": [], "cases": [], "total": 0, "beaten": 0}
    blockable은 그 경우에서 어떤 i로도 뚫리지 않는(막는 쪽이 이기는) 분할 수, common_i는 그 경우의 모든 분할을 뚫는 i다.
    """
    stage = _find_pumping_stage(stage_id, "cfl_pumping")
    if error := _cfl_m_error(m, stage) or _word_error(stage, word, m):
        return {"ok": False, "error": error, "splits": [], "cases": [], "total": 0, "beaten": 0}
    splits = list(_cfl_splits(stage_id, word, m))
    cases = summarize_cases(word, splits)
    runs = letter_runs(word)
    index = {c.key: n for n, c in enumerate(cases)}
    return {
        "ok": True,
        "error": None,
        "splits": [
            {**_cuts_dict(word, s.cuts), "breaking": list(s.breaking), "case": index[case_key(runs, s.cuts)]}
            for s in splits
        ],
        "cases": [
            {"label": c.label, "total": c.total, "blockable": c.blockable, "common_i": list(c.common_i),
             "example": _cuts_dict(word, c.example)}
            for c in cases
        ],
        "total": len(splits),
        "beaten": sum(1 for s in splits if s.breaking),
    }


CFL_CASE_REPORT_CACHE_SIZE = 16


@lru_cache(maxsize=CFL_CASE_REPORT_CACHE_SIZE)
def _cfl_case_report(stage_id: str, template: str):
    """(스테이지, 템플릿)마다 경우별 정리 표를 한 번만 만든다.

    Streamlit은 경기가 끝난 화면을 버튼이나 펼침 영역을 누를 때마다 다시 그리는데, 결과는 스테이지와 템플릿이 같으면
    항상 같다. 템플릿은 100글자 이하(MAX_TEMPLATE_LENGTH)라 키가 작다. 캐시한 엔진 결과는 밖으로 내보내지 않고,
    cfl_case_report가 매번 새 dict로 바꿔서 돌려준다 (세션끼리 같은 객체를 나눠 쓰지 않도록).
    """
    stage = _find_pumping_stage(stage_id, "cfl_pumping")
    return cfl_case_report_engine(stage.language, template, stage.m_values)


def cfl_case_report(stage_id: str, template: str) -> dict:
    """깨는 쪽이 이겼을 때 경기 기록(w 템플릿)을 경우별 정리 표로 만든다. 스테이지의 모든 m으로 확인한다.

    {"available": bool, "reason": str | None, "checked_m": [int] | None,
     "rows": [{"label": str, "smash": [i, ...], "example": {"u", "v", "x", "y", "z"}, "example_m": int}]}
    """
    _find_pumping_stage(stage_id, "cfl_pumping")
    if not isinstance(template, str):
        return {"available": False, "reason": "w는 문자열로 적어주세요.", "checked_m": None, "rows": []}
    # 캐시 키에는 앞뒤 공백을 뺀, 길이 상한 이하의 템플릿만 넣는다 (공백을 붙인 긴 입력이 캐시에 그대로 남지 않도록).
    template = template.strip()
    if len(template) > MAX_TEMPLATE_LENGTH:
        return {"available": False, "reason": f"w는 {MAX_TEMPLATE_LENGTH}글자 이내로 적어주세요.",
                "checked_m": None, "rows": []}
    report = _cfl_case_report(stage_id, template)
    return {
        "available": report.available,
        "reason": report.reason,
        "checked_m": None if report.checked_m is None else list(report.checked_m),  # 캐시한 목록을 그대로 내보내지 않는다
        "rows": [
            {"label": r.label, "smash": list(r.smash), "example_m": r.example_m,
             "example": dict(zip(("u", "v", "x", "y", "z"), r.example))}
            for r in report.rows
        ],
    }


@lru_cache(maxsize=128)
def _cfl_receive_scores(stage_id: str, m: int):
    """(스테이지, m)마다 후보 w의 점수를 한 번만 계산한다 (정규 게임의 _receive_scores와 같은 역할).

    키는 스테이지와 확인을 거친 m(1 ~ max_serve)뿐이라 개수가 스테이지 수 × 8개를 넘지 않고, 하나가 0.5MB 이하다.
    """
    return cfl_receive_scores(_find_pumping_stage(stage_id, "cfl_pumping").language, m)


def cfl_computer_receive(stage_id: str, m: int, point: int = 0, seed: int | None = None) -> dict:
    """막는 쪽 게임에서 컴퓨터의 리시브(w). 후보 길이는 m ~ 3m + 3이다.

    {"ok": True, "word": str, "mode": "best" | "mistake", "error": None}
    {"ok": False, "word": None, "mode": None, "error": "화면에 보여줄 이유"}
    """
    stage = _find_pumping_stage(stage_id, "cfl_pumping")
    if error := _serve_error(m, stage):
        return {"ok": False, "word": None, "mode": None, "error": error}
    choice = choose_receive(
        stage.language, m, random.Random(seed), pumping_mistake_rate(point), scores=_cfl_receive_scores(stage_id, m)
    )
    if choice is None:
        return {"ok": False, "word": None, "mode": None, "error": f"m = {m}일 때 고를 수 있는 w가 없어요."}
    return {"ok": True, "word": choice.word, "mode": choice.mode, "error": None}


def cfl_computer_smash(stage_id: str, word: str, m: int, cuts) -> dict:
    """막는 쪽 게임에서 플레이어의 수비(분할)에 대한 컴퓨터의 스매시. 실수(헛스윙)는 하지 않는다.

    {"ok": True, "error": None, "i": int | None, "pumped": str | None, "in_language": bool}
    i가 None이면 어떤 i로도 L 밖으로 보내지 못한 것이다 (막는 쪽 득점).
    """
    stage = _find_pumping_stage(stage_id, "cfl_pumping")
    error = _serve_error(m, stage) or _word_error(stage, word, m) or cfl_split_error(word, m, cuts)
    if error:
        return {"ok": False, "error": error, "i": None, "pumped": None, "in_language": None}
    i = cfl_computer_smash_engine(stage.language, word, tuple(cuts))
    if i is None:
        return {"ok": True, "error": None, "i": None, "pumped": None, "in_language": True}
    return {"ok": True, "error": None, "i": i, "pumped": cfl_pump(word, tuple(cuts), i), "in_language": False}


def cfl_best_receive(stage_id: str, m: int) -> dict:
    """이 m에서 어떤 수비도 뚫는 리시브(w)들. 형식은 pumping_best_receive와 같다."""
    stage = _find_pumping_stage(stage_id, "cfl_pumping")
    if error := _serve_error(m, stage):
        return {"ok": False, "error": error, "winning_words": [], "winning_count": 0, "total": 0}
    winning, total = best_receives(stage.language, m, scores=_cfl_receive_scores(stage_id, m))
    return {"ok": True, "error": None, "winning_words": winning[:3], "winning_count": len(winning), "total": total}


def cfl_reveal(stage_id: str) -> dict:
    """경기가 끝난 뒤에만 부른다: {"context_free": bool}"""
    return {"context_free": _find_pumping_stage(stage_id, "cfl_pumping").context_free}
