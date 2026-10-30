<img width="1917" height="972" alt="image" src="https://github.com/user-attachments/assets/b7ef31a3-ee81-4bf4-84c5-9dc19ce98687" />
<img width="1915" height="968" alt="image" src="https://github.com/user-attachments/assets/382c35be-0878-441c-a963-fafda0c51a5c" />

보너스 과제: 서비스 내보내기, 다크모드

<img width="325" height="253" alt="image" src="https://github.com/user-attachments/assets/4a390fde-56e9-4307-8cd9-25e210a71f30" />
<img width="1917" height="955" alt="image" src="https://github.com/user-attachments/assets/5061acb1-c29f-4a3f-8e73-49cb475f1217" />


<<<<<<< HEAD
# 💰 나만의 재무 비서 — 내 지출 데이터를 아는 AI

일반 챗봇은 "이번 달 지출 어때?"라고 물으면 일반론만 답합니다.
이 서비스는 **내 소비 지출 시계열 데이터를 분석한 요약을 GPT 시스템 프롬프트에 주입**해서, 실제 숫자에 근거한 맞춤형 답변을 제공합니다.

- 지출 데이터 CRUD (date, value, memo) → Firestore 저장
- 데이터 요약(기간·개수·합계/평균/최대/최소·최근 추세·이번 달 예상·카테고리 비중) 자동 계산
- 요약을 시스템 프롬프트에 넣어 GPT 호출 → 대화는 Firestore에 자동 저장
- 대화 목록/불러오기/삭제, 월별 지출 그래프, CSV 내보내기, 다크 모드

## 배포 URL

| 구분 | URL |
|---|---|
| 프론트엔드 (Vercel) | `https://financial-management-mu-three.vercel.app` |
| 백엔드 API (Render) | `https://finance-management-api-n14t.onrender.com` |
| Swagger UI | `https://finance-management-api-n14t.onrender.com/docs` |

> ⚠️ Render 무료 티어는 15분간 요청이 없으면 잠듭니다. 첫 접속 시 최대 1분 정도 걸릴 수 있으며, 프론트엔드가 접속 즉시 `/health`를 호출해 서버를 깨우고 안내 배너를 표시합니다.

## 기술 스택

| 영역 | 기술 |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, Uvicorn |
| DB | Firebase Firestore (`firebase-admin`) |
| AI | OpenAI Chat Completions API (`gpt-4o-mini`, 모델은 환경 변수로 변경 가능) |
| Frontend | HTML / CSS / Vanilla JavaScript (프레임워크 없음), SVG 차트 직접 구현 |
| 배포 | Render (백엔드), Vercel (프론트엔드) |

## 프로젝트 구조

```
backend/
├── main.py                  # 앱 생성, CORS, 라우터 등록, 전역 예외 처리
├── app/
│   ├── config.py            # 환경 변수 로딩
│   ├── db.py                # Firestore 접근 계층 (+ 테스트용 메모리 저장소)
│   ├── schemas.py           # Pydantic 요청/응답 스키마 (입력 검증)
│   ├── routers/             # HTTP 계층: 경로, 상태코드, 에러 → HTTP 변환
│   │   ├── data.py  conversations.py  chat.py
│   └── services/            # 비즈니스 로직: 요약 계산, 대화 저장, GPT 호출
│       ├── data_service.py  summary_service.py
│       ├── conversation_service.py  chat_service.py
├── scripts/
│   ├── generate_data.py     # 2026년 가상 지출 데이터 생성 (667건)
│   └── seed_firestore.py    # CSV → Firestore 업로드
├── data/spending_2026.csv
└── tests/test_api.py
frontend/
├── index.html  style.css  app.js
├── config.js                # 로컬용 API 주소
└── build.js                 # Vercel 빌드 시 API_BASE_URL → dist/config.js 생성
```

**분리 기준**: 라우터는 "HTTP를 어떻게 받고 돌려줄지"만, 서비스는 "무엇을 계산·저장할지"만 담당합니다. 덕분에 `/api/chat`이 HTTP 요청 없이 `summary_service.get_summary()`를 직접 재사용할 수 있습니다.

## API

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/data` | 지출 추가 |
| GET | `/api/data` | 목록 조회 (`start`, `end`, `limit`, `order` 쿼리 지원) |
| PUT | `/api/data/{id}` | 수정 (보낸 필드만 부분 수정) |
| DELETE | `/api/data/{id}` | 삭제 |
| GET | `/api/data/summary` | 데이터 요약 (프롬프트 주입용) |
| POST | `/api/conversations` | 대화 저장 |
| GET | `/api/conversations` | 대화 목록 — **messages 미포함** (id, title, message_count, 시각) |
| GET | `/api/conversations/{id}` | 특정 대화의 전체 messages 조회 |
| DELETE | `/api/conversations/{id}` | 대화 삭제 |
| POST | `/api/chat` | AI 채팅 (요약 주입 → GPT → 자동 저장) |
| GET | `/health` | 헬스 체크 / 서버 깨우기 |

### 컨텍스트 주입 흐름 (`POST /api/chat`)

1. `summary_service.get_summary()`로 데이터 요약 조회 (`/api/data/summary`와 동일 로직, 데이터 변경 시에만 재계산하는 캐시 적용)
2. 요약을 텍스트로 변환해 시스템 프롬프트의 `[사용자 지출 데이터 요약]` 자리에 삽입
3. `system + 이전 대화 최근 10개 + 사용자 질문`으로 GPT 호출 (`max_completion_tokens=500`)
4. 질문/답변을 `conversations`에 저장 (`conversation_id`가 없으면 새 대화 생성)

### Firestore 컬렉션

```
data/{autoId}          { date: "2026-10-30", value: 12000, memo: "식비 | 점심 식사" }
conversations/{autoId} { title, messages: [{role, content}], created_at, updated_at }
```

## 로컬 실행

### 백엔드
```bash
cd backend
py -3.12 -m venv venv          # macOS/Linux: python3.12 -m venv venv
.\venv\Scripts\Activate.ps1    # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # 값 채우기
python -m scripts.seed_firestore   # 최초 1회 (재업로드: --reset)
uvicorn main:app --reload      # http://127.0.0.1:8000/docs
```
키 없이 흐름만 확인하려면 `.env`에 `DB_BACKEND=memory` (CSV 자동 로드, 재시작 시 초기화).

### 프론트엔드
```bash
cd frontend
python -m http.server 5500     # http://127.0.0.1:5500
```
`config.js`의 기본 API 주소는 `http://127.0.0.1:8000`입니다.

## 환경 변수

**Backend (Render)**

| 이름 | 필수 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | OpenAI API 키 |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | ✅ (배포) | 서비스 계정 JSON 전체 문자열 |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | 로컬 | 서비스 계정 키 파일 경로 (JSON 대신) |
| `ALLOWED_ORIGINS` | ✅ | CORS 허용 도메인, 쉼표 구분 (예: `https://xxx.vercel.app`) |
| `OPENAI_MODEL` | | 기본 `gpt-4o-mini` |
| `OPENAI_MAX_TOKENS` | | 답변 최대 토큰, 기본 500 |
| `CHAT_HISTORY_LIMIT` | | 프롬프트에 포함할 이전 메시지 수, 기본 10 |

**Frontend (Vercel)**

| 이름 | 필수 | 설명 |
|---|---|---|
| `API_BASE_URL` | ✅ | 백엔드 주소 (예: `https://xxx.onrender.com`) |

## 보안 · 운영

- API 키와 서비스 계정 키는 환경 변수로만 관리하고 `.gitignore`로 커밋을 막습니다.
- CORS는 `ALLOWED_ORIGINS`에 등록된 도메인만 허용합니다.
- Pydantic으로 날짜 형식, 금액 범위(1원~1억 원), 문자열 길이를 검증하고 실패 시 422를 반환합니다.
- 없는 ID는 404, GPT 호출 실패는 502, 그 외 예외는 내부 정보를 숨긴 500으로 응답합니다.
- 프론트는 서버 응답을 `textContent`로 렌더링해 XSS를 방지합니다.
- 비용 제한: 답변 토큰 상한, 이전 대화 개수 제한, 요약 캐시로 Firestore 읽기 횟수 절감.

## 스크린샷

| 데이터 요약 + 채팅 | 데이터 관리 | 대화 기록 |
|---|---|---|
| ![chat](docs/screenshot-chat.png) | ![data](docs/screenshot-data.png) | ![history](docs/screenshot-history.png) |
=======
# M1-2
>>>>>>> 5631679a1eb9466071a124251ac1f6d761eaecf2
