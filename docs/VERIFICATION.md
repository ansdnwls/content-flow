# ContentFlow Adapter Verification Report
> Verification date: 2026-04-08
> Verified by: Code3

## Adapter Status

| Platform | Status | Notes |
|---|---|---|
| YouTube | Pass | Resumable upload endpoint verified. `publishAt` handling corrected. |
| TikTok | Pass | Direct post init endpoint verified. `privacy_level` validation added. |
| Instagram | Pass | Content publishing flow verified. Container status polling added before publish. |
| X | Pass | Media upload flow updated to X API v2 and waits for processing completion. |
| LinkedIn | Warn | Posts API and upload flow verified against the current versioned docs. Adapter corrected for video finalize flow, but OAuth provider wiring is still absent. |

## Findings And Fixes

### YouTube
- Finding: Adapter did not support `status.publishAt`, even though `videos.insert` allows `status.publishAt` and `snippet.categoryId`.
- Fix: Updated [youtube.py](/C:/Users/y2k_w/projects/content-flow/app/adapters/youtube.py) to build `status.publishAt` from RFC 3339 / ISO 8601 input and force `privacyStatus=private` when scheduled publishing is requested.

### TikTok
- Finding: Adapter accepted arbitrary `privacy_level` strings and did not fail when `publish_id` was missing.
- Fix: Updated [tiktok.py](/C:/Users/y2k_w/projects/content-flow/app/adapters/tiktok.py) to validate against the current official enum set and to reject init responses without `publish_id`.

### Instagram
- Finding: Adapter published immediately after container creation without checking `status_code`, contrary to current content publishing guidance.
- Fix: Updated [instagram.py](/C:/Users/y2k_w/projects/content-flow/app/adapters/instagram.py) to use `v21.0` and poll `GET /<IG_CONTAINER_ID>?fields=status_code` before `media_publish`.

### X
- Finding: Adapter still used legacy `upload.twitter.com/1.1/media/upload.json` flow and did not wait for asynchronous video processing before `POST /2/tweets`.
- Fix: Updated [x_twitter.py](/C:/Users/y2k_w/projects/content-flow/app/adapters/x_twitter.py) to use the current v2 media upload endpoints, poll `STATUS`, and reject text longer than 280 characters.

### LinkedIn
- Finding: Adapter used `rest/posts` but video upload skipped the required finalize step and did not capture `uploadedPartIds` from upload response `ETag` headers.
- Fix: Updated [linkedin.py](/C:/Users/y2k_w/projects/content-flow/app/adapters/linkedin.py) to initialize video upload with `fileSizeBytes`, upload all instructed parts, collect `ETag` values, and call `action=finalizeUpload`.
- Remaining gap: The repo still does not expose a LinkedIn OAuth provider in [app/oauth/__init__.py](/C:/Users/y2k_w/projects/content-flow/app/oauth/__init__.py), so `w_member_social` is not wired through account connect flows.
- Docs refresh: Rechecked the current Microsoft Learn `Posts API` page and moved the verifier link target to the latest versioned page (`view=li-lms-2026-03`).

## OAuth Scope Summary

| Platform | Required scopes | Notes |
|---|---|---|
| YouTube | `https://www.googleapis.com/auth/youtube.upload` | `youtube.readonly` is still useful for validation and analytics. |
| TikTok | `video.publish`, `video.upload` | `video.publish` is mandatory for direct posting. |
| Instagram | `instagram_basic`, `instagram_content_publish`, `pages_read_engagement` | Based on the Facebook Login publishing flow. |
| X | `tweet.write`, `users.read`, `offline.access` | OAuth 2.0 Authorization Code with PKCE remains the verified flow. |
| LinkedIn | `w_member_social` | Provider implementation is still missing in this repo. |

## Platform Approval Requirements

| Platform | Required approval | Human review | Typical lead time |
|---|---|---|---|
| YouTube | OAuth consent screen verification | Yes | 1-2 weeks |
| TikTok | Content Posting API audit / approval | Yes | 5-10 days |
| Instagram | Meta App Review / Page Publishing Authorization | Yes | 1-2 weeks |
| X | Project / app permission review varies by account tier | Sometimes | Varies |
| LinkedIn | Product access and app review for member posting | Yes | 1-2 weeks |

## Smoke Test Notes

- Added [smoke_test.py](/C:/Users/y2k_w/projects/content-flow/scripts/smoke_test.py) to validate the local Docker-backed API flow.
- The script now exercises `/health`, `/api/v1/accounts/connect/youtube`, `/api/v1/posts?dry_run=true`, `/api/v1/videos/generate`, and `/api/v1/bombs`.
- The script now uses `/api/v1/keys` with the current response contract (`raw_key`) instead of the stale `api_key` field name.
- The repo does expose `/api/v1/keys`, but it does not expose `POST /api/v1/webhooks` in this branch. The smoke step was updated to validate the implemented webhook surface via `GET /api/v1/webhooks/dead-letters`.

## Next Steps

- [ ] Add a real LinkedIn OAuth provider and wire `w_member_social` into account connect flows.
- [ ] Decide whether smoke automation should rely on a pre-issued key, or keep creating a fresh smoke key from `CONTENTFLOW_BOOTSTRAP_API_KEY` / `CONTENTFLOW_API_KEY`.
- [ ] Decide whether webhook registration should be restored, or whether replay/history-only webhook routes are the intended product surface.
- [ ] Run `scripts/smoke_test.py` against a real local stack with valid Supabase/Redis credentials and a valid API key.
