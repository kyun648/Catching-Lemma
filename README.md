# Catching Lemma

> 만들고, 틀리고, 증명하는 오토마타 퍼즐

조건에 맞는 오토마타를 직접 설계해서 푸는 퍼즐 게임입니다.
설계가 틀리면 **가장 짧은 반례**와 그 반례를 실행한 경로를 보여주고,
펌핑 보조정리 게임에서는 **탁구 랠리**처럼 컴퓨터와 번갈아 공을 주고받습니다.
Lemma의 주장에 반박하는 **깨는 쪽**과 Lemma 편에서 주장을 지키는 **막는 쪽** 중 하나를 골라 플레이하고,
깨는 쪽으로 이기면 경기 기록이 **증명문으로 정리**됩니다.

## 만든 이유

형식언어와 오토마타를 공부할 때 가장 막혔던 부분은 펌핑 보조정리였습니다.
기존 도구들은 펌핑 과정을 게임이나 애니메이션으로 보여주지만,
그 과정을 **증명 문장으로 옮기는 단계**는 다루지 않습니다.
Catching Lemma는 게임의 각 차례가 증명의 어느 문장에 해당하는지 연결해 주는 것을 목표로 합니다.

## 기능 현황

| 챕터 | 내용 | 상태 |
|---|---|---|
| 1. DFA | 전이표로 DFA 설계, 자동 다이어그램, 최단 반례, 최소 상태 수 비교 | 동작 |
| 2. NFA | λ 전이를 포함한 NFA 설계, 실행 중 활성 상태 집합 추적, 부분집합 구성으로 변환한 DFA 보기 | 동작 |
| 3. 정규 펌핑 게임 | 탁구 4구 랠리 방식의 펌핑 보조정리 게임 (깨는 쪽·막는 쪽 역할 선택), 정규·비정규 언어 스테이지, 수비 코스(분할) 분석, 증명문 생성 | 동작 |
| 4. 문맥자유 펌핑 게임 | uvxyz 분할 버전 | 예정 |
| 5. PDA, 튜링머신 | 설계 퍼즐 (테스트 문자열 기반 채점) | 여유가 있으면 |

## 설치와 실행

Python 3.10 이상과 Streamlit 1.49 이상이 필요합니다 (`requirements.txt`로 함께 설치됩니다).

```bash
git clone https://github.com/kyun648/Catching-Lemma.git
cd Catching-Lemma
python -m venv .venv
```

가상환경 활성화:

```bash
# Windows (PowerShell)
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

> Windows PowerShell에서 "스크립트를 실행할 수 없습니다" 오류가 나면
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`를 한 번 실행한 뒤 다시 시도하세요.

패키지 설치와 실행:

```bash
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 `http://localhost:8501`이 열립니다.

## 테스트

```bash
pytest
```

## 프로젝트 구조

```
catching-lemma/
├── app.py                      # Streamlit 화면 (catching_lemma.api만 사용)
├── catching_lemma/
│   ├── api.py                  # 화면과 엔진 사이 창구 (dict로 주고받기)
│   ├── engine/
│   │   ├── dfa.py              # DFA 표현, 검증, 실행, 최단 반례, 최소 상태 수
│   │   ├── nfa.py              # NFA 표현, λ-closure, 실행, 부분집합 구성
│   │   └── pumping.py          # 블록 언어, w 템플릿, 분할 분석, 수비 선택, 증명문
│   ├── stages.py               # 스테이지 불러오기와 채점
│   ├── diagram.py              # DFA·NFA → Graphviz DOT 변환
│   └── stage_data/
│       ├── dfa/*.json          # DFA 스테이지 정의
│       ├── nfa/*.json          # NFA 스테이지 정의
│       └── pumping/*.json      # 펌핑 게임 언어 정의
└── tests/                      # pytest 테스트
```

표기는 교재(Linz)를 따릅니다. 빈 문자열은 λ, 펌핑 길이는 m, 펌핑할 문자열은 w, 분할은 w = xyz입니다.

화면(`app.py`)은 `catching_lemma.api`만 쓰고, 엔진과는 오토마타 JSON(dict) 형식으로만 주고받습니다.
엔진 내부를 바꿔도 `api.py`가 돌려주는 형식만 지키면 화면은 고치지 않아도 됩니다. `tests/test_api.py`가 이 규칙을 검사합니다.
펌핑 게임 api는 받은 값(m, w, 분할 위치, i)을 스스로 확인하고, 잘못된 값이면 예외 대신 `{"ok": False, "error": ...}`를 돌려줍니다.
사용자가 입력한 w는 문자열을 만들기 전에 길이를 계산하고, 펌핑한 뒤에도 판정 상한(200글자)을 넘지 않도록 w를 `200 − 4m`글자 이하로 제한합니다.

### 동작 방식

- **최단 반례**: 플레이어의 DFA와 정답 DFA를 짝지은 곱 오토마톤을 너비 우선 탐색(BFS)해서,
  두 기계의 판정이 처음으로 갈리는 문자열을 찾습니다. BFS이므로 찾은 반례가 가장 짧습니다.
- **빠진 전이**: 전이표의 빈칸은 보이지 않는 죽은 상태로 가서 거부하는 것으로 처리합니다.
  미완성 설계도 채점할 수 있도록 하기 위해서입니다.
- **최소 상태 수**: 도달 가능한 상태만 남기고 분할 세분화(Moore 알고리즘)로 구분되지 않는 상태를 합쳐서 계산합니다.
  빠진 전이가 있으면 죽은 상태 1개를 포함한 "완전한 DFA" 기준으로 셉니다.
- **NFA 채점**: 부분집합 구성(subset construction)으로 NFA를 DFA로 바꾼 뒤 위의 반례 탐색을 그대로 씁니다.
  DFA의 각 상태는 NFA 상태들의 집합이고, 시작 상태의 λ-closure에서 도달 가능한 집합만 만듭니다.
  NFA 스테이지에 DFA로 답해도 같은 언어면 정답입니다.
  NFA 상태가 n개면 DFA는 최대 2^n개까지 커질 수 있어서, 바꾼 DFA가 2,000개 상태를 넘으면 변환과 채점을 멈추고 안내합니다.
  DFA 상태 이름이 `{q0,q1}` 형식이므로 NFA 상태 이름에는 쉼표와 중괄호를 쓸 수 없습니다.

- **펌핑 게임 (탁구 4구 랠리)**: 1구 서브(m) → 2구 리시브(w) → 3구 수비(|xy| ≤ m, |y| ≥ 1인 분할) → 4구 스매시(i) 순서로,
  증명의 "모든 m / 어떤 w / 모든 분할 / 어떤 i"와 하나씩 대응합니다. 스매시가 들어가면(xyⁱz ∉ L) 깨는 쪽, 막히면 막는 쪽이 득점하고,
  먼저 3포인트를 따면 이깁니다.
  - **깨는 쪽**: Lemma(컴퓨터)가 서브와 수비를 맡습니다. 서브하는 m은 포인트마다 커지고, 수비는 통하는 i가 가장 적은 분할(가장 까다로운 코스)을 고릅니다.
  - **막는 쪽**: 내가 m을 서브하고(1~8) y 구간을 슬라이더로 골라 수비합니다. 컴퓨터는 길이 m ~ 2m+3인 L의 문자열을 모두 검사해서
    뚫을 수 있는 수비 코스가 가장 많은 w로 리시브하고, 내 분할에 통하는 i가 있으면 그 i로 스매시합니다.
  - **컴퓨터의 실수**: 최선이 아닌 수(깨는 쪽에서는 아무 분할, 막는 쪽에서는 더 약한 w)를 두는 확률이 1포인트 40%에서 시작해 포인트마다 10%씩 줄어 10%까지 내려갑니다.
  - 포인트마다 모든 분할을 검사한 **수비 코스 분석**을 보여주고, 막는 쪽에는 그 m에서 컴퓨터의 최선 리시브도 알려줍니다. 실수 덕분에 얻은 득점은 따로 알려줍니다.
  - 스테이지에는 정규가 아닌 언어와 정규 언어가 섞여 있고, 정규 언어인지는 경기가 끝난 뒤에 알려줍니다.
    정규가 아닌 언어는 깨는 쪽이, 정규 언어는 막는 쪽이 최선으로 두면 언제나 이길 수 있습니다.
  - 컴퓨터는 i = 0, 2, 3, 4, 5만 시험하므로, 막는 쪽의 "막았다"는 판정은 이 범위 안에서의 확인입니다.
- **증명문 생성**: 이긴 w로 스테이지의 모든 m과 모든 분할을 다시 검사해서, 한 가지 i로 모두 L 밖이 되면 교재 형식의 증명문을 씁니다.
  w의 첫 블록 길이가 m 이상이어서 y가 첫 블록 글자로만 이루어지는 경우만 자동으로 씁니다.
  유한한 m에 대한 확인이므로, 증명문 끝에 확인 범위를 밝히고 핵심 단계는 직접 따져보도록 안내합니다.

### 스테이지 추가하기

`catching_lemma/stage_data/<챕터>/`에 JSON 파일을 추가하면 자동으로 목록에 나타납니다.
`reference`에는 정답 기계(DFA 또는 NFA)를 넣습니다. 같은 언어를 받아들이기만 하면 플레이어의 설계 모양은 달라도 정답으로 인정됩니다.
`examples`에는 설명에 적은 예시 문자열을 넣습니다. 테스트가 정답 기계의 판정과 맞는지 확인합니다.

```json
{
  "id": "nfa-04",
  "chapter": "nfa",
  "title": "스테이지 제목",
  "description": "문제 설명",
  "hint": "힌트 (선택)",
  "alphabet": ["a", "b"],
  "examples": { "accept": ["ab"], "reject": ["ba"] },
  "reference": { "type": "nfa", "states": [], "alphabet": ["a", "b"], "start": "", "accept": [], "transitions": {} }
}
```

NFA의 `transitions`는 도착 상태 목록을 쓰고, λ 전이는 `"λ"` 키로 적습니다. 예: `{"q0": {"a": ["q0", "q1"], "λ": ["q1"]}}`

### 펌핑 게임 언어 추가하기

펌핑 게임의 언어는 **블록 언어** L = { a^n0 b^n1 … | 조건 } 으로 정의합니다.
`catching_lemma/stage_data/pumping/`에 JSON 파일을 하나 추가하면 됩니다.

```json
{
  "id": "pump-06",
  "chapter": "pumping",
  "title": "aⁿb²ⁿ",
  "description": "문제 설명",
  "hint": "깨는 쪽 힌트",
  "hint_defend": "막는 쪽 힌트",
  "regular": false,
  "language": {
    "notation": "L = \\{\\, a^n b^{2n} \\mid n \\ge 0 \\,\\}",
    "blocks": ["a", "b"],
    "constraint": "n1 == 2 * n0",
    "condition_text": "b의 개수가 a의 개수의 두 배다"
  },
  "m_values": [3, 4, 5, 6, 7],
  "examples": { "accept": ["", "abb"], "reject": ["ab", "ba"] },
  "sample_receive": "a^m b^(2m)"
}
```

- `id`: 다른 스테이지와 겹치지 않는 값. 이미 `pump-01`~`pump-05`가 있으므로 새 언어는 그다음 번호를 씁니다.
- `blocks`: 블록 글자 순서. 같은 글자가 두 번 나와도 됩니다 (예: `["a", "b", "a"]`).
- `constraint`: 블록 길이 `n0`, `n1`, …에 대한 조건식. 정수 사칙연산(`+ - * // %`), 비교, `and/or/not`, `is_square()`, `is_prime()`을 쓸 수 있습니다. `eval`을 쓰지 않는 자체 계산기로 계산합니다.
- `notation`: 화면에 보여줄 언어 표기 (LaTeX). `condition_text`: 증명문의 "조건을 만족하지 않는다" 문장에 들어갈 설명.
- `hint`, `hint_defend`: 깨는 쪽과 막는 쪽 힌트.
- `regular`: 정규 언어인지. 화면에는 경기가 끝난 뒤에만 보여주고, 테스트가 실제 게임 결과와 맞는지 확인합니다
  (정규가 아닌 언어는 모든 m(1~8)에서 어떤 수비든 뚫는 리시브가 있어야 하고, 정규 언어는 `m_values`의 모든 m에서 그런 리시브가 없어야 합니다).
- `m_values`: 깨는 쪽 게임에서 포인트마다 Lemma가 서브하는 m. 3포인트 선승이라 5개 이상 필요합니다.
- `sample_receive`: 정규가 아닌 언어에서 이기는 w의 예시. 화면에는 보내지 않고, 테스트가 이 w로 모든 m·모든 분할을 이기는지와 증명문이 만들어지는지 확인합니다. 정규 언어에는 적지 않습니다. 지수에는 플레이어 입력과 같이 정수, `m`, `+ - *`, 괄호만 쓸 수 있습니다.

## 참고자료

이 프로젝트의 코드는 직접 작성했으며, 아래 자료의 아이디어와 설계를 참고했습니다.

- P. Linz, S. H. Rodger, *An Introduction to Formal Languages and Automata*, 7th ed., Jones & Bartlett Learning, 2022 : 용어와 표기(λ, 펌핑 길이 m, w = xyz), 펌핑 보조정리의 서술

- **JFLAP** (Duke University): 오토마타 시뮬레이터와 정규·문맥자유 펌핑 보조정리 게임. 게임 진행 흐름과 언어 예시 참고
- **The Pumping Game** (Edmund Weitz), https://weitz.de/pump : 정규 언어 펌핑 보조정리 브라우저 게임
- **FSM Builder** (2024), https://arxiv.org/abs/2405.01717 : DFA·NFA 자동 채점과 반례 피드백 도구
- L. D'Antoni et al., "How Can Automatic Feedback Help Students Construct Automata?", *ACM TOCHI* 22(2), 2015 : 반례 피드백의 학습 효과
- **Manufactoria 2022** (Pleasingfungus Games): 기계 설계 퍼즐의 스테이지 구성 참고
- 형식언어와 오토마타 과목 실습 과제 경험 (과제 코드는 사용하지 않음)

## 사용한 라이브러리

| 라이브러리 | 용도 | 라이선스 |
|---|---|---|
| [Streamlit](https://github.com/streamlit/streamlit) | 웹 화면, 다이어그램 표시 | Apache-2.0 |
| [pandas](https://github.com/pandas-dev/pandas) | 전이표 편집 | BSD-3-Clause |
| [pytest](https://github.com/pytest-dev/pytest) | 테스트 | MIT |

## 라이선스

[MIT License](LICENSE)
