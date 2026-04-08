"""In-app notifications — list, read, and delete dashboard notifications."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES, NOT_FOUND_ERROR
from app.services.notification_service import (
    delete_notification,
    get_unread_count,
    list_notifications,
    mark_all_read,
    mark_read,
)

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
    responses=COMMON_RESPONSES,
)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    body: str
    link_url: str | None = None
    read_at: str | None = None
    created_at: str


class NotificationListResponse(BaseModel):
    data: list[NotificationResponse]
    total: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkAllReadResponse(BaseModel):
    updated: int


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List Notifications",
    responses=NOT_FOUND_ERROR,
)
async def list_user_notifications(
    user: CurrentUser,
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
) -> NotificationListResponse:
    items = list_notifications(user.id, unread_only=unread_only, limit=limit)
    return NotificationListResponse(data=items, total=len(items))


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Get Unread Notification Count",
)
async def unread_notification_count(
    user: CurrentUser,
) -> UnreadCountResponse:
    count = get_unread_count(user.id)
    return UnreadCountResponse(unread_count=count)


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark Notification as Read",
    responses=NOT_FOUND_ERROR,
)
async def mark_notification_read(
    notification_id: str,
    user: CurrentUser,
) -> NotificationResponse:
    updated = mark_read(notification_id, user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Notification not found")
    return NotificationResponse(**updated)


@router.post(
    "/read-all",
    response_model=MarkAllReadResponse,
    summary="Mark All Notifications as Read",
)
async def mark_all_notifications_read(
    user: CurrentUser,
) -> MarkAllReadResponse:
    count = mark_all_read(user.id)
    return MarkAllReadResponse(updated=count)


@router.delete(
    "/{notification_id}",
    status_code=204,
    response_model=None,
    summary="Delete Notification",
    responses=NOT_FOUND_ERROR,
)
async def delete_user_notification(
    notification_id: str,
    user: CurrentUser,
) -> None:
    deleted = delete_notification(notification_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Notification not found")
