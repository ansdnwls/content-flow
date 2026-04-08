"""Tests for Comment Autopilot: API, service, adapters, and worker."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.adapters.base import Comment, ReplyResult
from app.core.auth import build_api_key_record
from tests.fakes import FakeSupabase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_user_and_key(fake_supabase: FakeSupabase) -> tuple[str, str]:
    """Create a user + API key in the fake DB, return (user_id, raw_key)."""
    user_id = str(uuid4())
    fake_supabase.insert_row(
        "users", {"id": user_id, "email": "commenter@example.com", "plan": "free"},
    )
    issued, record = build_api_key_record(user_id=uuid4(), name="default")
    record["user_id"] = user_id
    fake_supabase.insert_row("api_keys", record)
    return user_id, issued.raw_key


def _insert_comment(
    fake_supabase: FakeSupabase,
    user_id: str,
    *,
    comment_id: str | None = None,
    platform: str = "youtube",
    reply_status: str = "pending",
) -> dict:
    """Insert a comment row and return it."""
    row = {
        "id": comment_id or str(uuid4()),
        "user_id": user_id,
        "platform": platform,
        "platform_post_id": "vid_001",
        "platform_comment_id": f"pc_{uuid4().hex[:8]}",
        "author_id": "author_1",
        "author_name": "Test User",
        "text": "Great video! How do I get started?",
        "comment_created_at": datetime.now(UTC).isoformat(),
        "ai_reply": None,
        "reply_status": reply_status,
        "platform_reply_id": None,
    }
    return fake_supabase.insert_row("comments", row)


# ---------------------------------------------------------------------------
# Adapter tests
# ---------------------------------------------------------------------------

@respx.mock
async def test_youtube_get_comments() -> None:
    from app.adapters.youtube import YouTubeAdapter

    respx.get("https://www.googleapis.com/youtube/v3/commentThreads").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "snippet": {
                            "topLevelComment": {
                                "id": "c1",
                                "snippet": {
                                    "authorChannelId": {"value": "ch1"},
                                    "authorDisplayName": "Alice",
                                    "textDisplay": "Hello!",
                                    "publishedAt": "2026-04-07T12:00:00Z",
                                },
                            },
                        },
                    },
                ],
            },
        ),
    )

    adapter = YouTubeAdapter()
    comments = await adapter.get_comments("vid1", {"access_token": "tok"})
    assert len(comments) == 1
    assert comments[0].author_name == "Alice"
    assert comments[0].text == "Hello!"


@respx.mock
async def test_youtube_reply_comment() -> None:
    from app.adapters.youtube import YouTubeAdapter

    respx.post("https://www.googleapis.com/youtube/v3/comments").mock(
        return_value=httpx.Response(200, json={"id": "reply_1"}),
    )

    adapter = YouTubeAdapter()
    result = await adapter.reply_comment("vid1", "c1", "Thanks!", {"access_token": "tok"})
    assert result.success is True
    assert result.platform_comment_id == "reply_1"


@respx.mock
async def test_tiktok_get_comments() -> None:
    from app.adapters.tiktok import TikTokAdapter

    respx.post("https://open.tiktokapis.com/v2/comment/list/").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "comments": [
                        {
                            "id": "tc1",
                            "user": {"id": "u1", "display_name": "Bob"},
                            "text": "Cool!",
                            "create_time": 1712505600,
                            "parent_comment_id": None,
                        },
                    ],
                    "has_more": False,
                    "cursor": 0,
                },
            },
        ),
    )

    adapter = TikTokAdapter()
    comments = await adapter.get_comments("tt_vid1", {"access_token": "tok"})
    assert len(comments) == 1
    assert comments[0].author_name == "Bob"


@respx.mock
async def test_tiktok_reply_comment() -> None:
    from app.adapters.tiktok import TikTokAdapter

    respx.post("https://open.tiktokapis.com/v2/comment/reply/").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"comment_id": "reply_tc1"}},
        ),
    )

    adapter = TikTokAdapter()
    result = await adapter.reply_comment(
        "tt_vid1", "tc1", "Thanks!", {"access_token": "tok"},
    )
    assert result.success is True
    assert result.platform_comment_id == "reply_tc1"


@respx.mock
async def test_instagram_get_comments() -> None:
    from app.adapters.instagram import InstagramAdapter

    respx.get("https://graph.facebook.com/v21.0/ig_post_1/comments").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "ic1",
                        "from": {"id": "igu1", "username": "carol"},
                        "text": "Love it!",
                        "timestamp": "2026-04-07T12:00:00+00:00",
                    },
                ],
            },
        ),
    )

    adapter = InstagramAdapter()
    comments = await adapter.get_comments(
        "ig_post_1", {"access_token": "tok", "ig_user_id": "ig123"},
    )
    assert len(comments) == 1
    assert comments[0].author_name == "carol"


@respx.mock
async def test_instagram_reply_comment() -> None:
    from app.adapters.instagram import InstagramAdapter

    respx.post("https://graph.facebook.com/v21.0/ic1/replies").mock(
        return_value=httpx.Response(200, json={"id": "reply_ic1"}),
    )

    adapter = InstagramAdapter()
    result = await adapter.reply_comment(
        "ig_post_1", "ic1", "Thank you!", {"access_token": "tok"},
    )
    assert result.success is True
    assert result.platform_comment_id == "reply_ic1"


@respx.mock
async def test_x_twitter_get_comments() -> None:
    from app.adapters.x_twitter import XTwitterAdapter

    respx.get("https://api.x.com/2/tweets/search/recent").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "x_reply_1",
                        "author_id": "user_1",
                        "text": "Interesting thread",
                        "created_at": "2026-04-07T12:00:00Z",
                    },
                ],
                "includes": {
                    "users": [{"id": "user_1", "name": "Drew", "username": "drew"}],
                },
                "meta": {},
            },
        ),
    )

    adapter = XTwitterAdapter()
    comments = await adapter.get_comments("tweet_1", {"access_token": "tok"})
    assert len(comments) == 1
    assert comments[0].author_name == "Drew"
    assert comments[0].text == "Interesting thread"


@respx.mock
async def test_x_twitter_reply_comment() -> None:
    from app.adapters.x_twitter import XTwitterAdapter

    respx.post("https://api.x.com/2/tweets").mock(
        return_value=httpx.Response(201, json={"data": {"id": "reply_x_1"}}),
    )

    adapter = XTwitterAdapter()
    result = await adapter.reply_comment(
        "tweet_1", "x_reply_1", "Thanks for replying", {"access_token": "tok"},
    )
    assert result.success is True
    assert result.platform_comment_id == "reply_x_1"


@respx.mock
async def test_linkedin_get_comments() -> None:
    from app.adapters.linkedin import LinkedInAdapter

    respx.get(
        "https://api.linkedin.com/rest/socialActions/urn:li:share:1/comments"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "elements": [
                    {
                        "id": "urn:li:comment:1",
                        "actor": {"urn": "urn:li:person:1", "name": "Casey"},
                        "message": {"text": "Solid post"},
                        "created": {"time": 1775563200000},
                    },
                ],
                "paging": {"total": 1},
            },
        ),
    )

    adapter = LinkedInAdapter()
    comments = await adapter.get_comments(
        "urn:li:share:1",
        {"access_token": "tok", "author_urn": "urn:li:person:me"},
    )
    assert len(comments) == 1
    assert comments[0].author_name == "Casey"
    assert comments[0].text == "Solid post"


@respx.mock
async def test_linkedin_reply_comment() -> None:
    from app.adapters.linkedin import LinkedInAdapter

    respx.post(
        "https://api.linkedin.com/rest/socialActions/urn:li:comment:1/comments"
    ).mock(
        return_value=httpx.Response(201, json={"id": "urn:li:comment:reply-1"}),
    )

    adapter = LinkedInAdapter()
    result = await adapter.reply_comment(
        "urn:li:share:1",
        "urn:li:comment:1",
        "Thanks for the feedback",
        {"access_token": "tok", "author_urn": "urn:li:person:me"},
    )
    assert result.success is True
    assert result.platform_comment_id == "urn:li:comment:reply-1"


@respx.mock
async def test_facebook_get_comments() -> None:
    from app.adapters.facebook import FacebookAdapter

    respx.get("https://graph.facebook.com/v19.0/fb_post_1/comments").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "fb_c1",
                        "from": {"id": "fb_user_1", "name": "Morgan"},
                        "message": "Helpful post",
                        "created_time": "2026-04-07T12:00:00+00:00",
                    },
                ],
            },
        ),
    )

    adapter = FacebookAdapter()
    comments = await adapter.get_comments(
        "fb_post_1",
        {"page_access_token": "tok", "page_id": "page_1"},
    )
    assert len(comments) == 1
    assert comments[0].author_name == "Morgan"
    assert comments[0].text == "Helpful post"


@respx.mock
async def test_facebook_reply_comment() -> None:
    from app.adapters.facebook import FacebookAdapter

    respx.post("https://graph.facebook.com/v19.0/fb_c1/comments").mock(
        return_value=httpx.Response(200, json={"id": "fb_reply_1"}),
    )

    adapter = FacebookAdapter()
    result = await adapter.reply_comment(
        "fb_post_1",
        "fb_c1",
        "Thanks for reading",
        {"page_access_token": "tok", "page_id": "page_1"},
    )
    assert result.success is True
    assert result.platform_comment_id == "fb_reply_1"


@respx.mock
async def test_threads_get_comments() -> None:
    from app.adapters.threads import ThreadsAdapter

    respx.get("https://graph.threads.net/v1.0/thread_1/replies").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "thr_reply_1",
                        "username": "zoe",
                        "text": "Nice thread",
                        "timestamp": "2026-04-07T12:00:00Z",
                        "reply_to_id": "thread_1",
                    },
                ],
            },
        ),
    )

    adapter = ThreadsAdapter()
    comments = await adapter.get_comments(
        "thread_1",
        {"access_token": "tok", "threads_user_id": "user_1"},
    )
    assert len(comments) == 1
    assert comments[0].author_name == "zoe"
    assert comments[0].parent_id == "thread_1"


@respx.mock
async def test_threads_reply_comment() -> None:
    from app.adapters.threads import ThreadsAdapter

    respx.post("https://graph.threads.net/v1.0/user_1/threads").mock(
        return_value=httpx.Response(200, json={"id": "thr_reply_publish_1"}),
    )

    adapter = ThreadsAdapter()
    result = await adapter.reply_comment(
        "thread_1",
        "thr_reply_1",
        "Appreciate it",
        {"access_token": "tok", "threads_user_id": "user_1"},
    )
    assert result.success is True
    assert result.platform_comment_id == "thr_reply_publish_1"


async def test_naver_blog_get_comments_returns_empty_list() -> None:
    from app.adapters.naver_blog import NaverBlogAdapter

    adapter = NaverBlogAdapter()
    comments = await adapter.get_comments("naver_post_1", {"access_token": "tok"})
    assert comments == []


async def test_naver_blog_reply_comment_returns_todo_error() -> None:
    from app.adapters.naver_blog import NaverBlogAdapter

    adapter = NaverBlogAdapter()
    result = await adapter.reply_comment(
        "naver_post_1",
        "comment_1",
        "reply",
        {"access_token": "tok"},
    )
    assert result.success is False
    assert "TODO" in (result.error or "")


async def test_tistory_get_comments_returns_empty_list() -> None:
    from app.adapters.tistory import TistoryAdapter

    adapter = TistoryAdapter()
    comments = await adapter.get_comments(
        "tistory_post_1",
        {"access_token": "tok", "blog_name": "myblog"},
    )
    assert comments == []


async def test_tistory_reply_comment_returns_todo_error() -> None:
    from app.adapters.tistory import TistoryAdapter

    adapter = TistoryAdapter()
    result = await adapter.reply_comment(
        "tistory_post_1",
        "comment_1",
        "reply",
        {"access_token": "tok", "blog_name": "myblog"},
    )
    assert result.success is False
    assert "TODO" in (result.error or "")


@respx.mock
async def test_kakao_get_comments() -> None:
    from app.adapters.kakao import KAKAO_API, KakaoAdapter

    respx.get(f"{KAKAO_API}/v1/api/talk/channel/messages/kakao_post_1/comments").mock(
        return_value=httpx.Response(
            200,
            json={
                "comments": [
                    {
                        "id": "kakao_c1",
                        "user_id": "user_1",
                        "nickname": "Mina",
                        "text": "좋은 글이네요",
                        "created_at": "2026-04-07T12:00:00Z",
                    }
                ]
            },
        ),
    )

    adapter = KakaoAdapter()
    comments = await adapter.get_comments("kakao_post_1", {"access_token": "tok"})
    assert len(comments) == 1
    assert comments[0].author_name == "Mina"
    assert comments[0].text == "좋은 글이네요"


@respx.mock
async def test_kakao_reply_comment() -> None:
    from app.adapters.kakao import KAKAO_API, KakaoAdapter

    respx.post(
        f"{KAKAO_API}/v1/api/talk/channel/messages/kakao_post_1/comments/kakao_c1/reply"
    ).mock(return_value=httpx.Response(200, json={"id": "kakao_reply_1"}))

    adapter = KakaoAdapter()
    result = await adapter.reply_comment(
        "kakao_post_1", "kakao_c1", "감사합니다", {"access_token": "tok"},
    )
    assert result.success is True
    assert result.platform_comment_id == "kakao_reply_1"


@respx.mock
async def test_mastodon_get_comments() -> None:
    from app.adapters.mastodon import MastodonAdapter

    respx.get("https://mastodon.social/api/v1/statuses/123/context").mock(
        return_value=httpx.Response(
            200,
            json={
                "descendants": [
                    {
                        "id": "456",
                        "content": "<p>Hello fediverse</p>",
                        "created_at": "2026-04-07T12:00:00Z",
                        "in_reply_to_id": "123",
                        "account": {
                            "id": "acct_1",
                            "display_name": "Nova",
                            "username": "nova",
                        },
                    }
                ]
            },
        ),
    )

    adapter = MastodonAdapter()
    comments = await adapter.get_comments(
        "123",
        {"instance_url": "https://mastodon.social", "access_token": "tok"},
    )
    assert len(comments) == 1
    assert comments[0].author_name == "Nova"
    assert comments[0].parent_id == "123"


@respx.mock
async def test_mastodon_reply_comment() -> None:
    from app.adapters.mastodon import MastodonAdapter

    respx.post("https://mastodon.social/api/v1/statuses").mock(
        return_value=httpx.Response(200, json={"id": "789"}),
    )

    adapter = MastodonAdapter()
    result = await adapter.reply_comment(
        "123",
        "456",
        "Thanks from Mastodon",
        {"instance_url": "https://mastodon.social", "access_token": "tok"},
    )
    assert result.success is True
    assert result.platform_comment_id == "789"


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------

async def test_comment_service_generate_reply_fallback(monkeypatch) -> None:
    from app.services.comment_service import CommentService

    monkeypatch.setattr(
        "app.services.comment_service.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    service = CommentService()
    reply = await service.generate_reply("What's the best approach?")
    assert "question" in reply.lower() or "great" in reply.lower()


async def test_comment_service_generate_reply_no_question(monkeypatch) -> None:
    from app.services.comment_service import CommentService

    monkeypatch.setattr(
        "app.services.comment_service.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    service = CommentService()
    reply = await service.generate_reply("Nice content!")
    assert "thanks" in reply.lower() or "appreciate" in reply.lower()


async def test_comment_service_collect_comments(monkeypatch) -> None:
    from app.services.comment_service import CommentService

    fake_supabase = FakeSupabase()
    monkeypatch.setattr(
        "app.services.comment_service.get_supabase",
        lambda: fake_supabase,
    )
    monkeypatch.setattr(
        "app.services.comment_service.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    class FakeYouTubeAdapter:
        platform_name = "youtube"

        async def get_comments(self, post_id, creds, since=None):
            return [
                Comment(
                    platform_comment_id="yt_c1",
                    author_id="a1",
                    author_name="Alice",
                    text="Hello!",
                    created_at=datetime.now(UTC),
                ),
            ]

    monkeypatch.setattr(
        "app.services.comment_service._get_adapter_map",
        lambda: {"youtube": type("F", (), {
            "__init__": lambda self: None,
            "get_comments": FakeYouTubeAdapter().get_comments,
        })},
    )

    # Simpler approach: monkeypatch the adapter map directly
    from app.services import comment_service

    def fake_adapter_map():
        return {"youtube": FakeYouTubeAdapter}

    monkeypatch.setattr(comment_service, "_get_adapter_map", fake_adapter_map)

    service = CommentService()
    stored = await service.collect_comments(
        user_id="u1",
        platform="youtube",
        platform_post_id="vid_001",
        credentials={"access_token": "tok"},
    )
    assert len(stored) == 1
    assert stored[0]["platform_comment_id"] == "yt_c1"


async def test_comment_service_auto_reply(monkeypatch) -> None:
    from app.services.comment_service import CommentService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    comment_id = str(uuid4())
    fake_supabase.insert_row("comments", {
        "id": comment_id,
        "user_id": user_id,
        "platform": "youtube",
        "platform_post_id": "vid_001",
        "platform_comment_id": "yt_c1",
        "author_id": "a1",
        "author_name": "Alice",
        "text": "How does this work?",
        "reply_status": "pending",
    })

    monkeypatch.setattr(
        "app.services.comment_service.get_supabase", lambda: fake_supabase,
    )
    monkeypatch.setattr(
        "app.services.comment_service.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    class FakeYouTubeAdapter:
        platform_name = "youtube"

        async def reply_comment(self, post_id, cid, text, creds):
            return ReplyResult(success=True, platform_comment_id="reply_yt_1")

    from app.services import comment_service
    monkeypatch.setattr(
        comment_service, "_get_adapter_map",
        lambda: {"youtube": FakeYouTubeAdapter},
    )

    service = CommentService()
    result = await service.auto_reply(
        comment_id=comment_id,
        user_id=user_id,
        credentials={"access_token": "tok"},
    )
    assert result["success"] is True
    assert result["platform_reply_id"] == "reply_yt_1"
    assert result["ai_reply"] is not None

    # Verify DB was updated
    updated = fake_supabase.tables["comments"][0]
    assert updated["reply_status"] == "replied"


@pytest.mark.parametrize(
    ("platform", "module_name", "class_name", "credentials"),
    [
        ("x_twitter", "x_twitter", "XTwitterAdapter", {"access_token": "tok"}),
        (
            "linkedin",
            "linkedin",
            "LinkedInAdapter",
            {"access_token": "tok", "author_urn": "urn:li:person:me"},
        ),
        (
            "facebook",
            "facebook",
            "FacebookAdapter",
            {"page_access_token": "tok", "page_id": "page_1"},
        ),
        (
            "threads",
            "threads",
            "ThreadsAdapter",
            {"access_token": "tok", "threads_user_id": "user_1"},
        ),
        ("naver_blog", "naver_blog", "NaverBlogAdapter", {"access_token": "tok"}),
        (
            "tistory",
            "tistory",
            "TistoryAdapter",
            {"access_token": "tok", "blog_name": "myblog"},
        ),
        ("kakao", "kakao", "KakaoAdapter", {"access_token": "tok"}),
        (
            "mastodon",
            "mastodon",
            "MastodonAdapter",
            {"instance_url": "https://mastodon.social", "access_token": "tok"},
        ),
    ],
)
async def test_comment_service_collect_comments_expanded_platforms(
    monkeypatch,
    platform: str,
    module_name: str,
    class_name: str,
    credentials: dict[str, str],
) -> None:
    from app.services.comment_service import CommentService

    fake_supabase = FakeSupabase()
    monkeypatch.setattr("app.services.comment_service.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.services.comment_service.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    module = __import__(f"app.adapters.{module_name}", fromlist=[class_name])
    adapter_cls = getattr(module, class_name)

    async def fake_get_comments(self, post_id, creds, since=None):
        return [
            Comment(
                platform_comment_id=f"{platform}_c1",
                author_id="a1",
                author_name=f"{platform} user",
                text="Hello from expanded platform",
                created_at=datetime.now(UTC),
            )
        ]

    monkeypatch.setattr(adapter_cls, "get_comments", fake_get_comments)

    service = CommentService()
    stored = await service.collect_comments(
        user_id="u1",
        platform=platform,
        platform_post_id="post_1",
        credentials=credentials,
    )
    assert len(stored) == 1
    assert stored[0]["platform"] == platform


@pytest.mark.parametrize(
    ("platform", "module_name", "class_name", "credentials"),
    [
        ("x_twitter", "x_twitter", "XTwitterAdapter", {"access_token": "tok"}),
        (
            "linkedin",
            "linkedin",
            "LinkedInAdapter",
            {"access_token": "tok", "author_urn": "urn:li:person:me"},
        ),
        (
            "facebook",
            "facebook",
            "FacebookAdapter",
            {"page_access_token": "tok", "page_id": "page_1"},
        ),
        (
            "threads",
            "threads",
            "ThreadsAdapter",
            {"access_token": "tok", "threads_user_id": "user_1"},
        ),
        ("naver_blog", "naver_blog", "NaverBlogAdapter", {"access_token": "tok"}),
        (
            "tistory",
            "tistory",
            "TistoryAdapter",
            {"access_token": "tok", "blog_name": "myblog"},
        ),
        ("kakao", "kakao", "KakaoAdapter", {"access_token": "tok"}),
        (
            "mastodon",
            "mastodon",
            "MastodonAdapter",
            {"instance_url": "https://mastodon.social", "access_token": "tok"},
        ),
    ],
)
async def test_comment_service_auto_reply_expanded_platforms(
    monkeypatch,
    platform: str,
    module_name: str,
    class_name: str,
    credentials: dict[str, str],
) -> None:
    from app.services.comment_service import CommentService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    comment_id = str(uuid4())
    fake_supabase.insert_row(
        "comments",
        {
            "id": comment_id,
            "user_id": user_id,
            "platform": platform,
            "platform_post_id": "post_1",
            "platform_comment_id": "comment_1",
            "author_id": "a1",
            "author_name": "Alice",
            "text": "How does this work?",
            "reply_status": "pending",
        },
    )

    monkeypatch.setattr("app.services.comment_service.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.services.comment_service.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    module = __import__(f"app.adapters.{module_name}", fromlist=[class_name])
    adapter_cls = getattr(module, class_name)

    async def fake_reply_comment(self, post_id, cid, text, creds):
        return ReplyResult(success=True, platform_comment_id=f"{platform}_reply_1")

    monkeypatch.setattr(adapter_cls, "reply_comment", fake_reply_comment)

    service = CommentService()
    result = await service.auto_reply(
        comment_id=comment_id,
        user_id=user_id,
        credentials=credentials,
    )
    assert result["success"] is True
    assert result["platform_reply_id"] == f"{platform}_reply_1"


async def test_comment_service_list_and_get(monkeypatch) -> None:
    from app.services.comment_service import CommentService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    comment_id = str(uuid4())
    _insert_comment(fake_supabase, user_id, comment_id=comment_id)

    monkeypatch.setattr(
        "app.services.comment_service.get_supabase", lambda: fake_supabase,
    )
    monkeypatch.setattr(
        "app.services.comment_service.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    service = CommentService()

    # list
    data, total = await service.list_comments(user_id)
    assert total == 1
    assert data[0]["id"] == comment_id

    # get
    comment = await service.get_comment(comment_id, user_id)
    assert comment is not None
    assert comment["text"] == "Great video! How do I get started?"

    # get non-existent
    missing = await service.get_comment(str(uuid4()), user_id)
    assert missing is None


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

async def test_comments_api_collect(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake_supabase)

    class FakeYouTubeAdapter:
        platform_name = "youtube"

        async def get_comments(self, post_id, creds, since=None):
            return [
                Comment(
                    platform_comment_id="yt_api_c1",
                    author_id="a1",
                    author_name="Tester",
                    text="API test comment",
                    created_at=datetime.now(UTC),
                ),
            ]

    from app.services import comment_service
    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.services.comment_service.get_supabase", lambda: fake_supabase,
    )
    monkeypatch.setattr(
        "app.services.comment_service.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )
    monkeypatch.setattr(
        comment_service, "_get_adapter_map",
        lambda: {"youtube": FakeYouTubeAdapter},
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            "/api/v1/comments/collect",
            json={
                "platform": "youtube",
                "platform_post_id": "vid_001",
                "credentials": {"access_token": "tok"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["platform_comment_id"] == "yt_api_c1"


async def test_comments_api_list_and_get(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake_supabase)
    comment = _insert_comment(fake_supabase, user_id)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.services.comment_service.get_supabase", lambda: fake_supabase,
    )
    monkeypatch.setattr(
        "app.services.comment_service.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        # List
        list_resp = await client.get("/api/v1/comments")
        assert list_resp.status_code == 200
        body = list_resp.json()
        assert body["total"] == 1
        assert body["data"][0]["id"] == comment["id"]

        # Get single
        get_resp = await client.get(f"/api/v1/comments/{comment['id']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["text"] == comment["text"]

        # Get non-existent
        missing_resp = await client.get(f"/api/v1/comments/{uuid4()}")
        assert missing_resp.status_code == 404


async def test_comments_api_reply(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake_supabase)
    comment = _insert_comment(fake_supabase, user_id)

    class FakeYouTubeAdapter:
        platform_name = "youtube"

        async def reply_comment(self, post_id, cid, text, creds):
            return ReplyResult(success=True, platform_comment_id="reply_api_1")

    from app.services import comment_service
    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.services.comment_service.get_supabase", lambda: fake_supabase,
    )
    monkeypatch.setattr(
        "app.services.comment_service.get_settings",
        lambda: type("S", (), {
            "anthropic_api_key": None,
            "anthropic_model": "claude-3-5-sonnet-latest",
            "anthropic_api_base_url": "https://api.anthropic.com/v1",
        })(),
    )
    monkeypatch.setattr(
        comment_service, "_get_adapter_map",
        lambda: {"youtube": FakeYouTubeAdapter},
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            f"/api/v1/comments/{comment['id']}/reply",
            json={
                "credentials": {"access_token": "tok"},
                "context": "Python tips video",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["platform_reply_id"] == "reply_api_1"

        # Attempting to reply again should fail with 409
        conflict_resp = await client.post(
            f"/api/v1/comments/{comment['id']}/reply",
            json={"credentials": {"access_token": "tok"}},
        )
        assert conflict_resp.status_code == 409


# ---------------------------------------------------------------------------
# Worker tests
# ---------------------------------------------------------------------------

async def test_comment_worker_collect_all(monkeypatch) -> None:
    from app.workers.comment_worker import run_collect_all_comments

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    fake_supabase.insert_row("post_deliveries", {
        "owner_id": user_id,
        "platform": "youtube",
        "platform_post_id": "vid_w1",
        "status": "published",
        "post_id": str(uuid4()),
    })
    fake_supabase.insert_row("social_accounts", {
        "owner_id": user_id,
        "platform": "youtube",
        "handle": "my_channel",
        "encrypted_access_token": "tok",
        "metadata": {},
    })

    class FakeYouTubeAdapter:
        platform_name = "youtube"

        async def get_comments(self, post_id, creds, since=None):
            return [
                Comment(
                    platform_comment_id="wc1",
                    author_id="wa1",
                    author_name="Worker Tester",
                    text="Worker test",
                    created_at=datetime.now(UTC),
                ),
            ]

    from app.services import comment_service
    monkeypatch.setattr(
        "app.workers.comment_worker.get_supabase", lambda: fake_supabase,
    )
    monkeypatch.setattr(
        "app.services.comment_service.get_supabase", lambda: fake_supabase,
    )
    monkeypatch.setattr(
        "app.services.comment_service.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )
    monkeypatch.setattr(
        comment_service, "_get_adapter_map",
        lambda: {"youtube": FakeYouTubeAdapter},
    )

    result = await run_collect_all_comments()
    assert result["collected"] == 1
    assert result["deliveries_scanned"] == 1


async def test_comment_worker_auto_reply_pending(monkeypatch) -> None:
    from app.workers.comment_worker import run_auto_reply_pending

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    comment_id = str(uuid4())
    _insert_comment(fake_supabase, user_id, comment_id=comment_id)
    fake_supabase.insert_row("social_accounts", {
        "owner_id": user_id,
        "platform": "youtube",
        "handle": "my_channel",
        "encrypted_access_token": "tok",
        "metadata": {},
    })

    class FakeYouTubeAdapter:
        platform_name = "youtube"

        async def reply_comment(self, post_id, cid, text, creds):
            return ReplyResult(success=True, platform_comment_id="wr1")

    from app.services import comment_service
    monkeypatch.setattr(
        "app.workers.comment_worker.get_supabase", lambda: fake_supabase,
    )
    monkeypatch.setattr(
        "app.services.comment_service.get_supabase", lambda: fake_supabase,
    )
    monkeypatch.setattr(
        "app.services.comment_service.get_settings",
        lambda: type("S", (), {"anthropic_api_key": None})(),
    )
    monkeypatch.setattr(
        comment_service, "_get_adapter_map",
        lambda: {"youtube": FakeYouTubeAdapter},
    )

    result = await run_auto_reply_pending()
    assert result["replied"] == 1
    assert result["failed"] == 0
