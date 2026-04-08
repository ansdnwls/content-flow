"""ShopSync API: product registration, content generation, and publish."""
from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.core.cache import cache
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


# ---------------------------------------------------------------------------
# Analytics helpers
# ---------------------------------------------------------------------------

# Assumed: manual work 6h/product, ShopSync 10min/product → 5h50m saved
_MANUAL_HOURS_PER_PRODUCT = 6.0
_SHOPSYNC_HOURS_PER_PRODUCT = 10.0 / 60.0  # 10 minutes
_SAVED_HOURS_PER_PRODUCT = _MANUAL_HOURS_PER_PRODUCT - _SHOPSYNC_HOURS_PER_PRODUCT


def _month_range(dt: datetime) -> tuple[str, str]:
    """Return (start_iso, end_iso) for the month containing *dt*."""
    start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.isoformat(), end.isoformat()


def _prev_month(dt: datetime) -> datetime:
    if dt.month == 1:
        return dt.replace(year=dt.year - 1, month=12)
    return dt.replace(month=dt.month - 1)


def _pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _fetch_products_in_range(
    sb: Any, user_id: str, start: str, end: str,
) -> list[dict]:
    return (
        sb.table("shopsync_products")
        .select("*")
        .eq("user_id", user_id)
        .gte("created_at", start)
        .lte("created_at", end)
        .execute()
        .data
    )


# ---------------------------------------------------------------------------
# GET /shopsync/analytics/overview
# ---------------------------------------------------------------------------


@router.get("/analytics/overview")
@cache(ttl=300, key_prefix="shopsync-analytics-overview")
async def analytics_overview(
    request: Request,
    response: Response,
    user: CurrentUser,
) -> dict:
    """Monthly overview: products, time saved, channels published."""
    sb = get_supabase()
    now = datetime.now(UTC)
    cur_start, cur_end = _month_range(now)
    prev_start, prev_end = _month_range(_prev_month(now))

    cur_products = _fetch_products_in_range(sb, user.id, cur_start, cur_end)
    prev_products = _fetch_products_in_range(sb, user.id, prev_start, prev_end)

    cur_count = len(cur_products)
    prev_count = len(prev_products)

    cur_channels = sum(
        len(p.get("channels_generated", [])) for p in cur_products
    )
    prev_channels = sum(
        len(p.get("channels_generated", [])) for p in prev_products
    )

    cur_saved = round(cur_count * _SAVED_HOURS_PER_PRODUCT, 1)
    prev_saved = round(prev_count * _SAVED_HOURS_PER_PRODUCT, 1)

    return {
        "this_month_products": cur_count,
        "prev_month_products": prev_count,
        "products_change_pct": _pct_change(cur_count, prev_count),
        "channels_published": cur_channels,
        "prev_channels_published": prev_channels,
        "channels_change_pct": _pct_change(cur_channels, prev_channels),
        "time_saved_hours": cur_saved,
        "prev_time_saved_hours": prev_saved,
        "time_saved_change_pct": _pct_change(cur_saved, prev_saved),
    }


# ---------------------------------------------------------------------------
# GET /shopsync/analytics/by-channel
# ---------------------------------------------------------------------------


@router.get("/analytics/by-channel")
@cache(ttl=300, key_prefix="shopsync-analytics-by-channel")
async def analytics_by_channel(
    request: Request,
    response: Response,
    user: CurrentUser,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """Per-channel stats: publish count, success rate."""
    sb = get_supabase()
    now = datetime.now(UTC)

    range_start = start or _month_range(now)[0]
    range_end = end or _month_range(now)[1]

    products = _fetch_products_in_range(sb, user.id, range_start, range_end)

    channel_total: Counter[str] = Counter()
    channel_published: Counter[str] = Counter()

    for p in products:
        for ch in p.get("channels_generated", []):
            channel_total[ch] += 1
            if p.get("status") == "published":
                channel_published[ch] += 1

    channels = []
    for ch in sorted(channel_total):
        total = channel_total[ch]
        published = channel_published[ch]
        channels.append(
            {
                "channel": ch,
                "total": total,
                "published": published,
                "success_rate": (
                    round(published / total * 100, 1) if total else 0
                ),
            }
        )

    return {"channels": channels, "start": range_start, "end": range_end}


# ---------------------------------------------------------------------------
# GET /shopsync/analytics/top-products
# ---------------------------------------------------------------------------


@router.get("/analytics/top-products")
@cache(ttl=300, key_prefix="shopsync-analytics-top-products")
async def analytics_top_products(
    request: Request,
    response: Response,
    user: CurrentUser,
    limit: int = 10,
) -> dict:
    """Top products by number of channels published."""
    sb = get_supabase()
    products = (
        sb.table("shopsync_products")
        .select("*")
        .eq("user_id", user.id)
        .execute()
        .data
    )

    scored = [
        {
            "id": p["id"],
            "product_name": p.get("product_name", ""),
            "price": p.get("price", 0),
            "status": p.get("status", ""),
            "channels_generated": p.get("channels_generated", []),
            "channel_count": len(p.get("channels_generated", [])),
        }
        for p in products
    ]
    scored.sort(key=lambda x: x["channel_count"], reverse=True)

    return {"products": scored[:limit]}


# ---------------------------------------------------------------------------
# GET /shopsync/analytics/time-saved
# ---------------------------------------------------------------------------


@router.get("/analytics/time-saved")
@cache(ttl=300, key_prefix="shopsync-analytics-time-saved")
async def analytics_time_saved(
    request: Request,
    response: Response,
    user: CurrentUser,
    period: str = "daily",
    days: int = 30,
) -> dict:
    """Time-series time-saved data for charts.

    period: daily | weekly | monthly
    days: lookback window (default 30)
    """
    if period not in ("daily", "weekly", "monthly"):
        raise HTTPException(
            status_code=400,
            detail="period must be daily, weekly, or monthly",
        )
    if days < 1 or days > 365:
        raise HTTPException(
            status_code=400, detail="days must be 1-365",
        )

    sb = get_supabase()
    now = datetime.now(UTC)
    since = (now - timedelta(days=days)).isoformat()

    products = _fetch_products_in_range(
        sb, user.id, since, now.isoformat(),
    )

    # Bucket by date key
    buckets: dict[str, int] = {}
    for p in products:
        created = p.get("created_at", "")[:10]  # YYYY-MM-DD
        if not created:
            continue
        if period == "monthly":
            key = created[:7]  # YYYY-MM
        elif period == "weekly":
            dt = datetime.fromisoformat(created)
            week_start = dt - timedelta(days=dt.weekday())
            key = week_start.strftime("%Y-%m-%d")
        else:
            key = created
        buckets[key] = buckets.get(key, 0) + 1

    series = [
        {
            "period": k,
            "products": v,
            "manual_hours": round(v * _MANUAL_HOURS_PER_PRODUCT, 1),
            "shopsync_hours": round(v * _SHOPSYNC_HOURS_PER_PRODUCT, 1),
            "saved_hours": round(v * _SAVED_HOURS_PER_PRODUCT, 1),
        }
        for k, v in sorted(buckets.items())
    ]

    total_products = sum(buckets.values())
    return {
        "period": period,
        "days": days,
        "total_products": total_products,
        "total_saved_hours": round(
            total_products * _SAVED_HOURS_PER_PRODUCT, 1,
        ),
        "series": series,
    }
