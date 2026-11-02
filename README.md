# Baton (바톤)

> **전임자는 떠나도, 결정의 이유는 남는다.**
> 업무를 인수인계받은 사람이 "이거 왜 이렇게 됐어?"라고 물으면, 메일에서 결정 흐름을 찾아 원본 출처와 함께 보여주는 사내 AI 에이전트

![status](https://img.shields.io/badge/status-S1%20개발%20중-orange)

## 왜 만드나

인수인계 문서에는 "무엇"은 남지만 "왜 그렇게 결정했는지"는 남지 않습니다.
그 이유는 메일 스레드 여러 개에 흩어져 있어서, 후임은 전임자에게 다시 묻거나 이미 끝난 논의를 반복합니다.
기획자로서 8개 프로덕트를 인수인계받으며 겪은 이 문제를 직접 풀어보는 프로젝트입니다.

## 어떻게 동작하나

```
메일 ─▶ 수집 ─▶ 정제 ─▶ 개인정보 가림 ─▶ 결정 추출 ─▶ 색인
질문 ─▶ 권한 필터 ─▶ 검색 ─▶ 근거 판단 ─▶ 답변 생성 ─▶ 출처 검증 ─▶ 화면
```

- **근거가 없으면 답하지 않습니다.** 추측 대신 "찾지 못했어요"라고 답합니다.
- **모든 답변에 출처 메일이 붙습니다.** 출처는 코드가 실제 메일 본문과 대조해 검증합니다.
- **개인정보는 저장 전에 가립니다.** LLM에는 가린 텍스트만 전달됩니다.

## 진행 상황

| 단계 | 내용 | 상태 |
|---|---|---|
| S1 | 합성 메일 → 정제 → 가림 → 검색 → 답변 → 위젯 화면 | 🚧 진행 중 |
| S2 | 결정 이벤트 추출 + 구조화 답변 + 출처 검증 | ⏳ |
| S3 | 하이브리드 검색 + 리랭커 + 평가셋 20문항 측정 | ⏳ |
| S4~ | Gmail 연결 · 권한 · 사내 파일럿 (회사 승인 필요) | ⏳ |

## 폴더 구조

```
src/baton/
  ingest/   ② 메일 읽기 (mbox · eml → 공통 형식)
  clean/    ③ 인용문 · 서명 · 자동 메일 제거
  mask/     ④ 개인정보 가림
  extract/  ⑤ 결정 이벤트 추출 (S2)
  index/    ⑥ 검색 색인
  answer/   ⑦~⑪ 검색 · 답변 · 출처 검증
app/        위젯 화면 (Chainlit)
eval/       평가셋 · 채점
data/synthetic/  합성 메일 (공개)
data/real/       실제 메일 (git에 올리지 않음)
docs/devlog/     개발일지
```

## 실행 방법

```bash
# 1. uv 설치 후 (https://docs.astral.sh/uv/)
uv sync

# 2. API 키 설정
cp .env.example .env   # .env 파일에 ANTHROPIC_API_KEY 입력

# 3. 합성 메일 생성 · 테스트
uv run python scripts/make_synthetic_mails.py
uv run pytest tests -q
```

> 실행 명령은 S1 단계가 진행되면서 추가됩니다.

## 데이터 원칙

- 이 레포에는 **가상 회사의 합성 메일만** 올라갑니다. 실제 메일은 `data/real/`에 두며 git에서 제외됩니다.
- API 키는 `.env`에만 두고 커밋하지 않습니다.

## 기술 스택

Python 3.12 · uv · Anthropic Claude API · ChromaDB · Chainlit · (예정) LangChain · LangSmith · PostgreSQL + pgvector
