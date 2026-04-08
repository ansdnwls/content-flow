"""Worker for ShopSync CSV bulk import — parses CSV and runs ProductBomb per row."""
from __future__ import annotations

import asyncio
import csv
import io
from uuid import uuid4

from app.core.db import get_supabase
from app.workers.celery_app import celery_app

_REQUIRED_COLUMNS = {"name", "price", "category", "image_url"}
_MAX_ROWS = 1000


def _parse_csv(raw: str) -> tuple[list[dict], str | None]:
    """Parse CSV text and return (rows, error).

    Each row is normalised to: name, price, category, image_url, description.
    Returns an error string if the CSV is invalid.
    """
    reader = csv.DictReader(io.StringIO(raw))
    if reader.fieldnames is None:
        return [], "Empty or invalid CSV"

    headers = {h.strip().lower() for h in reader.fieldnames}
    missing = _REQUIRED_COLUMNS - headers
    if missing:
        return [], f"Missing required columns: {', '.join(sorted(missing))}"

    rows: list[dict] = []
    for row in reader:
        normalised = {k.strip().lower(): v.strip() for k, v in row.items()}
        try:
            price = int(normalised["price"])
        except (ValueError, KeyError):
            price = 0
        rows.append(
            {
                "name": normalised.get("name", ""),
                "price": price,
                "category": normalised.get("category", ""),
                "image_url": normalised.get("image_url", ""),
                "description": normalised.get("description", ""),
            }
        )

    if not rows:
        return [], "CSV file has no data rows"

    if len(rows) > _MAX_ROWS:
        return [], f"Too many rows ({len(rows)}). Maximum is {_MAX_ROWS}"

    return rows, None


async def _run_bulk_import(job_id: str, csv_text: str, user_id: str) -> None:
    """Execute the bulk import: parse CSV, run ProductBomb per row."""
    from app.services.product_bomb import generate_product_bomb

    sb = get_supabase()

    rows, parse_error = _parse_csv(csv_text)
    if parse_error:
        sb.table("shopsync_bulk_jobs").update(
            {"status": "failed", "error": parse_error},
        ).eq("id", job_id).execute()
        return

    sb.table("shopsync_bulk_jobs").update(
        {"status": "processing", "total_rows": len(rows)},
    ).eq("id", job_id).execute()

    succeeded = 0
    failed = 0
    results: list[dict] = []

    for idx, row in enumerate(rows):
        product_id = str(uuid4())
        try:
            image_urls = [row["image_url"]] if row["image_url"] else []
            bomb_result = await generate_product_bomb(
                product_images=[],
                product_name=row["name"],
                price=row["price"],
                category=row["category"],
                image_urls=image_urls,
                auto_publish=False,
                user_id=user_id,
            )
            record = {
                "id": product_id,
                "user_id": user_id,
                "product_name": row["name"],
                "price": row["price"],
                "category": row["category"],
                "image_urls": image_urls,
                "target_platforms": list(bomb_result.channels_generated),
                "channels_generated": bomb_result.channels_generated,
                "status": "generated",
            }
            sb.table("shopsync_products").insert(record).execute()
            succeeded += 1
            results.append(
                {"index": idx, "status": "created", "product_id": product_id}
            )
        except Exception as exc:
            failed += 1
            results.append(
                {"index": idx, "status": "failed", "error": str(exc)}
            )

    sb.table("shopsync_bulk_jobs").update(
        {
            "status": "completed",
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        },
    ).eq("id", job_id).execute()


@celery_app.task(name="contentflow.shopsync_bulk_import")
def shopsync_bulk_import_task(job_id: str, csv_text: str, user_id: str) -> None:
    asyncio.run(_run_bulk_import(job_id, csv_text, user_id))
