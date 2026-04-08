"""yt-factory webhook receiver for YtBoost."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.youtube_trigger import verify_webhook_signature
from app.services.yt_factory_integration import YtFactoryIntegration

router = APIRouter(prefix="/api/webhooks", tags=["yt-factory Webhooks"])


class YtFactoryPayload(BaseModel):
    yt_factory_job_id: str | None = None
    youtube_video_id: str
    youtube_channel_id: str
    user_id: str
    transcript: list[dict] = Field(default_factory=list)
    video_metadata: dict = Field(default_factory=dict)
    script_data: dict = Field(default_factory=dict)


@router.post(
    "/yt-factory",
    status_code=202,
    summary="yt-factory Publish Webhook",
    description="Triggers YtBoost extraction after yt-factory finishes a YouTube publish.",
)
async def yt_factory_webhook(
    payload: YtFactoryPayload,
    request: Request,
    x_ytboost_signature: str | None = Header(default=None, alias="X-YtBoost-Signature"),
) -> dict[str, object]:
    raw = await request.body()
    if not verify_webhook_signature(raw, x_ytboost_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    result = await YtFactoryIntegration().handle_publish_complete(
        user_id=payload.user_id,
        youtube_video_id=payload.youtube_video_id,
        youtube_channel_id=payload.youtube_channel_id,
        transcript=payload.transcript,
        video_metadata={
            **payload.video_metadata,
            "yt_factory_job_id": payload.yt_factory_job_id,
            "script_data": payload.script_data,
        },
    )
    return {"status": "accepted", **result}
