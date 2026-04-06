# ContentFlow API — 팀 핸드오프

> 기준일: 2026-04-06
> 작성: 클팀장

---

## 프로젝트 요약

ContentFlow API = **Zernio 클론 + AI 영상 생성**
하나의 API로 14+ 소셜 플랫폼 동시 배포 + yt-factory 엔진으로 AI 영상 자동 생성.

## 현재 상태: 설계 완료, 구현 시작 대기

### 완료된 것
- [x] 아키텍처 설계서 (`docs/ARCHITECTURE.md`)
- [x] FastAPI 뼈대 (`app/main.py`, 라우터, 설정)
- [x] Posts API 엔드포인트 (`app/api/v1/posts.py`) — 스키마 + 라우트 완성
- [x] Videos API 엔드포인트 (`app/api/v1/videos.py`) — 스키마 + 라우트 완성
- [x] Accounts/Analytics/Webhooks/API Keys 스텁
- [x] 인증 모듈 (`app/core/auth.py`) — API Key 파싱 + User 모델
- [x] 과금 모듈 (`app/core/billing.py`) — 요금제별 한도 체크 스텁
- [x] Rate limiter 스텁 (`app/core/rate_limiter.py`)
- [x] 어댑터 베이스 클래스 (`app/adapters/base.py`) — 인터페이스 확정
- [x] YouTube 어댑터 (`app/adapters/youtube.py`) — Resumable upload 구현
- [x] TikTok 어댑터 (`app/adapters/tiktok.py`) — Content Posting API
- [x] Instagram 어댑터 (`app/adapters/instagram.py`) — Reels + Carousel
- [x] PostService 오케스트레이터 (`app/services/post_service.py`)
- [x] 웹훅 디스패처 (`app/core/webhook_dispatcher.py`) — HMAC 서명
- [x] MCP 서버 (`mcp/server.py`) — 4개 도구
- [x] DB 모델/스키마 (`app/models/schemas.py`) — 7개 테이블
- [x] Dockerfile + pyproject.toml
- [x] 가격 정책 설계

### TODO 우선순위

## Week 1 작업 분배 (4/7~4/11)

### 코드2: Posts API 실동작
```
1. Supabase 프로젝트 생성 + 테이블 마이그레이션
   - app/models/schemas.py의 SQL을 Supabase에 실행
   - Supabase URL/Key를 .env에 설정

2. app/core/auth.py → 실제 DB 연동
   - _lookup_user_by_key(): Supabase에서 api_keys 테이블 조회
   - bcrypt 해시 비교

3. app/api/v1/posts.py → 실제 DB CRUD
   - _create_post_record(): Supabase insert
   - _get_post(): Supabase select
   - _cancel_post(): status 업데이트

4. 테스트
   - tests/test_posts.py: POST/GET/DELETE 통합 테스트
   - httpx.AsyncClient로 FastAPI TestClient 사용
```

### 코드3: 어댑터 실동작 + 추가 플랫폼
```
1. YouTube 어댑터 실 테스트
   - 테스트 채널에 실제 업로드 → 삭제
   - OAuth 토큰 갱신 검증

2. 추가 어댑터 구현 (우선순위 순)
   - app/adapters/x_twitter.py (X API v2)
   - app/adapters/linkedin.py (LinkedIn API)
   - app/adapters/facebook.py (Graph API — Instagram과 공유)
   - app/adapters/threads.py (Threads API)

3. PostService 통합 테스트
   - 3개 플랫폼 동시 배포 → 부분 실패 처리 검증
```

### 코덱1: DB + 인프라
```
1. Supabase 프로젝트 설정
   - 테이블 생성 (schemas.py SQL 실행)
   - Row Level Security 정책 설정
   - API Key 발급 플로우

2. Redis 설정 (Railway 또는 Upstash)
   - rate_limiter.py 실제 Redis 연동
   - Celery broker 설정

3. CI/CD
   - GitHub Actions: lint + test
   - Railway/Fly.io 자동 배포
```

## Week 2 작업 분배 (4/14~4/18)

### 코드2: Videos API + yt-factory 연결
```
1. yt-factory에 HTTP API 래퍼 추가
   - FastAPI 엔드포인트로 run_pipeline() 호출 가능하게
   - 비동기: Celery task로 감싸기

2. Videos API → yt-factory 연결
   - _enqueue_video_generation(): Celery task 호출
   - 완료 콜백: yt-factory → ContentFlow webhook

3. auto_publish 구현
   - 영상 생성 완료 → Posts API 내부 호출 → 배포
```

### 코드3: OAuth 프록시
```
1. app/oauth/provider.py — OAuth 공통 흐름
   - Authorization URL 생성
   - Callback 처리 → 토큰 저장
   - 토큰 암호화 (AES-256)

2. Google OAuth (YouTube + Google Business)
3. Meta OAuth (Instagram + Facebook + Threads)
4. TikTok OAuth
```

### 코드4: MCP + Webhook + 스케줄러
```
1. MCP 서버 실동작 테스트
   - Claude Code에서 contentflow_post 호출 검증

2. webhook_dispatcher 실제 전송 구현
   - post.published, video.completed 이벤트 연동
   - 실패 시 3회 재시도 + 자동 비활성화

3. 스케줄러
   - scheduled_for 시각 도달 → 자동 배포
   - Celery Beat 또는 APScheduler
```

### 코덱2: 랜딩페이지 + 문서
```
1. contentflow-lovat.vercel.app 업그레이드
   - Zernio 수준의 랜딩페이지
   - 가격표
   - API 문서 링크

2. API 문서 사이트
   - FastAPI 자동 생성 /docs 활용
   - 또는 Mintlify/Docusaurus
```

---

## 핵심 원칙

1. **어댑터는 com 모듈** — 다른 프로젝트에서도 재사용 가능하게 설계
2. **OAuth 토큰은 반드시 암호화 저장** — AES-256, DB에 평문 저장 금지
3. **부분 실패 허용** — 5개 플랫폼 중 1개 실패해도 나머지는 성공 처리
4. **비동기 우선** — 영상 생성/배포는 Celery 워커로, API는 즉시 응답
5. **테스트 모드** — `cf_test_` 키로 호출 시 실제 배포 안 함

---

## 파일 위치 참조

```
contentflow-api/
├── app/main.py              # 엔트리포인트
├── app/config.py            # 환경변수
├── app/api/v1/posts.py      # ★ Posts API (핵심)
├── app/api/v1/videos.py     # ★ Videos API (차별화)
├── app/api/v1/accounts.py   # OAuth 연결
├── app/api/v1/analytics.py  # 분석
├── app/api/v1/webhooks.py   # 웹훅
├── app/api/v1/api_keys.py   # 키 관리
├── app/core/auth.py         # 인증
├── app/core/billing.py      # 과금
├── app/core/rate_limiter.py # 요청 제한
├── app/core/webhook_dispatcher.py # 이벤트 전달
├── app/adapters/base.py     # ★ 어댑터 인터페이스 (com)
├── app/adapters/youtube.py  # YouTube
├── app/adapters/tiktok.py   # TikTok
├── app/adapters/instagram.py # Instagram
├── app/services/post_service.py # ★ 배포 오케스트레이터 (com)
├── app/models/schemas.py    # DB 테이블 정의
├── mcp/server.py            # MCP 서버
├── docs/ARCHITECTURE.md     # 아키텍처 설계서
└── docs/HANDOFF.md          # 이 문서
```
