"""화면과 엔진 사이 창구(catching_lemma.api) 테스트.

- app.py가 api만 쓰는지 (경계 규칙)
- api의 입력과 출력이 모두 JSON으로 바꿀 수 있는 값인지
"""

import ast
import json
from pathlib import Path

import pytest

from catching_lemma import api

APP = Path(__file__).resolve().parent.parent / "app.py"

DFA_WRONG = {  # dfa-01에 대한 틀린 답: "a로 시작"만 확인한다
    "type": "dfa",
    "states": ["s", "x", "a"],
    "alphabet": ["a", "b"],
    "start": "s",
    "accept": ["a"],
    "transitions": {"s": {"a": "a", "b": "x"}, "x": {"a": "x", "b": "x"}, "a": {"a": "a", "b": "a"}},
}

NFA_SECOND_LAST_A = {
    "type": "nfa",
    "states": ["q1", "q0", "q2"],
    "alphabet": ["a", "b"],
    "start": "q0",
    "accept": ["q2"],
    "transitions": {"q0": {"a": ["q1", "q0"], "b": ["q0"]}, "q1": {"a": ["q2"], "b": ["q2"]}},
}


def nth_from_last_a(n: int) -> dict:
    """끝에서 n번째 글자가 a인 NFA. 상태 n+1개, 바꾼 DFA는 상태 2^n개."""
    transitions = {"q0": {"a": ["q0", "q1"], "b": ["q0"]}}
    for i in range(1, n):
        transitions[f"q{i}"] = {"a": [f"q{i + 1}"], "b": [f"q{i + 1}"]}
    return {"type": "nfa", "states": [f"q{i}" for i in range(n + 1)], "alphabet": ["a", "b"],
            "start": "q0", "accept": [f"q{n}"], "transitions": transitions}


def roundtrips_as_json(value) -> bool:
    return json.loads(json.dumps(value)) == value


# ---------- 경계 규칙 ----------


def test_app_imports_only_api_from_package():
    """app.py는 catching_lemma 패키지에서 api 모듈만 가져온다."""
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    used = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            used += [a.name for a in node.names if a.name.split(".")[0] == "catching_lemma"]
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "catching_lemma":
            if node.module == "catching_lemma":
                used += [f"catching_lemma.{a.name}" for a in node.names]
            else:
                used.append(node.module)
    assert used, "app.py가 catching_lemma.api를 쓰지 않고 있어요"
    assert set(used) == {"catching_lemma.api"}, f"api 말고 다른 모듈을 쓰고 있어요: {sorted(set(used))}"


# ---------- 출력 형식 ----------


def test_list_stages_hides_reference():
    stages = api.list_stages("nfa")
    assert len(stages) >= 3
    assert roundtrips_as_json(stages)
    assert set(stages[0]) == {"id", "chapter", "title", "description", "hint", "alphabet"}


def test_validate_returns_dicts():
    issues = api.validate({"type": "dfa", "states": [], "alphabet": ["a"], "start": "", "accept": []})
    assert roundtrips_as_json(issues)
    assert {"level": "error", "message": "상태가 하나도 없어요."} in issues
    assert not api.is_valid({"type": "dfa", "states": [], "alphabet": ["a"], "start": "", "accept": []})


def test_run_dfa_trace_ends_with_none_when_stuck():
    machine = {"type": "dfa", "states": ["q0"], "alphabet": ["a", "b"], "start": "q0",
               "accept": ["q0"], "transitions": {"q0": {"a": "q0"}}}
    result = api.run(machine, "ab")
    assert result == {"type": "dfa", "accepted": False, "trace": ["q0", "q0", None]}
    assert roundtrips_as_json(result)


def test_run_nfa_trace_is_sorted_lists():
    result = api.run(NFA_SECOND_LAST_A, "ab")
    assert result == {"type": "nfa", "accepted": True, "trace": [["q0"], ["q0", "q1"], ["q0", "q2"]]}
    # abb: q2에서 더 갈 곳이 없어 사라지고 q0만 남는다
    assert api.run(NFA_SECOND_LAST_A, "abb")["trace"] == [["q0"], ["q0", "q1"], ["q0", "q2"], ["q0"]]
    assert roundtrips_as_json(result)


def test_grade_correct_and_wrong():
    wrong = api.grade("dfa-01", DFA_WRONG)
    assert roundtrips_as_json(wrong)
    assert wrong["correct"] is False
    assert wrong["counterexample"] == "a"
    assert wrong["expected"] is False

    right = api.grade("nfa-01", NFA_SECOND_LAST_A)
    assert right == {"correct": True, "counterexample": None, "expected": None,
                     "used_states": 3, "optimal_states": 4, "too_large": False}


def test_grade_unknown_stage():
    with pytest.raises(KeyError):
        api.grade("없는-스테이지", DFA_WRONG)


def test_to_dfa_and_normalize():
    dfa = api.to_dfa(NFA_SECOND_LAST_A)
    assert dfa["type"] == "dfa"
    assert dfa["start"] == "{q0}"
    assert roundtrips_as_json(dfa)
    assert api.grade("nfa-01", dfa)["correct"]
    # 도착 상태 순서만 다른 같은 설계는 같은 dict가 된다
    reordered = {**NFA_SECOND_LAST_A, "transitions": {"q0": {"a": ["q0", "q1"], "b": ["q0"]},
                                                      "q1": {"a": ["q2"], "b": ["q2"]}}}
    assert api.normalize(reordered) == api.normalize(NFA_SECOND_LAST_A)


def test_large_nfa_is_not_converted_or_graded():
    big = nth_from_last_a(12)  # DFA로 바꾸면 2^12 = 4096개 상태 > 상한
    assert api.MAX_DFA_STATES < 2**12
    assert api.to_dfa(big) is None
    result = api.grade("nfa-01", big)
    assert result["too_large"] is True
    assert result["correct"] is False
    assert result["counterexample"] is None
    assert roundtrips_as_json(result)
    # 화면에 그리는 것(변환 없음)은 그대로 된다
    assert api.diagram(big).startswith("digraph")


def test_diagram_highlights_counterexample():
    plain = api.diagram(DFA_WRONG)
    highlighted = api.diagram(DFA_WRONG, counterexample="a")
    assert "penwidth=2" not in plain
    assert "penwidth=2" in highlighted

    nfa_highlighted = api.diagram(NFA_SECOND_LAST_A, counterexample="ab")
    assert "style=filled" in nfa_highlighted


def test_diagram_skips_highlight_for_invalid_machine():
    broken = {**DFA_WRONG, "start": ""}
    assert "penwidth=2" not in api.diagram(broken, counterexample="a")


# ---------- 펌핑 게임 ----------


def test_list_pumping_stages_hides_answers():
    stages = api.list_pumping_stages()
    assert len(stages) >= 2
    assert roundtrips_as_json(stages)
    assert set(stages[0]) == {"id", "chapter", "title", "description", "hint", "hint_defend", "notation",
                              "alphabet", "m_values", "max_serve"}
    assert all("regular" not in s for s in stages)  # 정규 언어인지는 경기 뒤에만 알려준다


def test_pumping_receive_ok_and_errors():
    ok = api.pumping_receive("pump-01", "a^m b^m", 3)
    assert ok == {"ok": True, "word": "aaabbb", "error": None, "kind": None}
    assert api.pumping_receive("pump-01", "c^m", 3)["kind"] == "parse"
    assert api.pumping_receive("pump-01", "a b", 3)["kind"] == "too_short"
    assert api.pumping_receive("pump-02", "a^m b^m", 3)["kind"] == "not_in_language"
    # 검토에서 찾은 문제: 펌핑하면 판정 상한을 넘는 긴 w는 리시브 단계에서 돌려보낸다
    long_w = api.pumping_receive("pump-01", "a^(14m) b^(14m)", 7)
    assert long_w["ok"] is False and long_w["kind"] == "too_long"
    assert api.pumping_receive("pump-01", "a^(10000000000)", 3)["kind"] == "too_long"
    for result in [ok, api.pumping_receive("pump-01", "c^m", 3)]:
        assert roundtrips_as_json(result)


def test_pumping_defend_follows_split_rules_and_hides_breaking():
    word = "aaaabbbb"
    for seed in range(20):
        d = api.pumping_defend("pump-01", word, 4, seed=seed)
        assert roundtrips_as_json(d)
        assert set(d) == {"ok", "error", "start", "end", "x", "y", "z", "mode"}
        assert d["ok"] is True and d["error"] is None
        assert d["x"] + d["y"] + d["z"] == word
        assert len(d["x"] + d["y"]) <= 4 and len(d["y"]) >= 1
        assert d["mode"] in {"tough", "random"}


def test_pumping_defend_is_reproducible_with_seed():
    assert api.pumping_defend("pump-01", "aaabbb", 3, seed=7) == api.pumping_defend("pump-01", "aaabbb", 3, seed=7)


def test_pumping_smash_and_analysis():
    smash = api.pumping_smash("pump-01", "aaabbb", 3, 0, 1, 0)
    assert smash == {"ok": True, "error": None, "pumped": "aabbb", "in_language": False}
    analysis = api.pumping_analysis("pump-01", "aaabbb", 3)
    assert roundtrips_as_json(analysis)
    assert analysis["ok"] and analysis["total"] == 6 and analysis["beaten"] == 6
    # aⁿbᵏ(k > n)에서 w = b^4는 막을 수 있는 코스가 있다
    weak = api.pumping_analysis("pump-02", "bbbb", 4)
    assert weak["beaten"] < weak["total"]


def test_pumping_proof():
    proof = api.pumping_proof("pump-02", "a^m b^(m+1)")
    assert roundtrips_as_json(proof)
    assert proof["available"] and proof["smash"] == 2
    missing = api.pumping_proof("pump-02", "b^m")
    assert missing["available"] is False and missing["reason"]


def test_pumping_unknown_stage():
    with pytest.raises(KeyError):
        api.pumping_receive("없는-스테이지", "a^m", 3)



# ---------- 펌핑 게임: 막는 쪽 ----------


def test_pumping_mistake_rate():
    assert [api.pumping_mistake_rate(p) for p in range(5)] == [0.4, 0.3, 0.2, 0.1, 0.1]


def test_pumping_computer_receive():
    for seed in range(10):
        r = api.pumping_computer_receive("pump-01", 3, point=0, seed=seed)
        assert roundtrips_as_json(r)
        assert r["ok"] and len(r["word"]) >= 3 and r["mode"] in {"best", "mistake"}
    assert api.pumping_computer_receive("pump-01", 0)["ok"] is False
    assert api.pumping_computer_receive("pump-01", api.MAX_SERVE + 1)["ok"] is False


def test_pumping_computer_smash_on_regular_language():
    # (aa)*: y = aa는 막히고, y = a는 i = 0에 뚫린다
    held = api.pumping_computer_smash("pump-03", "aaaa", 3, 0, 2)
    assert held == {"ok": True, "error": None, "i": None, "pumped": None, "in_language": True}
    broken = api.pumping_computer_smash("pump-03", "aaaa", 3, 0, 1)
    assert broken == {"ok": True, "error": None, "i": 0, "pumped": "aaa", "in_language": False}
    invalid = api.pumping_computer_smash("pump-03", "aaaa", 3, 2, 4)  # |xy| = 4 > m
    assert invalid["ok"] is False and invalid["error"]
    assert roundtrips_as_json(invalid)


def test_pumping_best_receive_and_reveal():
    non_regular = api.pumping_best_receive("pump-01", 4)
    assert non_regular["winning_count"] >= 1 and non_regular["winning_words"]
    regular = api.pumping_best_receive("pump-04", 4)
    assert regular["ok"] and regular["winning_count"] == 0 and regular["total"] > 0
    assert roundtrips_as_json(regular)
    assert api.pumping_reveal("pump-01") == {"regular": False}
    assert api.pumping_reveal("pump-03") == {"regular": True}



# ---------- 펌핑 api 입력 확인: 잘못된 입력에도 예외 대신 ok=False ----------

BAD_WORD_CASES = [
    ("aaabb", 3),  # L에 속하지 않음
    ("ab", 3),  # |w| < m
    ("a" * 100 + "b" * 100, 7),  # 길이 상한 초과 (펌핑하면 판정 상한을 넘음)
    ("aacbb", 3),  # 언어의 글자가 아님
    (123, 3),  # 문자열이 아님
    ("aaabbb", 0),  # m이 범위 밖
    ("aaabbb", "3"),  # m이 정수가 아님
]


@pytest.mark.parametrize("word, m", BAD_WORD_CASES)
def test_pumping_api_rejects_bad_word(word, m):
    for result in (
        api.pumping_defend("pump-01", word, m, seed=0),
        api.pumping_analysis("pump-01", word, m),
        api.pumping_smash("pump-01", word, m, 0, 1, 0),
    ):
        assert result["ok"] is False and result["error"]
        assert roundtrips_as_json(result)


@pytest.mark.parametrize(
    "start, end, i",
    [(1, 1, 0), (2, 4, 0), (0, 1, 1), (0, 1, 9), ("0", 1, 0), (0, 1, "2"), (0, 1, None), (0, 1, 2.0), (0, 1, False)],
)
def test_pumping_smash_rejects_bad_split_or_i(start, end, i):
    result = api.pumping_smash("pump-01", "aaabbb", 3, start, end, i)
    assert result["ok"] is False and result["error"]


def test_defender_api_rejects_bad_input():
    assert api.pumping_computer_smash("pump-03", "aaa", 3, 0, 2)["ok"] is False  # aaa는 L 밖
    assert api.pumping_computer_smash("pump-03", "aaaa", api.MAX_SERVE + 1, 0, 2)["ok"] is False
    assert api.pumping_best_receive("pump-01", 0)["ok"] is False
    assert api.pumping_receive("pump-01", "a^m b^m", 0)["kind"] == "bad_m"
    assert api.pumping_receive("pump-01", None, 3)["ok"] is False
    assert api.pumping_proof("pump-01", None)["available"] is False


@pytest.mark.parametrize("template", ["a^{is_prime(10**18)}", "a^{m//0}", "a^{m==3} b^m", "a^{m%2}"])
def test_pumping_receive_rejects_non_arithmetic_exponent(template):
    """지수에 함수, 나눗셈, 비교를 넣으면 오래 계산하거나 예외가 나지 않고 parse 오류로 돌아온다."""
    import time

    start = time.perf_counter()
    result = api.pumping_receive("pump-01", template, 3)
    assert time.perf_counter() - start < 0.5
    assert result["ok"] is False and result["kind"] == "parse"
    assert api.pumping_proof("pump-01", template)["available"] is False


def test_receive_scores_are_computed_once_per_stage_and_m():
    api._receive_scores.cache_clear()
    api.pumping_computer_receive("pump-02", 5, seed=1)
    api.pumping_best_receive("pump-02", 5)
    api.pumping_computer_receive("pump-02", 5, seed=2)
    info = api._receive_scores.cache_info()
    assert info.misses == 1 and info.hits == 2
    # 잘못된 m은 계산 전에 걸러서 캐시에 들어가지 않는다
    assert api.pumping_computer_receive("pump-02", True)["ok"] is False
    assert api._receive_scores.cache_info().misses == 1


# ---------- 문맥자유 펌핑 게임 ----------


def test_list_cfl_stages_hides_answers():
    stages = api.list_pumping_stages("cfl_pumping")
    assert len(stages) >= 4 and roundtrips_as_json(stages)
    assert {s["chapter"] for s in stages} == {"cfl_pumping"}
    assert all("context_free" not in s and "regular" not in s for s in stages)
    assert all(s["max_serve"] >= 1 for s in stages)


def test_cfl_break_flow():
    received = api.pumping_receive("cfl-01", "a^m b^m c^m", 3)
    assert received["ok"] and received["word"] == "aaabbbccc"
    defense = api.cfl_defend("cfl-01", "aaabbbccc", 3, seed=0, point=5)
    assert defense["ok"] and roundtrips_as_json(defense)
    assert "".join(defense[p] for p in "uvxyz") == "aaabbbccc"
    smash = api.cfl_smash("cfl-01", "aaabbbccc", 3, defense["cuts"], 0)
    assert smash["ok"] and smash["in_language"] is False
    analysis = api.cfl_analysis("cfl-01", "aaabbbccc", 3)
    assert analysis["ok"] and roundtrips_as_json(analysis)
    assert analysis["total"] == analysis["beaten"] == len(analysis["splits"])
    assert sum(c["total"] for c in analysis["cases"]) == analysis["total"]
    assert all(0 <= s["case"] < len(analysis["cases"]) for s in analysis["splits"])
    report = api.cfl_case_report("cfl-01", "a^m b^m c^m")
    assert report["available"] and roundtrips_as_json(report)


def test_cfl_defend_flow_on_context_free_language():
    received = api.cfl_computer_receive("cfl-04", 4, seed=0)
    assert received["ok"]
    word = received["word"]
    k = word.index("b")
    smash = api.cfl_computer_smash("cfl-04", word, 4, [k - 1, k, k, k + 1])  # v = 마지막 a, y = 첫 b
    assert smash == {"ok": True, "error": None, "i": None, "pumped": None, "in_language": True}
    best = api.cfl_best_receive("cfl-04", 4)
    assert best["ok"] and best["winning_count"] == 0
    assert api.cfl_reveal("cfl-04") == {"context_free": True}
    assert api.cfl_reveal("cfl-01") == {"context_free": False}


@pytest.mark.parametrize("cuts", [[0, 1, 1], [0, 0, 2, 2], [0, 1, 2, 9], [2, 1, 3, 4], [0, 1, 1, True], "0112", None])
def test_cfl_api_rejects_bad_split(cuts):
    for result in (
        api.cfl_smash("cfl-01", "aaabbbccc", 3, cuts, 0),
        api.cfl_computer_smash("cfl-01", "aaabbbccc", 3, cuts),
    ):
        assert result["ok"] is False and result["error"]


def test_cfl_api_rejects_bad_word_m_and_i():
    assert api.cfl_defend("cfl-01", "aabbc", 3)["ok"] is False
    assert api.cfl_analysis("cfl-01", "aaabbbccc", 0)["ok"] is False
    assert api.cfl_smash("cfl-01", "aaabbbccc", 3, [2, 3, 4, 5], 1)["ok"] is False
    assert api.cfl_smash("cfl-01", "aaabbbccc", 3, [2, 3, 4, 5], True)["ok"] is False
    assert api.cfl_computer_receive("cfl-01", 9)["ok"] is False  # max_serve 초과
    assert api.cfl_best_receive("cfl-01", "3")["ok"] is False
    assert api.cfl_case_report("cfl-01", None)["available"] is False


def test_chapters_do_not_mix_engines():
    with pytest.raises(KeyError):
        api.pumping_defend("cfl-01", "aaabbbccc", 3)
    with pytest.raises(KeyError):
        api.cfl_defend("pump-01", "aaabbb", 3)
    with pytest.raises(KeyError):
        api.cfl_reveal("pump-01")


def test_cfl_split_cache_stays_small():
    """분할 분석 캐시는 키에 사용자 입력 w가 들어가므로 상한이 작아야 하고, 밀려나도 결과가 같아야 한다."""
    assert api._cfl_splits.cache_parameters()["maxsize"] <= 8
    api._cfl_splits.cache_clear()
    first = api.cfl_analysis("cfl-01", "aaabbbccc", 3)
    for n in range(4, 4 + api.CFL_SPLIT_CACHE_SIZE + 1):  # 다른 w로 캐시를 밀어낸다
        api.cfl_analysis("cfl-01", "a" * n + "b" * n + "c" * n, 3)
    assert api._cfl_splits.cache_info().currsize <= api.CFL_SPLIT_CACHE_SIZE
    assert api.cfl_analysis("cfl-01", "aaabbbccc", 3) == first


def test_cfl_api_limits_m_to_screen_range():
    """문맥자유 분할 계산은 |w| × m³에 비례하므로 m을 화면에서 쓰는 범위(1 ~ cfl_max_m)까지만 받는다."""
    import time

    from catching_lemma.stages import load_pumping_stages

    limits = {s.id: api.cfl_max_m(s) for s in load_pumping_stages("cfl_pumping")}
    assert limits["cfl-01"] == 8 and limits["cfl-02"] == 7  # cfl-02는 max_serve 6, m_values 최대 7
    word = "a" * 30 + "b" * 30 + "c" * 30
    for m in (9, 12, 20):
        start = time.perf_counter()
        assert api.cfl_defend("cfl-01", word, m)["ok"] is False
        assert api.cfl_analysis("cfl-01", word, m)["ok"] is False
        assert api.cfl_smash("cfl-01", word, m, [0, 1, 1, 2], 0)["ok"] is False
        assert time.perf_counter() - start < 0.5
    assert api.cfl_analysis("cfl-02", "a" * 8 + "b" * 8 + "c" * 8, 8)["ok"] is False


@pytest.mark.parametrize("m", [1, 2, 8])
def test_cfl_analysis_accepts_serves_outside_m_values(m):
    """막는 쪽에서 m_values(3 ~ 7) 밖의 m을 서브해도 포인트 뒤 분석이 돼야 한다."""
    received = api.cfl_computer_receive("cfl-04", m, seed=0)
    assert received["ok"]
    assert api.cfl_analysis("cfl-04", received["word"], m)["ok"]
