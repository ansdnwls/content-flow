"""Billing API — checkout, portal, subscription management."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES
from app.services import billing_service

router = APIRouter(prefix="/billing", tags=["Billing"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


class CheckoutRequest(BaseModel):
    plan: Literal["build", "scale", "enterprise"]
    interval: Literal["monthly", "yearly"] = "monthly"


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class SubscriptionResponse(BaseModel):
    plan: str
    status: str
    subscription_id: str | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


class CancelResponse(BaseModel):
    status: str
    cancel_at_period_end: bool = False


class ChangePlanRequest(BaseModel):
    plan: Literal["build", "scale", "enterprise"]
    interval: Literal["monthly", "yearly"] = "monthly"


class ChangePlanResponse(BaseModel):
    status: str
    plan: str
    from_plan: str


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=201,
    summary="Start Checkout",
    description="Creates a Stripe Checkout session and returns the URL.",
)
async def create_checkout(req: CheckoutRequest, user: CurrentUser) -> CheckoutResponse:
    url = await billing_service.create_checkout_session(
        user.id, req.plan, req.interval,
    )
    return CheckoutResponse(checkout_url=url)


@router.post(
    "/portal",
    response_model=PortalResponse,
    summary="Customer Portal",
    description="Creates a Stripe Customer Portal session for subscription management.",
)
async def create_portal(user: CurrentUser) -> PortalResponse:
    url = await billing_service.create_portal_session(user.id)
    return PortalResponse(portal_url=url)


@router.get(
    "/subscription",
    response_model=SubscriptionResponse,
    summary="Get Subscription",
    description="Returns current subscription status and plan details.",
)
async def get_subscription(user: CurrentUser) -> SubscriptionResponse:
    info = await billing_service.get_subscription_status(user.id)
    return SubscriptionResponse(**info)


@router.post(
    "/cancel",
    response_model=CancelResponse,
    summary="Cancel Subscription",
    description="Cancels the subscription at the end of the current billing period.",
)
async def cancel_subscription(user: CurrentUser) -> CancelResponse:
    result = await billing_service.cancel_subscription(user.id)
    return CancelResponse(**result)


@router.post(
    "/change-plan",
    response_model=ChangePlanResponse,
    summary="Change Plan",
    description="Changes the subscription to a different plan with proration.",
)
async def change_plan(req: ChangePlanRequest, user: CurrentUser) -> ChangePlanResponse:
    result = await billing_service.change_plan(user.id, req.plan, req.interval)
    return ChangePlanResponse(**result)
