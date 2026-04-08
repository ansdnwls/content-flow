"""Async audit logging with sensitive-data masking."""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from typing import Any

from app.core.batch_processor import BatchWriter
from app.core.db import get_supabase
from app.core.pii_classifier import mask_dict, scrub_text

MASKED_FIELDS = re.compile(
    r"(password|secret|token|access_token|refresh_token|hashed_key|authorization)",
    re.IGNORECASE,
)

_WRITER: BatchWriter[dict[str, Any]] | None = None
_WRITER_LOCK = asyncio.Lock()


def mask_sensitive(data: dict[str, Any]) -> dict[str, Any]:
    """Return a recursively masked copy suitable for audit metadata."""
    masked = {}
    for key, value in data.items():
        if MASKED_FIELDS.search(key):
            masked[key] = "***"
        elif isinstance(value, str):
            masked[key] = scrub_text(mask_dict({key: value})[key])
        elif isinstance(value, dict):
            masked[key] = mask_sensitive(value)
        elif isinstance(value, list):
            masked[key] = [
                mask_sensitive(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            masked[key] = value
    return masked


def enqueue_audit_log(
    *,
    user_id: str,
    api_key_id: str | None = None,
    action: str,
    resource: str,
    ip: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a masked audit entry payload suitable for batch insertion."""
    return {
        "user_id": user_id,
        "api_key_id": api_key_id,
        "action": action,
        "resource": resource,
        "ip": ip,
        "user_agent": user_agent,
        "metadata": mask_sensitive(metadata) if metadata else {},
        "created_at": datetime.now(UTC).isoformat(),
    }


async def _write_audit_batch(batch: list[dict[str, Any]]) -> int:
    if not batch:
        return 0
    sb = get_supabase()
    sb.table("audit_logs").insert(batch).execute()
    return len(batch)


async def _get_writer() -> BatchWriter[dict[str, Any]]:
    global _WRITER
    async with _WRITER_LOCK:
        if _WRITER is None:
            _WRITER = BatchWriter(
                _write_audit_batch,
                flush_interval=1.0,
                batch_size=100,
            )
        return _WRITER


async def flush_audit_logs() -> int:
    """Flush queued audit entries to the database. Returns count flushed."""
    writer = await _get_writer()
    return await writer.flush()


async def record_audit(
    *,
    user_id: str,
    api_key_id: str | None = None,
    action: str,
    resource: str,
    ip: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Enqueue an audit log entry for batched persistence."""
    entry = enqueue_audit_log(
        user_id=user_id,
        api_key_id=api_key_id,
        action=action,
        resource=resource,
        ip=ip,
        user_agent=user_agent,
        metadata=metadata,
    )
    writer = await _get_writer()
    await writer.enqueue(entry)


async def reset_audit_writer() -> None:
    """Flush and reset the writer singleton. Useful for tests and shutdown."""
    global _WRITER
    if _WRITER is None:
        return
    try:
        await _WRITER.close()
    except Exception:
        pass
    _WRITER = None
