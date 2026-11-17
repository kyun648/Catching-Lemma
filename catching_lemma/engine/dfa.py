"""DFA 표현, 검증, 실행, 반례 탐색, 최소 상태 수 계산.

오토마타 데이터는 항상 dict(JSON) 형식을 기준으로 주고받는다.
입력 화면(전이표, 나중에 붙일 드래그 편집기)은 이 형식만 만들어 내면 된다.

    {
      "type": "dfa",
      "states": ["q0", "q1"],
      "alphabet": ["a", "b"],
      "start": "q0",
      "accept": ["q1"],
      "transitions": {"q0": {"a": "q1"}, "q1": {"a": "q1", "b": "q0"}},
      "layout": {}            # 선택: 상태별 화면 좌표 (드래그 편집용)
    }

전이가 빠져 있으면 "보이지 않는 죽은 상태(dead state)"로 가서 거부하는 것으로 처리한다.
플레이어가 만든 미완성 설계도 채점할 수 있게 하기 위해서다.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

DEAD = None  # 빠진 전이가 향하는 가상의 죽은 상태


@dataclass
class Issue:
    """설계에서 발견한 문제. level은 "error"(채점 불가) 또는 "warning"(채점은 가능)."""

    level: str
    message: str


@dataclass
class RunResult:
    """문자열 하나를 실행한 결과."""

    accepted: bool
    path: list  # 지나간 상태 목록. 죽은 상태에 빠지면 마지막 원소가 None
    stuck_at: int | None = None  # 빠진 전이를 만난 입력 위치 (없으면 None)


@dataclass
class DFA:
    states: list[str]
    alphabet: list[str]
    start: str
    accept: set[str]
    transitions: dict[str, dict[str, str]] = field(default_factory=dict)
    layout: dict[str, list[float]] = field(default_factory=dict)

    # ---------- 변환 ----------

    @classmethod
    def from_dict(cls, data: dict) -> "DFA":
        return cls(
            states=list(data.get("states", [])),
            alphabet=list(data.get("alphabet", [])),
            start=data.get("start", ""),
            accept=set(data.get("accept", [])),
            transitions={
                s: dict(row) for s, row in data.get("transitions", {}).items()
            },
            layout=dict(data.get("layout", {})),
        )

    def to_dict(self) -> dict:
        return {
            "type": "dfa",
            "states": list(self.states),
            "alphabet": list(self.alphabet),
            "start": self.start,
            "accept": sorted(self.accept),
            "transitions": {s: dict(row) for s, row in self.transitions.items()},
            "layout": dict(self.layout),
        }

    # ---------- 검증 ----------

    def validate(self) -> list[Issue]:
        """설계 문제를 모두 찾아서 돌려준다. error가 하나라도 있으면 채점하지 않는다."""
        issues: list[Issue] = []
        state_set = set(self.states)

        if not self.states:
            issues.append(Issue("error", "상태가 하나도 없어요."))
        if len(state_set) != len(self.states):
            issues.append(Issue("error", "같은 이름의 상태가 두 번 이상 있어요."))
        for sym in self.alphabet:
            if len(sym) != 1:
                issues.append(Issue("error", f"입력 기호 '{sym}'는 한 글자여야 해요."))
        if self.start not in state_set:
            issues.append(Issue("error", "시작 상태를 정해주세요."))
        for s in sorted(self.accept - state_set):
            issues.append(Issue("error", f"종료 상태 '{s}'가 상태 목록에 없어요."))

        for src, row in self.transitions.items():
            if src not in state_set:
                issues.append(Issue("error", f"전이표에 없는 상태 '{src}'가 있어요."))
                continue
            for sym, dst in row.items():
                if sym not in self.alphabet:
                    issues.append(
                        Issue("error", f"{src}에서 알파벳에 없는 기호 '{sym}'를 쓰고 있어요.")
                    )
                if dst not in state_set:
                    issues.append(
                        Issue("error", f"{src} --{sym}--> '{dst}': 없는 상태로 가요.")
                    )

        if not any(i.level == "error" for i in issues):
            for src in self.states:
                for sym in self.alphabet:
                    if self.step(src, sym) is DEAD:
                        issues.append(
                            Issue(
                                "warning",
                                f"{src}에서 '{sym}'를 읽을 때의 전이가 없어요. "
                                "이 경우는 거부로 처리해요.",
                            )
                        )
        return issues

    def is_valid(self) -> bool:
        return not any(i.level == "error" for i in self.validate())

    # ---------- 실행 ----------

    def step(self, state: str | None, symbol: str) -> str | None:
        """전이 함수 δ(state, symbol). 빠진 전이나 죽은 상태에서는 DEAD를 돌려준다."""
        if state is DEAD:
            return DEAD
        dst = self.transitions.get(state, {}).get(symbol)
        return dst if dst else DEAD

    def run(self, word: str) -> RunResult:
        state: str | None = self.start
        path: list = [state]
        stuck_at = None
        for i, ch in enumerate(word):
            nxt = self.step(state, ch)
            if nxt is DEAD and state is not DEAD:
                stuck_at = i
            state = nxt
            path.append(state)
            if state is DEAD:
                break
        accepted = state is not DEAD and state in self.accept
        return RunResult(accepted=accepted, path=path, stuck_at=stuck_at)

    def accepts(self, word: str) -> bool:
        return self.run(word).accepted

    def completed_state_count(self) -> int:
        """도달 가능한 상태 수. 빠진 전이가 있으면 죽은 상태 1개를 더해서 센다.

        minimal_state_count()와 같은 기준(완전한 DFA)으로 비교하기 위한 값이다.
        """
        reachable = self.reachable_states()
        missing = any(
            self.step(s, sym) is DEAD for s in reachable for sym in self.alphabet
        )
        return len(reachable) + (1 if missing else 0)

    def reachable_states(self) -> set[str]:
        seen = {self.start}
        queue = deque([self.start])
        while queue:
            s = queue.popleft()
            for sym in self.alphabet:
                t = self.step(s, sym)
                if t is not DEAD and t not in seen:
                    seen.add(t)
                    queue.append(t)
        return seen


# ---------- 두 DFA 비교 ----------


def find_counterexample(candidate: DFA, reference: DFA) -> str | None:
    """두 DFA가 다르게 판정하는 가장 짧은 문자열을 찾는다. 같은 언어면 None.

    곱 오토마톤 (candidate 상태, reference 상태)을 BFS로 탐색한다.
    BFS라서 처음 찾은 문자열이 가장 짧고, 기호를 정렬된 순서로 보므로
    길이가 같으면 사전순으로 가장 앞선 문자열이 나온다.
    """
    alphabet = sorted(set(candidate.alphabet) | set(reference.alphabet))

    def is_accepting(dfa: DFA, state: str | None) -> bool:
        return state is not DEAD and state in dfa.accept

    start = (candidate.start, reference.start)
    seen = {start}
    queue = deque([(start, "")])
    while queue:
        (p, q), word = queue.popleft()
        if is_accepting(candidate, p) != is_accepting(reference, q):
            return word
        for sym in alphabet:
            nxt = (candidate.step(p, sym), reference.step(q, sym))
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, word + sym))
    return None


def minimal_state_count(dfa: DFA) -> int:
    """같은 언어를 받아들이는 '완전한' 최소 DFA의 상태 수.

    도달 가능한 상태만 남기고, 빠진 전이가 있으면 죽은 상태 하나를 더한 뒤
    Moore 방식(분할 세분화)으로 구분 가능한 상태끼리 나눈다.
    """
    reachable = dfa.reachable_states()
    nodes: list = sorted(reachable)
    needs_dead = any(
        dfa.step(s, sym) is DEAD for s in nodes for sym in dfa.alphabet
    )
    if needs_dead:
        nodes.append(DEAD)

    # 처음에는 종료 / 비종료 두 그룹으로 나눈다.
    group = {n: (n is not DEAD and n in dfa.accept) for n in nodes}
    while True:
        signature = {
            n: (group[n],) + tuple(group[dfa.step(n, sym)] for sym in dfa.alphabet)
            for n in nodes
        }
        ids: dict = {}
        new_group = {n: ids.setdefault(signature[n], len(ids)) for n in nodes}
        if len(set(new_group.values())) == len(set(group.values())):
            return len(set(new_group.values()))
        group = new_group
