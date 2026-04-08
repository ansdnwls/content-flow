"""Webhook delivery history, replay, and dead-letter APIs."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES, NOT_FOUND_ERROR
from app.core.db import get_supabase
from app.core.errors import NotFoundError
from app.core.webhook_dispatcher import redeliver_latest_for_webhook, replay_delivery

router = APIRouter(prefix="/webhooks", tags=["Webhooks"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


class WebhookDeliveryResponse(BaseModel):
    id: str
    webhook_id: str
    event: str
    payload: dict[str, Any]
    status: str
    attempts: int
    last_error: str | None = None
    next_retry_at: str | None = None
    delivered_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class WebhookDeliveryListResponse(BaseModel):
    data: list[WebhookDeliveryResponse]
    total: int
    page: int
    limit: int


class ReplayResponse(BaseModel):
    success: bool = Field(description="Whether the replay succeeded immediately.")
    delivery: WebhookDeliveryResponse


def _ensure_webhook_owned(webhook_id: str, owner_id: str) -> None:
    webhook = (
        get_supabase()
        .table("webhooks")
        .select("id")
        .eq("id", webhook_id)
        .eq("owner_id", owner_id)
        .maybe_single()
        .execute()
        .data
    )
    if not webhook:
        raise NotFoundError("Webhook", webhook_id)


@router.get(
    "/dead-letters",
    response_model=WebhookDeliveryListResponse,
    summary="List Dead Letters",
    description=(
        "Returns webhook deliveries that exhausted retries "
        "and moved to the dead-letter queue."
    ),
)
async def list_dead_letters(
    user: CurrentUser,
    page: int = 1,
    limit: int = 50,
) -> WebhookDeliveryListResponse:
    start = (page - 1) * limit
    end = start + limit - 1
    result = (
        get_supabase()
        .table("webhook_deliveries")
        .select("*", count="exact")
        .eq("owner_id", user.id)
        .eq("status", "dead_letter")
        .order("created_at", desc=True)
        .range(start, end)
        .execute()
    )
    return WebhookDeliveryListResponse(
        data=[WebhookDeliveryResponse(**row) for row in result.data],
        total=result.count or 0,
        page=page,
        limit=limit,
    )


@router.get(
    "/{webhook_id}/deliveries",
    response_model=WebhookDeliveryListResponse,
    summary="List Webhook Deliveries",
    description="Returns delivery history for a single webhook.",
    responses=NOT_FOUND_ERROR,
)
async def list_deliveries(
    webhook_id: str,
    user: CurrentUser,
    page: int = 1,
    limit: int = 50,
) -> WebhookDeliveryListResponse:
    _ensure_webhook_owned(webhook_id, user.id)

    start = (page - 1) * limit
    end = start + limit - 1
    result = (
        get_supabase()
        .table("webhook_deliveries")
        .select("*", count="exact")
        .eq("owner_id", user.id)
        .eq("webhook_id", webhook_id)
        .order("created_at", desc=True)
        .range(start, end)
        .execute()
    )
    return WebhookDeliveryListResponse(
        data=[WebhookDeliveryResponse(**row) for row in result.data],
        total=result.count or 0,
        page=page,
        limit=limit,
    )


@router.post(
    "/{webhook_id}/redeliver",
    response_model=ReplayResponse,
    summary="Redeliver Latest Webhook Event",
    description="Replays the most recent delivery payload for the specified webhook.",
    responses=NOT_FOUND_ERROR,
)
async def redeliver_webhook(webhook_id: str, user: CurrentUser) -> ReplayResponse:
    delivery = await redeliver_latest_for_webhook(webhook_id, user.id)
    if not delivery:
        raise HTTPException(
            status_code=404,
            detail=f"No deliveries found for webhook '{webhook_id}'",
        )
    response = WebhookDeliveryResponse(**delivery)
    return ReplayResponse(success=response.status == "delivered", delivery=response)


@router.post(
    "/deliveries/{delivery_id}/replay",
    response_model=ReplayResponse,
    summary="Replay Delivery",
    description="Creates a fresh delivery attempt from a historical delivery payload.",
    responses=NOT_FOUND_ERROR,
)
async def replay_webhook_delivery(delivery_id: str, user: CurrentUser) -> ReplayResponse:
    delivery = await replay_delivery(delivery_id, user.id)
    if not delivery:
        raise NotFoundError("Webhook delivery", delivery_id)
    response = WebhookDeliveryResponse(**delivery)
    return ReplayResponse(success=response.status == "delivered", delivery=response)
