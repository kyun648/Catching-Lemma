"""정규 언어 펌핑 보조정리 게임 엔진.

표기는 교재(Linz)를 따른다: 펌핑 길이 m, 문자열 w, 분할 w = xyz (|xy| ≤ m, |y| ≥ 1).

언어는 "블록 언어"로 정의한다. 블록 순서(예: a, b)와 블록 길이 n0, n1, ...에 대한 조건식으로
L = { a^n0 b^n1 ... | 조건 } 을 나타낸다. 새 언어는 스테이지 JSON에 블록과 조건식만 적으면 된다.

    {"blocks": ["a", "b"], "constraint": "n0 == n1"}          # aⁿbⁿ
    {"blocks": ["a", "b"], "constraint": "n1 > n0"}           # aⁿbᵏ (k > n)

플레이어가 고르는 w도 블록 형태의 템플릿으로 쓴다: "a^m b^m", "a^m b^(m+1)", "a^(2m) b^m".
"""

from __future__ import annotations

import ast
import math
import random
import re
from dataclasses import dataclass

# 스매시에서 고를 수 있는 i. i = 1은 w 자신이라 언제나 L에 속하므로 뺀다.
SMASH_VALUES = [0, 2, 3, 4, 5]

# 블록 분해를 모두 찾을 때 다루는 문자열 길이 상한 (블록 글자가 반복되는 언어에서만 필요).
MAX_WORD_LENGTH = 200


class ExpressionError(ValueError):
    """조건식이나 지수식을 해석할 수 없을 때."""


class TemplateError(ValueError):
    """w 템플릿을 해석할 수 없을 때. 메시지는 화면에 그대로 보여준다."""


# ---------- 안전한 식 계산 (eval을 쓰지 않는다) ----------


def _is_square(n: int) -> bool:
    return n >= 0 and math.isqrt(n) ** 2 == n


_PRIME_BASES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)
MAX_PRIME_INPUT = 3_317_044_064_679_887_385_961_981  # 위 밑(base)들로 밀러-라빈 판정이 정확한 상한


def _is_prime(n: int) -> bool:
    """밀러-라빈 소수 판정. 나눗셈을 √n까지 해보는 방식과 달리 큰 수에서도 바로 끝난다.

    MAX_PRIME_INPUT 이하에서는 정확하고, 그보다 큰 수는 받지 않는다.
    """
    if n > MAX_PRIME_INPUT:
        raise ExpressionError("is_prime()에 넣을 수 있는 수보다 커요.")
    if n < 2:
        return False
    for p in _PRIME_BASES:
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for a in _PRIME_BASES:
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


FUNCTIONS = {"is_square": _is_square, "is_prime": _is_prime}

_BINARY = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
}
_COMPARE = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
}


# 플레이어가 입력하는 지수식에서 쓸 수 있는 연산 (함수, 비교, 나눗셈은 쓸 수 없다)
_ARITHMETIC = {ast.Add, ast.Sub, ast.Mult}


def evaluate(expr: str, variables: dict[str, int], *, arithmetic_only: bool = False):
    """eval을 쓰지 않는 계산기.

    기본(스테이지 JSON의 조건식): 정수 산술(+, -, *, //, %), 비교, and/or/not, is_square/is_prime.
    arithmetic_only=True(플레이어가 입력하는 지수식): 정수, 변수, +, -, *, 괄호만 허용한다.
    함수 호출이나 비교를 막아서 계산이 오래 걸리거나 참/거짓이 지수로 쓰이는 일을 막는다.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ExpressionError(f"식 '{expr}'를 해석할 수 없어요.") from e

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise ExpressionError(f"'{node.id}'는 쓸 수 없는 이름이에요.")
            return variables[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            if arithmetic_only and type(node.op) not in _ARITHMETIC:
                raise ExpressionError(f"식 '{expr}'에는 +, -, *만 쓸 수 있어요.")
            return _BINARY[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        if arithmetic_only:
            raise ExpressionError(f"식 '{expr}'에는 정수, m, +, -, *, 괄호만 쓸 수 있어요.")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not ev(node.operand)
        if isinstance(node, ast.BoolOp):
            values = [ev(v) for v in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.Compare) and all(type(op) in _COMPARE for op in node.ops):
            left = ev(node.left)
            for op, right_node in zip(node.ops, node.comparators):
                right = ev(right_node)
                if not _COMPARE[type(op)](left, right):
                    return False
                left = right
            return True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FUNCTIONS
            and len(node.args) == 1
            and not node.keywords
        ):
            return FUNCTIONS[node.func.id](ev(node.args[0]))
        raise ExpressionError(f"식 '{expr}'에 쓸 수 없는 부분이 있어요.")

    try:
        return ev(tree)
    except ZeroDivisionError as e:
        raise ExpressionError(f"식 '{expr}'에서 0으로 나누고 있어요.") from e


# ---------- 블록 언어 ----------


@dataclass
class BlockLanguage:
    blocks: list[str]  # 블록 글자 순서. 예: ["a", "b"]
    constraint: str  # 블록 길이 n0, n1, ...에 대한 조건식. 예: "n0 == n1"

    @property
    def alphabet(self) -> list[str]:
        return sorted(set(self.blocks))

    def _satisfies(self, counts: tuple[int, ...]) -> bool:
        return bool(evaluate(self.constraint, {f"n{i}": c for i, c in enumerate(counts)}))

    def _decompositions(self, word: str, start: int = 0, block: int = 0):
        """word[start:]를 blocks[block:]의 연속 블록으로 나누는 모든 방법 (각 블록 길이 0 이상)."""
        if block == len(self.blocks):
            if start == len(word):
                yield ()
            return
        ch = self.blocks[block]
        end = start
        while True:
            for rest in self._decompositions(word, end, block + 1):
                yield (end - start,) + rest
            if end < len(word) and word[end] == ch:
                end += 1
            else:
                return

    def contains(self, word: str) -> bool:
        if len(word) > MAX_WORD_LENGTH:
            raise ValueError(f"문자열이 너무 길어요 (최대 {MAX_WORD_LENGTH}글자).")
        return any(self._satisfies(c) for c in self._decompositions(word))


# ---------- w 템플릿 ----------

# 괄호 없는 지수는 정수, m, 2m 형태만 받는다 (a^3b^m에서 '3b'를 지수로 읽지 않도록).
_TOKEN = re.compile(r"\s*([a-z])(?:\^(\([^()]*\)|\{[^{}]*\}|\d*m|\d+))?\s*")


def _normalize_exponent(raw: str) -> str:
    """'(m+1)', '{2m}', '2m' 같은 지수를 계산할 수 있는 식으로: 'm+1', '2*m'"""
    body = raw[1:-1] if raw[:1] in "({" else raw
    body = re.sub(r"(\d)\s*([a-z(])", r"\1*\2", body)
    return body.strip()


MAX_TEMPLATE_LENGTH = 100  # w 템플릿 입력 글자 수 상한


def parse_template(template: str, alphabet: list[str]) -> list[tuple[str, str]]:
    """'a^m b^(m+1)' → [('a', 'm'), ('b', 'm+1')]. 지수가 없으면 '1'.

    지수에는 정수, m, +, -, *, 괄호만 쓸 수 있다 (evaluate의 arithmetic_only).
    """
    text = template.strip()
    if not text:
        raise TemplateError("w를 입력해주세요. 예: a^m b^m")
    if len(text) > MAX_TEMPLATE_LENGTH:
        raise TemplateError(f"w는 {MAX_TEMPLATE_LENGTH}글자 이내로 적어주세요.")
    blocks, pos = [], 0
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if not match or match.end() == pos:
            raise TemplateError(f"'{text[pos:]}' 부분을 읽을 수 없어요. 예: a^m b^(m+1)")
        ch, raw = match.group(1), match.group(2)
        if ch not in alphabet:
            raise TemplateError(f"'{ch}'는 이 언어의 글자가 아니에요. 쓸 수 있는 글자: {', '.join(alphabet)}")
        expr = _normalize_exponent(raw) if raw else "1"
        try:
            evaluate(expr, {"m": 1}, arithmetic_only=True)
        except ExpressionError as e:
            raise TemplateError(f"지수 '{raw}'를 계산할 수 없어요. 정수, m, +, -, *, 괄호만 쓸 수 있어요.") from e
        blocks.append((ch, expr))
        pos = match.end()
    return blocks


class WordTooLongError(TemplateError):
    """w가 길이 상한을 넘을 때."""


def max_receive_length(m: int) -> int:
    """리시브(w)의 길이 상한.

    펌핑한 문자열 xyⁱz는 |w| + (i - 1)|y| ≤ |w| + 4m 글자까지 늘어나므로(i ≤ 5, |y| ≤ m),
    펌핑한 뒤에도 MAX_WORD_LENGTH를 넘지 않도록 그만큼 여유를 둔다.
    """
    return MAX_WORD_LENGTH - (max(SMASH_VALUES) - 1) * m


def expand_template(blocks: list[tuple[str, str]], m: int, max_length: int = MAX_WORD_LENGTH) -> str:
    """템플릿을 m에 대해 펼친다. 길이를 먼저 계산해서 상한을 넘으면 문자열을 만들기 전에 거부한다.

    (a^(10000000000) 같은 입력으로 거대한 문자열을 만들지 않기 위해서다.)
    """
    lengths = []
    for ch, expr in blocks:
        try:
            n = evaluate(expr, {"m": m}, arithmetic_only=True)
        except ExpressionError as e:
            raise TemplateError(f"m = {m}일 때 지수 '{expr}'를 계산할 수 없어요. {e}") from e
        if type(n) is not int or n < 0:
            raise TemplateError(f"m = {m}일 때 지수 '{expr}'가 0 이상의 정수가 아니에요.")
        lengths.append(n)
    total = sum(lengths)
    if total > max_length:
        raise WordTooLongError(
            f"m = {m}일 때 w가 너무 길어요. 펌핑하면 더 길어지기 때문에 w는 {max_length}글자 이하여야 해요."
        )
    return "".join(ch * n for (ch, _), n in zip(blocks, lengths))


# ---------- 분할, 수비, 스매시 ----------


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


def choose_defense(splits: list[Split], rng: random.Random, random_rate: float = 0.2) -> tuple[Split, str]:
    """Lemma의 수비(분할) 선택.

    기본은 가장 까다로운 코스: 통하는 i가 가장 적은 분할 (동률이면 그중 무작위).
    random_rate 확률로 아무 분할이나 고른다. 이때 운 좋은 득점이 생길 수 있어서, 화면에서 수비 코스 분석으로 알려준다.
    """
    if rng.random() < random_rate:
        return rng.choice(splits), "random"
    fewest = min(len(s.breaking) for s in splits)
    return rng.choice([s for s in splits if len(s.breaking) == fewest]), "tough"


def mistake_rate(point: int) -> float:
    """컴퓨터가 최선이 아닌 수를 두는 확률. 포인트가 진행될수록 줄어든다.

    point는 0부터 센다: 1포인트 40%, 2포인트 30%, 3포인트 20%, 그 뒤로 10%.
    깨는 쪽에서는 Lemma(컴퓨터)의 수비에, 막는 쪽에서는 컴퓨터의 리시브에 적용한다.
    """
    return round(max(0.1, 0.4 - 0.1 * point), 2)


def split_error(word: str, m: int, start: int, end: int) -> str | None:
    """분할이 펌핑 보조정리의 조건(|xy| ≤ m, |y| ≥ 1)을 지키는지. 지키면 None."""
    if not (0 <= start < end <= len(word)):
        return "y는 w 안의 한 글자 이상이어야 해요 (|y| ≥ 1)."
    if end > m:
        return f"|xy|({end})가 m({m})보다 길어요. y는 w의 앞쪽 m글자 안에서 골라야 해요 (|xy| ≤ m)."
    return None


# ---------- 막는 쪽: 컴퓨터의 리시브와 스매시 ----------


def candidate_words(language: BlockLanguage, m: int, max_length: int | None = None) -> list[str]:
    """컴퓨터가 리시브로 고를 수 있는 w: L에 속하고 m ≤ |w| ≤ max_length인 문자열 (짧은 것부터).

    블록 길이 조합(n0, n1, ...)을 모두 만들어 조건식을 만족하는 것만 남긴다. 기본 max_length는 2m + 3이다.
    """
    max_length = 2 * m + 3 if max_length is None else max_length
    k = len(language.blocks)
    words = set()

    def build(prefix: tuple[int, ...], budget: int):
        if len(prefix) == k:
            if sum(prefix) >= m and language._satisfies(prefix):
                words.add("".join(ch * n for ch, n in zip(language.blocks, prefix)))
            return
        for n in range(budget + 1):
            build(prefix + (n,), budget - n)

    build((), max_length)
    return sorted(words, key=lambda w: (len(w), w))


def beaten_fraction(language: BlockLanguage, word: str, m: int) -> float:
    """w로 리시브했을 때 뚫을 수 있는 수비 코스의 비율. 1.0이면 어떤 수비도 뚫는 리시브다."""
    splits = analyze_splits(language, word, m)
    return sum(1 for s in splits if s.breaking) / len(splits)


@dataclass
class ReceiveChoice:
    word: str
    mode: str  # "best" (최선) 또는 "mistake" (실수)
    winning: bool  # 어떤 수비도 뚫을 수 있는 리시브인지


def choose_receive(language: BlockLanguage, m: int, rng: random.Random, rate: float) -> ReceiveChoice | None:
    """컴퓨터(깨는 쪽)의 리시브 선택.

    기본은 뚫을 수 있는 수비 코스의 비율이 가장 높은 w (동률이면 가장 짧은 것들 중 무작위).
    rate 확률로 그보다 약한 w를 고른다 (실수). 고를 수 있는 w가 없으면 None.
    """
    words = candidate_words(language, m)
    if not words:
        return None
    scored = [(w, beaten_fraction(language, w, m)) for w in words]
    best = max(score for _, score in scored)
    if rng.random() < rate:
        weaker = [w for w, score in scored if score < best] or words
        word, mode = rng.choice(weaker), "mistake"
    else:
        top = [w for w, score in scored if score == best]
        shortest = min(len(w) for w in top)
        word, mode = rng.choice([w for w in top if len(w) == shortest]), "best"
    return ReceiveChoice(word=word, mode=mode, winning=dict(scored)[word] == 1.0)


def best_receives(language: BlockLanguage, m: int) -> tuple[list[str], int]:
    """어떤 수비도 뚫는 리시브(w) 목록과 후보 전체 수. 목록이 비면 이 m에서는 막는 쪽이 언제나 막을 수 있다."""
    words = candidate_words(language, m)
    return [w for w in words if beaten_fraction(language, w, m) == 1.0], len(words)


def computer_smash(language: BlockLanguage, word: str, start: int, end: int) -> int | None:
    """컴퓨터(깨는 쪽)의 스매시: xyⁱz ∉ L이 되는 가장 작은 i. 그런 i가 SMASH_VALUES에 없으면 None."""
    for i in SMASH_VALUES:
        if not language.contains(pump(word, start, end, i)):
            return i
    return None


# ---------- 증명문 ----------


def _polynomial(expr: str) -> dict[int, int]:
    """지수식을 m에 대한 다항식 {차수: 계수}로 바꾼다. 예: '2*(m+1)' → {1: 2, 0: 2}.

    parse_template을 통과한 식(정수, m, +, -, *, 괄호)만 받는다.
    """

    def add(p, q, sign=1):
        r = dict(p)
        for d, c in q.items():
            r[d] = r.get(d, 0) + sign * c
        return {d: c for d, c in r.items() if c}

    def mul(p, q):
        r: dict[int, int] = {}
        for d1, c1 in p.items():
            for d2, c2 in q.items():
                r[d1 + d2] = r.get(d1 + d2, 0) + c1 * c2
        return {d: c for d, c in r.items() if c}

    def conv(node):
        if isinstance(node, ast.Expression):
            return conv(node.body)
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return {0: node.value} if node.value else {}
        if isinstance(node, ast.Name) and node.id == "m":
            return {1: 1}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return {d: -c for d, c in conv(node.operand).items()}
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return add(conv(node.left), conv(node.right))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
            return add(conv(node.left), conv(node.right), -1)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            return mul(conv(node.left), conv(node.right))
        raise ExpressionError(f"식 '{expr}'에는 정수, m, +, -, *, 괄호만 쓸 수 있어요.")

    try:
        return conv(ast.parse(expr, mode="eval"))
    except SyntaxError as e:
        raise ExpressionError(f"식 '{expr}'를 해석할 수 없어요.") from e


def _affine(expr: str) -> tuple[int, int] | None:
    """지수식이 a·m + b 꼴이면 (a, b), 아니면(m² 등) None."""
    poly = _polynomial(expr)
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
