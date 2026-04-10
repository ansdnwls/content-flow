# ContentFlow

> Claude Code가 이 프로젝트에서 작업할 때 가장 먼저 읽어야 하는 문서입니다.
> 이 파일은 불변 정보(제품 정의, 아키텍처, 규칙)만 담습니다.
> 변하는 상태는 `docs/SESSION_STATE.md`, 아이디어 백로그는 `docs/BACKLOG.md`를 참조하세요.

---

## 🎯 Product Identity

**한국 유튜버를 위한 OSMU (One Source Multi Use) 자동화 SaaS**

한 줄 요약:
> 유튜브 긴 영상 하나 올리면 블로그 글 + 쇼츠 3개 + 인스타/틱톡/스레드 자동 배포까지 전부 자동

### Target User
- 한국 유튜버 (구독자 1천~10만, 성장기)
- 영상 하나 만드는 데 시간 많이 쓰고, 다채널 관리할 여력 없는 1인 크리에이터
- 월 1~3만원 지불 의사 있는 세그먼트

### Core Value
- **"만들기"가 아니라 "뿌리기"에 집중**
- 영상 생산은 외부 도구(yt-factory 또는 사장님 직접 편집)에 위임
- ContentFlow는 **콘텐츠 변형 + 다채널 배포**만 잘함
- 경쟁 서비스(Zernio, Buffer)와의 차별: **한국 특화 + AI 변형 + 유튜버 전용**

---

## 🏗️ System Architecture

### 역할 분리 (중요)

```
[yt-factory]                    [ContentFlow]
 영상 생산 공장                    배포 + OSMU 허브
 ─────────────                    ───────────────
 - 영상 생성/편집                    - 영상/자막 받기
 - 쇼츠 렌더링                       - 블로그 변환 (Claude)
 - ffmpeg, Veo, 리프레이밍            - 다채널 배포
 - newVideoGen (Next.js UI)          - 플랫폼 OAuth 관리
 - yt-factory/python (엔진)          - AI 콘텐츠 변형
       │                               │
       └── webhook / API ──────────────▶
           (영상 완성됨)                │
                                        ▼
                              ┌─────────┼─────────┐
                              │         │         │
                          [블로그]   [인스타]  [틱톡]
                          Naver     Reels     ...
                          Tistory
```

**yt-factory는 ContentFlow의 "생산 부서", ContentFlow는 "유통 부서"입니다.**
절대 ContentFlow 안에 영상 편집 기능(ffmpeg, 리프레이밍, 더빙)을 넣지 마세요.

### 기술 스택

**Backend**
- FastAPI (Python 3.11)
- Supabase (PostgreSQL)
- Redis (cache + Celery broker)
- Celery (`--pool=solo` on Windows)
- Anthropic API (Claude Sonnet 4.5)

**Frontend (별도 프로젝트)**
- Next.js (Lovable로 개발)

**Infra**
- Docker Desktop (로컬)
- Sentry (에러 추적)
- Railway (배포 예정)

### 코드 구조 원칙
- `src/com` = 재사용 엔진 (플랫폼 어댑터, 공통 서비스)
- `src/biz` = 수직 제품 (YtBoost, ShopSync 등)
- `app/adapters/` = 21개 플랫폼 어댑터
- `app/api/v1/` = REST 엔드포인트
- `app/workers/` = Celery 백그라운드 태스크
- `app/services/` = 비즈니스 로직
- `app/oauth/` = OAuth 프로바이더들

---

## 📜 Rules for Claude

### 🚫 절대 하지 말 것

1. **영상 편집 기능 추가 금지**
   - ffmpeg, 리프레이밍, 자막 삽입, 더빙 = yt-factory 영역
   - ContentFlow는 mp4 파일을 받아서 배포만 함

2. **새 기능 즉흥 추가 금지**
   - 사장님이 "이것도 되나?" 물으면 **백로그에 추가만** 하고 구현 금지
   - 모든 새 기능 아이디어는 `docs/BACKLOG.md`에 먼저 적음
   - 현재 스프린트에 포함된 것만 구현

3. **Mock으로 얼버무리지 말 것**
   - "테스트 통과" ≠ "동작 확인"
   - 실제 외부 API 호출까지 검증
   - 2026-04-11 세션에서 이걸 뼈저리게 배웠음 (maybe_single 64곳 사태)

4. **`maybe_single().execute().data` 패턴 금지**
   - Supabase Python SDK에서 이게 None을 반환하면 AttributeError
   - 항상 `.limit(1).execute()` + `getattr(response, "data", None) or []` 패턴 사용
   - 예시는 `app/api/v1/workspaces.py::_ensure_slug_available` 참고

5. **민감 정보를 터미널/로그/코드에 노출 금지**
   - API 키, OAuth 시크릿, 토큰 등
   - 사용자 키는 `C:/Users/y2k_w/my_api_key.txt` 같은 파일에서 읽음
   - Client Secret, Access Token 절대 화면 출력 금지

### ✅ 반드시 할 것

1. **작업 시작 전 다음 파일 확인**
   - `CLAUDE.md` (이 파일) - 불변 규칙
   - `docs/SESSION_STATE.md` - 현재 상태
   - `docs/BACKLOG.md` - 우선순위

2. **커밋 메시지 컨벤션**
   ```
   fix: 짧은 설명
   feat: 짧은 설명
   test: 짧은 설명
   docs: 짧은 설명
   ```
   본문에는 무엇을/왜 바꿨는지 명시

3. **git 체크포인트**
   - 큰 변경 전 커밋
   - 각 작업 단위 완료 시 커밋
   - "작업 중" 상태로 오래 두지 말 것

4. **실제 동작 검증**
   - 로컬 서버 띄우고 실 요청 테스트
   - Supabase 실 연결 확인
   - 외부 API 실 호출 확인

5. **코딩 스타일**
   - 타입 힌트 필수 (Python 3.11+ 문법)
   - `from __future__ import annotations`
   - pydantic v2 스타일
   - async/await 일관성 유지

### 💡 작업 철학

- **문서 우선**: 코드 작성 전 spec/PRD/CLAUDE.md 먼저 작성
- **모듈화**: 독립 테스트 가능한 단위로 분리
- **체크포인트**: 작업 단계마다 git 커밋
- **재사용 우선**: 새 코드 작성 전 기존 코드 활용 방법 찾기
- **YAGNI**: 지금 필요 없는 기능은 만들지 않음

---

## 🔑 Key Information

### 필수 환경변수
```
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
JWT_SECRET=... (64자)

# OAuth (ContentFlow 운영자가 Google Cloud Console에서 발급)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
YOUTUBE_REDIRECT_URI=http://localhost:8000/api/v1/accounts/callback/youtube

# AI
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-sonnet-4-5

# Sentry
SENTRY_DSN=...
```

### Settings 모델 주의
`app/config.py`의 Settings는 `extra="ignore"` 필수. 없으면 새 환경변수 추가 시 서버가 안 뜸.

### YouTube OAuth 스코프
```python
_DEFAULT_SCOPES = {
    "youtube": [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/youtube.force-ssl",  # 댓글 쓰기 필수
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ],
}
```

### Supabase 주요 제약
```sql
-- social_accounts에 필수 UNIQUE (upsert용)
ALTER TABLE public.social_accounts 
ADD CONSTRAINT social_accounts_owner_ws_platform_handle_unique 
UNIQUE (owner_id, workspace_id, platform, handle);
```

### yt-factory 연결 구조 (이미 코드 있음)
- `app/workers/video_worker.py::_run_yt_factory()`
- `POST {YT_FACTORY_BASE_URL}/api/v1/pipelines/run`
- `GET {YT_FACTORY_BASE_URL}/api/v1/pipelines/{id}` (상태 폴링)
- yt-factory 측에 FastAPI 래퍼 필요 (아직 미구현)

### yt-factory 프로젝트 위치
- 루트: `C:\Users\y2k_w\projects\autoyoutube\`
- Next.js 대시보드: `newVideoGen/` (`npm run dev` → localhost:3000)
- Python 엔진: `yt-factory/python/` (`python main.py --channel ch001`)
- 변경 중인 파일: `video_renderer.py`, `subtitle_generator.py`, `hook_overlay.py`, `video_generator.py`

---

## 🎬 Verified Working Workflows (2026-04-11 기준)

아래 워크플로우는 실제로 한 번 이상 검증됨:

### 1. YouTube OAuth 연결
```
Google OAuth → access_token + refresh_token → Supabase 암호화 저장
```

### 2. YouTube 댓글 자동 답변 (풀 사이클)
```
YouTube API → 댓글 수집 → DB 저장 → Claude AI 답변 생성 → YouTube 실제 게시
```

### 3. Claude AI 쇼츠 구간 분석
```
transcript → Claude → 3개 하이라이트 구간 + 제목 + 해시태그
```

### 4. 쇼츠 승인 워크플로우
```
pending → approved (수동 또는 auto_distribute 옵션)
```

---

## 📂 문서 맵

- **CLAUDE.md** (이 파일) - 불변 규칙, 아키텍처, 정체성
- **docs/SESSION_STATE.md** - 현재 작업 상태 (휘발성, gitignore 권장)
- **docs/BACKLOG.md** - 아이디어 백로그 (B01~B07)
- **docs/OPS.md** - 운영 가이드 (있으면)
- **docs/DESIGN_GATE.md** - 디자인 결정 기록 (있으면)

---

## 🚀 세션 시작 체크리스트 (Claude Code용)

새 세션 시작 시 Claude Code는 반드시:

1. [ ] 이 `CLAUDE.md` 파일 전체 읽기
2. [ ] `docs/SESSION_STATE.md` 읽고 현재 진행 상황 파악
3. [ ] `docs/BACKLOG.md` 읽고 현재 스프린트 확인
4. [ ] `git log --oneline -10`으로 최근 커밋 확인
5. [ ] 사용자의 요청이 현재 스프린트에 포함되는지 확인
6. [ ] 포함되지 않으면 → 백로그 추가만 제안, 구현 거부
