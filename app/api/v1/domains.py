"""Custom domain verification APIs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES, NOT_FOUND_ERROR
from app.core.db import get_supabase
from app.core.workspaces import require_workspace_role
from app.middleware.custom_domain import normalize_host, verify_custom_domain_record

router = APIRouter(tags=["Domains"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


class DomainVerifyRequest(BaseModel):
    check_dns: bool = False


class DomainVerifyResponse(BaseModel):
    workspace_id: str
    domain: str
    txt_record_name: str
    txt_record_value: str
    verified: bool


@router.post(
    "/workspaces/{workspace_id}/domain/verify",
    response_model=DomainVerifyResponse,
    summary="Verify Custom Domain",
    responses=NOT_FOUND_ERROR,
)
async def verify_workspace_domain(
    workspace_id: str,
    req: DomainVerifyRequest,
    user: CurrentUser,
) -> DomainVerifyResponse:
    require_workspace_role(workspace_id, user.id, allowed_roles={"owner", "admin"})
    sb = get_supabase()
    workspace = sb.table("workspaces").select("*").eq("id", workspace_id).single().execute().data
    domain = normalize_host(workspace.get("custom_domain") or "")
    token = workspace.get("domain_verification_token") or ""
    verified = False
    if req.check_dns and domain and token:
        verified = verify_custom_domain_record(domain, token)
        if verified:
            sb.table("workspaces").update(
                {"domain_verified_at": datetime.now(UTC).isoformat()}
            ).eq("id", workspace_id).execute()

    return DomainVerifyResponse(
        workspace_id=workspace_id,
        domain=domain,
        txt_record_name=f"_contentflow-verify.{domain}",
        txt_record_value=token,
        verified=verified or bool(workspace.get("domain_verified_at")),
    )
