"""ShopSync API: product registration, content generation, and publish."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.core.db import get_supabase

router = APIRouter(prefix="/shopsync", tags=["ShopSync"])
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]

_ALL_CHANNELS = ["smart_store", "coupang", "instagram", "naver_blog", "kakao"]


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CreateProductRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=200)
    price: int = Field(..., ge=0)
    category: str = ""
    image_urls: list[str] = Field(default_factory=list)
    target_platforms: list[str] = Field(default_factory=lambda: list(_ALL_CHANNELS))
    auto_publish: bool = False


class PublishRequest(BaseModel):
    target_channels: list[str] = Field(
        default_factory=lambda: list(_ALL_CHANNELS),
        min_length=1,
    )
    dry_run: bool = False


# ---------------------------------------------------------------------------
# POST /shopsync/products
# ---------------------------------------------------------------------------


@router.post("/products", status_code=201)
async def create_product(body: CreateProductRequest, user: CurrentUser) -> dict:
    """Register a product and run Product Content Bomb."""
    from app.services.product_bomb import generate_product_bomb

    product_id = str(uuid4())

    bomb_result = await generate_product_bomb(
        product_images=[],
        product_name=body.product_name,
        price=body.price,
        category=body.category,
        image_urls=body.image_urls,
        target_platforms=body.target_platforms,
        auto_publish=body.auto_publish,
        user_id=user.id,
    )

    record: dict[str, Any] = {
        "id": product_id,
        "user_id": user.id,
        "product_name": body.product_name,
        "price": body.price,
        "category": body.category,
        "image_urls": body.image_urls,
        "target_platforms": body.target_platforms,
        "channels_generated": bomb_result.channels_generated,
        "status": "generated",
    }
    sb = get_supabase()
    sb.table("shopsync_products").insert(record).execute()

    return {
        "id": product_id,
        "product_name": body.product_name,
        "price": body.price,
        "channels_generated": bomb_result.channels_generated,
        "errors": bomb_result.errors,
        "auto_published": body.auto_publish,
    }


# ---------------------------------------------------------------------------
# GET /shopsync/products
# ---------------------------------------------------------------------------


@router.get("/products")
async def list_products(
    user: CurrentUser,
    page: int = 1,
    limit: int = 20,
) -> dict:
    """List user's ShopSync products with pagination."""
    sb = get_supabase()
    offset = (page - 1) * limit
    result = sb.table("shopsync_products").select(
        "*", count="exact",
    ).eq(
        "user_id", user.id,
    ).order(
        "created_at", desc=True,
    ).range(
        offset, offset + limit - 1,
    ).execute()

    return {
        "data": result.data,
        "total": result.count or 0,
        "page": page,
        "limit": limit,
    }


# ---------------------------------------------------------------------------
# GET /shopsync/products/{product_id}
# ---------------------------------------------------------------------------


@router.get("/products/{product_id}")
async def get_product(product_id: str, user: CurrentUser) -> dict:
    """Fetch a single ShopSync product."""
    sb = get_supabase()
    row = (
        sb.table("shopsync_products")
        .select("*")
        .eq("id", product_id)
        .maybe_single()
        .execute()
        .data
    )
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    if row["user_id"] != user.id:
        raise HTTPException(status_code=404, detail="Product not found")
    return row


# ---------------------------------------------------------------------------
# POST /shopsync/products/{product_id}/publish
# ---------------------------------------------------------------------------


@router.post("/products/{product_id}/publish")
async def publish_product(
    product_id: str,
    body: PublishRequest,
    user: CurrentUser,
) -> dict:
    """Publish generated content to selected channels."""
    from app.services.product_bomb import generate_product_bomb
    from app.services.shopsync_publisher import ShopsyncPublisher

    sb = get_supabase()
    row = (
        sb.table("shopsync_products")
        .select("*")
        .eq("id", product_id)
        .maybe_single()
        .execute()
        .data
    )
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    if row["user_id"] != user.id:
        raise HTTPException(status_code=404, detail="Product not found")

    # Re-generate bomb result for publish
    bomb_result = await generate_product_bomb(
        product_images=[],
        product_name=row["product_name"],
        price=row["price"],
        category=row.get("category", ""),
        image_urls=row.get("image_urls", []),
        target_platforms=body.target_channels,
    )

    publisher = ShopsyncPublisher()
    pub_result = await publisher.publish(
        bomb_result=bomb_result,
        target_channels=body.target_channels,
        user_id=user.id,
        dry_run=body.dry_run,
    )

    if not body.dry_run:
        sb.table("shopsync_products").update(
            {"status": "published"},
        ).eq("id", product_id).execute()

    return {
        "product_id": product_id,
        "dry_run": body.dry_run,
        "succeeded": pub_result.succeeded,
        "failed": pub_result.failed,
        "results": [
            {
                "channel": r.channel,
                "success": r.success,
                "error": r.error,
                "payload": r.payload,
            }
            for r in pub_result.results
        ],
    }


# ---------------------------------------------------------------------------
# DELETE /shopsync/products/{product_id}
# ---------------------------------------------------------------------------


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(product_id: str, user: CurrentUser) -> Response:
    """Delete a ShopSync product."""
    sb = get_supabase()
    row = (
        sb.table("shopsync_products")
        .select("id, user_id")
        .eq("id", product_id)
        .maybe_single()
        .execute()
        .data
    )
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    if row["user_id"] != user.id:
        raise HTTPException(status_code=404, detail="Product not found")

    sb.table("shopsync_products").delete().eq("id", product_id).execute()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# POST /shopsync/products/bulk-import
# ---------------------------------------------------------------------------

_MAX_CSV_ROWS = 1000


@router.post("/products/bulk-import", status_code=202)
async def bulk_import_products(file: UploadFile, user: CurrentUser) -> dict:
    """Upload a CSV file to bulk-import products via background worker."""
    if file.content_type and file.content_type not in (
        "text/csv",
        "application/vnd.ms-excel",
        "application/octet-stream",
    ):
        raise HTTPException(status_code=400, detail="File must be CSV")

    raw_bytes = await file.read()
    if not raw_bytes.strip():
        raise HTTPException(status_code=400, detail="CSV file is empty")

    csv_text = raw_bytes.decode("utf-8-sig", errors="replace")

    # Quick row count check (header + data rows)
    line_count = csv_text.strip().count("\n")
    if line_count > _MAX_CSV_ROWS + 1:
        raise HTTPException(
            status_code=413,
            detail=f"Too many rows. Maximum is {_MAX_CSV_ROWS}",
        )

    # Quick column validation
    first_line = csv_text.split("\n", 1)[0].lower()
    required = {"name", "price", "category", "image_url"}
    headers = {h.strip() for h in first_line.split(",")}
    missing = required - headers
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {', '.join(sorted(missing))}",
        )

    job_id = str(uuid4())
    sb = get_supabase()
    sb.table("shopsync_bulk_jobs").insert(
        {
            "id": job_id,
            "user_id": user.id,
            "status": "pending",
            "total_rows": line_count,
            "succeeded": 0,
            "failed": 0,
            "results": [],
            "error": None,
        },
    ).execute()

    from app.workers.shopsync_bulk_worker import shopsync_bulk_import_task

    shopsync_bulk_import_task.delay(job_id, csv_text, user.id)

    return {
        "job_id": job_id,
        "total_rows": line_count,
        "status_url": f"/api/v1/shopsync/products/bulk-import/{job_id}",
    }


# ---------------------------------------------------------------------------
# GET /shopsync/products/bulk-import/{job_id}
# ---------------------------------------------------------------------------


@router.get("/products/bulk-import/{job_id}")
async def get_bulk_import_status(job_id: str, user: CurrentUser) -> dict:
    """Get bulk import job progress."""
    sb = get_supabase()
    row = (
        sb.table("shopsync_bulk_jobs")
        .select("*")
        .eq("id", job_id)
        .maybe_single()
        .execute()
        .data
    )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    if row["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return row
