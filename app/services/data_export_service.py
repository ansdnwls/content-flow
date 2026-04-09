"""User data export packaging, status tracking, and signed download URLs."""

from __future__ import annotations

import csv
import json
import tempfile
import zipfile
from datetime import UTC, datetime, timedelta
from html import escape
from io import StringIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import jwt

from app.config import get_settings
from app.core.db import get_supabase

try:
    import pyzipper
except ImportError:  # pragma: no cover - exercised when encryption is requested without dependency
    pyzipper = None

EXPORT_LINK_TTL_HOURS = 24
EXPORT_ROOT = Path(tempfile.gettempdir()) / "contentflow-exports"


def now_utc() -> datetime:
    return datetime.now(UTC)


def _ensure_export_root() -> Path:
    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
    return EXPORT_ROOT


def _export_zip_path(export_id: str) -> Path:
    return _ensure_export_root() / f"{export_id}.zip"


def _export_manifest_path(export_id: str) -> Path:
    return _ensure_export_root() / f"{export_id}.json"


def _sanitize_account(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if "token" not in key.lower()
    }


def _serialize_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _serialize_audit_log_csv(rows: list[dict[str, Any]]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["created_at", "action", "resource", "ip", "metadata"],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({
            "created_at": row.get("created_at"),
            "action": row.get("action"),
            "resource": row.get("resource"),
            "ip": row.get("ip"),
            "metadata": _serialize_json(row.get("metadata", {})),
        })
    return buffer.getvalue()


def _render_summary_html(
    bundle: dict[str, Any],
    summary: dict[str, int],
    metadata: dict[str, Any],
) -> str:
    profile = bundle["profile"]
    rows = "".join(
        (
            f"<tr><th>{escape(label)}</th><td>{count}</td></tr>"
            for label, count in (
                ("Posts", summary["posts"]),
                ("Videos", summary["videos"]),
                ("Accounts", summary["accounts"]),
                ("Analytics snapshots", summary["analytics"]),
                ("Notifications", summary["notifications"]),
                ("Audit log entries", summary["audit_logs"]),
            )
        ),
    )
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>ContentFlow Data Export</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }}
      table {{ border-collapse: collapse; width: 100%; max-width: 640px; }}
      th, td {{ border: 1px solid #d1d5db; padding: 10px 12px; text-align: left; }}
      th {{ background: #f3f4f6; }}
      h1 {{ margin-bottom: 8px; }}
      p {{ max-width: 720px; line-height: 1.6; }}
    </style>
  </head>
  <body>
    <h1>ContentFlow Data Export</h1>
    <p>This export was generated for {escape(str(profile.get("email", "unknown")))}.</p>
    <p>
      Export ID: {escape(metadata["export_id"])}<br>
      Requested at: {escape(metadata["requested_at"])}<br>
      Expires at: {escape(metadata["expires_at"])}
    </p>
    <table>
      <thead>
        <tr><th>Dataset</th><th>Count</th></tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </body>
</html>
"""


def collect_user_export_data(user_id: str, *, sb=None) -> dict[str, Any]:
    sb = sb or get_supabase()
    profile = (
        sb.table("users")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    posts = sb.table("posts").select("*").eq("owner_id", user_id).execute().data
    videos = sb.table("video_jobs").select("*").eq("owner_id", user_id).execute().data
    accounts = (
        sb.table("social_accounts")
        .select("*")
        .eq("owner_id", user_id)
        .execute()
        .data
    )
    analytics = (
        sb.table("analytics_snapshots")
        .select("*")
        .eq("owner_id", user_id)
        .execute()
        .data
    )
    notifications = (
        sb.table("notifications")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )
    audit_logs = (
        sb.table("audit_logs")
        .select("action, resource, created_at, ip, metadata")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )
    return {
        "profile": profile,
        "posts": posts,
        "videos": videos,
        "accounts": [_sanitize_account(row) for row in accounts],
        "analytics": analytics,
        "notifications": notifications,
        "audit_logs": audit_logs,
    }


def build_export_summary(bundle: dict[str, Any]) -> dict[str, int]:
    return {
        "posts": len(bundle["posts"]),
        "videos": len(bundle["videos"]),
        "accounts": len(bundle["accounts"]),
        "analytics": len(bundle["analytics"]),
        "notifications": len(bundle["notifications"]),
        "audit_logs": len(bundle["audit_logs"]),
    }


def _build_download_token(export_id: str, user_id: str, expires_at: str) -> str:
    expires_at_dt = datetime.fromisoformat(expires_at)
    payload = {
        "sub": user_id,
        "export_id": export_id,
        "exp": int(expires_at_dt.timestamp()),
        "scope": "privacy_export_download",
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


def build_download_url(export_id: str, user_id: str, expires_at: str, *, base_url: str) -> str:
    token = _build_download_token(export_id, user_id, expires_at)
    return (
        f"{base_url.rstrip('/')}/api/v1/privacy/export/{export_id}/download?token={token}"
    )


def _write_zip_bundle(
    bundle: dict[str, Any],
    metadata: dict[str, Any],
    password: str | None,
) -> Path:
    zip_path = _export_zip_path(metadata["export_id"])
    summary = build_export_summary(bundle)
    summary_html = _render_summary_html(bundle, summary, metadata)
    json_options = {"ensure_ascii": False, "indent": 2, "sort_keys": True}

    if password:
        if pyzipper is None:
            raise RuntimeError("pyzipper is required for encrypted exports")
        with pyzipper.AESZipFile(
            zip_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            encryption=pyzipper.WZ_AES,
        ) as archive:
            archive.setpassword(password.encode("utf-8"))
            _write_zip_entries(archive, bundle, summary_html, json_options)
    else:
        with zipfile.ZipFile(
            zip_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            _write_zip_entries(archive, bundle, summary_html, json_options)

    return zip_path


def _write_zip_entries(
    archive: zipfile.ZipFile,
    bundle: dict[str, Any],
    summary_html: str,
    json_options: dict[str, Any],
) -> None:
    archive.writestr("profile.json", json.dumps(bundle["profile"], **json_options))
    archive.writestr("accounts.json", json.dumps(bundle["accounts"], **json_options))
    archive.writestr("analytics.json", json.dumps(bundle["analytics"], **json_options))
    archive.writestr("notifications.json", json.dumps(bundle["notifications"], **json_options))
    archive.writestr("audit_log.csv", _serialize_audit_log_csv(bundle["audit_logs"]))
    archive.writestr("summary.html", summary_html)
    archive.writestr("posts/", "")
    archive.writestr("videos/", "")
    for post in bundle["posts"]:
        archive.writestr(
            f"posts/{post['id']}.json",
            json.dumps(post, **json_options),
        )
    for video in bundle["videos"]:
        archive.writestr(
            f"videos/{video['id']}.json",
            json.dumps(video, **json_options),
        )


def _write_manifest(metadata: dict[str, Any]) -> dict[str, Any]:
    path = _export_manifest_path(metadata["export_id"])
    path.write_text(_serialize_json(metadata), encoding="utf-8")
    return metadata


def load_export_manifest(export_id: str) -> dict[str, Any] | None:
    path = _export_manifest_path(export_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def delete_export_artifacts(export_id: str) -> None:
    for path in (_export_zip_path(export_id), _export_manifest_path(export_id)):
        if path.exists():
            path.unlink()


def purge_expired_export(export_id: str) -> bool:
    manifest = load_export_manifest(export_id)
    if not manifest:
        return False
    if datetime.fromisoformat(manifest["expires_at"]) > now_utc():
        return False
    delete_export_artifacts(export_id)
    return True


def create_export_request(
    user_id: str,
    *,
    export_format: str,
    encrypted: bool,
    sb=None,
) -> dict[str, Any]:
    requested_at = now_utc()
    expires_at = requested_at + timedelta(hours=EXPORT_LINK_TTL_HOURS)
    bundle = collect_user_export_data(user_id, sb=sb)
    export_id = f"exp_{uuid4().hex[:12]}"
    metadata = {
        "export_id": export_id,
        "user_id": user_id,
        "status": "queued",
        "format": export_format,
        "encrypted": encrypted,
        "requested_at": requested_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "summary": build_export_summary(bundle),
        "file_path": None,
        "completed_at": None,
        "html_summary_included": True,
    }
    return _write_manifest(metadata)


def build_export_archive(
    export_id: str,
    user_id: str,
    *,
    export_format: str,
    password: str | None = None,
    sb=None,
) -> dict[str, Any]:
    manifest = load_export_manifest(export_id)
    if manifest is None:
        requested_at = now_utc()
        manifest = _write_manifest({
            "export_id": export_id,
            "user_id": user_id,
            "status": "queued",
            "format": export_format,
            "encrypted": bool(password),
            "requested_at": requested_at.isoformat(),
            "expires_at": (requested_at + timedelta(hours=EXPORT_LINK_TTL_HOURS)).isoformat(),
            "summary": {},
            "file_path": None,
            "completed_at": None,
            "html_summary_included": True,
        })
    bundle = collect_user_export_data(user_id, sb=sb)
    zip_path = _write_zip_bundle(bundle, manifest, password)
    manifest.update({
        "status": "ready",
        "encrypted": bool(password),
        "file_path": str(zip_path),
        "completed_at": now_utc().isoformat(),
        "summary": build_export_summary(bundle),
    })
    return _write_manifest(manifest)


def mark_export_failed(export_id: str, *, error: str) -> dict[str, Any] | None:
    manifest = load_export_manifest(export_id)
    if manifest is None:
        return None
    manifest.update({
        "status": "failed",
        "error": error,
        "completed_at": now_utc().isoformat(),
    })
    return _write_manifest(manifest)


def get_export_status(
    export_id: str,
    *,
    user_id: str,
    base_url: str,
) -> dict[str, Any]:
    if purge_expired_export(export_id):
        msg = "Export link has expired"
        raise ValueError(msg)

    manifest = load_export_manifest(export_id)
    if manifest is None:
        raise FileNotFoundError(export_id)
    if manifest["user_id"] != user_id:
        raise PermissionError(export_id)

    status = dict(manifest)
    if status["status"] == "ready" and status.get("file_path"):
        status["download_url"] = build_download_url(
            export_id,
            user_id,
            status["expires_at"],
            base_url=base_url,
        )
    else:
        status["download_url"] = None
    return status


def validate_download_token(export_id: str, user_id: str, token: str) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        get_settings().jwt_secret,
        algorithms=["HS256"],
    )
    if payload.get("scope") != "privacy_export_download":
        raise PermissionError("invalid scope")
    if payload.get("export_id") != export_id or payload.get("sub") != user_id:
        raise PermissionError("token mismatch")
    return payload
