"""Notification preferences — manage email alert settings."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES
from app.core.db import get_supabase

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
    responses=COMMON_RESPONSES,
)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]

PREF_FIELDS = [
    "product_updates",
    "billing",
    "security",
    "monthly_summary",
    "webhook_alerts",
]

DEFAULT_PREFS = {f: True for f in PREF_FIELDS}


class NotificationPreferences(BaseModel):
    product_updates: bool = True
    billing: bool = True
    security: bool = True
    monthly_summary: bool = True
    webhook_alerts: bool = True


class UpdatePreferencesRequest(BaseModel):
    product_updates: bool | None = None
    billing: bool | None = None
    security: bool | None = None
    monthly_summary: bool | None = None
    webhook_alerts: bool | None = None


def _get_or_create_prefs(user_id: str) -> dict:
    sb = get_supabase()
    result = (
        sb.table("notification_preferences")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if result.data:
        return result.data

    row = {"user_id": user_id, **DEFAULT_PREFS}
    return sb.table("notification_preferences").insert(row).execute().data[0]


@router.get(
    "/preferences",
    response_model=NotificationPreferences,
    summary="Get Notification Preferences",
)
async def get_preferences(
    user: CurrentUser,
) -> NotificationPreferences:
    prefs = _get_or_create_prefs(user.id)
    return NotificationPreferences(
        **{f: prefs.get(f, True) for f in PREF_FIELDS},
    )


@router.patch(
    "/preferences",
    response_model=NotificationPreferences,
    summary="Update Notification Preferences",
)
async def update_preferences(
    req: UpdatePreferencesRequest,
    user: CurrentUser,
) -> NotificationPreferences:
    _get_or_create_prefs(user.id)

    updates = req.model_dump(exclude_none=True)
    if updates:
        sb = get_supabase()
        sb.table("notification_preferences").update(
            updates,
        ).eq("user_id", user.id).execute()

    prefs = _get_or_create_prefs(user.id)
    return NotificationPreferences(
        **{f: prefs.get(f, True) for f in PREF_FIELDS},
    )
