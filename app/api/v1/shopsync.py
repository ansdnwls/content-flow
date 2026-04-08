"""ShopSync API: product registration, content generation, and publish."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
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
