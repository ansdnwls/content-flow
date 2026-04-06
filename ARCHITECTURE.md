# ContentFlow API — 아키텍처 설계서

> 기준일: 2026-04-06
> 상태: 설계 확정 대기

---

## 1. 제품 정의

**ContentFlow API**는 소셜 미디어 통합 배포 + AI 영상 생성 API 서비스다.

### 경쟁 포지셔닝

```
Zernio:       콘텐츠(유저 준비) → 배포 API
ContentFlow:  주제 하나 → AI 영상 제작 → 배포 API
              ──────────────────────────────
              Zernio 기능 전부 + AI 생성 레이어
```

### 핵심 가치
1. **하나의 API로 14+ 플랫폼 동시 배포** (Zernio 대등)
2. **AI 영상 생성 → 배포까지 원콜** (Zernio가 못하는 영역)
3. **White-label** — 고객 브랜딩 노출 없음
4. **MCP 서버** — AI 에이전트에서 직접 호출 가능

---

## 2. 시스템 아키텍처

```
┌─────────────────────────────────────────────────┐
│                  Client Layer                    │
│  REST API  │  Python SDK  │  JS SDK  │  MCP     │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│              API Gateway (FastAPI)               │
│  Auth │ Rate Limit │ Billing │ Webhook Dispatch  │
└──────────────────┬──────────────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│ Post     │ │ Video    │ │ Account      │
│ Service  │ │ Gen      │ │ Service      │
│          │ │ Service  │ │ (OAuth Proxy)│
│ 멀티플랫폼│ │ yt-factory│ │              │
│ 동시배포  │ │ 엔진 연결 │ │ 14+ 플랫폼   │
└────┬─────┘ └────┬─────┘ └──────┬───────┘
     │            │              │
     ▼            ▼              ▼
┌──────────────────────────────────────────┐
│           Platform Adapters               │
│ YouTube│TikTok│Instagram│X│LinkedIn│...   │
└──────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────┐
│              Data Layer                   │
│  PostgreSQL (Supabase)  │  Redis (Queue)  │
└──────────────────────────────────────────┘
```

---

## 3. 핵심 모듈 구조

```
contentflow-api/
├── app/
│   ├── main.py                 # FastAPI 엔트리포인트
│   ├── config.py               # 환경변수 + 설정
│   ├── dependencies.py         # 인증/의존성 주입
│   │
│   ├── api/                    # 라우터 (REST 엔드포인트)
│   │   ├── v1/
│   │   │   ├── posts.py        # /api/v1/posts
│   │   │   ├── videos.py       # /api/v1/videos
│   │   │   ├── accounts.py     # /api/v1/accounts
│   │   │   ├── analytics.py    # /api/v1/analytics
│   │   │   ├── webhooks.py     # /api/v1/webhooks
│   │   │   └── api_keys.py     # /api/v1/keys
│   │   └── router.py
│   │
│   ├── core/                   # 공통 모듈 (src/com)
│   │   ├── auth.py             # API Key 인증 + JWT
│   │   ├── rate_limiter.py     # 요금제별 rate limit
│   │   ├── billing.py          # 사용량 추적 + 과금
│   │   ├── webhook_dispatcher.py
│   │   └── errors.py           # 통합 에러 처리
│   │
│   ├── services/               # 비즈니스 로직
│   │   ├── post_service.py     # 멀티플랫폼 포스팅
│   │   ├── video_service.py    # AI 영상 생성 오케스트레이션
│   │   ├── account_service.py  # OAuth 연결 관리
│   │   ├── analytics_service.py
│   │   └── scheduler.py        # 예약 포스팅
│   │
│   ├── adapters/               # 플랫폼 어댑터 (src/com)
│   │   ├── base.py             # 어댑터 인터페이스
│   │   ├── youtube.py
│   │   ├── tiktok.py
│   │   ├── instagram.py
│   │   ├── facebook.py
│   │   ├── x_twitter.py
│   │   ├── linkedin.py
│   │   ├── threads.py
│   │   ├── pinterest.py
│   │   ├── reddit.py
│   │   ├── bluesky.py
│   │   ├── telegram.py
│   │   ├── wordpress.py
│   │   ├── snapchat.py
│   │   └── google_business.py
│   │
│   ├── oauth/                  # OAuth 프록시 (src/com)
│   │   ├── provider.py         # OAuth 공통 흐름
│   │   ├── token_store.py      # 토큰 암호화 저장
│   │   └── providers/
│   │       ├── google.py       # YouTube + Google Business
│   │       ├── meta.py         # Instagram + Facebook + Threads
│   │       ├── tiktok.py
│   │       ├── x.py
│   │       ├── linkedin.py
│   │       └── ...
│   │
│   ├── models/                 # DB 모델 (SQLAlchemy / Supabase)
│   │   ├── user.py
│   │   ├── api_key.py
│   │   ├── social_account.py
│   │   ├── post.py
│   │   ├── video_job.py
│   │   └── webhook.py
│   │
│   └── workers/                # 비동기 작업 (Celery / Redis Queue)
│       ├── post_worker.py      # 실제 배포 실행
│       ├── video_worker.py     # 영상 생성 파이프라인
│       └── analytics_worker.py # 분석 데이터 수집
│
├── mcp/                        # MCP 서버
│   └── server.py
│
├── sdk/                        # 클라이언트 SDK
│   ├── python/
│   └── javascript/
│
├── tests/
├── docs/
│   ├── ARCHITECTURE.md         # 이 문서
│   ├── API_SPEC.md             # OpenAPI 스펙
│   └── PRICING.md              # 가격 정책
│
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

### com / biz 분리 원칙

| 레이어 | 분류 | 재사용성 |
|--------|------|----------|
| `core/` | **com** | 모든 프로젝트에서 재사용 (인증, 과금, 웹훅) |
| `adapters/` | **com** | 모든 프로젝트에서 재사용 (플랫폼 어댑터) |
| `oauth/` | **com** | 모든 프로젝트에서 재사용 (OAuth 프록시) |
| `services/` | **biz** | ContentFlow 비즈니스 로직 |
| `api/` | **biz** | ContentFlow 엔드포인트 |
| `workers/` | **biz** | ContentFlow 워커 |

---

## 4. API 엔드포인트 설계

### 4.1 Posts API (Zernio 대등 기능)

```
POST   /api/v1/posts              # 즉시/예약 포스팅
GET    /api/v1/posts               # 포스트 목록 조회
GET    /api/v1/posts/{id}          # 포스트 상태 조회
DELETE /api/v1/posts/{id}          # 예약 포스트 취소
PATCH  /api/v1/posts/{id}          # 예약 포스트 수정
```

**POST /api/v1/posts 요청 예시:**
```json
{
  "text": "새 영상이 올라왔습니다!",
  "platforms": ["youtube", "tiktok", "instagram"],
  "media_urls": ["https://drive.google.com/.../video.mp4"],
  "media_type": "video",
  "scheduled_for": "2026-04-07T09:00:00+09:00",
  "platform_options": {
    "youtube": {
      "title": "대법원이 뒤집은 판결",
      "description": "...",
      "tags": ["법률", "판례"],
      "privacy": "public",
      "category": "Education"
    },
    "tiktok": {
      "title": "판사도 놀란 판결 #법률 #판례",
      "privacy_level": "PUBLIC_TO_EVERYONE"
    },
    "instagram": {
      "caption": "대법원이 뒤집은 판결 🔨\n#법률상식 #판례 #법률",
      "share_to_feed": true
    }
  }
}
```

**응답:**
```json
{
  "id": "post_abc123",
  "status": "scheduled",
  "scheduled_for": "2026-04-07T09:00:00+09:00",
  "platforms": {
    "youtube": { "status": "pending", "platform_post_id": null },
    "tiktok": { "status": "pending", "platform_post_id": null },
    "instagram": { "status": "pending", "platform_post_id": null }
  },
  "created_at": "2026-04-06T15:30:00Z"
}
```

### 4.2 Videos API (ContentFlow 차별화 기능)

```
POST   /api/v1/videos/generate     # AI 영상 생성 요청
GET    /api/v1/videos/{id}          # 생성 상태/결과 조회
POST   /api/v1/videos/{id}/publish  # 생성된 영상 → 즉시 배포
GET    /api/v1/videos               # 영상 목록
```

**POST /api/v1/videos/generate 요청:**
```json
{
  "topic": "음주운전 3진아웃 제도의 진실",
  "mode": "legal",
  "language": "ko",
  "format": "shorts",
  "style": "realistic",
  "auto_publish": {
    "enabled": true,
    "platforms": ["youtube", "tiktok"],
    "scheduled_for": "2026-04-07T09:00:00+09:00"
  }
}
```

**응답 (비동기 — 웹훅으로 완료 알림):**
```json
{
  "id": "vid_xyz789",
  "status": "generating",
  "estimated_minutes": 8,
  "webhook_url": "설정된 웹훅으로 완료 시 콜백"
}
```

### 4.3 Accounts API (OAuth 프록시)

```
GET    /api/v1/accounts                     # 연결된 계정 목록
POST   /api/v1/accounts/connect/{platform}  # OAuth 연결 시작
DELETE /api/v1/accounts/{id}                # 계정 연결 해제
GET    /api/v1/accounts/{id}/status         # 토큰 유효성 확인
```

### 4.4 Analytics API

```
GET    /api/v1/analytics                    # 통합 분석
GET    /api/v1/analytics/{platform}         # 플랫폼별 분석
GET    /api/v1/analytics/posts/{post_id}    # 개별 포스트 성과
```

### 4.5 Webhooks API

```
POST   /api/v1/webhooks                     # 웹훅 등록
GET    /api/v1/webhooks                     # 웹훅 목록
DELETE /api/v1/webhooks/{id}                # 웹훅 삭제
```

**웹훅 이벤트:**
```
post.published      # 포스팅 완료
post.failed          # 포스팅 실패
post.scheduled       # 예약 등록 완료
video.completed      # 영상 생성 완료
video.failed         # 영상 생성 실패
account.disconnected # 계정 토큰 만료
```

---

## 5. 인증 & 과금

### API Key 구조
```
cf_live_xxxxxxxxxxxxxxxxxxxx    # 운영 키
cf_test_xxxxxxxxxxxxxxxxxxxx    # 테스트 키 (실제 배포 안 함)
```

### 요금제

| 플랜 | 월 가격 | Social Sets | Posts/월 | Video Gen/월 | Analytics | Comments |
|------|---------|------------|---------|-------------|-----------|----------|
| Free | $0 | 2 | 20 | 3 | - | - |
| Build | $29 | 5 | 200 | 20 | +$15 | +$15 |
| Scale | $79 | 20 | Unlimited | 100 | +$30 | +$30 |
| Enterprise | $299 | Unlimited | Unlimited | Unlimited | 포함 | 포함 |

- **Social Set** = 플랫폼별 계정 1개씩 묶은 그룹 (Zernio의 Profile과 동일)
- Video Gen은 ContentFlow만의 차별화 요소이므로 무료 플랜에도 3개 포함
- Analytics/Comments는 애드온 (Zernio 방식 벤치마킹)

---

## 6. 기술 스택

| 레이어 | 기술 | 근거 |
|--------|------|------|
| API Framework | FastAPI | 비동기, OpenAPI 자동 생성, Python 생태계 |
| DB | Supabase (PostgreSQL) | 인증 내장, 실시간 구독, 무료 티어 |
| Queue | Redis + Celery | 비동기 배포/생성 작업 |
| OAuth Token Store | Supabase + AES-256 암호화 | 보안 |
| 영상 생성 엔진 | yt-factory (내부 호출) | 기존 검증된 파이프라인 |
| 호스팅 | Railway / Fly.io | FastAPI 배포, 가격 효율 |
| 프론트 (대시보드) | Next.js (기존 Vercel) | contentflow-lovat.vercel.app 확장 |
| SDK 배포 | PyPI + npm | 표준 패키지 관리 |
| MCP 서버 | Python MCP SDK | Claude Code/에이전트 연동 |

---

## 7. yt-factory 연결 전략

ContentFlow API는 yt-factory를 **내부 엔진으로 호출**한다.

```
ContentFlow API                    yt-factory
     │                                │
     │ POST /api/v1/videos/generate   │
     │ ──────────────────────────►    │
     │                                │ run_pipeline()
     │                                │ script → image → tts → video
     │                                │
     │      webhook: video.completed  │
     │ ◄──────────────────────────    │
     │                                │
     │ POST (internal) distribute     │
     │ ──────────────────────────►    │
     │                       adapters/youtube, tiktok...
```

### 분리 원칙
- yt-factory는 **영상 제작 엔진**으로만 유지
- ContentFlow API는 **배포 + 인증 + 과금 + 고객 관리** 담당
- 두 프로젝트는 독립 배포 가능 (yt-factory 없이도 Posts API는 동작)

---

## 8. 2주 실행 계획

### Week 1 (4/7~4/11)

| 담당 | 작업 | 산출물 |
|------|------|--------|
| 클팀장 | 아키텍처 확정 + OAuth 설계 | 이 문서 + OAuth 시퀀스 |
| 코드2 | FastAPI 뼈대 + Posts API | `app/api/v1/posts.py` + 테스트 |
| 코드3 | 어댑터 레이어 (YouTube, TikTok, Instagram) | `app/adapters/` 3개 |
| 코덱1 | DB 스키마 + Supabase 설정 | `models/` + migration |

### Week 2 (4/14~4/18)

| 담당 | 작업 | 산출물 |
|------|------|--------|
| 코드2 | Videos API + yt-factory 연결 | `app/api/v1/videos.py` |
| 코드3 | OAuth 프록시 (Google, Meta) | `app/oauth/` |
| 코드4 | MCP 서버 + Webhook 시스템 | `mcp/server.py` + `core/webhook_dispatcher.py` |
| 코덱2 | 랜딩페이지 업그레이드 + 문서 사이트 | Vercel 배포 |

### MVP 완료 기준
- [ ] Posts API로 YouTube + TikTok + Instagram 동시 배포 성공
- [ ] Videos API로 주제 → 영상 생성 → 자동 배포 성공
- [ ] API Key 인증 + rate limiting 동작
- [ ] 웹훅 콜백 동작
- [ ] MCP 서버에서 호출 가능
- [ ] 랜딩페이지에 API 문서 링크

---

## 9. 리스크 & 대응

| 리스크 | 영향 | 대응 |
|--------|------|------|
| 플랫폼 OAuth 앱 승인 지연 | 배포 불가 | YouTube(승인완)/TikTok(심사중)부터 → 나머지 순차 |
| yt-factory 엔진 불안정 | Video Gen 실패 | Posts API만 먼저 출시, Video Gen은 beta 표시 |
| Rate limit 초과 | 서비스 중단 | 플랫폼별 큐 분리 + 재시도 로직 |
| 토큰 만료 | 배포 실패 | 자동 refresh + account.disconnected 웹훅 |
