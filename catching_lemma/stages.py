"""스테이지 정의(JSON) 불러오기와 채점."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .engine import (
    DFA,
    NFA,
    TooManyStatesError,
    automaton_from_dict,
    find_counterexample,
    minimal_state_count,
)
from .engine.pumping_common import BlockLanguage

STAGE_DIR = Path(__file__).parent / "stage_data"


@dataclass
class Stage:
    id: str
    chapter: str  # "dfa" 또는 "nfa"
    title: str
    description: str
    alphabet: list[str]
    reference: DFA | NFA  # 정답 기계. 같은 언어이기만 하면 어떤 모양이든 정답으로 인정한다.
    hint: str = ""
    # 설명에 쓴 예시 문자열. 테스트에서 정답 기계와 맞는지 확인한다.
    examples_accept: list[str] = field(default_factory=list)
    examples_reject: list[str] = field(default_factory=list)

    @property
    def reference_dfa(self) -> DFA:
        return to_dfa(self.reference)


@dataclass
class GradeResult:
    correct: bool
    counterexample: str | None = None
    expected: bool | None = None  # 반례를 정답 기계가 받아들이는지
    used_states: int | None = None  # 플레이어 설계의 상태 수 (DFA는 완전한 DFA 기준)
    optimal_states: int | None = None  # 같은 언어의 최소 DFA 상태 수 (완전한 DFA 기준)
    too_large: bool = False  # NFA를 DFA로 바꾸다가 상태 수 상한을 넘어서 채점하지 못함


def to_dfa(automaton: DFA | NFA) -> DFA:
    return automaton.to_dfa() if isinstance(automaton, NFA) else automaton


def load_stages(chapter: str | None = None) -> list[Stage]:
    """오토마타 설계 스테이지(DFA, NFA). 펌핑 게임 스테이지는 load_pumping_stages()로 불러온다."""
    stages = []
    for path in sorted(STAGE_DIR.glob("*/*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["chapter"] in PUMPING_CHAPTERS:
            continue
        if chapter and data["chapter"] != chapter:
            continue
        examples = data.get("examples", {})
        stages.append(
            Stage(
                id=data["id"],
                chapter=data["chapter"],
                title=data["title"],
                description=data["description"],
                alphabet=data["alphabet"],
                reference=automaton_from_dict(data["reference"]),
                hint=data.get("hint", ""),
                examples_accept=examples.get("accept", []),
                examples_reject=examples.get("reject", []),
            )
        )
    return stages


def grade(stage: Stage, candidate: DFA | NFA) -> GradeResult:
    """플레이어 설계를 정답 기계와 비교한다. 호출 전에 candidate.is_valid()를 확인할 것.

    NFA는 부분집합 구성으로 DFA로 바꾼 뒤 비교한다. 상태 수 비교는 DFA 챕터에서만 의미가 있다.
    바꾼 DFA가 상태 수 상한을 넘으면 채점하지 않고 too_large=True를 돌려준다.
    """
    reference = stage.reference_dfa
    optimal = minimal_state_count(reference)
    try:
        candidate_dfa = to_dfa(candidate)
    except TooManyStatesError:
        return GradeResult(correct=False, too_large=True, optimal_states=optimal)
    cex = find_counterexample(candidate_dfa, reference)
    if cex is None:
        if isinstance(candidate, NFA):
            used = len(candidate.states)
        else:
            used = candidate.completed_state_count()
        return GradeResult(correct=True, used_states=used, optimal_states=optimal)
    return GradeResult(
        correct=False,
        counterexample=cex,
        expected=reference.accepts(cex),
        optimal_states=optimal,
    )


# ---------- 펌핑 게임 스테이지 ----------

# 펌핑 게임 장과, 그 장의 JSON에서 "막는 쪽이 이길 수 있는 언어인지"를 적는 키
PUMPING_CHAPTERS = {
    "pumping": "regular",  # 정규 펌핑 게임 (w = xyz)
    "cfl_pumping": "context_free",  # 문맥자유 펌핑 게임 (w = uvxyz)
}
MAX_SERVE = 8  # 막는 쪽에서 서브할 수 있는 m의 최대값. 스테이지 JSON의 max_serve로 더 낮출 수 있다.


@dataclass
class PumpingStage:
    id: str
    chapter: str  # "pumping" 또는 "cfl_pumping"
    title: str
    description: str
    notation: str  # 언어 표기 (LaTeX)
    condition_text: str  # 증명문에 쓰는 조건 설명. 예: "a의 개수와 b의 개수가 같다"
    language: BlockLanguage
    m_values: list[int]  # 깨는 쪽 게임에서 포인트마다 Lemma가 서브하는 m
    # 막는 쪽이 이길 수 있는 언어인지: 정규 펌핑 장은 정규 언어인지, 문맥자유 펌핑 장은 문맥자유 언어인지.
    # 화면에는 경기가 끝난 뒤에만 알려준다.
    pumpable: bool
    max_serve: int = MAX_SERVE  # 막는 쪽에서 서브할 수 있는 m의 최대값 (컴퓨터의 리시브 계산 시간 때문에 언어마다 다르게 둘 수 있다)
    hint: str = ""  # 깨는 쪽 힌트
    hint_defend: str = ""  # 막는 쪽 힌트
    examples_accept: list[str] = field(default_factory=list)
    examples_reject: list[str] = field(default_factory=list)
    sample_receive: str = ""  # 막을 수 없는 언어에서 이기는 w 템플릿 예시. 테스트에서만 쓰고 화면에는 보내지 않는다.

    @property
    def regular(self) -> bool | None:
        """정규 언어인지. 정규 펌핑 장에서만 알 수 있다 (문맥자유 펌핑 장에서는 None)."""
        return self.pumpable if self.chapter == "pumping" else None

    @property
    def context_free(self) -> bool | None:
        """문맥자유 언어인지. 문맥자유 펌핑 장에서만 알 수 있다 (정규 펌핑 장에서는 None)."""
        return self.pumpable if self.chapter == "cfl_pumping" else None


def load_pumping_stages(chapter: str | None = "pumping") -> list[PumpingStage]:
    """펌핑 게임 스테이지. chapter가 None이면 두 장 모두 불러온다."""
    stages = []
    for path in sorted(STAGE_DIR.glob("*/*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["chapter"] not in PUMPING_CHAPTERS:
            continue
        if chapter and data["chapter"] != chapter:
            continue
        lang = data["language"]
        examples = data.get("examples", {})
        stages.append(
            PumpingStage(
                id=data["id"],
                chapter=data["chapter"],
                title=data["title"],
                description=data["description"],
                notation=lang["notation"],
                condition_text=lang["condition_text"],
                language=BlockLanguage(blocks=list(lang["blocks"]), constraint=lang["constraint"]),
                m_values=list(data["m_values"]),
                pumpable=bool(data[PUMPING_CHAPTERS[data["chapter"]]]),
                max_serve=int(data.get("max_serve", MAX_SERVE)),
                hint=data.get("hint", ""),
                hint_defend=data.get("hint_defend", ""),
                examples_accept=examples.get("accept", []),
                examples_reject=examples.get("reject", []),
                sample_receive=data.get("sample_receive", ""),
            )
        )
    return stages
