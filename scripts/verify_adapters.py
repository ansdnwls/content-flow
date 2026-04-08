"""Static verification script for adapter implementations.

This script does not call external APIs. It checks that adapter source files
and OAuth providers still match the latest verification notes captured from
official documentation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class VerificationCheck:
    description: str
    alternatives: tuple[str, ...]


@dataclass(frozen=True)
class VerificationProfile:
    name: str
    adapter_path: str
    docs_url: str
    endpoint_checks: tuple[VerificationCheck, ...]
    required_scopes: tuple[str, ...]
    scope_source: str | None
    notes: tuple[str, ...]


PROFILES = (
    VerificationProfile(
        name="YouTube",
        adapter_path="app/adapters/youtube.py",
        docs_url="https://developers.google.com/youtube/v3/docs/videos/insert",
        endpoint_checks=(
            VerificationCheck(
                description="resumable upload endpoint",
                alternatives=(
                    "https://www.googleapis.com/upload/youtube/v3/videos",
                    "/upload/youtube/v3/videos",
                ),
            ),
            VerificationCheck(
                description="resumable upload mode",
                alternatives=("uploadType", "resumable"),
            ),
            VerificationCheck(
                description="snippet payload",
                alternatives=("snippet",),
            ),
            VerificationCheck(
                description="status payload",
                alternatives=("status",),
            ),
            VerificationCheck(
                description="category id field",
                alternatives=("\"categoryId\"", "categoryId"),
            ),
            VerificationCheck(
                description="scheduled publish field",
                alternatives=("\"publishAt\"", "publishAt"),
            ),
        ),
        required_scopes=(
            "https://www.googleapis.com/auth/youtube.upload",
        ),
        scope_source="app/oauth/providers/google.py",
        notes=(
            "Upload endpoint should be videos.insert with resumable upload.",
            (
                "status.publishAt must be RFC 3339 / ISO 8601 and should be paired "
                "with private visibility."
            ),
            (
                "Video statistics may omit like/comment counts for new uploads; "
                "adapter already defaults missing counters to zero."
            ),
            "Delete endpoint should use DELETE /youtube/v3/videos?id=<video_id>.",
        ),
    ),
    VerificationProfile(
        name="TikTok",
        adapter_path="app/adapters/tiktok.py",
        docs_url="https://developers.tiktok.com/doc/content-posting-api-get-started",
        endpoint_checks=(
            VerificationCheck(
                description="publish init endpoint",
                alternatives=(
                    "https://open.tiktokapis.com/v2/post/publish/video/init/",
                    "/v2/post/publish/video/init/",
                    "post/publish/video/init/",
                ),
            ),
            VerificationCheck(
                description="pull upload source mode",
                alternatives=("PULL_FROM_URL",),
            ),
            VerificationCheck(
                description="file upload source mode",
                alternatives=("FILE_UPLOAD",),
            ),
            VerificationCheck(
                description="privacy level field",
                alternatives=("privacy_level",),
            ),
            VerificationCheck(
                description="publish id handling",
                alternatives=("publish_id",),
            ),
        ),
        required_scopes=(
            "video.publish",
            "video.upload",
        ),
        scope_source="app/oauth/providers/tiktok.py",
        notes=(
            "Init endpoint must be /v2/post/publish/video/init/.",
            "source_info differs between FILE_UPLOAD and PULL_FROM_URL.",
            "privacy_level should be constrained to creator-supported enums.",
            "publish_id must be persisted because follow-up status checks are publish_id based.",
        ),
    ),
    VerificationProfile(
        name="Instagram",
        adapter_path="app/adapters/instagram.py",
        docs_url="https://developers.facebook.com/docs/instagram-platform/content-publishing",
        endpoint_checks=(
            VerificationCheck(
                description="graph api version",
                alternatives=(
                    "https://graph.facebook.com/v21.0",
                    "https://graph.facebook.com/v21.0",
                    "v21.0",
                ),
            ),
            VerificationCheck(
                description="media container endpoint",
                alternatives=("/media",),
            ),
            VerificationCheck(
                description="publish endpoint",
                alternatives=("/media_publish",),
            ),
            VerificationCheck(
                description="container status polling",
                alternatives=("status_code",),
            ),
            VerificationCheck(
                description="reel share-to-feed option",
                alternatives=("share_to_feed",),
            ),
            VerificationCheck(
                description="carousel media type",
                alternatives=("CAROUSEL",),
            ),
            VerificationCheck(
                description="reel media type",
                alternatives=("REELS",),
            ),
        ),
        required_scopes=(
            "instagram_basic",
            "instagram_content_publish",
            "pages_read_engagement",
        ),
        scope_source="app/oauth/providers/meta.py",
        notes=(
            "Create container first, then publish via /media_publish.",
            (
                "Video and reel containers should be polled via "
                "GET /<IG_CONTAINER_ID>?fields=status_code before publish."
            ),
            (
                "Current docs page is under instagram-platform/content-publishing "
                "and shows latest version placeholders beyond v19."
            ),
            "share_to_feed applies to reels but not carousel containers.",
        ),
    ),
    VerificationProfile(
        name="X",
        adapter_path="app/adapters/x_twitter.py",
        docs_url="https://docs.x.com/x-api/posts/create-post",
        endpoint_checks=(
            VerificationCheck(
                description="tweet create endpoint",
                alternatives=(
                    "https://api.x.com/2/tweets",
                    'f"{X_API_V2}/tweets"',
                    "/2/tweets",
                ),
            ),
            VerificationCheck(
                description="media initialize endpoint",
                alternatives=(
                    "https://api.x.com/2/media/upload/initialize",
                    "/2/media/upload/initialize",
                    "media/upload/initialize",
                ),
            ),
            VerificationCheck(
                description="media append/finalize routes",
                alternatives=("/media/upload/",),
            ),
            VerificationCheck(
                description="status polling",
                alternatives=("STATUS",),
            ),
            VerificationCheck(
                description="processing backoff support",
                alternatives=("check_after_secs",),
            ),
        ),
        required_scopes=(
            "tweet.write",
            "users.read",
            "offline.access",
        ),
        scope_source="app/oauth/providers/x.py",
        notes=(
            (
                "Media upload should use the v2 upload endpoints and wait for "
                "processing_info before creating the post."
            ),
            "OAuth 2.0 Authorization Code with PKCE remains the correct flow for user posting.",
            "Post creation remains POST /2/tweets.",
            "280-character limit is still enforced for post text.",
        ),
    ),
    VerificationProfile(
        name="LinkedIn",
        adapter_path="app/adapters/linkedin.py",
        docs_url="https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-03",
        endpoint_checks=(
            VerificationCheck(
                description="posts endpoint",
                alternatives=(
                    "https://api.linkedin.com/rest/posts",
                    "/rest/posts",
                ),
            ),
            VerificationCheck(
                description="initialize upload action",
                alternatives=("initializeUpload",),
            ),
            VerificationCheck(
                description="finalize upload action",
                alternatives=("finalizeUpload",),
            ),
            VerificationCheck(
                description="uploaded part ids",
                alternatives=("uploadedPartIds",),
            ),
            VerificationCheck(
                description="person urn support",
                alternatives=("urn:li:person", "_is_valid_author_urn"),
            ),
            VerificationCheck(
                description="organization urn support",
                alternatives=("urn:li:organization", "_is_valid_author_urn"),
            ),
        ),
        required_scopes=(
            "w_member_social",
        ),
        scope_source=None,
        notes=(
            "Posts API is the current path; UGC Posts should not be used for new work.",
            "Author must be a person or organization URN.",
            (
                "Video upload requires initializeUpload, binary PUT(s), and "
                "finalizeUpload with uploadedPartIds from ETag headers."
            ),
            (
                "This repo does not yet expose a LinkedIn OAuth provider, so "
                "scope wiring remains incomplete."
            ),
        ),
    ),
)


def load_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def find_missing_checks(
    text: str,
    checks: tuple[VerificationCheck, ...],
) -> list[str]:
    normalized = normalize_text(text)
    missing: list[str] = []
    for check in checks:
        if not any(fragment in normalized for fragment in check.alternatives):
            missing.append(check.description)
    return missing


def find_missing_scopes(text: str, scopes: tuple[str, ...]) -> list[str]:
    return [scope for scope in scopes if scope not in text]


def verify_profile(profile: VerificationProfile) -> tuple[str, bool]:
    adapter_source = load_text(profile.adapter_path)
    missing_checks = find_missing_checks(
        adapter_source,
        profile.endpoint_checks,
    )

    print(f"=== {profile.name} Adapter ===")
    print(f"Docs: {profile.docs_url}")
    print(f"Adapter: {profile.adapter_path}")

    if missing_checks:
        print(
            "FAIL Endpoint/signature checks missing: "
            f"{', '.join(missing_checks)}"
        )
        ok = False
    else:
        print("OK Endpoint and request-shape fragments matched verification profile")
        ok = True

    if profile.scope_source:
        scope_source = load_text(profile.scope_source)
        missing_scopes = find_missing_scopes(
            scope_source,
            profile.required_scopes,
        )
        if missing_scopes:
            print(f"FAIL OAuth scope declarations missing: {', '.join(missing_scopes)}")
            ok = False
        else:
            print(f"OK OAuth scopes present in {profile.scope_source}")
    else:
        print("WARN OAuth scope wiring is not implemented in a provider file for this platform")

    for note in profile.notes:
        print(f"WARN {note}")

    print()
    return profile.name, ok


def main() -> int:
    results = [verify_profile(profile) for profile in PROFILES]
    failed = [name for name, ok in results if not ok]

    if failed:
        print("Static verification completed with failures:")
        for name in failed:
            print(f"- {name}")
        return 1

    print("Static verification completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
