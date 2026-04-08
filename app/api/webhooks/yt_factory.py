"""yt-factory webhook receiver for YtBoost."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.monitoring import get_logger
from app.core.webhook_signature import SignatureError, verify_yt_factory_signature
from app.services.yt_factory_integration import YtFactoryIntegration

logger = get_logger(__name__)

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
    secret = get_settings().ytboost_webhook_secret

    try:
        verify_yt_factory_signature(raw, x_ytboost_signature, secret)
    except SignatureError as exc:
        if exc.reason == "Malformed signature format":
            raise HTTPException(status_code=400, detail=exc.reason) from None
        raise HTTPException(status_code=401, detail=exc.reason) from None

    try:
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
    except Exception:
        logger.exception(
            "yt_factory_webhook_failed",
            user_id=payload.user_id,
            youtube_video_id=payload.youtube_video_id,
            youtube_channel_id=payload.youtube_channel_id,
        )
        raise HTTPException(status_code=500, detail="Internal processing error") from None

    return {"status": "accepted", **result}
