# Integration Status

기준 시점: 2026-04-08  
조사 범위: `app/`, `verticals/`, `tests/`, `infra/supabase/migrations/`, `TASK_*.md`

이 문서는 "코드가 있다"와 "실제 플로우에 연결되어 검증됐다"를 분리해서 정리한다.

## 조사 방법

- 파일 인벤토리:
  - `git ls-files app verticals packages tools | rg "(^app/|^verticals/)"`
- 라우터/서비스/워커 연결 추적:
  - `rg -n "include_router\\(|from app\\.services|from app\\.workers|from app\\.adapters" app`
- 어댑터 연결 여부:
  - `rg -n "ADAPTERS =|platform_name =" app/services app/adapters`
- Celery 등록 확인:
  - `rg -n "@celery_app.task|name=\"contentflow\\." app/workers`
- API 테스트 커버리지 추적:
  - `rg -n '"/api/v1/|client\\.(get|post|patch|delete)\\("/api/v1/' tests`
- YtBoost / yt-factory 검증 범위 추적:
  - `rg -n "yt_factory|youtube_trigger|shorts_extractor|ytboost" app tests`

## 1. 완성된 것 (🟢)

### 1-1. 실동작 가능한 어댑터

판정 기준:

- `app/services/post_service.py`의 `ADAPTERS`에 연결되어 있다.
- 해당 어댑터용 테스트 파일이 `tests/test_adapters/`에 있다.
- 게시물 publish 플로우 또는 관련 서비스에서 실제로 호출될 수 있다.

현재 이 기준을 만족하는 어댑터:

- `youtube`
- `tiktok`
- `instagram`
- `x_twitter`
- `linkedin`
- `facebook`
- `threads`
- `pinterest`
- `reddit`
- `bluesky`
- `snapchat`
- `telegram`
- `wordpress`
- `google_business`
- `naver_blog`
- `tistory`
- `kakao`
- `note_jp`
- `line`
- `mastodon`
- `medium`

주의:

- 위 목록은 "배포 경로에 연결 + 어댑터 테스트 존재" 기준의 완료다.
- 이 저장소 안에서 각 외부 SaaS에 실제 운영 자격증명으로 live publish까지 검증한 흔적은 없다.
- 즉 현재 증거는 주로 contract test / mocked HTTP 검증이다.

### 1-2. API 엔드포인트 중 플로우 기준으로 테스트된 것

직접 route 테스트가 확인되는 영역:

- 게시물 플로우
  - `/api/v1/posts`
  - bulk post 관련 흐름
  - 예약 발행 연계
  - 근거: `tests/test_posts.py`, `tests/test_bulk_posts.py`, `tests/test_schedules.py`, `tests/test_post_service.py`
- 소셜 계정 연결
  - `/api/v1/accounts`
  - 근거: `tests/test_accounts.py`
- 댓글 수집/답글
  - `/api/v1/comments`
  - 근거: `tests/test_comments.py`
- 분석/트렌딩/사용량
  - `/api/v1/analytics`
  - `/api/v1/trending`
  - `/api/v1/usage`
  - 근거: `tests/test_analytics_engine.py`, `tests/test_trending.py`, `tests/test_usage.py`
- 비디오 생성
  - `/api/v1/videos`
  - `/api/v1/videos/templates`
  - 근거: `tests/test_videos.py`, `tests/test_video_templates.py`, `tests/test_video_worker.py`
- YtBoost API
  - `/api/v1/ytboost/channels`
  - `/api/v1/ytboost/shorts/extract`
  - `/api/v1/ytboost/shorts/{id}/approve`
  - `/api/v1/ytboost/shorts/{id}/reject`
  - `/api/v1/ytboost/comments/pending`
  - `/api/v1/ytboost/comments/{id}/approve`
  - `/api/v1/ytboost/comments/{id}/edit`
  - 근거: `tests/test_ytboost_api.py`
- YouTube webhook
  - `/api/webhooks/youtube/{user_id}`
  - verification challenge + notification enqueue까지 테스트됨
  - 근거: `tests/test_youtube_trigger.py`
- 워크스페이스/도메인/API key
  - `/api/v1/workspaces`
  - `/api/v1/workspaces/{id}/branding`
  - `/api/v1/workspaces/{id}/domain`
  - `/api/v1/workspaces/{id}/domain/verify`
  - `/api/v1/keys`
  - 근거: `tests/test_workspaces.py`, `tests/test_workspace_members.py`, `tests/test_api_keys.py`
- 관리자/감사/과금/보안/GDPR 계열
  - `/api/v1/admin`
  - `/api/v1/audit`
  - `/api/v1/billing`
  - `/api/v1/privacy`
  - `/api/v1/consent`
  - `/api/v1/notifications/preferences`
  - `/api/v1/onboarding`
  - `/api/v1/auth/verify-email`
  - 근거: `tests/test_admin.py`, `tests/test_audit.py`, `tests/test_billing.py`, `tests/test_privacy.py`, `tests/test_consent.py`, `tests/test_notification_prefs.py`, `tests/test_onboarding.py`, `tests/test_email_verify.py`
- 기타
  - `/api/v1/bombs`
  - `/api/v1/predict`
  - `/api/v1/webhooks`
  - 근거: `tests/test_bombs.py`, `tests/test_predict.py`, `tests/test_webhooks.py`

직접 route 테스트가 확인되지 않은 라우터:

- `/api/v1/users`
- `/api/v1/legal`
- `/api/webhooks/yt-factory`

### 1-3. Celery에 등록된 워커와 태스크

`app/workers/celery_app.py`에 import 등록된 워커 모듈:

- `analytics_worker`
- `billing_worker`
- `bomb_worker`
- `comment_worker`
- `post_worker`
- `retention_worker`
- `schedule_worker`
- `shorts_worker`
- `token_refresh_worker`
- `video_worker`
- `webhook_retry_worker`
- `trending_worker`
- `scheduler`

실제 등록된 태스크:

- `contentflow.publish_post`
- `contentflow.schedule_due_posts`
- `contentflow.run_due_schedules`
- `contentflow.collect_comments`
- `contentflow.auto_reply_comments`
- `contentflow.collect_analytics`
- `contentflow.refresh_oauth_tokens`
- `contentflow.retry_webhook_deliveries`
- `contentflow.refresh_trending_topics`
- `contentflow.check_past_due_subscriptions`
- `contentflow.run_retention_policies`
- `contentflow.generate_video`
- `contentflow.extract_ytboost_shorts`
- `contentflow.transform_bomb`
- `contentflow.publish_bomb`

beat schedule에 연결된 주기 실행 항목:

- due post scheduling
- due schedule execution
- comment collection / auto reply
- analytics collection
- OAuth token refresh
- webhook retry
- trending refresh
- billing dunning check
- retention policy execution

## 2. 반쯤 된 것 (🟡)

### 2-1. 구현은 있지만 실 API 호출 검증이 안 된 것

- 대부분의 소셜 어댑터
  - 어댑터 테스트와 publish 경로 연결은 있으나, live vendor credential로 실제 네트워크 publish를 검증한 흔적은 없다.
- `app/workers/video_worker.py`
  - yt-factory 호출과 auto-publish 연계는 `respx` mock으로만 검증되어 있다.
  - `tests/test_video_worker.py`
- `app/services/shorts_extractor.py`
  - transcript/clip 선택/저장 흐름은 테스트됐지만 외부 YouTube/Claude/clip pipeline은 mock 기반이다.
  - `tests/test_shorts_extractor.py`
- `app/services/youtube_trigger.py`
  - PubSub subscribe 요청과 webhook parsing은 테스트됐지만, 실제 YouTube PubSub subscription round-trip은 없다.

### 2-2. Mock만 있고 프로덕션 대응이 아닌 것

- `app/adapters/coupang_wing.py`
  - 파일 자체에 `v1: mock implementation`이 명시돼 있다.
  - mock ID와 `{"mock": True}`를 반환한다.
  - `tests/test_product_bomb.py`도 mock 동작만 검증한다.

### 2-3. 구현은 있는데 메인 플로우에 연결되지 않은 것

- `app/adapters/naver_smart_store.py`
  - 실제 HTTP publish/delete/validate 로직이 있다.
  - 하지만 `app/services/post_service.py`의 `ADAPTERS`에는 없다.
  - 즉 일반 post publish 플로우에서는 호출되지 않는다.
  - 테스트도 별도 route/flow가 아니라 `tests/test_product_bomb.py`에서 "token 없으면 실패" 수준만 있다.
- `app/services/product_bomb.py`
  - SmartStore/Coupang/Instagram/Naver Blog/Kakao용 콘텐츠 렌더링은 된다.
  - 그러나 이를 실제 marketplace/social publish로 이어주는 orchestration은 없다.
  - 현재는 "콘텐츠 생성 엔진"이지 "배포 엔진"은 아니다.

### 2-4. YtBoost는 구현됐지만 yt-factory 연결 검증은 절반

검증된 것:

- `YtFactoryIntegration.handle_publish_complete()` 서비스 레벨 테스트 존재
  - `tests/test_youtube_trigger.py`
- video worker에서 yt-factory API 호출 후 auto-publish까지 mock으로 검증
  - `tests/test_video_worker.py`

검증되지 않은 것:

- `/api/webhooks/yt-factory` 라우트 직접 테스트 없음
- `X-YtBoost-Signature` 검증 포함한 end-to-end webhook route 테스트 없음
- 실제 yt-factory 시스템에서 콜백을 보내는 live integration 검증 없음

### 2-5. 기능은 있으나 지원 플랫폼이 일부로 제한된 것

- `app/services/comment_service.py`
  - 댓글 수집/답글 경로는 `youtube`, `tiktok`, `instagram`만 lazy-load한다.
  - 다른 게시 어댑터들과 coverage가 맞지 않는다.
- `app/services/analytics_service.py`
  - analytics 수집도 `youtube`, `tiktok`, `instagram` 중심이다.
  - 게시 가능한 플랫폼 수에 비해 분석 지원 범위가 작다.

## 3. 누락된 것 (🔴)

### 3-1. TASK 문서에는 있었지만 실제 코드가 없는 것

`TASK_SHOPSYNC.md` 대비 누락:

- 11번가/`eleven_street` 어댑터 없음
- ShopSync 전용 API 엔드포인트 없음
- `tests/test_naver_smart_store.py` 없음
- ShopSync 백엔드가 일반 post publish 플로우에 편입되지 않음

`TASK_YTBOOST.md` 대비 누락:

- YouTube Data API polling fallback worker/beat 흐름 없음
- `/api/webhooks/yt-factory` direct route test 없음
- live inbound 시나리오 검증 없음

### 3-2. 다른 모듈과 연결 안 된 고립 코드

- `verticals/ytboost`, `verticals/shopsync`
  - landing/dashboard 프론트엔드와 preset/config는 존재한다.
  - 하지만 Python `app/` 런타임이 이 디렉터리를 import하거나 직접 참조하지는 않는다.
  - 현재 상태는 "별도 배포 가능한 프론트엔드 자산"에 가깝다.
- `app/api/v1/users.py`
  - 라우터에는 등록돼 있지만 직접 route 테스트가 보이지 않는다.
- `app/api/v1/legal.py`
  - DPA 서명/조회/서브프로세서 목록 구현은 있으나 직접 route 테스트가 보이지 않는다.
- `app/middleware/custom_domain.py`
  - 유틸 함수 테스트는 있으나, 전체 custom-domain 런타임 배포 검증은 없다.

## 4. 파일 기준 dive

### 4-1. `app/` 실행 그래프 요약

- HTTP 진입점
  - `app/main.py`
  - `app/api/router.py`
  - `app/api/webhooks/*.py`
- 게시/배포 코어
  - `app/api/v1/posts.py`
  - `app/services/post_service.py`
  - `app/adapters/*.py`
  - `app/workers/post_worker.py`
- 영상/숏폼/YtBoost
  - `app/api/v1/videos.py`
  - `app/workers/video_worker.py`
  - `app/api/v1/ytboost.py`
  - `app/services/shorts_extractor.py`
  - `app/services/ytboost_distributor.py`
  - `app/services/youtube_comment_autopilot.py`
  - `app/api/webhooks/youtube.py`
  - `app/api/webhooks/yt_factory.py`
- ShopSync/Product Bomb
  - `app/services/product_bomb.py`
  - `app/services/product_image_analyzer.py`
  - `app/services/channel_renderers/*.py`
  - `app/adapters/naver_smart_store.py`
  - `app/adapters/coupang_wing.py`

실질 허브는 `app/services/post_service.py`다. 여기에 없는 플랫폼은 구현이 있어도 일반 게시 플로우에 편입되지 않는다.

### 4-2. `verticals/` 구조 요약

- `_template/`
  - 새 vertical scaffold의 베이스
- `ytboost/`
  - `landing/`, `dashboard/`, `presets/`, `config.json`, `vercel.json`
- `shopsync/`
  - `landing/`, `dashboard/`, `presets/`, `config.json`, `vercel.json`

현재 `verticals/README.md`도 두 vertical 모두 상태를 `Development`로 표시한다.

### 4-3. import 관계에서 드러나는 핵심 사실

- `app/api/v1/ytboost.py`는 실제 서비스 레이어를 호출한다.
  - `extract_shorts`
  - `YouTubeCommentAutopilot`
  - `subscribe_to_channel`
  - `YtBoostDistributor`
- `app/api/webhooks/youtube.py`와 `app/services/yt_factory_integration.py`는 둘 다 `extract_ytboost_shorts_task`로 이어진다.
- `app/services/product_bomb.py`는 render-only다. `post_service`나 marketplace adapter orchestration으로 이어지지 않는다.
- `verticals/*`는 `packages/@contentflow/*`를 참조하지만 Python 백엔드와 직접 import 연결은 없다.

## 5. 다음 세션에서 우선 검증해야 할 TOP 10

1. `/api/webhooks/yt-factory` route에 대한 직접 API 테스트를 추가하고 signature 검증까지 확인
2. yt-factory -> webhook -> shorts task enqueue의 실제 end-to-end 시나리오를 한 번이라도 통과시킬 수 있는지 검증
3. `naver_smart_store`를 `post_service.ADAPTERS`에 붙일지, 아니면 ShopSync 전용 publish 경로를 따로 둘지 결정
4. `coupang_wing`을 계속 mock으로 둘지, v2 실 API 연동 범위를 확정
5. ShopSync task에 있었던 11번가 integration이 진짜 필요한지 결정하고 없으면 TASK 정리
6. `users` 라우터 직접 테스트 추가
7. `legal` 라우터 직접 테스트 추가
8. live credential이 가능한 최소 1개 플랫폼로 실제 publish smoke test 전략 수립
9. comment/analytics 서비스의 지원 플랫폼 범위와 게시 어댑터 범위를 맞출지 정리
10. `verticals/ytboost`, `verticals/shopsync`가 실제 백엔드 API와 어느 환경변수/도메인 조합으로 붙는지 배포 수준에서 검증

## 결론

현재 코드베이스는 "공용 게시 엔진"과 "YtBoost 백엔드"는 꽤 많이 연결돼 있다. 반면 ShopSync 계열은 콘텐츠 생성 엔진과 프론트 자산은 존재하지만, 실제 publish orchestration과 실 API 검증이 비어 있다.

다음 세션의 최우선 리스크는 두 가지다:

- yt-factory 연동이 서비스 단위에서는 맞지만 webhook route 단위에서 아직 증명되지 않았다는 점
- SmartStore/Coupang/11번가 계열이 문서상 기대치에 비해 실제 런타임 연결이 훨씬 약하다는 점
