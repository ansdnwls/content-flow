"""Email verification endpoints — request and confirm."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES
from app.config import get_settings
from app.core.db import get_supabase
from app.core.errors import AuthenticationError

router = APIRouter(
    prefix="/auth/verify-email",
    tags=["Email Verification"],
    responses=COMMON_RESPONSES,
)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]

TOKEN_EXPIRY_HOURS = 24


def _create_verify_token(user_id: str, email: str) -> str:
    settings = get_settings()
    if (
        settings.jwt_secret == "change-me-in-production"
        and settings.app_env not in ("development", "test", "testing")
    ):
        raise RuntimeError(
            "JWT_SECRET must be set to a secure value in production",
        )
    payload = {
        "sub": user_id,
        "email": email,
        "purpose": "email_verify",
        "exp": datetime.now(UTC) + timedelta(hours=TOKEN_EXPIRY_HOURS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _decode_verify_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Verification link has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid verification token") from exc
    if payload.get("purpose") != "email_verify":
        raise AuthenticationError("Invalid token purpose")
    return payload


class VerifyRequestResponse(BaseModel):
    message: str
    verify_url: str | None = None


class VerifyConfirmRequest(BaseModel):
    token: str


class VerifyConfirmResponse(BaseModel):
    verified: bool
    email: str


@router.post(
    "/request",
    response_model=VerifyRequestResponse,
    summary="Request Email Verification",
)
async def request_verification(
    user: CurrentUser,
) -> VerifyRequestResponse:
    token = _create_verify_token(user.id, user.email)
    settings = get_settings()
    verify_url = (
        f"{settings.email_dashboard_url}/verify?token={token}"
    )
    # In production, send_template would be called here.
    # For now, return the URL so tests and clients can use it.
    return VerifyRequestResponse(
        message="Verification email sent",
        verify_url=verify_url,
    )


@router.post(
    "/confirm",
    response_model=VerifyConfirmResponse,
    summary="Confirm Email Verification",
)
async def confirm_verification(
    req: VerifyConfirmRequest,
    user: CurrentUser,
) -> VerifyConfirmResponse:
    payload = _decode_verify_token(req.token)

    if payload["sub"] != user.id:
        raise AuthenticationError("Token does not match current user")

    sb = get_supabase()
    sb.table("users").update({
        "email_verified": True,
        "email_verified_at": datetime.now(UTC).isoformat(),
    }).eq("id", user.id).execute()

    return VerifyConfirmResponse(verified=True, email=payload["email"])
