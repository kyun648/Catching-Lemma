# Catching Lemma

> 만들고, 틀리고, 증명하는 오토마타 퍼즐

조건에 맞는 오토마타를 직접 설계해서 푸는 퍼즐 게임입니다.
설계가 틀리면 **가장 짧은 반례**와 그 반례를 실행한 경로를 보여주고,
펌핑 보조정리 게임에서는 컴퓨터와 번갈아 두며 언어가 정규(또는 문맥자유)가 아님을 보이고,
이기면 게임 기록이 **증명문으로 정리**됩니다.

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
| 3. 정규 펌핑 게임 | p 변수 문자열 입력, 모든 분할 검사, 패배 이유 표, 증명문 생성 | 예정 |
| 4. 문맥자유 펌핑 게임 | uvxyz 분할 버전 | 예정 |
| 5. PDA, 튜링머신 | 설계 퍼즐 (테스트 문자열 기반 채점) | 여유가 있으면 |

## 설치와 실행

Python 3.10 이상이 필요합니다.

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
│   │   └── nfa.py              # NFA 표현, λ-closure, 실행, 부분집합 구성
│   ├── stages.py               # 스테이지 불러오기와 채점
│   ├── diagram.py              # DFA·NFA → Graphviz DOT 변환
│   └── stage_data/
│       ├── dfa/*.json          # DFA 스테이지 정의
│       └── nfa/*.json          # NFA 스테이지 정의
└── tests/                      # pytest 테스트
```

빈 문자열은 교재 표기를 따라 λ로 씁니다.

화면(`app.py`)은 `catching_lemma.api`만 쓰고, 엔진과는 오토마타 JSON(dict) 형식으로만 주고받습니다.
엔진 내부를 바꿔도 `api.py`가 돌려주는 형식만 지키면 화면은 고치지 않아도 됩니다. `tests/test_api.py`가 이 규칙을 검사합니다.

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

## 참고자료

이 프로젝트의 코드는 직접 작성했으며, 아래 자료의 아이디어와 설계를 참고했습니다.

- **JFLAP** (Duke University): 오토마타 시뮬레이터와 정규·문맥자유 펌핑 보조정리 게임. 게임 진행 흐름 참고
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
