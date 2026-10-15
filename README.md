# gemini-ai-bot — 24/7 AI 비서 텔레그램 봇

[![CI](https://github.com/dashcloud-kr/gemini-ai-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/dashcloud-kr/gemini-ai-bot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

**무료 Gemini API**로 동작하는 AI 비서 텔레그램 봇입니다.
대화 기억, 페르소나, 이미지 분석, 그룹방 멘션 응답을 지원하며
[대시클라우드(DashCloud)](https://dashcloud.kr)에서 **평생 무료로 24시간** 가동할 수 있습니다.

> **English** — A Telegram AI assistant powered by the free Gemini API: conversation memory, custom persona, image understanding and group mentions. Built to run 24/7 on [DashCloud](https://dashcloud.kr) for free.

## 기능

| 기능 | 설명 |
| --- | --- |
| 대화 기억 | 최근 10턴 문맥 유지 (SQLite 영구 저장), `/reset`으로 초기화 |
| 페르소나 | `/persona 너는 친절한 비서야` — 봇 성격(시스템 프롬프트) 지정 |
| 이미지 분석 | 사진을 보내면 Gemini가 한국어로 설명 (캡션을 프롬프트로 사용) |
| 그룹방 지원 | 멘션(`@봇이름`) 또는 봇 메시지에 답장할 때만 응답 |
| 사용량 보호 | 유저별 하루 30회 제한 (`/usage`) — 무료 티어 안전 |
| 오류 안내 | 한도 초과(429)·크레딧 부족(402) 등 친절한 한국어 안내 |

## 명령어

```
(그냥 메시지)           AI가 답합니다
/reset                 대화 기억 초기화
/persona 너는 비서야     페르소나 설정 (/persona off 로 해제)
/usage                 오늘 사용량 (30회/일)
(사진)                  이미지 분석
/status /id            봇 상태 / 내 chat id
```

## 준비물 — Gemini API 키 (무료)

1. [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → Google 로그인
2. **Create API key** → 프로젝트 선택(없으면 자동 생성)
3. `.env`의 `GEMINI_API_KEY`에 입력
- 기본 모델: `gemini-flash-latest` (항상 최신 Flash를 가리키는 별칭)
- 다른 모델을 쓰려면 `.env`에 `GEMINI_MODEL=gemini-3-flash-preview`처럼 지정

> **402 크레딧 오류가 나면** [ai.studio/projects](https://ai.studio/projects)에서
> 프로젝트의 무료 티어/결제 상태를 확인하세요 (키 자체는 정상이어도 프로젝트 크레딧이 없으면 호출이 거부됩니다).

## 30초 로컬 실행

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env 에 TELEGRAM_BOT_TOKEN, GEMINI_API_KEY 입력

python bot.py
```

## DashCloud로 24시간 무료 가동

1. [dashcloud.kr](https://dashcloud.kr) 가입 — 휴대폰 인증 1회, 결제 정보 불필요
2. 이 폴더를 대시보드에 **드래그 앤 드롭**
3. 환경변수에 `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY` 등록
4. 배포 — `dashcloud.json`이 런타임(Python 3.12)과 진입점을 자동 설정합니다

> 노트북을 덮어도 봇이 계속 돌아갑니다. Free 플랜은 평생 무료이며 갱신·슬립이 없습니다.

## 구조

```
gemini-ai-bot/
├── bot.py                    # 엔트리포인트
├── app/
│   ├── clients/gemini.py     # Gemini API (generateContent·이미지·429/402 처리)
│   ├── services/repository.py# SQLite (대화·페르소나·사용량)
│   ├── handlers/ai.py        # 메시지 핸들러 (개인/그룹·사진) + 명령어
│   └── utils/                # 메시지 분할 등 공통
└── tests/                    # 60개 (API 모킹·그룹 멘션·사진·한도 테스트)
```

## 테스트

```bash
pip install -r requirements-dev.txt
ruff check . && pytest -q
```

## 라이선스

[MIT](LICENSE) — 자유롭게 복사·수정·배포하세요.
