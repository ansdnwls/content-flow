# ContentFlow — Deployment Checklist

Production 배포 전/중/후 전체 체크리스트.
아키텍처 개요와 상세 가이드는 [`DEPLOYMENT.md`](./DEPLOYMENT.md) 참조.

---

## 1. Supabase 프로젝트 생성 전 체크리스트

- [ ] Supabase 계정 생성 및 Organization 설정
- [ ] Region 선택 — API 서버(Railway)와 같은 리전 권장 (예: `ap-northeast-1` / `us-east-1`)
- [ ] 프로젝트 이름 결정 (예: `contentflow-prod`)
- [ ] 강력한 DB 비밀번호 생성 (최소 24자, 특수문자 포함)
- [ ] Pro 플랜 여부 결정 — Free tier 제한: 500MB DB, 2 프로젝트, 일주일 미사용 시 pause
- [ ] 프로젝트 생성 후 기록할 값 3개 확인:
  - `Project URL` → `SUPABASE_URL`
  - `anon (public) key` → `SUPABASE_ANON_KEY`
  - `service_role key` → `SUPABASE_SERVICE_ROLE_KEY`
- [ ] Settings > Database > Connection string 기록 (직접 접속용)

---

## 2. SQL 실행 순서

반드시 아래 순서대로 실행. 선행 테이블에 FK 의존성이 있음.

| 순서 | 파일 | 설명 |
|------|------|------|
| 1 | `infra/supabase/01_schema.sql` | 핵심 테이블 (`users`, `api_keys`, `social_accounts`, `posts`, `post_deliveries`, `video_jobs`, `webhooks`, `webhook_deliveries`, `bombs`, `comments`, `schedules`, `analytics_snapshots`, `video_templates`, `trending_snapshots`) |
| 2 | `infra/supabase/02_rls.sql` | Row Level Security 정책 — 모든 테이블에 `user_id` 기반 RLS 활성화 |
| 3 | `migrations/009_add_user_language.sql` | `users.language` 컬럼 추가 (i18n) |
| 4 | `migrations/010_ytboost_tables.sql` | YtBoost 전용 4개 테이블 (`ytboost_subscriptions`, `ytboost_shorts`, `ytboost_channel_tones`, `ytboost_detected_videos`) |
| 5 | `infra/supabase/03_seed.sql` | 시드 데이터 — **개발 환경에서만** 실행 |

### 실행 방법

**A. Supabase SQL Editor (권장)**

Dashboard > SQL Editor에서 각 파일 내용을 순서대로 붙여넣고 Run.

**B. psql CLI**

```bash
export SUPABASE_DB_URL="postgresql://postgres:PASSWORD@db.PROJECT_REF.supabase.co:5432/postgres"

psql $SUPABASE_DB_URL -f infra/supabase/01_schema.sql
psql $SUPABASE_DB_URL -f infra/supabase/02_rls.sql
psql $SUPABASE_DB_URL -f migrations/009_add_user_language.sql
psql $SUPABASE_DB_URL -f migrations/010_ytboost_tables.sql

# 개발 환경만:
# psql $SUPABASE_DB_URL -f infra/supabase/03_seed.sql
```

### 실행 후 검증

```sql
-- 테이블 수 확인 (18개 이상)
SELECT count(*) FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

-- RLS 활성화 확인
SELECT tablename, rowsecurity FROM pg_tables
WHERE schemaname = 'public' AND rowsecurity = true;
```

---

## 3. 환경변수

### 3.1 최소 필수 (이것 없으면 서버 시작 불가)

| 변수 | 설명 | 예시 |
|------|------|------|
| `SUPABASE_URL` | Supabase 프로젝트 URL | `https://abc123.supabase.co` |
| `SUPABASE_ANON_KEY` | Supabase anon key | `eyJ...` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key | `eyJ...` |
| `REDIS_URL` | Redis 연결 문자열 | `redis://default:pw@host:6379/0` |
| `TOKEN_ENCRYPTION_KEY` | Fernet 암호화 키 (OAuth 토큰 암호화) | 아래 생성 명령 참조 |
| `OAUTH_STATE_SECRET` | OAuth state 서명 시크릿 | 아래 생성 명령 참조 |

**키 생성 명령:**

```bash
# TOKEN_ENCRYPTION_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# OAUTH_STATE_SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3.2 권장 (기능 활성화에 필요)

| 변수 | 용도 | 미설정 시 |
|------|------|-----------|
| `OAUTH_REDIRECT_BASE_URL` | OAuth 콜백 기본 URL | 콜백 URL 생성 실패 |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | YouTube, Google Business 연동 | Google 플랫폼 비활성 |
| `META_CLIENT_ID` / `META_CLIENT_SECRET` | Instagram, Facebook, Threads 연동 | Meta 플랫폼 비활성 |
| `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` | TikTok 연동 | TikTok 비활성 |
| `X_CLIENT_ID` / `X_CLIENT_SECRET` | X (Twitter) 연동 | X 비활성 |
| `ANTHROPIC_API_KEY` | Comment Autopilot, Viral Score, Shorts Extraction | AI 기능 비활성 |
| `YOUTUBE_API_KEY` | Trending 데이터 수집 | Trending 기능 비활성 |
| `SENTRY_DSN` | 에러 트래킹 | Sentry 비활성 |

### 3.3 선택 (기본값 있음)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `APP_ENV` | `development` | `production` 설정 권장 |
| `APP_PORT` | `8000` | 서버 포트 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |
| `PROMETHEUS_ENABLED` | `true` | Prometheus 메트릭 |
| `API_KEY_PREFIX` | `cf_live` | API 키 접두사 |
| `ANTHROPIC_MODEL` | `claude-3-5-sonnet-latest` | AI 모델 |
| `COMMENT_POLL_INTERVAL_SECONDS` | `300` | 댓글 폴링 간격 |

---

## 4. OAuth 앱 생성 가이드

### 4.1 Google (YouTube + Google Business)

| 항목 | 내용 |
|------|------|
| 콘솔 | [Google Cloud Console](https://console.cloud.google.com) > APIs & Services > Credentials |
| 앱 유형 | OAuth 2.0 Client ID > **Web application** |
| Redirect URI | `https://{YOUR_DOMAIN}/api/v1/accounts/callback/google` |
| 필요 API | YouTube Data API v3, YouTube Analytics API |
| 필요 Scope | `youtube.upload`, `youtube.readonly`, `youtube.force-ssl`, `yt-analytics.readonly` |
| 심사 | Sensitive scope → **Google OAuth 심사 필요 (2~6주)** |
| 심사 준비물 | 개인정보처리방침 URL, 앱 홈페이지, 사용 목적 설명 영상 |
| 팁 | 개발 중에는 "Test" 모드로 100명까지 테스트 가능 (심사 없이) |

### 4.2 Meta (Instagram / Facebook / Threads)

| 항목 | 내용 |
|------|------|
| 콘솔 | [Meta for Developers](https://developers.facebook.com) > My Apps > Create App |
| 앱 유형 | Business |
| Redirect URI | `https://{YOUR_DOMAIN}/api/v1/accounts/callback/meta` |
| 필요 권한 | `instagram_basic`, `instagram_content_publish`, `pages_manage_posts`, `pages_read_engagement` |
| 앱 리뷰 | **필수** — 각 권한별 사용 사례 설명 + 스크린캐스트 제출 |
| 심사 기간 | 보통 **5~10 영업일**, 거절 시 수정 후 재제출 가능 |
| 주의 | Instagram Content Publishing API는 Business/Creator 계정만 지원 |

### 4.3 TikTok

| 항목 | 내용 |
|------|------|
| 콘솔 | [TikTok for Developers](https://developers.tiktok.com) > Manage Apps |
| Redirect URI | `https://{YOUR_DOMAIN}/api/v1/accounts/callback/tiktok` |
| 필요 Scope | `video.upload`, `video.list`, `user.info.basic` |
| 앱 리뷰 | **필수** — Content Posting API 사용 시 심사 |
| 심사 기간 | **5~10 영업일** |
| 주의 | Sandbox 모드에서 본인 계정으로만 테스트 가능. 일일 업로드 제한 존재 |

### 4.4 X (Twitter)

| 항목 | 내용 |
|------|------|
| 콘솔 | [X Developer Portal](https://developer.x.com) > Projects & Apps |
| 개발자 계정 | **Developer Portal 가입 필수** — 사용 목적 설명 필요 |
| 인증 방식 | OAuth 2.0 with PKCE (User Authentication) |
| Redirect URI | `https://{YOUR_DOMAIN}/api/v1/accounts/callback/x` |
| 필요 Scope | `tweet.read`, `tweet.write`, `users.read`, `offline.access` |
| 티어 | Free: 월 1,500 트윗 읽기 / Basic ($100/mo): 월 50,000 읽기 + 10,000 쓰기 |
| 주의 | Free tier는 게시만 가능. Analytics 필요 시 Basic 이상 |

### 4.5 LinkedIn

| 항목 | 내용 |
|------|------|
| 콘솔 | [LinkedIn Developer](https://developer.linkedin.com) > My Apps |
| Redirect URI | `https://{YOUR_DOMAIN}/api/v1/accounts/callback/linkedin` |
| 필요 제품 | **Marketing Developer Platform** (별도 신청) |
| 필요 Scope | `w_member_social`, `r_liteprofile` |
| 심사 | Marketing Developer Platform 접근 신청 후 **1~4주** |
| 주의 | Community Management API는 별도 신청. Company Page 게시에는 `w_organization_social` 필요 |

---

## 5. Railway 배포 전 체크

- [ ] `scripts/deploy_check.sh` 실행 — 환경변수 누락, 포트 충돌 확인
- [ ] `.env.production.example` 기반으로 모든 Required 변수 설정 완료
- [ ] Railway 프로젝트에 Redis 서비스 추가됨
- [ ] `Dockerfile` 확인 — 빌드 정상 (`docker build .` 로컬 테스트)
- [ ] `infra/railway/railway.toml` 서비스 설정 확인:
  - `api`: uvicorn, 포트 8000
  - `worker`: celery worker
  - `beat`: celery beat (**반드시 1개 replica**)
- [ ] Railway 환경변수에 Supabase, Redis, Security 키 입력 완료
- [ ] Custom domain 설정 (선택): Railway Settings > Networking > Custom Domain
- [ ] Railway healthcheck 설정: `/health/live` 엔드포인트 지정

### 배포 명령

```bash
# 프리플라이트 체크
./scripts/deploy_check.sh

# Railway CLI 배포
railway up

# 또는 Git push 자동 배포
git push origin main
```

---

## 6. 첫 실행 후 헬스체크 순서

배포 완료 후 아래 순서대로 확인. 각 단계가 통과해야 다음으로 진행.

```bash
BASE_URL="https://contentflow-api.railway.app"

# Step 1: Liveness — 프로세스 살아있는지
curl -s $BASE_URL/health/live
# 기대: {"status":"ok"}

# Step 2: Readiness — DB, Redis, Celery 연결 확인
curl -s $BASE_URL/health/ready
# 기대: {"status":"ready","checks":{"supabase":true,"redis":true,"celery":true}}

# Step 3: 전체 헬스
curl -s $BASE_URL/health
# 기대: {"status":"ok","environment":"production"}

# Step 4: API 문서 접근
curl -s -o /dev/null -w "%{http_code}" $BASE_URL/docs
# 기대: 200

# Step 5: Prometheus 메트릭 (선택)
curl -s $BASE_URL/metrics | head -5
# 기대: # HELP ... 텍스트
```

### 판단 기준

| 결과 | 의미 | 조치 |
|------|------|------|
| `/health/live` 실패 | 프로세스 미기동 | Railway 로그 확인, 환경변수 누락 점검 |
| `/health/ready` — supabase: false | DB 연결 실패 | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` 확인 |
| `/health/ready` — redis: false | Redis 연결 실패 | `REDIS_URL` 확인, Railway Redis 서비스 상태 확인 |
| `/health/ready` — celery: false | Worker 미기동 | Worker 서비스 로그 확인, Redis 브로커 연결 확인 |
| `/docs` 200 | 정상 | API 호출 테스트 진행 |

---

## 7. 첫 API 호출 테스트

### 7.1 사용자 생성 (Supabase Auth 또는 직접)

```bash
# Supabase Dashboard > Authentication > Users에서 수동 생성
# 또는 Supabase Auth API 사용
```

### 7.2 API 키 발급

```bash
# Supabase SQL Editor에서 직접 키 확인 (seed 데이터 사용 시)
SELECT key_prefix, key_preview FROM api_keys LIMIT 5;
```

### 7.3 사용량 조회

```bash
curl -s -H "X-API-Key: cf_live_YOUR_KEY" \
  $BASE_URL/api/v1/usage/summary | python3 -m json.tool
```

### 7.4 플랫폼 연결 (OAuth 시작)

```bash
# Google 연동 시작
curl -s -H "X-API-Key: cf_live_YOUR_KEY" \
  "$BASE_URL/api/v1/accounts/connect/google" | python3 -m json.tool
# → authorization_url 반환 → 브라우저에서 열어 인증
```

### 7.5 계정 목록 조회

```bash
curl -s -H "X-API-Key: cf_live_YOUR_KEY" \
  $BASE_URL/api/v1/accounts | python3 -m json.tool
```

### 7.6 게시물 생성

```bash
curl -s -X POST \
  -H "X-API-Key: cf_live_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello from ContentFlow!",
    "platforms": ["x"],
    "mode": "instant"
  }' \
  $BASE_URL/api/v1/posts | python3 -m json.tool
```

### 7.7 게시물 상태 확인

```bash
curl -s -H "X-API-Key: cf_live_YOUR_KEY" \
  $BASE_URL/api/v1/posts/{POST_ID} | python3 -m json.tool
```

---

## 8. 자주 발생하는 에러 + 해결법

### 8.1 `SUPABASE_URL is not set` — 서버 시작 실패

**원인:** 필수 환경변수 누락.
**해결:**
```bash
# Railway Variables에서 확인
railway variables
# 또는 .env 파일 확인
cat .env | grep SUPABASE
```

### 8.2 `connection refused` on Redis — Worker/Beat 시작 실패

**원인:** Redis URL이 잘못되었거나 Redis 서비스 미기동.
**해결:**
```bash
# Railway에서 Redis 서비스 상태 확인
railway status
# REDIS_URL 형식 확인: redis://default:PASSWORD@HOST:PORT/0
# Railway Redis는 자동 주입되므로, 수동 설정 시 오타 주의
```

### 8.3 `Invalid Fernet key` — TOKEN_ENCRYPTION_KEY 오류

**원인:** Fernet 키 형식이 잘못됨 (정확히 32바이트 base64-encoded여야 함).
**해결:**
```bash
# 올바른 키 재생성
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Railway Variables에서 교체
```

### 8.4 `401 Unauthorized` — API 키 인증 실패

**원인:** API 키가 없거나 만료되었거나 비활성화됨.
**해결:**
```bash
# 키 확인
curl -v -H "X-API-Key: cf_live_WRONG" $BASE_URL/api/v1/usage/summary
# → 401이면 Supabase에서 api_keys 테이블 확인
# → is_active = true, expires_at > now() 인지 확인
```

### 8.5 `502 Bad Gateway` — OAuth 콜백 실패

**원인:** `OAUTH_REDIRECT_BASE_URL`이 실제 배포 URL과 불일치, 또는 플랫폼 앱에 등록된 Redirect URI와 불일치.
**해결:**
```bash
# 1. OAUTH_REDIRECT_BASE_URL 확인
echo $OAUTH_REDIRECT_BASE_URL
# → https://contentflow-api.railway.app 이어야 함 (trailing slash 없이)

# 2. 각 OAuth 콘솔에서 Redirect URI 정확히 일치하는지 확인
# Google: https://YOUR_DOMAIN/api/v1/accounts/callback/google
# Meta:   https://YOUR_DOMAIN/api/v1/accounts/callback/meta
```

### 8.6 `RLS policy violation` — DB 쿼리 실패

**원인:** `02_rls.sql` 미실행, 또는 `service_role` 대신 `anon` 키로 서버 연결.
**해결:**
```bash
# RLS 정책 확인
psql $SUPABASE_DB_URL -c "SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname='public';"
# → 모든 테이블이 rowsecurity = true

# 서버는 SUPABASE_SERVICE_ROLE_KEY (RLS bypass) 사용해야 함
# SUPABASE_ANON_KEY는 클라이언트용
```

### 8.7 `Task timeout` — Celery 작업 타임아웃

**원인:** Worker가 부족하거나, 외부 API (yt-factory, 플랫폼 API) 응답 지연.
**해결:**
```bash
# Worker 상태 확인
curl -s $BASE_URL/health/metrics
# → active_workers: 0 이면 worker 서비스 확인

# Queue depth 확인
# → queue_depth가 계속 증가하면 worker 수 증가 필요
# railway.toml에서 worker concurrency 조정
```

### 8.8 `duplicate key value violates unique constraint` — 중복 데이터

**원인:** 동일 사용자가 같은 플랫폼 계정을 이미 연결했거나, upsert 미사용.
**해결:**
```bash
# 해당 테이블의 unique 제약조건 확인
psql $SUPABASE_DB_URL -c "\d social_accounts"
# → UNIQUE(user_id, platform, platform_user_id) 등

# 기존 레코드 확인 후 삭제 또는 업데이트
# API에서는 재연결(disconnect → connect) 시도
```

### 8.9 `rate limit exceeded` — 플랫폼 API 제한 초과

**원인:** 플랫폼별 API rate limit 도달.
**해결:**
```bash
# 플랫폼별 기본 제한:
# YouTube: 10,000 units/day (upload = 1,600 units)
# TikTok: 일일 업로드 제한 (sandbox: 더 제한적)
# X Free: 월 1,500 트윗 읽기
# Instagram: 시간당 25 게시 (Content Publishing)

# → 게시 간격 늘리기, 플랫폼 API 티어 업그레이드
# → scheduled_for를 활용하여 분산 게시
```

### 8.10 `CORS error` — 프론트엔드에서 API 호출 시

**원인:** API 서버의 CORS 허용 origin에 프론트엔드 도메인 미포함.
**해결:**
```bash
# app/main.py에서 CORS 미들웨어 설정 확인
# 또는 환경변수로 허용 origin 추가

# 프론트엔드 도메인을 CORS allow_origins에 추가:
# https://dashboard.contentflow.dev
# https://app.contentflow.dev
# http://localhost:3000  (개발용)
```

---

## Quick Reference

```
배포 순서 요약:

1. Supabase 프로젝트 생성
2. SQL 실행: 01_schema → 02_rls → 009_user_language → 010_ytboost
3. Railway 프로젝트 + Redis 추가
4. 환경변수 설정 (필수 6개 최소)
5. OAuth 앱 생성 (필요한 플랫폼만)
6. deploy_check.sh → railway up
7. 헬스체크: /health/live → /health/ready → /docs
8. API 키 발급 → 첫 호출 테스트
```
