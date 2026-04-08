from __future__ import annotations

from types import SimpleNamespace

import httpx
import respx

from tests.fakes import FakeSupabase


async def test_extract_shorts_fallback_inserts_three_rows(monkeypatch) -> None:
    from app.services.shorts_extractor import extract_shorts

    fake = FakeSupabase()
    monkeypatch.setattr("app.services.shorts_extractor.get_supabase", lambda: fake)

    rows = await extract_shorts(
        "vid_123",
        "user_123",
        "chan_123",
        video_metadata={"duration": "PT5M"},
    )

    assert len(rows) == 3
    assert rows[0]["source_video_id"] == "vid_123"
    assert fake.tables["ytboost_shorts"][0]["status"] == "pending"


@respx.mock
async def test_extract_shorts_uses_claude_when_transcript_available(monkeypatch) -> None:
    from app.services.shorts_extractor import extract_shorts

    fake = FakeSupabase()
    monkeypatch.setattr("app.services.shorts_extractor.get_supabase", lambda: fake)
    monkeypatch.setattr(
        "app.services.shorts_extractor.get_settings",
        lambda: SimpleNamespace(
            anthropic_api_key="anthropic-key",
            anthropic_model="claude-3-5-sonnet-latest",
            anthropic_api_base_url="https://api.anthropic.com/v1",
        ),
    )
    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '[{"start_seconds": 12, "end_seconds": 60, '
                            '"hook_line": "Wait for it", '
                            '"reason": "Strong suspense", '
                            '"suggested_title": "Best moment", '
                            '"suggested_hashtags": ["#shorts", "#viral"]}]'
                        ),
                    }
                ]
            },
        )
    )

    rows = await extract_shorts(
        "vid_456",
        "user_123",
        "chan_123",
        transcript=[{"start": 0, "text": "intro"}],
        video_metadata={"duration_seconds": 600},
    )

    assert len(rows) == 1
    assert rows[0]["start_seconds"] == 12
    assert rows[0]["suggested_title"] == "Best moment"


def test_fallback_segments_cover_varied_durations() -> None:
    from app.services.shorts_extractor import _fallback_segments

    for duration in (300, 1800, 7200):
        clips = _fallback_segments(duration)
        assert len(clips) == 3
        assert all(clip.end_seconds > clip.start_seconds for clip in clips)
        assert clips[-1].end_seconds <= duration
