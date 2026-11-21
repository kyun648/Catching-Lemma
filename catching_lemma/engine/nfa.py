"""NFA 표현, 검증, 실행(상태 집합 추적), 부분집합 구성으로 DFA 변환.

DFA와 같은 JSON 형식을 쓰되, 전이의 도착지가 상태 '목록'이고 λ(빈 문자열) 전이를 허용한다.

    {
      "type": "nfa",
      "states": ["q0", "q1"],
      "alphabet": ["a", "b"],
      "start": "q0",
      "accept": ["q1"],
      "transitions": {"q0": {"a": ["q0", "q1"], "λ": ["q1"]}},
      "layout": {}
    }

NFA는 전이가 비어 있는 것이 자연스러우므로, 빠진 전이는 경고하지 않는다.
채점은 to_dfa()로 DFA로 바꾼 뒤 DFA 엔진의 반례 탐색을 그대로 쓴다.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .dfa import DFA, Issue

LAMBDA = "λ"


def set_name(states: frozenset) -> str:
    """상태 집합을 DFA 상태 이름으로 바꾼다. 예: {q0, q1} → "{q0,q1}" """
    return "{" + ",".join(sorted(states)) + "}"


@dataclass
class NFARunResult:
    accepted: bool
    steps: list[frozenset]  # steps[0]은 시작 상태의 λ-closure, steps[i]는 i번째 글자를 읽은 뒤의 상태 집합


@dataclass
class NFA:
    states: list[str]
    alphabet: list[str]
    start: str
    accept: set[str]
    transitions: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    layout: dict[str, list[float]] = field(default_factory=dict)

    # ---------- 변환 ----------

    @classmethod
    def from_dict(cls, data: dict) -> "NFA":
        return cls(
            states=list(data.get("states", [])),
            alphabet=list(data.get("alphabet", [])),
            start=data.get("start", ""),
            accept=set(data.get("accept", [])),
            transitions={
                s: {sym: list(dsts) for sym, dsts in row.items()}
                for s, row in data.get("transitions", {}).items()
            },
            layout=dict(data.get("layout", {})),
        )

    def to_dict(self) -> dict:
        return {
            "type": "nfa",
            "states": list(self.states),
            "alphabet": list(self.alphabet),
            "start": self.start,
            "accept": sorted(self.accept),
            "transitions": {
                s: {sym: sorted(dsts) for sym, dsts in row.items()}
                for s, row in self.transitions.items()
            },
            "layout": dict(self.layout),
        }

    # ---------- 검증 ----------

    def validate(self) -> list[Issue]:
        issues: list[Issue] = []
        state_set = set(self.states)

        if not self.states:
            issues.append(Issue("error", "상태가 하나도 없어요."))
        if len(state_set) != len(self.states):
            issues.append(Issue("error", "같은 이름의 상태가 두 번 이상 있어요."))
        for sym in self.alphabet:
            if len(sym) != 1:
                issues.append(Issue("error", f"입력 기호 '{sym}'는 한 글자여야 해요."))
            if sym == LAMBDA:
                issues.append(Issue("error", f"'{LAMBDA}'는 빈 문자열 전용이라 입력 기호로 쓸 수 없어요."))
        if self.start not in state_set:
            issues.append(Issue("error", "시작 상태를 정해주세요."))
        for s in sorted(self.accept - state_set):
            issues.append(Issue("error", f"종료 상태 '{s}'가 상태 목록에 없어요."))

        for src, row in self.transitions.items():
            if src not in state_set:
                issues.append(Issue("error", f"전이표에 없는 상태 '{src}'가 있어요."))
                continue
            for sym, dsts in row.items():
                if sym != LAMBDA and sym not in self.alphabet:
                    issues.append(
                        Issue("error", f"{src}에서 알파벳에 없는 기호 '{sym}'를 쓰고 있어요.")
                    )
                for dst in dsts:
                    if dst not in state_set:
                        label = "λ" if sym == LAMBDA else sym
                        issues.append(
                            Issue("error", f"{src} --{label}--> '{dst}': 없는 상태로 가요.")
                        )
        return issues

    def is_valid(self) -> bool:
        return not any(i.level == "error" for i in self.validate())

    # ---------- 실행 ----------

    def lambda_closure(self, states) -> frozenset:
        """주어진 상태들에서 λ 전이만으로 갈 수 있는 모든 상태 (자기 자신 포함)."""
        result = set(states)
        stack = list(states)
        while stack:
            s = stack.pop()
            for t in self.transitions.get(s, {}).get(LAMBDA, []):
                if t not in result:
                    result.add(t)
                    stack.append(t)
        return frozenset(result)

    def step(self, states: frozenset, symbol: str) -> frozenset:
        """상태 집합에서 symbol 하나를 읽은 뒤의 상태 집합 (λ-closure 포함)."""
        moved = set()
        for s in states:
            moved.update(self.transitions.get(s, {}).get(symbol, []))
        return self.lambda_closure(moved)

    def run(self, word: str) -> NFARunResult:
        current = self.lambda_closure({self.start})
        steps = [current]
        for ch in word:
            current = self.step(current, ch)
            steps.append(current)
        return NFARunResult(accepted=bool(current & self.accept), steps=steps)

    def accepts(self, word: str) -> bool:
        return self.run(word).accepted

    # ---------- DFA 변환 ----------

    def to_dfa(self) -> DFA:
        """부분집합 구성(subset construction).

        DFA의 각 상태는 NFA 상태들의 집합이다. 시작 상태의 λ-closure에서 출발해
        도달 가능한 집합만 만든다. 빈 집합으로 가는 전이는 만들지 않고 비워둔다.
        (DFA 엔진은 빠진 전이를 죽은 상태로 처리하므로 같은 의미다.)
        """
        start = self.lambda_closure({self.start})
        names = {start: set_name(start)}
        order = [start]
        transitions: dict[str, dict[str, str]] = {}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for sym in self.alphabet:
                nxt = self.step(current, sym)
                if not nxt:
                    continue
                if nxt not in names:
                    names[nxt] = set_name(nxt)
                    order.append(nxt)
                    queue.append(nxt)
                transitions.setdefault(names[current], {})[sym] = names[nxt]

        return DFA(
            states=[names[s] for s in order],
            alphabet=list(self.alphabet),
            start=names[start],
            accept={names[s] for s in order if s & self.accept},
            transitions=transitions,
        )
