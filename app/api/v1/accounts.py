"""Accounts API: OAuth connect, callback, list, and disconnect."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES, NOT_FOUND_ERROR
from app.core.cache import cache, invalidate_user_cache
from app.core.webhook_dispatcher import dispatch_event
from app.oauth import SUPPORTED_PLATFORMS, get_oauth_provider
from app.oauth.provider import create_oauth_state, verify_oauth_state
from app.oauth.providers.x import XOAuthProvider
from app.oauth.token_store import delete_account, list_accounts, save_tokens

router = APIRouter(prefix="/accounts", tags=["Accounts"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class AccountResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "acc_123",
                "platform": "youtube",
                "handle": "@contentflow",
                "display_name": "ContentFlow Media",
                "token_expires_at": "2026-04-09T12:00:00+00:00",
                "metadata": {"channel_id": "UC123"},
            },
        },
    )

    id: str = Field(description="Connected social account identifier.")
    platform: str = Field(description="Target platform slug.")
    handle: str = Field(description="Public handle or username.")
    display_name: str | None = Field(default=None, description="Human-friendly account name.")
    token_expires_at: str | None = Field(
        default=None,
        description="OAuth access token expiration in ISO 8601 format.",
    )
    metadata: dict = Field(default_factory=dict, description="Provider-specific metadata.")


class AccountsListResponse(BaseModel):
    data: list[AccountResponse]
    total: int


class ConnectResponse(BaseModel):
    authorize_url: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_platform(platform: str) -> None:
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported platform '{platform}'. "
                f"Must be one of: {', '.join(SUPPORTED_PLATFORMS)}"
            ),
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/connect/{platform}",
    response_model=ConnectResponse,
    summary="Start OAuth Connection",
    description="Returns an authorization URL to redirect the user for OAuth consent.",
)
async def connect_account(platform: str, user: CurrentUser) -> ConnectResponse:
    _validate_platform(platform)
    provider = get_oauth_provider(platform)
    extra: dict[str, str] = {}
    if user.workspace_id is not None:
        extra["workspace_id"] = user.workspace_id
    state = create_oauth_state(user.id, platform, extra=extra or None)

    if isinstance(provider, XOAuthProvider):
        url, verifier = provider.get_authorize_url_with_pkce(state)
        # Re-create state with verifier embedded so callback can extract it
        state = create_oauth_state(
            user.id,
            platform,
            extra={**extra, "code_verifier": verifier},
        )
        url, _ = provider.get_authorize_url_with_pkce(state)
        return ConnectResponse(authorize_url=url)

    return ConnectResponse(authorize_url=provider.get_authorize_url(state))


@router.get(
    "/callback/{platform}",
    response_model=AccountResponse,
    summary="OAuth Callback",
    description="Handles the OAuth callback: exchanges the code, encrypts and stores tokens.",
)
async def oauth_callback(
    platform: str,
    code: str = Query(...),
    state: str = Query(...),
) -> AccountResponse:
    _validate_platform(platform)

    try:
        claims = verify_oauth_state(state)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid OAuth state: {exc}") from exc

    if claims.get("platform") != platform:
        raise HTTPException(status_code=400, detail="Platform mismatch in OAuth state")

    owner_id: str = claims["sub"]
    provider = get_oauth_provider(platform)
    redirect_uri = provider.build_redirect_uri()

    # Exchange code for tokens
    if isinstance(provider, XOAuthProvider):
        token_resp = await provider.exchange_code(
            code, redirect_uri, code_verifier=claims.get("code_verifier")
        )
    else:
        token_resp = await provider.exchange_code(code, redirect_uri)

    # Fetch user info
    user_info = await provider.get_user_info(token_resp.access_token)

    # Compute expiry
    token_expires_at = None
    if token_resp.expires_in:
        token_expires_at = (
            datetime.now(UTC) + timedelta(seconds=token_resp.expires_in)
        ).isoformat()

    # Save encrypted tokens
    row = save_tokens(
        owner_id=owner_id,
        workspace_id=claims.get("workspace_id"),
        platform=platform,
        handle=user_info.handle,
        access_token=token_resp.access_token,
        refresh_token=token_resp.refresh_token,
        token_expires_at=token_expires_at,
        display_name=user_info.display_name,
        metadata=user_info.metadata or {},
    )

    # Dispatch webhook
    await dispatch_event(
        owner_id, "account.connected", {"account_id": row["id"], "platform": platform}
    )
    await invalidate_user_cache(owner_id)

    return AccountResponse(
        id=row["id"],
        platform=row["platform"],
        handle=row["handle"],
        display_name=row.get("display_name"),
        token_expires_at=row.get("token_expires_at"),
        metadata=row.get("metadata", {}),
    )


@router.get(
    "",
    response_model=AccountsListResponse,
    summary="List Connected Accounts",
    description=(
        "Returns all connected social media accounts for the authenticated owner. "
        "Use this endpoint to confirm which platforms are available for publishing."
    ),
)
@cache(ttl=3600, key_prefix="accounts-list")
async def list_connected_accounts(
    request: Request,
    user: CurrentUser,
) -> AccountsListResponse:
    accounts = list_accounts(user.id, user.workspace_id)
    return AccountsListResponse(
        data=[AccountResponse(**row) for row in accounts],
        total=len(accounts),
    )


@router.delete(
    "/{account_id}",
    response_model=AccountResponse,
    summary="Disconnect Account",
    description="Removes a connected social media account and its stored tokens.",
    responses=NOT_FOUND_ERROR,
)
async def disconnect_account(account_id: str, user: CurrentUser) -> AccountResponse:
    row = delete_account(account_id, user.id, user.workspace_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' not found")

    await dispatch_event(
        user.id, "account.disconnected", {"account_id": account_id, "platform": row["platform"]}
    )
    await invalidate_user_cache(user.id)

    return AccountResponse(
        id=row["id"],
        platform=row["platform"],
        handle=row["handle"],
        display_name=row.get("display_name"),
        token_expires_at=row.get("token_expires_at"),
        metadata=row.get("metadata", {}),
    )
