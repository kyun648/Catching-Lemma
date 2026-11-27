"""정규 언어 펌핑 보조정리 게임 엔진.

표기는 교재(Linz)를 따른다: 펌핑 길이 m, 문자열 w, 분할 w = xyz (|xy| ≤ m, |y| ≥ 1).

블록 언어, w 템플릿, 계산기, 컴퓨터의 수비·리시브 선택은 두 펌핑 게임이 같이 쓰므로 pumping_common.py에 있다.
이 모듈에는 xyz 분할에 따른 부분만 둔다: 분할 나열과 펌핑, 리시브 점수, 컴퓨터의 스매시, 증명문.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .pumping_common import (
    BlockLanguage,
    ExpressionError,
    ReceiveChoice,
    ReceiveScore,
    SMASH_VALUES,
    TemplateError,
    candidate_words,
    expand_template,
    exponent_polynomial,
    max_receive_length,
    parse_template,
    pick_receive,
    winning_receives,
)

# ---------- 분할과 펌핑 ----------


@dataclass
class Split:
    start: int  # y의 시작 위치 (= |x|)
    end: int  # y의 끝 위치 (= |xy|)
    breaking: list[int]  # 이 분할에서 xyⁱz가 L 밖으로 나가는 i 목록 (SMASH_VALUES 안에서)

    def parts(self, word: str) -> tuple[str, str, str]:
        return word[: self.start], word[self.start : self.end], word[self.end :]


def pump(word: str, start: int, end: int, i: int) -> str:
    return word[:start] + word[start:end] * i + word[end:]


def analyze_splits(language: BlockLanguage, word: str, m: int) -> list[Split]:
    """|xy| ≤ m, |y| ≥ 1인 모든 분할과, 각 분할에서 통하는 스매시(i) 목록."""
    splits = []
    for start in range(0, m):
        for end in range(start + 1, min(m, len(word)) + 1):
            breaking = [i for i in SMASH_VALUES if not language.contains(pump(word, start, end, i))]
            splits.append(Split(start, end, breaking))
    return splits


def split_error(word: str, m: int, start: int, end: int) -> str | None:
    """분할이 펌핑 보조정리의 조건(|xy| ≤ m, |y| ≥ 1)을 지키는지. 지키면 None."""
    if not (0 <= start < end <= len(word)):
        return "y는 w 안의 한 글자 이상이어야 해요 (|y| ≥ 1)."
    if end > m:
        return f"|xy|({end})가 m({m})보다 길어요. y는 w의 앞쪽 m글자 안에서 골라야 해요 (|xy| ≤ m)."
    return None


# ---------- 막는 쪽: 컴퓨터의 리시브 점수와 스매시 ----------

MAX_RECEIVE_CANDIDATES = 300  # 막는 쪽 게임에서 m = 8일 때 컴퓨터가 살펴보는 후보 w 수의 상한 (스테이지 테스트가 확인)


def candidate_length(m: int) -> int:
    """정규 게임에서 컴퓨터가 리시브로 살펴보는 w의 최대 길이. aⁿbⁿ의 a^m b^m(길이 2m)이 들어가도록 2m + 3으로 잡는다."""
    return 2 * m + 3


def regular_candidate_words(language: BlockLanguage, m: int) -> list[str]:
    """정규 게임에서 컴퓨터가 리시브로 고를 수 있는 w: L에 속하고 m ≤ |w| ≤ 2m + 3인 문자열 (짧은 것부터)."""
    return candidate_words(language, m, max_length=candidate_length(m))


def _breakable(language: BlockLanguage, word: str, start: int, end: int) -> bool:
    """이 수비 코스(분할)를 뚫는 i가 있는지. 처음 찾은 i에서 멈춘다."""
    return any(not language.contains(pump(word, start, end, i)) for i in SMASH_VALUES)


def _split_ranges(word: str, m: int):
    for start in range(0, m):
        for end in range(start + 1, min(m, len(word)) + 1):
            yield start, end


def beaten_fraction(language: BlockLanguage, word: str, m: int) -> float:
    """w로 리시브했을 때 뚫을 수 있는 수비 코스의 비율. 1.0이면 어떤 수비도 뚫는 리시브다."""
    score = _score(language, word, m)
    return score.beaten / score.total


def is_winning_receive(language: BlockLanguage, word: str, m: int) -> bool:
    """어떤 수비도 뚫는 리시브인지. 못 뚫는 코스를 하나 찾으면 바로 멈춘다."""
    return all(_breakable(language, word, s, e) for s, e in _split_ranges(word, m))


def _score(language: BlockLanguage, word: str, m: int) -> ReceiveScore:
    ranges = list(_split_ranges(word, m))
    beaten = sum(1 for s, e in ranges if _breakable(language, word, s, e))
    return ReceiveScore(word, beaten, len(ranges))


def receive_scores(language: BlockLanguage, m: int) -> tuple[ReceiveScore, ...]:
    """후보 w마다 뚫을 수 있는 수비 코스 수. choose_receive와 best_receives가 같이 쓰도록 한 번에 계산한다."""
    return tuple(_score(language, w, m) for w in regular_candidate_words(language, m))


def choose_receive(
    language: BlockLanguage,
    m: int,
    rng: random.Random,
    rate: float,
    scores: tuple[ReceiveScore, ...] | None = None,
) -> ReceiveChoice | None:
    """정규 게임에서 컴퓨터(깨는 쪽)의 리시브 선택. scores가 없으면 receive_scores로 계산해서 pick_receive에 넘긴다."""
    return pick_receive(receive_scores(language, m) if scores is None else scores, rng, rate)


def best_receives(
    language: BlockLanguage, m: int, scores: tuple[ReceiveScore, ...] | None = None
) -> tuple[list[str], int]:
    """어떤 수비도 뚫는 리시브(w) 목록과 후보 전체 수. 목록이 비면 이 m에서는 막는 쪽이 언제나 막을 수 있다.

    scores가 없으면 후보마다 못 뚫는 코스를 찾는 즉시 다음 후보로 넘어간다.
    """
    if scores is not None:
        return winning_receives(scores)
    words = regular_candidate_words(language, m)
    return [w for w in words if is_winning_receive(language, w, m)], len(words)


def computer_smash(language: BlockLanguage, word: str, start: int, end: int) -> int | None:
    """컴퓨터(깨는 쪽)의 스매시: xyⁱz ∉ L이 되는 가장 작은 i. 그런 i가 SMASH_VALUES에 없으면 None."""
    for i in SMASH_VALUES:
        if not language.contains(pump(word, start, end, i)):
            return i
    return None


# ---------- 증명문 ----------


def _affine(expr: str) -> tuple[int, int] | None:
    """지수식이 a·m + b 꼴이면 (a, b), 아니면(m² 등) None."""
    poly = exponent_polynomial(expr)
    if any(d > 1 for d in poly):
        return None
    return poly.get(1, 0), poly.get(0, 0)


def _affine_latex(a: int, b: int, extra: str = "") -> str:
    """(2, -1) → '2m-1'. extra는 뒤에 붙일 항(예: '-k')."""
    terms = []
    if a:
        terms.append({1: "m", -1: "-m"}.get(a, f"{a}m"))
    if b or not (a or extra):
        terms.append(f"{b:+d}" if terms else str(b))
    text = "".join(terms) + extra
    return text.lstrip("+") if text.startswith("+") else text


def _pumped_exponent(coef: tuple[int, int], i: int) -> str:
    extra = {0: "-k", 2: "+k"}.get(i, f"+{i - 1}k")
    return _affine_latex(*coef, extra=extra)


def _block_latex(blocks: list[tuple[str, tuple[int, int]]]) -> str:
    return "".join(ch if c == (0, 1) else f"{ch}^{{{_affine_latex(*c)}}}" for ch, c in blocks)


@dataclass
class ProofResult:
    available: bool
    text: str | None = None
    reason: str | None = None  # available이 False일 때 이유
    smash: int | None = None  # 모든 분할에 통하는 i
    checked_m: list[int] | None = None


def build_proof(
    language: BlockLanguage,
    condition_text: str,
    template: str,
    checked_m: list[int],
) -> ProofResult:
    """경기 기록(w 템플릿)을 교재 형식의 증명문으로 정리한다.

    자동으로 쓸 수 있는 경우만 다룬다:
    - 모든 지수가 m에 대한 일차식(a·m + b)이다
    - 모든 m ≥ 1에서 첫 블록 길이가 m 이상이다 (식으로 확인) → y는 첫 블록 글자로만 이루어진다 (y = c^k)
    - 검사한 m에서 w ∈ L이고, 하나의 i가 검사한 모든 m, 모든 분할에서 w를 L 밖으로 보낸다
    셋째 조건은 유한한 m에 대한 확인이므로, 증명문 끝에 보조 검증 범위를 밝힌다.
    """
    try:
        blocks = parse_template(template, language.alphabet)
        coefs = [_affine(expr) for _, expr in blocks]
    except (TemplateError, ExpressionError) as e:
        return ProofResult(False, reason=str(e))

    if any(c is None for c in coefs):
        return ProofResult(False, reason="지수가 m에 대한 일차식(예: 2m+1)이 아니면 증명문을 자동으로 쓰지 않아요.")
    (a, b), rest = coefs[0], coefs[1:]
    if a < 1 or (a - 1) + b < 0:
        # a·m + b ≥ m 이 모든 m ≥ 1에서 성립 ⇔ a ≥ 1 이고 m = 1에서 성립
        return ProofResult(
            False,
            reason="첫 블록의 길이가 m보다 짧아질 수 있는 w는 y가 여러 블록에 걸칠 수 있어서, 증명문을 자동으로 쓰지 않아요.",
        )
    if any(ra < 0 or ra + rb < 0 for ra, rb in rest):
        return ProofResult(False, reason="m에 따라 지수가 음수가 되는 블록이 있어서 증명문을 자동으로 쓰지 않아요.")

    first_ch = blocks[0][0]
    words = {}
    for m in checked_m:
        # 경기에서 쓴 m보다 큰 m으로도 검사하므로, 리시브와 같은 길이 상한을 여기서도 지킨다.
        try:
            word = words[m] = expand_template(blocks, m, max_length=max_receive_length(m))
        except TemplateError as e:
            return ProofResult(False, reason=f"증명문을 확인하는 중에 멈췄어요. {e}")
        if not language.contains(word):
            return ProofResult(False, reason=f"m = {m}일 때 w가 L에 속하지 않아요.")

    smash = None
    for i in SMASH_VALUES:
        if all(
            not language.contains(pump(words[m], s.start, s.end, i))
            for m in checked_m
            for s in analyze_splits(language, words[m], m)
        ):
            smash = i
            break
    if smash is None:
        return ProofResult(
            False,
            reason="모든 분할에 한 번에 통하는 i가 없어요. 분할마다 다른 i가 필요한 경우는 증명문을 자동으로 쓰지 않아요.",
            checked_m=checked_m,
        )

    w = _block_latex([(ch, c) for (ch, _), c in zip(blocks, coefs)])
    pumped = f"{first_ch}^{{{_pumped_exponent((a, b), smash)}}}" + _block_latex(
        [(ch, c) for (ch, _), c in zip(blocks[1:], rest)]
    )
    lo, hi = min(checked_m), max(checked_m)
    text = "\n\n".join(
        [
            "$L$이 정규 언어라고 가정하자. 그러면 펌핑 보조정리의 상수 $m$이 존재한다.",
            f"다음 문자열을 고른다: $w = {w}$. 그러면 $w \\in L$이고 $|w| \\ge m$이다.",
            f"$|xy| \\le m$, $|y| \\ge 1$인 어떤 분할 $w = xyz$를 생각하자. "
            f"$w$의 처음 $m$글자는 모두 ${first_ch}$이므로 $y = {first_ch}^{{k}}$ $(1 \\le k \\le m)$이다.",
            f"$i = {smash}$일 때 $xy^{{{smash}}}z = {pumped}$이다. "
            f"$k \\ge 1$이므로 이 문자열은 '{condition_text}'라는 조건을 만족하지 않아 $L$에 속하지 않는다.",
            "이는 펌핑 보조정리에 모순이므로 $L$은 정규 언어가 아니다. $\\blacksquare$",
            f"*보조 검증: m = {lo}~{hi}에서 w ∈ L이고, 모든 분할에서 i = {smash}일 때 L 밖이 되는 것을 확인했어요. "
            "첫 블록이 m글자 이상이라는 것은 모든 m에서 식으로 확인했지만, 나머지는 유한한 m에 대한 확인이므로 "
            "둘째 문단의 'w ∈ L'과 넷째 문단의 '조건을 만족하지 않는다'는 직접 따져서 확인해보세요.*",
        ]
    )
    return ProofResult(True, text=text, smash=smash, checked_m=checked_m)
