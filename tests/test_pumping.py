import random

import pytest

from catching_lemma.engine.pumping import (
    MAX_RECEIVE_CANDIDATES,
    analyze_splits,
    beaten_fraction,
    best_receives,
    build_proof,
    choose_receive,
    computer_smash,
    is_winning_receive,
    pump,
    receive_scores,
    regular_candidate_words,
    split_error,
)
from catching_lemma.engine.pumping_common import (
    SMASH_VALUES,
    BlockLanguage,
    ExpressionError,
    TemplateError,
    WordTooLongError,
    choose_defense,
    evaluate,
    expand_template,
    max_receive_length,
    mistake_rate,
    parse_template,
)

ANBN = BlockLanguage(["a", "b"], "n0 == n1")
A_LESS_B = BlockLanguage(["a", "b"], "n1 > n0")


# ---------- 식 계산 ----------


def test_evaluate_arithmetic_and_comparison():
    assert evaluate("n0 == n1", {"n0": 2, "n1": 2}) is True
    assert evaluate("2*m + 1", {"m": 3}) == 7
    assert evaluate("n0 < n1 <= n2", {"n0": 1, "n1": 2, "n2": 2}) is True
    assert evaluate("n0 != n1 and not n0 == 0", {"n0": 1, "n1": 2}) is True
    assert evaluate("is_square(n0)", {"n0": 9}) is True
    assert evaluate("is_prime(n0)", {"n0": 9}) is False


@pytest.mark.parametrize(
    "expr",
    ["__import__('os')", "n0.real", "[1, 2]", "n0 ** 2", "x == 1", "lambda: 1", "m // 0"],
)
def test_evaluate_rejects_unsafe_or_unknown(expr):
    with pytest.raises(ExpressionError):
        evaluate(expr, {"n0": 1, "m": 1})


def test_evaluate_arithmetic_only():
    assert evaluate("2*(m+1)-3", {"m": 4}, arithmetic_only=True) == 7
    for expr in ["is_prime(m)", "m // 2", "m % 2", "m == 3", "not m", "m and 1"]:
        with pytest.raises(ExpressionError):
            evaluate(expr, {"m": 4}, arithmetic_only=True)


def test_is_prime_is_fast_and_correct_for_large_numbers():
    import time

    start = time.perf_counter()
    assert evaluate("is_prime(n0)", {"n0": 10**18 + 9}) is True  # 10^18 다음 소수
    assert evaluate("is_prime(n0)", {"n0": 10**18 + 1}) is False
    assert evaluate("is_prime(n0)", {"n0": 561}) is False  # 카마이클 수
    assert time.perf_counter() - start < 0.5
    small = [n for n in range(60) if evaluate("is_prime(n0)", {"n0": n})]
    assert small == [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59]
    with pytest.raises(ExpressionError):
        evaluate("is_prime(n0)", {"n0": 10**40})


# ---------- 블록 언어 ----------


def test_block_language_contains():
    assert ANBN.contains("")
    assert ANBN.contains("aabb")
    assert not ANBN.contains("aab")
    assert not ANBN.contains("abab")  # 블록 순서가 어긋남
    assert not ANBN.contains("ba")
    assert A_LESS_B.contains("abb")
    assert not A_LESS_B.contains("aabb")


def test_block_language_with_repeated_letter():
    # a^n b a^n: 'a' 블록이 두 번 나와서 분해 방법이 여러 개다
    lang = BlockLanguage(["a", "b", "a"], "n0 == n2 and n1 == 1")
    assert lang.contains("aabaa")
    assert lang.contains("b")
    assert not lang.contains("aaba")
    assert not lang.contains("aa")


# ---------- 템플릿 ----------


def test_parse_and_expand_template():
    blocks = parse_template("a^m b^(m+1)", ["a", "b"])
    assert blocks == [("a", "m"), ("b", "m+1")]
    assert expand_template(blocks, 3) == "aaabbbb"
    assert expand_template(parse_template("a^{2m}b^m", ["a", "b"]), 2) == "aaaabb"
    assert expand_template(parse_template("a^(2m) b", ["a", "b"]), 2) == "aaaab"
    assert expand_template(parse_template("a^3b^m", ["a", "b"]), 2) == "aaabb"


@pytest.mark.parametrize(
    "template",
    [
        "", "c^m", "a^m b^", "a^(m+) b", "a^m + b^m", "a^x",
        # 지수에는 정수, m, + - *, 괄호만 (함수 호출, 나눗셈, 비교, 참/거짓은 안 됨)
        "a^{is_prime(m)}", "a^{m//2}", "a^{m%2}", "a^{m==3}", "a^{not m}", "a^{m>1 and m}",
        "a^m" * 40,  # 템플릿 길이 상한
    ],
)
def test_parse_template_errors(template):
    with pytest.raises(TemplateError):
        parse_template(template, ["a", "b"])


def test_expand_template_negative_exponent():
    with pytest.raises(TemplateError):
        expand_template(parse_template("a^(m-5)", ["a"]), 3)


def test_expand_template_converts_expression_error():
    # parse_template을 거치지 않은 블록이 들어와도 ExpressionError가 아니라 TemplateError로 알린다
    with pytest.raises(TemplateError):
        expand_template([("a", "m // 0")], 3)
    with pytest.raises(TemplateError):
        expand_template([("a", "m == 3")], 3)


# ---------- 분할과 수비 ----------


def test_split_count_and_conditions():
    word = "aaaabbbb"
    splits = analyze_splits(ANBN, word, 4)
    assert len(splits) == 4 * 5 // 2  # 0 ≤ |x| < |xy| ≤ m 인 경우의 수
    for s in splits:
        x, y, z = s.parts(word)
        assert len(x + y) <= 4 and len(y) >= 1 and x + y + z == word


def test_good_receive_beats_every_split():
    word = "aaaabbbb"  # a^m b^m, m = 4
    assert all(s.breaking for s in analyze_splits(ANBN, word, 4))


def test_bad_receive_has_unbeatable_split():
    # aⁿbᵏ(k > n)에서 w = b^m을 고르면 y는 b로만 이루어진다.
    # b를 늘리면(i ≥ 2) 여전히 L 안이고, 줄여도(i = 0) b가 하나 이상 남으면 L 안이다.
    word = "bbbb"
    splits = analyze_splits(A_LESS_B, word, 4)
    assert any(not s.breaking for s in splits)  # Lemma가 받아낼 수 있는 코스가 있다


def test_smash_needs_i_at_least_2_for_a_less_b():
    word = "aaabbbb"  # a^m b^(m+1), m = 3
    for s in analyze_splits(A_LESS_B, word, 3):
        assert 0 not in s.breaking  # a를 줄이면 여전히 b가 더 많다
        assert 2 in s.breaking


def test_choose_defense_prefers_toughest():
    word = "aaabbbb"
    splits = analyze_splits(A_LESS_B, word, 3)
    rng = random.Random(0)
    split, mode = choose_defense(splits, rng, random_rate=0.0)
    assert mode == "tough"
    assert len(split.breaking) == min(len(s.breaking) for s in splits)


def test_choose_defense_random_mode():
    splits = analyze_splits(ANBN, "aaabbb", 3)
    split, mode = choose_defense(splits, random.Random(0), random_rate=1.0)
    assert mode == "random"
    assert split in splits


def test_pump():
    assert pump("aaabbb", 1, 2, 0) == "aabbb"
    assert pump("aaabbb", 1, 2, 3) == "aaaaabbb"
    assert set(SMASH_VALUES) >= {0, 2}


# ---------- 증명문 ----------


def test_proof_for_anbn_uses_i_0():
    proof = build_proof(ANBN, "a의 개수와 b의 개수가 같다", "a^m b^m", [3, 4, 5, 6, 7])
    assert proof.available
    assert proof.smash == 0
    assert "w = a^{m}b^{m}" in proof.text and "다음 문자열을 고른다" in proof.text
    assert "a^{m-k}b^{m}" in proof.text


def test_proof_for_a_less_b_uses_i_2():
    proof = build_proof(A_LESS_B, "b의 개수가 a의 개수보다 많다", "a^m b^(m+1)", [3, 4, 5, 6, 7])
    assert proof.available
    assert proof.smash == 2
    assert "a^{m+k}b^{m+1}" in proof.text


def test_proof_keeps_multiplication_in_exponent():
    # 2*(m+1)을 '2(m+1)'처럼 곱셈 없이 이어 쓰지 않고 정리된 일차식으로 쓴다
    lang = BlockLanguage(["a", "b"], "n1 == 2 * n0")
    proof = build_proof(lang, "b가 a의 두 배", "a^{m} b^{2*(m+1)-2}", [3, 4, 5, 6, 7])
    assert proof.available
    assert "w = a^{m}b^{2m}" in proof.text
    assert "2(m" not in proof.text


def test_proof_requires_first_block_at_least_m_for_every_m():
    # a^7 b^7은 m = 3~7에서는 첫 블록 ≥ m이지만 m = 8부터 아니다 → 증명문을 쓰지 않는다
    proof = build_proof(ANBN, "같다", "a^7 b^7", [3, 4, 5, 6, 7])
    assert not proof.available
    assert "첫 블록" in proof.reason
    # 2m-1 ≥ m (m ≥ 1)은 통과, m-1은 통과하지 않음
    assert build_proof(ANBN, "같다", "a^(2m-1) b^(2m-1)", [3, 4, 5]).available
    assert not build_proof(ANBN, "같다", "a^(m-1) b^(m-1)", [3, 4, 5]).available


def test_proof_unavailable_for_non_affine_exponent():
    proof = build_proof(ANBN, "같다", "a^{m*m} b^{m*m}", [3, 4])
    assert not proof.available
    assert "일차식" in proof.reason


def test_proof_unavailable_when_first_block_short():
    proof = build_proof(ANBN, "같다", "a b", [3, 4])
    assert not proof.available  # w = ab는 첫 블록 길이 1 < m (게다가 |w| < m)


def test_proof_unavailable_when_not_in_language():
    proof = build_proof(A_LESS_B, "많다", "a^m b^m", [3, 4])
    assert not proof.available
    assert "L에 속하지 않아요" in proof.reason


# ---------- 실수 비율과 분할 규칙 ----------


def test_mistake_rate_decreases_with_points():
    rates = [mistake_rate(p) for p in range(6)]
    assert rates == [0.2, 0.1, 0.0, 0.0, 0.0, 0.0]


def test_luck_alone_cannot_win():
    """실수가 나올 수 있는 포인트 수가 이기는 데 필요한 점수(app.py의 WIN_POINTS = 3)보다 적다.

    즉 컴퓨터의 실수만으로는 경기를 이길 수 없다. 경기는 최대 5포인트(3:2)까지 간다.
    """
    win_points = 3
    lucky_points = sum(1 for p in range(2 * win_points - 1) if mistake_rate(p) > 0)
    assert lucky_points < win_points


def test_split_error():
    assert split_error("aaabbb", 3, 0, 1) is None
    assert split_error("aaabbb", 3, 1, 1) is not None  # |y| = 0
    assert split_error("aaabbb", 3, 2, 4) is not None  # |xy| = 4 > m
    assert split_error("aa", 3, 0, 3) is not None  # w 밖


# ---------- 막는 쪽: 컴퓨터의 리시브와 스매시 ----------

EVEN_A = BlockLanguage(["a"], "n0 % 2 == 0")  # (aa)*: 정규 언어
A_STAR_B_STAR = BlockLanguage(["a", "b"], "n0 >= 0")  # a*b*: 정규 언어


def test_regular_candidate_words():
    words = regular_candidate_words(ANBN, 3)
    assert words == ["aabb", "aaabbb", "aaaabbbb"]  # |w| ≥ 3, |w| ≤ 2·3 + 3
    assert all(len(w) >= 3 and A_LESS_B.contains(w) for w in regular_candidate_words(A_LESS_B, 3))


def test_non_regular_language_always_has_winning_receive():
    for language in (ANBN, A_LESS_B):
        for m in range(1, 9):
            winning, total = best_receives(language, m)
            assert winning and total, m


def test_regular_language_has_no_winning_receive_for_large_m():
    # (aa)*는 m = 1이면 y = a 하나라 i = 0에서 홀수가 되지만, m ≥ 2면 y = aa로 언제나 막을 수 있다
    assert best_receives(EVEN_A, 1)[0]
    for m in range(2, 9):
        assert best_receives(EVEN_A, m)[0] == []
    for m in range(1, 9):
        assert best_receives(A_STAR_B_STAR, m)[0] == []


def test_choose_receive_best_and_mistake():
    best = choose_receive(ANBN, 3, random.Random(0), rate=0.0)
    assert best.mode == "best" and best.winning
    # A_LESS_B는 뚫을 수 없는 코스가 있는 약한 w도 후보에 있다
    mistake = choose_receive(A_LESS_B, 3, random.Random(0), rate=1.0)
    assert mistake.mode == "mistake" and not mistake.winning


def test_choose_receive_none_when_no_candidates():
    empty = BlockLanguage(["a"], "n0 == 1")  # 유한 언어 {a}: m = 3 이상인 w가 없다
    assert choose_receive(empty, 3, random.Random(0), rate=0.0) is None


def test_computer_smash():
    assert computer_smash(ANBN, "aaabbb", 0, 1) == 0
    assert computer_smash(EVEN_A, "aaaa", 0, 2) is None  # y = aa는 몇 번 펌핑해도 짝수
    assert computer_smash(EVEN_A, "aaaa", 0, 1) == 0  # y = a는 i = 0에서 홀수


# ---------- 길이 상한 (검토에서 찾은 문제) ----------


def test_huge_exponent_is_rejected_before_building_string():
    """a^(10000000000)처럼 지수가 커도 문자열을 만들기 전에 거부한다 (메모리 고갈 방지)."""
    import time

    start = time.perf_counter()
    with pytest.raises(WordTooLongError):
        expand_template(parse_template("a^(10000000000)", ["a"]), 3)
    assert time.perf_counter() - start < 0.5


def test_receive_length_leaves_room_for_pumping():
    for m in range(1, 9):
        limit = max_receive_length(m)
        assert limit + (max(SMASH_VALUES) - 1) * m <= 200


def test_proof_with_too_long_template_is_unavailable_not_error():
    # m = 3에서는 리시브할 수 있지만 m = 7에서는 너무 긴 w
    proof = build_proof(ANBN, "같다", "a^(14m) b^(14m)", [3, 4, 5, 6, 7])
    assert not proof.available
    assert "너무 길어요" in proof.reason


# ---------- 리시브 계산량 (검토에서 찾은 문제) ----------


@pytest.mark.parametrize("language", [ANBN, A_LESS_B, EVEN_A, A_STAR_B_STAR])
def test_early_exit_matches_full_analysis(language):
    """i 하나를 찾으면 멈추는 계산이 모든 i를 보는 analyze_splits와 같은 결과를 낸다."""
    for m in range(1, 7):
        for score in receive_scores(language, m):
            splits = analyze_splits(language, score.word, m)
            assert score.total == len(splits)
            assert score.beaten == sum(1 for s in splits if s.breaking)
            assert score.winning == is_winning_receive(language, score.word, m)
            assert beaten_fraction(language, score.word, m) == score.beaten / score.total


@pytest.mark.parametrize("language", [ANBN, A_LESS_B, EVEN_A, A_STAR_B_STAR])
def test_best_receives_same_with_or_without_shared_scores(language):
    for m in range(1, 7):
        assert best_receives(language, m) == best_receives(language, m, scores=receive_scores(language, m))


def test_choose_receive_same_with_or_without_shared_scores():
    for rate in (0.0, 1.0):
        for seed in range(5):
            a = choose_receive(A_LESS_B, 4, random.Random(seed), rate)
            b = choose_receive(A_LESS_B, 4, random.Random(seed), rate, scores=receive_scores(A_LESS_B, 4))
            assert a == b


def test_early_exit_reduces_membership_checks():
    calls = {"n": 0}

    class Counting(BlockLanguage):
        def contains(self, word):
            calls["n"] += 1
            return super().contains(word)

    lang = Counting(["a", "b"], "n1 > n0")
    receive_scores(lang, 6)
    full = sum(len(analyze_splits(A_LESS_B, w, 6)) * len(SMASH_VALUES) for w in regular_candidate_words(A_LESS_B, 6))
    assert calls["n"] < full
    assert MAX_RECEIVE_CANDIDATES >= len(regular_candidate_words(A_STAR_B_STAR, 8))
