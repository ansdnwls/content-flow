# TASK: 실동작 검증 모드

> 담당: 코드3
> 우선순위: P0
> 모드: 기능 추가 중단, 검증 전용

---

## 배경

지금까지 ContentFlow에 21개 플랫폼 어댑터를 구현했지만, 모두 fake/mock 기반 테스트만 통과한 상태다. 실제 플랫폼 API에 호출했을 때 동작할지는 검증되지 않았다.

이번 임무는 **기능 추가를 멈추고 실제 동작을 검증**하는 것이다.

---

## 작업 1: 어댑터 정적 검증 스크립트

### 파일: `scripts/verify_adapters.py`

각 어댑터를 정적으로 검증하는 스크립트를 작성한다.

검증 항목:
- 엔드포인트 URL이 최신 공식 문서와 일치하는가
- 요청 파라미터 이름이 정확한가
- OAuth scope가 충분한가
- 응답 파싱 경로가 맞는가
- HTTP 메서드(GET/POST/PUT/DELETE)가 맞는가

출력 형식:
```
=== YouTube Adapter ===
✓ Upload endpoint: https://www.googleapis.com/upload/youtube/v3/videos
✓ OAuth scope: youtube.upload
⚠ Response parsing: items[0].statistics may be empty for new videos
✗ Delete endpoint: should use DELETE not POST

=== TikTok Adapter ===
...
```

---

## 작업 2: 우선순위 어댑터 재검증 (Top 5)

다음 5개 어댑터를 **web search로 공식 문서 최신 스펙을 확인**한 후, `app/adapters/*.py`에서 잘못된 부분을 수정한다.

### 2.1 YouTube
- 공식 문서: https://developers.google.com/youtube/v3/docs/videos/insert
- 검증할 것:
  - Resumable upload 플로우 정확성
  - snippet/status 필드명
  - categoryId 매핑
  - publishAt 시간 포맷 (RFC 3339)
  - OAuth scope: `https://www.googleapis.com/auth/youtube.upload`

### 2.2 TikTok
- 공식 문서: https://developers.tiktok.com/doc/content-posting-api-get-started
- 검증할 것:
  - `/v2/post/publish/video/init/` 엔드포인트 정확성
  - PULL_FROM_URL vs FILE_UPLOAD source_info 차이
  - privacy_level enum 값
  - publish_id 폴링 방식
  - OAuth scope: `video.publish`, `video.upload`

### 2.3 Instagram
- 공식 문서: https://developers.facebook.com/docs/instagram-api/guides/content-publishing
- 검증할 것:
  - Graph API 버전 (현재 v19.0이 최신인지)
  - REELS vs IMAGE vs CAROUSEL 컨테이너 생성 차이
  - 2단계 플로우 (create container → publish container)
  - share_to_feed 파라미터
  - 필요한 권한: `instagram_basic`, `instagram_content_publish`

### 2.4 X (Twitter)
- 공식 문서: https://developer.x.com/en/docs/x-api/tweets/manage-tweets/api-reference/post-tweets
- 검증할 것:
  - `/2/tweets` 엔드포인트
  - 미디어 업로드는 v1.1 API 사용 필요할 수 있음
  - OAuth 2.0 PKCE 플로우
  - text 필드 길이 제한 (280자)
  - scope: `tweet.write`, `tweet.read`, `users.read`, `offline.access`

### 2.5 LinkedIn
- 공식 문서: https://learn.microsoft.com/en-us/linkedin/marketing/integrations/community-management/shares/posts-api
- 검증할 것:
  - Posts API vs UGC Posts API (Posts API가 새 버전)
  - author URN 포맷 (`urn:li:person:{id}` 또는 `urn:li:organization:{id}`)
  - 미디어 업로드 3단계 플로우 (register → upload → reference)
  - scope: `w_member_social`

각 어댑터에서 발견된 이슈는 수정하고, 수정 내역은 docs/VERIFICATION.md에 기록한다.

---

## 작업 3: Smoke Test 스크립트

### 파일: `scripts/smoke_test.py`

로컬 `docker compose up`으로 서버 띄운 상태에서 전체 플로우를 검증한다.

테스트 시나리오:
1. Health check (`GET /health`)
2. API Key 발급 (`POST /api/v1/keys`)
3. OAuth URL 생성 (`POST /api/v1/accounts/connect/youtube`)
4. Posts API dry-run (`POST /api/v1/posts` with `dry_run=true` 옵션 추가)
5. Videos API 시뮬레이션 (`POST /api/v1/videos/generate`)
6. Webhook 등록 (`POST /api/v1/webhooks`)
7. Bombs API (`POST /api/v1/bombs`)

각 단계에서 응답 코드/스키마를 검증하고, 실패 시 어디서 막혔는지 명확하게 출력한다.

dry_run 옵션은 `app/api/v1/posts.py`에 추가:
- `dry_run=true`이면 실제 플랫폼 호출은 안 하고 요청 빌드까지만 수행
- 응답에 `dry_run: true` + 예상 호출 정보 포함

---

## 작업 4: 검증 리포트 문서

### 파일: `docs/VERIFICATION.md`

다음 형식으로 작성한다:

```markdown
# ContentFlow 어댑터 검증 리포트

> 검증일: 2026-04-XX
> 검증자: 코드3

## 어댑터별 상태

| 플랫폼 | 상태 | 비고 |
|--------|------|------|
| YouTube | ✓ | 검증 완료, 실배포 가능 |
| TikTok | ⚠ | publish_id 폴링 로직 보강 필요 |
| Instagram | ✓ | 검증 완료 |
| X | ⚠ | 미디어 업로드 v1.1 마이그레이션 필요 |
| LinkedIn | ✗ | UGC Posts → Posts API 재작성 필요 |
| ... | ... | ... |

## 발견된 이슈 + 수정 내역

### YouTube
- 이슈: ...
- 수정: app/adapters/youtube.py 라인 X 수정

### TikTok
...

## 플랫폼별 OAuth Scope

| 플랫폼 | 필수 Scope | 비고 |
|--------|----------|------|
| YouTube | youtube.upload, youtube.readonly | ... |
| TikTok | video.publish, video.upload | ... |
| ... | ... | ... |

## 플랫폼별 개발자 앱 요구사항

| 플랫폼 | 필요한 권한 | 심사 필요 여부 | 예상 심사 기간 |
|--------|------------|--------------|--------------|
| YouTube | OAuth consent screen | Yes | 1-2 weeks |
| TikTok | Content Posting API | Yes | 5-10 days |
| Instagram | App Review | Yes | 1-2 weeks |
| ... | ... | ... | ... |

## 다음 단계

- [ ] 사장님이 직접 해야 할 것
- [ ] 추가 코드 작업이 필요한 것
```

---

## 완료 기준

- [ ] `scripts/verify_adapters.py` 작성 + 실행 결과 첨부
- [ ] Top 5 어댑터 web search로 공식 문서 확인 + 코드 수정
- [ ] `scripts/smoke_test.py` 작성
- [ ] `app/api/v1/posts.py`에 `dry_run` 옵션 추가
- [ ] `docs/VERIFICATION.md` 완성
- [ ] ruff check 통과
- [ ] pytest 통과

---

## 중요

**이건 기능 추가가 아니다. 검증과 수정 작업이다.**
새로운 기능을 만들지 말고, 기존 어댑터가 진짜 동작할지 확인하는 데 집중해라.

발견되는 이슈가 많을수록 좋다. 그게 이 작업의 가치다.
