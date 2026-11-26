"""문맥자유 펌핑 게임 엔진(uvxyz 분할, 경우 분류, 리시브) 검사."""

import random

import pytest

from catching_lemma.engine.cfl_pumping import (
    Membership,
    analyze_cfl_splits,
    case_key,
    cfl_candidate_length,
    cfl_candidate_words,
    cfl_case_report,
    cfl_computer_smash,
    cfl_has_winning_receive,
    cfl_is_winning_receive,
    cfl_pump,
    cfl_receive_scores,
    cfl_split_error,
    cfl_split_ranges,
    letter_runs,
    summarize_cases,
)
from catching_lemma.engine.pumping import (
    SMASH_VALUES,
    BlockLanguage,
    best_receives,
    choose_receive,
    max_receive_length,
)

ANBNCN = BlockLanguage(["a", "b", "c"], "n0 == n1 == n2")
ANBN = BlockLanguage(["a", "b"], "n0 == n1")
A_LE_B_LE_C = BlockLanguage(["a", "b", "c"], "n0 <= n1 <= n2")
SQUARE = BlockLanguage(["a"], "is_square(n0)")


# ---------- 분할 ----------


def brute_force_splits(word, m):
    n = len(word)
    return {
        (p1, p2, p3, p4)
        for p1 in range(n + 1)
        for p2 in range(p1, n + 1)
        for p3 in range(p2, n + 1)
        for p4 in range(p3, n + 1)
        if p4 - p1 <= m and (p2 - p1) + (p4 - p3) >= 1
    }


@pytest.mark.parametrize("word, m", [("aabb", 2), ("aaabbbccc", 3), ("abc", 5), ("a", 1)])
def test_split_ranges_match_definition(word, m):
    ranges = list(cfl_split_ranges(word, m))
    assert len(ranges) == len(set(ranges))
    assert set(ranges) == brute_force_splits(word, m)
    assert all(cfl_split_error(word, m, c) is None for c in ranges)


def test_split_error():
    w = "aaabbbccc"
    assert cfl_split_error(w, 3, (2, 3, 4, 5)) is None
    assert "|vy| ≥ 1" in cfl_split_error(w, 3, (2, 2, 4, 4))
    assert "|vxy|" in cfl_split_error(w, 3, (0, 1, 3, 4))
    assert cfl_split_error(w, 3, (3, 2, 4, 5)) is not None  # 순서가 거꾸로
    assert cfl_split_error(w, 3, (0, 1, 1, 10)) is not None  # w 밖
    for bad in [(0, 1, 1), (0, 1, 1, True), (0, 1, 1, 2.0), "0112", None]:
        assert cfl_split_error(w, 3, bad) is not None


def test_pump():
    w = "aaabbbccc"
    # u = aa, v = a, x = b, y = b, z = bccc
    assert cfl_pump(w, (2, 3, 4, 5), 0) == "aa" + "b" + "bccc"
    assert cfl_pump(w, (2, 3, 4, 5), 2) == "aa" + "aa" + "b" + "bb" + "bccc"
    assert cfl_pump(w, (2, 3, 4, 5), 1) == w


def test_anbncn_every_split_breaks():
    for m in range(1, 7):
        w = "a" * m + "b" * m + "c" * m
        assert all(s.breaking for s in analyze_cfl_splits(ANBNCN, w, m)), m


def test_anbn_has_blockable_split():
    # aⁿbⁿ은 문맥자유 언어: v = 마지막 a, y = 첫 b로 막을 수 있다
    w = "aaaabbbb"
    splits = analyze_cfl_splits(ANBN, w, 4)
    blocked = [s for s in splits if not s.breaking]
    assert (3, 4, 4, 5) in {s.cuts for s in blocked}


def test_membership_memo_matches_language():
    member = Membership(ANBN)
    for word in ["", "ab", "aab", "abab", "aabb", "ab"]:
        assert member(word) == ANBN.contains(word)


def test_computer_smash():
    assert cfl_computer_smash(ANBNCN, "aaabbbccc", (2, 3, 4, 5)) == 0
    assert cfl_computer_smash(ANBN, "aaaabbbb", (3, 4, 4, 5)) is None


# ---------- 막는 쪽: 컴퓨터의 리시브 ----------


def test_candidate_length_covers_three_blocks_of_m():
    for m in range(1, 9):
        assert cfl_candidate_length(m) >= 3 * m
        assert cfl_candidate_length(m) <= max_receive_length(m)
    assert "aaabbbccc" in cfl_candidate_words(ANBNCN, 3)


@pytest.mark.parametrize("language", [ANBN, ANBNCN, A_LE_B_LE_C])
def test_receive_scores_match_full_analysis(language):
    for m in range(1, 4):
        for score in cfl_receive_scores(language, m):
            splits = analyze_cfl_splits(language, score.word, m)
            assert score.total == len(splits)
            assert score.beaten == sum(1 for s in splits if s.breaking)
            assert score.winning == cfl_is_winning_receive(language, score.word, m)


def test_non_context_free_has_winning_receive_and_cfl_does_not():
    for m in range(1, 7):
        assert cfl_has_winning_receive(ANBNCN, m)
        assert cfl_has_winning_receive(A_LE_B_LE_C, m)
        assert cfl_has_winning_receive(SQUARE, m)
    for m in range(2, 7):
        assert not cfl_has_winning_receive(ANBN, m)


def test_choose_receive_with_cfl_scores():
    scores = cfl_receive_scores(ANBNCN, 3)
    choice = choose_receive(ANBNCN, 3, random.Random(0), 0.0, scores=scores)
    assert choice.mode == "best" and choice.winning
    winning, total = best_receives(ANBNCN, 3, scores=scores)
    assert winning and total == len(scores)


# ---------- 경우 분류 ----------


def test_letter_runs():
    assert letter_runs("aabbbc") == [("a", 0, 2), ("b", 2, 5), ("c", 5, 6)]
    assert letter_runs("a") == [("a", 0, 1)]


def test_cases_partition_all_splits():
    w = "aaabbbccc"
    splits = analyze_cfl_splits(ANBNCN, w, 3)
    cases = summarize_cases(w, splits)
    assert sum(c.total for c in cases) == len(splits)
    assert len({c.key for c in cases}) == len(cases)
    runs = letter_runs(w)
    for c in cases:
        assert case_key(runs, c.example) == c.key


def test_case_count_for_blocks_at_least_m():
    """블록마다 m글자 이상이면 vxy는 이웃한 두 블록까지만 걸친다.
    v, y가 모두 비어 있지 않은 경우는 JFLAP과 같은 4k − 3가지이고, 빈 v / 빈 y는 위치별로 2k − 1가지씩 나눈다."""
    for blocks, word, m in [(["a", "b"], "aaabbb", 3), (["a", "b", "c"], "aaabbbccc", 3)]:
        k = len(blocks)
        lang = BlockLanguage(blocks, " == ".join(f"n{i}" for i in range(k)))
        cases = summarize_cases(word, analyze_cfl_splits(lang, word, m))
        both = [c for c in cases if None not in c.key]
        assert len(both) == 4 * k - 3
        assert len(cases) == (4 * k - 3) + 2 * (2 * k - 1)


def test_case_labels_and_blockable():
    w = "aaabbb"
    cases = {c.label: c for c in summarize_cases(w, analyze_cfl_splits(ANBN, w, 3))}
    assert "v: a만 · y: b만" in cases
    assert cases["v: a만 · y: b만"].blockable > 0  # aⁿbⁿ은 이 경우로 막을 수 있다
    assert cases["v: a만 · y: a만"].blockable == 0
    assert cases["v: a만 · y: a만"].common_i == tuple(SMASH_VALUES)
    assert "v: 빈 문자열 · y: b만" in cases


def test_case_labels_with_repeated_letter():
    lang = BlockLanguage(["a", "b", "a"], "n0 == n2 and n1 == 1")
    w = "aaabaaa"
    labels = [c.label for c in summarize_cases(w, analyze_cfl_splits(lang, w, 3))]
    assert any("1번째 a" in s for s in labels) and any("2번째 a" in s for s in labels)


# ---------- 경우별 정리 표 ----------


def test_case_report_for_winning_template():
    report = cfl_case_report(ANBNCN, "a^m b^m c^m", [3, 4, 5])
    assert report.available, report.reason
    assert len(report.rows) == 19
    assert all(row.smash for row in report.rows)
    assert all("".join(row.example) == "a" * 5 + "b" * 5 + "c" * 5 for row in report.rows)


def test_case_report_needs_different_i_per_case():
    report = cfl_case_report(A_LE_B_LE_C, "a^m b^m c^m", [3, 4, 5])
    assert report.available
    smash = {row.label: row.smash for row in report.rows}
    assert 0 not in smash["v: a만 · y: a만"]  # a를 줄이면 여전히 a ≤ b ≤ c
    assert 0 in smash["v: c만 · y: c만"]


@pytest.mark.parametrize(
    "language, template, reason",
    [
        (ANBN, "a^m b^m", "막히는 분할"),  # 문맥자유 언어라 막히는 경우가 있다
        (ANBNCN, "a^m b^m", "L에 속하지 않"),
        (ANBNCN, "a^7 b^7 c^7", "m글자 이상"),  # 고정 지수: m ≥ 8이면 경우 목록이 바뀌고, m ≥ 22면 |w| < m
        (ANBNCN, "a^(m-1) b^(m-1) c^(m-1)", "m글자 이상"),
        (A_LE_B_LE_C, "a^(m-3) b^m c^m", "m글자 이상"),
        (ANBNCN, "c^m", ""),  # 템플릿 오류
    ],
)
def test_case_report_unavailable(language, template, reason):
    report = cfl_case_report(language, template, [3, 4, 5])
    assert not report.available
    assert reason in report.reason


def test_case_report_accepts_polynomial_exponents():
    # a^(m*m)은 일차식이 아니지만 모든 m ≥ 1에서 m² ≥ m이라 정리 표를 만든다
    assert cfl_case_report(SQUARE, "a^(m*m)", [3, 4, 5]).available
    assert cfl_case_report(ANBNCN, "a^(2m-1) b^(2m-1) c^(2m-1)", [3, 4]).available


@pytest.mark.parametrize(
    "expr, expected",
    [("m", True), ("m*m", True), ("2*m-1", True), ("m+3", True), ("3*m*m-2*m", True),
     ("7", False), ("m-1", False), ("2*m-2", False), ("0", False), ("m*m-2*m+2", False)],
)
def test_at_least_m_for_all_m(expr, expected):
    from catching_lemma.engine.pumping import at_least_m_for_all_m

    assert at_least_m_for_all_m(expr) is expected
    if expected:  # 참이라고 했으면 실제로도 성립해야 한다
        from catching_lemma.engine.pumping import evaluate

        assert all(evaluate(expr, {"m": m}, arithmetic_only=True) >= m for m in range(1, 60))


def test_split_count_matches_enumeration():
    from catching_lemma.engine.cfl_pumping import cfl_split_count

    for n in range(0, 16):
        for m in range(1, 9):
            assert cfl_split_count(n, m) == len(list(cfl_split_ranges("a" * n, m)))


def test_case_report_requires_checked_m_at_least_3():
    """m = 1, 2에서는 v가 블록 경계에 걸치고 y가 다음 블록에 있는 경우(|vxy| ≥ 3)가 나타나지 않아서 표가 불완전하다."""
    from catching_lemma.engine.cfl_pumping import MIN_CASE_REPORT_M, cfl_case_report
    from catching_lemma.engine.pumping import BlockLanguage

    lang = BlockLanguage(["a", "b", "c"], "n0 == n1 == n2")
    assert MIN_CASE_REPORT_M == 3
    for checked in ([1, 2], [2, 3, 4], []):
        report = cfl_case_report(lang, "a^m b^m c^m", checked)
        assert not report.available and report.reason, checked
    # m = 3 하나만으로도 m = 3~7과 같은 경우 목록이 나온다
    only3 = cfl_case_report(lang, "a^m b^m c^m", [3])
    full = cfl_case_report(lang, "a^m b^m c^m", [3, 4, 5, 6, 7])
    assert only3.available and full.available
    assert [r.label for r in only3.rows] == [r.label for r in full.rows]

