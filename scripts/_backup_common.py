"""Common helpers for Supabase backup and restore scripts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from supabase import Client, create_client

DEFAULT_DB_TABLES: tuple[str, ...] = (
    "users",
    "workspaces",
    "workspace_members",
    "api_keys",
    "social_accounts",
    "posts",
    "post_deliveries",
    "video_jobs",
    "schedules",
    "comments",
    "bombs",
    "webhooks",
    "webhook_deliveries",
    "analytics_snapshots",
    "audit_logs",
    "payments",
    "subscription_events",
    "notification_preferences",
    "consents",
    "dpa_signatures",
    "data_breaches",
    "deletion_requests",
    "shopsync_products",
    "shopsync_bulk_jobs",
    "ytboost_subscriptions",
    "ytboost_shorts",
    "ytboost_channel_tones",
)

DEFAULT_PAGE_SIZE = 1000
DEFAULT_GPG_PASSPHRASE_ENV = "BACKUP_GPG_PASSPHRASE"


class BackupError(RuntimeError):
    """Raised when a backup or restore operation cannot continue safely."""


@dataclass(frozen=True)
class SupabaseCredentials:
    url: str
    service_role_key: str


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_timestamp_slug() -> str:
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def ensure_output_dir(output_dir: Path | None, *, root: str = "backups") -> Path:
    target = output_dir or Path(root) / utc_timestamp_slug()
    target.mkdir(parents=True, exist_ok=True)
    return target


def resolve_supabase_credentials(
    *,
    url: str | None = None,
    service_role_key: str | None = None,
) -> SupabaseCredentials:
    resolved_url = url or os.getenv("SUPABASE_URL")
    resolved_key = service_role_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not resolved_url or not resolved_key:
        raise BackupError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return SupabaseCredentials(url=resolved_url, service_role_key=resolved_key)


def create_supabase_client(
    *,
    url: str | None = None,
    service_role_key: str | None = None,
) -> Client:
    creds = resolve_supabase_credentials(url=url, service_role_key=service_role_key)
    return create_client(creds.url, creds.service_role_key)


def parse_tables(tables: Iterable[str] | None) -> list[str]:
    if not tables:
        return list(DEFAULT_DB_TABLES)
    cleaned = [table.strip() for table in tables if table.strip()]
    if not cleaned:
        raise BackupError("At least one table must be provided")
    return cleaned


def fetch_all_rows(
    client: Any,
    table_name: str,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = (
            client.table(table_name)
            .select("*")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = list(response.data or [])
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BackupError(f"Invalid JSON file: {path}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_passphrase(
    *,
    passphrase: str | None = None,
    passphrase_env: str = DEFAULT_GPG_PASSPHRASE_ENV,
) -> str:
    resolved = passphrase or os.getenv(passphrase_env)
    if not resolved:
        raise BackupError(
            f"GPG passphrase is required. Set --passphrase or {passphrase_env}."
        )
    return resolved


def _gpg_base_command() -> list[str]:
    if shutil.which("gpg") is None:
        raise BackupError("gpg is required for encrypted backups but was not found in PATH")
    return [
        "gpg",
        "--batch",
        "--yes",
        "--pinentry-mode",
        "loopback",
        "--passphrase-fd",
        "0",
    ]


def encrypt_file(path: Path, *, passphrase: str, remove_source: bool = True) -> Path:
    output_path = path.with_suffix(path.suffix + ".gpg")
    completed = subprocess.run(
        [
            *_gpg_base_command(),
            "--symmetric",
            "--cipher-algo",
            "AES256",
            "--output",
            str(output_path),
            str(path),
        ],
        input=passphrase.encode("utf-8"),
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="ignore").strip()
        raise BackupError(stderr or "gpg encryption failed")
    if remove_source and path.exists():
        path.unlink()
    return output_path


def decrypt_file_to_bytes(path: Path, *, passphrase: str) -> bytes:
    completed = subprocess.run(
        [
            *_gpg_base_command(),
            "--decrypt",
            str(path),
        ],
        input=passphrase.encode("utf-8"),
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="ignore").strip()
        raise BackupError(stderr or "gpg decryption failed")
    return completed.stdout


def load_json_file(path: Path, *, passphrase: str | None = None) -> Any:
    if path.suffix == ".gpg":
        if not passphrase:
            raise BackupError(f"Passphrase required to read encrypted file: {path}")
        try:
            return json.loads(decrypt_file_to_bytes(path, passphrase=passphrase).decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise BackupError(f"Invalid decrypted JSON file: {path}") from exc
    return read_json(path)


def chunked(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def prompt_for_confirmation(prompt: str, *, token: str = "RESTORE") -> None:
    response = input(f"{prompt}\nType {token} to continue: ").strip()
    if response != token:
        raise BackupError("Restore aborted by operator")
