"""문맥자유 언어의 펌핑 보조정리 게임 엔진.

정규 펌핑 게임(pumping.py)과 같은 블록 언어, w 템플릿, 실수 비율을 쓰고 분할만 다르다.

    w = uvxyz,  |vxy| ≤ m,  |vy| ≥ 1,  모든 i ≥ 0에 대해 uvⁱxyⁱz ∈ L

분할은 다섯 조각의 경계 네 곳(cuts = (p1, p2, p3, p4))으로 나타낸다.
u = w[:p1], v = w[p1:p2], x = w[p2:p3], y = w[p3:p4], z = w[p4:]

vxy가 w 어디에나 올 수 있어서 수비 코스가 정규 게임보다 수십 배 많다. 같은 문자열을 여러 번
판정하는 일이 많으므로 판정 결과를 Membership에 저장해 다시 쓴다.

경우(case) 분류는 JFLAP의 문맥자유 펌핑 게임을 참고했다. JFLAP은 언어마다 경우 목록을 손으로 적지만,
여기서는 w의 글자 블록(같은 글자가 이어진 구간)을 보고 "v와 y가 각각 어느 블록에 있는가"로 자동 분류한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb

from .pumping import (
    SMASH_VALUES,
    BlockLanguage,
    ReceiveScore,
    candidate_words,
    max_receive_length,
)

Cuts = tuple[int, int, int, int]

# 막는 쪽 게임에서 m = max_serve일 때 컴퓨터의 첫 리시브 계산량(후보 w마다 분할 수를 더한 값)의 상한. 스테이지 테스트가 확인한다.
# 후보 수만으로는 막을 수 없다: aⁱbʲcᵏ는 m = 8에서 후보가 754개뿐이지만 후보마다 분할이 수천 개라 계산량이 약 181만이다.
# 측정(리뷰 환경 기준)으로 계산량 약 37만이 첫 리시브 1.4초 정도였다.
MAX_CFL_RECEIVE_WORK = 400_000


def cfl_candidate_length(m: int) -> int:
    """컴퓨터가 리시브로 살펴보는 w의 최대 길이. aⁿbⁿcⁿ의 a^m b^m c^m(길이 3m)이 들어가도록 3m + 3으로 잡는다."""
    return min(3 * m + 3, max_receive_length(m))


class Membership:
    """판정 결과를 저장해두는 language.contains. 한 번의 계산(분석, 리시브 선택) 동안만 쓴다."""

    def __init__(self, language: BlockLanguage):
        self.language = language
        self._memo: dict[str, bool] = {}

    def __call__(self, word: str) -> bool:
        result = self._memo.get(word)
        if result is None:
            result = self._memo[word] = self.language.contains(word)
        return result


# ---------- 분할 ----------


@dataclass(frozen=True, slots=True)  # 분할이 수천~수만 개라 객체마다 __dict__를 두지 않는다
class CFLSplit:
    cuts: Cuts
    breaking: tuple[int, ...]  # 이 분할을 L 밖으로 보내는 i

    def parts(self, word: str) -> tuple[str, str, str, str, str]:
        return cfl_parts(word, self.cuts)


def cfl_parts(word: str, cuts: Cuts) -> tuple[str, str, str, str, str]:
    p1, p2, p3, p4 = cuts
    return word[:p1], word[p1:p2], word[p2:p3], word[p3:p4], word[p4:]


def cfl_pump(word: str, cuts: Cuts, i: int) -> str:
    u, v, x, y, z = cfl_parts(word, cuts)
    return u + v * i + x + y * i + z


def cfl_split_error(word: str, m: int, cuts) -> str | None:
    """분할이 조건(|vxy| ≤ m, |vy| ≥ 1)을 지키는지. 지키면 None."""
    if (
        not isinstance(cuts, (list, tuple))
        or len(cuts) != 4
        or any(type(c) is not int for c in cuts)
    ):
        return "분할은 경계 위치 정수 네 개로 적어야 해요."
    p1, p2, p3, p4 = cuts
    if not (0 <= p1 <= p2 <= p3 <= p4 <= len(word)):
        return "u, v, x, y, z가 w 안에서 차례대로 이어져야 해요."
    if (p2 - p1) + (p4 - p3) < 1:
        return "v와 y가 둘 다 비어 있어요. 둘 중 하나는 한 글자 이상이어야 해요 (|vy| ≥ 1)."
    if p4 - p1 > m:
        return f"|vxy|({p4 - p1})가 m({m})보다 길어요 (|vxy| ≤ m)."
    return None


def cfl_split_count(n: int, m: int) -> int:
    """길이 n인 w에서 |vxy| ≤ m, |vy| ≥ 1인 분할의 수 (분할을 만들지 않고 센다).

    vxy 길이 L마다 시작 위치가 n − L + 1곳이고, 그 안에서 x를 고르는 방법 C(L + 2, 2)개 중 v, y가 모두 빈 1개를 뺀다.
    """
    return sum((n - length + 1) * (comb(length + 2, 2) - 1) for length in range(1, min(m, n) + 1))


def cfl_split_ranges(word: str, m: int):
    """|vxy| ≤ m, |vy| ≥ 1인 모든 분할의 경계."""
    n = len(word)
    for p1 in range(n + 1):
        for p4 in range(p1 + 1, min(p1 + m, n) + 1):
            for p2 in range(p1, p4 + 1):
                for p3 in range(p2, p4 + 1):
                    if (p2 - p1) + (p4 - p3) >= 1:
                        yield p1, p2, p3, p4


def _breaking(member: Membership, word: str, cuts: Cuts) -> tuple[int, ...]:
    return tuple(i for i in SMASH_VALUES if not member(cfl_pump(word, cuts, i)))


def _breakable(member: Membership, word: str, cuts: Cuts) -> bool:
    """이 분할을 뚫는 i가 있는지. 처음 찾은 i에서 멈춘다."""
    return any(not member(cfl_pump(word, cuts, i)) for i in SMASH_VALUES)


def analyze_cfl_splits(language: BlockLanguage, word: str, m: int) -> list[CFLSplit]:
    """모든 수비 코스(분할)와 각 코스에서 통하는 스매시(i) 목록."""
    member = Membership(language)
    shared: dict[tuple[int, ...], tuple[int, ...]] = {}  # 같은 breaking tuple은 객체 하나를 같이 쓴다 (메모리 절약)
    return [
        CFLSplit(cuts, shared.setdefault(b, b))
        for cuts in cfl_split_ranges(word, m)
        for b in (_breaking(member, word, cuts),)
    ]


def cfl_computer_smash(language: BlockLanguage, word: str, cuts: Cuts) -> int | None:
    """컴퓨터의 스매시: 분할을 L 밖으로 보내는 가장 작은 i. 없으면 None (막는 쪽 득점)."""
    for i in SMASH_VALUES:
        if not language.contains(cfl_pump(word, cuts, i)):
            return i
    return None


# ---------- 막는 쪽: 컴퓨터의 리시브 ----------


def cfl_candidate_words(language: BlockLanguage, m: int) -> list[str]:
    return candidate_words(language, m, max_length=cfl_candidate_length(m))


def cfl_receive_work(language: BlockLanguage, m: int) -> int:
    """컴퓨터의 첫 리시브 계산량: 후보 w마다 살펴볼 분할 수를 더한 값. 실제 계산 시간과 거의 비례한다."""
    return sum(cfl_split_count(len(w), m) for w in cfl_candidate_words(language, m))


def _score(member: Membership, word: str, m: int) -> ReceiveScore:
    ranges = list(cfl_split_ranges(word, m))
    beaten = sum(1 for cuts in ranges if _breakable(member, word, cuts))
    return ReceiveScore(word, beaten, len(ranges))


def cfl_receive_scores(language: BlockLanguage, m: int) -> tuple[ReceiveScore, ...]:
    """후보 w마다 뚫을 수 있는 수비 코스 수. pumping.choose_receive / best_receives에 scores로 넘긴다."""
    member = Membership(language)
    return tuple(_score(member, w, m) for w in cfl_candidate_words(language, m))


def cfl_is_winning_receive(language: BlockLanguage, word: str, m: int, member: Membership | None = None) -> bool:
    """어떤 수비도 뚫는 리시브인지. 못 뚫는 코스를 하나 찾으면 바로 멈춘다."""
    member = member or Membership(language)
    return all(_breakable(member, word, cuts) for cuts in cfl_split_ranges(word, m))


def cfl_has_winning_receive(language: BlockLanguage, m: int) -> bool:
    """이 m에서 어떤 수비도 뚫는 리시브가 하나라도 있는지 (첫 번째를 찾으면 멈춘다)."""
    member = Membership(language)
    return any(cfl_is_winning_receive(language, w, m, member) for w in cfl_candidate_words(language, m))


# ---------- 경우(case) 분류 ----------

Span = tuple[int, int] | None  # (첫 블록, 마지막 블록) 번호. 빈 문자열이면 None


def letter_runs(word: str) -> list[tuple[str, int, int]]:
    """같은 글자가 이어진 구간들: [(글자, 시작, 끝)]. 예: 'aabbb' → [('a', 0, 2), ('b', 2, 5)]"""
    runs = []
    start = 0
    for k in range(1, len(word) + 1):
        if k == len(word) or word[k] != word[start]:
            runs.append((word[start], start, k))
            start = k
    return runs


def _span(runs, a: int, b: int) -> Span:
    if a == b:
        return None
    first = next(k for k, (_, s, e) in enumerate(runs) if s <= a < e)
    last = next(k for k, (_, s, e) in enumerate(runs) if s < b <= e)
    return first, last


def case_key(runs, cuts: Cuts) -> tuple[Span, Span]:
    """분할의 경우: (v가 걸친 블록 범위, y가 걸친 블록 범위)."""
    p1, p2, p3, p4 = cuts
    return _span(runs, p1, p2), _span(runs, p3, p4)


def _run_name(runs, k: int) -> str:
    letter = runs[k][0]
    same = [j for j, (ch, _, _) in enumerate(runs) if ch == letter]
    if len(same) == 1:
        return letter
    return f"{same.index(k) + 1}번째 {letter}"


def _span_text(runs, span: Span) -> str:
    if span is None:
        return "빈 문자열"
    first, last = span
    if first == last:
        return f"{_run_name(runs, first)}만"
    if last == first + 1:
        return f"{_run_name(runs, first)} 뒤에 {_run_name(runs, last)} (경계에 걸침)"
    return f"{_run_name(runs, first)}부터 {_run_name(runs, last)}까지 (블록 {last - first + 1}개에 걸침)"


def case_label(runs, key: tuple[Span, Span]) -> str:
    v, y = key
    return f"v: {_span_text(runs, v)} · y: {_span_text(runs, y)}"


def _case_order(key: tuple[Span, Span]):
    v, y = key
    if v is None or y is None:  # JFLAP처럼 빈 v, 빈 y 경우는 맨 뒤에
        return (1, 0 if v is None else 1, (v or y))
    return (0, v, y)


@dataclass(frozen=True)
class CaseSummary:
    key: tuple[Span, Span]
    label: str
    total: int  # 이 경우에 속하는 분할 수
    blockable: int  # 그중 어떤 i로도 뚫리지 않는(막는 쪽이 이기는) 분할 수
    common_i: tuple[int, ...]  # 이 경우의 모든 분할을 뚫는 i (없으면 빈 tuple)
    example: Cuts  # 대표 분할: 막히는 분할이 있으면 그것, 없으면 첫 분할


def summarize_cases(word: str, splits: list[CFLSplit]) -> list[CaseSummary]:
    """분할들을 경우별로 묶어서 정리한다 (경기 뒤 경우별 표와 증명의 뼈대)."""
    runs = letter_runs(word)
    groups: dict[tuple[Span, Span], list[CFLSplit]] = {}
    for s in splits:
        groups.setdefault(case_key(runs, s.cuts), []).append(s)
    summaries = []
    for key in sorted(groups, key=_case_order):
        group = groups[key]
        common = set(SMASH_VALUES)
        for s in group:
            common &= set(s.breaking)
        blocked = [s for s in group if not s.breaking]
        summaries.append(
            CaseSummary(
                key=key,
                label=case_label(runs, key),
                total=len(group),
                blockable=len(blocked),
                common_i=tuple(sorted(common)),
                example=(blocked[0] if blocked else group[0]).cuts,
            )
        )
    return summaries


# ---------- 경기 뒤 경우별 정리 표 (깨는 쪽이 이겼을 때) ----------


@dataclass
class CaseReportRow:
    label: str
    smash: tuple[int, ...]  # 확인한 모든 m에서 이 경우의 모든 분할을 뚫는 i
    example: tuple[str, str, str, str, str]  # 가장 큰 m에서의 대표 분할 (u, v, x, y, z)
    example_m: int


@dataclass
class CaseReport:
    available: bool
    rows: list[CaseReportRow]
    reason: str | None = None
    checked_m: list[int] | None = None


MIN_CASE_REPORT_M = 3  # 경우별 정리 표를 만들 때 확인하는 m의 최솟값 (cfl_case_report docstring 참고)


def cfl_case_report(language: BlockLanguage, template: str, checked_m: list[int]) -> CaseReport:
    """깨는 쪽 리시브(w 템플릿)로 경우별 정리 표를 만든다. 증명문의 뼈대가 된다.

    - 모든 블록의 지수가 모든 m ≥ 1에서 m 이상이어야 한다 (식으로 확인, at_least_m_for_all_m).
      그러면 |vxy| ≤ m인 vxy는 언제나 이웃한 두 블록까지만 걸쳐서, 확인한 m의 경우 목록이 모든 m의 경우 목록과 같다.
      a^7 b^7 c^7처럼 지수가 고정된 w는 m이 커지면 경우 목록이 바뀌고 결국 |w| < m이 되므로 정리 표를 만들지 않는다.
    - 확인하는 m이 모두 MIN_CASE_REPORT_M(3) 이상이어야 한다. 이웃한 두 블록에 걸치는 경우 중 가장 긴 것
      (예: v가 a와 b에 걸치고 y는 b에 있음, v = ab, y = b)도 |vxy| = 3이면 나타나므로, m ≥ 3이면 위의
      "확인한 m의 경우 목록 = 모든 m의 경우 목록"이 성립한다. m = 1, 2에서는 이런 경우가 빠져서 표가 불완전해진다.
    - 확인한 모든 m에서 w ∈ L이고, w의 글자 블록 구조(몇 번째 블록이 무슨 글자인지)가 같아야 한다.
    - 경우마다, 확인한 모든 m에서 그 경우의 모든 분할을 뚫는 i가 하나 이상 있어야 한다.
    마지막 두 조건은 유한한 m에 대한 확인이므로 화면에 확인 범위를 함께 보여준다.
    """
    from .pumping import ExpressionError, TemplateError, at_least_m_for_all_m, expand_template, parse_template

    if not checked_m or min(checked_m) < MIN_CASE_REPORT_M:
        return CaseReport(
            False, [],
            reason=f"경우별 정리 표는 확인하는 m이 모두 {MIN_CASE_REPORT_M} 이상일 때만 만들어요. "
            "m이 그보다 작으면 v와 y가 블록 경계에 걸치는 경우 일부가 나타나지 않아서 경우 목록이 빠져요.",
        )
    try:
        blocks = parse_template(template, language.alphabet)
        long_enough = all(at_least_m_for_all_m(expr) for _, expr in blocks)
    except (TemplateError, ExpressionError) as e:
        return CaseReport(False, [], reason=str(e))
    if not long_enough:
        return CaseReport(
            False, [],
            reason="블록마다 모든 m에서 m글자 이상인 w(예: a^m b^m c^m)일 때만 경우별 정리 표를 만들어요. "
            "그보다 짧은 블록이 있으면 m이 커질 때 vxy가 걸칠 수 있는 블록이 달라져서 경우 목록이 바뀌어요.",
        )

    # 1단계: 모든 m에서 w를 만들고, 글자 블록 구조가 같은지 먼저 확인한다 (경우를 같은 기준으로 나누기 위한 전제)
    words = {}
    for m in checked_m:
        try:
            word = expand_template(blocks, m, max_length=max_receive_length(m))
        except TemplateError as e:
            return CaseReport(False, [], reason=f"경우별 정리를 확인하는 중에 멈췄어요. {e}")
        if len(word) < m or not language.contains(word):
            return CaseReport(False, [], reason=f"m = {m}일 때 w가 L에 속하지 않거나 m보다 짧아요.")
        words[m] = word
    if len({tuple(ch for ch, _, _ in letter_runs(w)) for w in words.values()}) > 1:
        return CaseReport(False, [], reason="m에 따라 w의 글자 블록 구조가 달라져서 경우를 같은 기준으로 나눌 수 없어요.")

    # 2단계: 경우마다 모든 m에서 통하는 i를 모은다
    smash: dict[tuple, set[int]] = {}
    examples: dict[tuple, tuple[tuple[str, ...], int]] = {}
    labels: dict[tuple, str] = {}
    for m, word in words.items():
        for case in summarize_cases(word, analyze_cfl_splits(language, word, m)):
            if case.blockable:
                return CaseReport(
                    False, [],
                    reason=f"m = {m}에서 '{case.label}' 경우에 막히는 분할이 있어요. Lemma가 최선으로 수비했다면 받아낼 수 있었어요.",
                )
            smash[case.key] = smash.get(case.key, set(SMASH_VALUES)) & set(case.common_i)
            examples[case.key] = (cfl_parts(word, case.example), m)
            labels[case.key] = case.label
    missing = [labels[k] for k, v in smash.items() if not v]
    if missing:
        return CaseReport(
            False, [],
            reason=f"'{missing[0]}' 경우는 m마다 통하는 i가 달라서 i 하나로 정리할 수 없어요.",
            checked_m=checked_m,
        )
    rows = [
        CaseReportRow(labels[k], tuple(sorted(smash[k])), examples[k][0], examples[k][1])
        for k in sorted(smash, key=_case_order)
    ]
    return CaseReport(True, rows, checked_m=list(checked_m))
