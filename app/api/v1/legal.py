"""Legal / DPA endpoints — Data Processing Agreement signing and sub-processors."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES
from app.core.audit import record_audit
from app.core.db import get_supabase

router = APIRouter(
    prefix="/legal",
    tags=["Legal (GDPR)"],
    responses=COMMON_RESPONSES,
)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]

CURRENT_DPA_VERSION = "2026-04"

SUB_PROCESSORS = [
    {
        "name": "Supabase",
        "purpose": "Database and authentication",
        "location": "United States",
        "dpa_url": "https://supabase.com/legal/dpa",
    },
    {
        "name": "Stripe",
        "purpose": "Payment processing",
        "location": "United States",
        "dpa_url": "https://stripe.com/legal/dpa",
    },
    {
        "name": "Resend",
        "purpose": "Transactional email delivery",
        "location": "United States",
        "dpa_url": "https://resend.com/legal/dpa",
    },
    {
        "name": "Railway",
        "purpose": "Application hosting",
        "location": "United States",
        "dpa_url": "https://railway.app/legal/dpa",
    },
]


# -- Models -----------------------------------------------------------------


class DPAInfoResponse(BaseModel):
    version: str
    effective_date: str
    sub_processors_count: int


class DPASignRequest(BaseModel):
    signer_name: str = Field(..., min_length=1, max_length=200)
    signer_email: str = Field(..., min_length=1, max_length=320)
    company: str = Field(..., min_length=1, max_length=200)


class DPASignResponse(BaseModel):
    signed: bool
    dpa_version: str
    signed_at: str


class DPASignedResponse(BaseModel):
    dpa_version: str
    signer_name: str
    company: str
    signed_at: str
    pdf_url: str | None = None


class SubProcessor(BaseModel):
    name: str
    purpose: str
    location: str
    dpa_url: str


class SubProcessorsResponse(BaseModel):
    sub_processors: list[SubProcessor]
    last_updated: str


# -- Endpoints --------------------------------------------------------------


@router.get(
    "/dpa",
    response_model=DPAInfoResponse,
    summary="Get current DPA version",
)
async def get_dpa(user: CurrentUser) -> DPAInfoResponse:
    """Return the current DPA version information."""
    return DPAInfoResponse(
        version=CURRENT_DPA_VERSION,
        effective_date="2026-04-08",
        sub_processors_count=len(SUB_PROCESSORS),
    )


@router.post(
    "/dpa/sign",
    response_model=DPASignResponse,
    summary="Sign the DPA",
)
async def sign_dpa(
    body: DPASignRequest,
    user: CurrentUser,
    request: Request,
) -> DPASignResponse:
    """Sign the Data Processing Agreement."""
    sb = get_supabase()
    now_iso = datetime.now(UTC).isoformat()
    client_ip = request.client.host if request.client else None
    pdf_url = f"https://contentflow.dev/legal/dpa/signed/{user.id}/{CURRENT_DPA_VERSION}.pdf"

    sb.table("dpa_signatures").insert({
        "user_id": user.id,
        "dpa_version": CURRENT_DPA_VERSION,
        "signer_name": body.signer_name,
        "signer_email": body.signer_email,
        "company": body.company,
        "signed_at": now_iso,
        "ip": client_ip,
        "pdf_url": pdf_url,
    }).execute()

    await record_audit(
        user_id=user.id,
        action="legal.dpa_sign",
        resource="legal",
        ip=client_ip,
        metadata={"company": body.company, "version": CURRENT_DPA_VERSION},
    )

    return DPASignResponse(
        signed=True,
        dpa_version=CURRENT_DPA_VERSION,
        signed_at=now_iso,
    )


@router.get(
    "/dpa/signed",
    response_model=DPASignedResponse,
    summary="Get signed DPA",
)
async def get_signed_dpa(user: CurrentUser) -> DPASignedResponse:
    """Return the user's signed DPA details."""
    sb = get_supabase()
    response = (
        sb.table("dpa_signatures")
        .select("dpa_version, signer_name, company, signed_at, pdf_url")
        .eq("user_id", user.id)
        .order("signed_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    result = rows[0] if rows else None
    if not result:
        from app.core.errors import NotFoundError

        raise NotFoundError("dpa_signature", user.id)

    return DPASignedResponse(**result)


@router.get(
    "/sub-processors",
    response_model=SubProcessorsResponse,
    summary="List sub-processors",
)
async def list_sub_processors(user: CurrentUser) -> SubProcessorsResponse:
    """Return the list of third-party sub-processors."""
    return SubProcessorsResponse(
        sub_processors=[SubProcessor(**sp) for sp in SUB_PROCESSORS],
        last_updated="2026-04-08",
    )
