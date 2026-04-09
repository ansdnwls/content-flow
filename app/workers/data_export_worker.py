"""Celery task for GDPR data export packaging and user notifications."""

from __future__ import annotations

import asyncio

from app.config import get_settings
from app.core.db import get_supabase
from app.services.data_export_service import (
    build_download_url,
    build_export_archive,
    load_export_manifest,
    mark_export_failed,
)
from app.services.email_service import send_email
from app.services.notification_service import create_notification
from app.workers.celery_app import celery_app


async def run_user_data_export(
    export_id: str,
    user_id: str,
    export_format: str,
    password: str | None = None,
) -> dict:
    sb = get_supabase()
    manifest = load_export_manifest(export_id)
    if manifest is None:
        msg = f"Unknown export request: {export_id}"
        raise FileNotFoundError(msg)

    try:
        manifest = build_export_archive(
            export_id,
            user_id,
            export_format=export_format,
            password=password,
            sb=sb,
        )

        user = (
            sb.table("users")
            .select("email, full_name")
            .eq("id", user_id)
            .maybe_single()
            .execute()
            .data
        ) or {}

        download_url = build_download_url(
            export_id,
            user_id,
            manifest["expires_at"],
            base_url=get_settings().oauth_redirect_base_url,
        )

        try:
            create_notification(
                user_id=user_id,
                type="export_ready",
                title="Data export ready",
                body="Your data export is ready for download for the next 24 hours.",
                link_url=f"/privacy/export/{export_id}",
            )
        except Exception:
            pass

        if user.get("email"):
            await send_email(
                user_id=user_id,
                to=user["email"],
                subject="Your ContentFlow data export is ready",
                html=(
                    "<p>Your data export is ready.</p>"
                    f"<p><a href=\"{download_url}\">Download export</a></p>"
                    f"<p>This link expires at {manifest['expires_at']}.</p>"
                ),
            )
        return manifest
    except Exception as exc:
        mark_export_failed(export_id, error=str(exc))
        raise


@celery_app.task(name="contentflow.generate_user_data_export")
def generate_user_data_export_task(
    export_id: str,
    user_id: str,
    export_format: str,
    password: str | None = None,
) -> dict:
    return asyncio.run(run_user_data_export(export_id, user_id, export_format, password))

