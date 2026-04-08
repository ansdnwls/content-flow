"""Restore Supabase table backups created by scripts.backup_db."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts._backup_common import (
    DEFAULT_GPG_PASSPHRASE_ENV,
    BackupError,
    chunked,
    create_supabase_client,
    load_json_file,
    parse_tables,
    prompt_for_confirmation,
    resolve_passphrase,
    resolve_supabase_credentials,
    sha256_file,
)


@dataclass(frozen=True)
class RestoreConfig:
    backup_dir: Path
    tables: list[str] | None
    dry_run: bool
    yes: bool
    batch_size: int
    passphrase: str | None
    passphrase_env: str
    project_url: str | None
    service_role_key: str | None


def load_manifest(backup_dir: Path) -> dict[str, Any]:
    manifest_path = backup_dir / "db_manifest.json"
    if not manifest_path.exists():
        raise BackupError(f"Backup manifest not found: {manifest_path}")
    manifest = load_json_file(manifest_path)
    if manifest.get("backup_type") != "supabase-table-json":
        raise BackupError(f"Unsupported backup type: {manifest.get('backup_type')}")
    tables = manifest.get("tables")
    if not isinstance(tables, list) or not tables:
        raise BackupError("Backup manifest does not contain any tables")
    return manifest


def build_restore_plan(
    manifest: dict[str, Any],
    selected_tables: list[str] | None,
) -> list[dict[str, Any]]:
    entries = manifest["tables"]
    if not selected_tables:
        return list(entries)
    selected = set(selected_tables)
    plan = [entry for entry in entries if entry["name"] in selected]
    if not plan:
        joined = ", ".join(selected_tables)
        raise BackupError(f"None of the requested tables were found in the manifest: {joined}")
    return plan


def load_table_payload(
    backup_dir: Path,
    entry: dict[str, Any],
    *,
    passphrase: str | None,
) -> dict[str, Any]:
    payload_path = backup_dir / entry["file"]
    if not payload_path.exists():
        raise BackupError(f"Backup file missing: {payload_path}")
    expected_hash = entry.get("sha256")
    actual_hash = sha256_file(payload_path)
    if expected_hash and expected_hash != actual_hash:
        raise BackupError(f"Checksum mismatch for {payload_path}")
    payload = load_json_file(payload_path, passphrase=passphrase)
    if payload.get("table") != entry["name"]:
        raise BackupError(f"Backup file/table mismatch for {entry['name']}")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise BackupError(f"Backup file rows are invalid for {entry['name']}")
    return payload


def restore_rows(
    client: Any,
    *,
    table_name: str,
    rows: list[dict[str, Any]],
    batch_size: int,
) -> int:
    restored = 0
    for batch in chunked(rows, batch_size):
        if all(row.get("id") is not None for row in batch):
            client.table(table_name).upsert(batch, on_conflict="id").execute()
        else:
            client.table(table_name).insert(batch).execute()
        restored += len(batch)
    return restored


def restore_database(config: RestoreConfig, *, client: Any | None = None) -> list[dict[str, Any]]:
    manifest = load_manifest(config.backup_dir)
    plan = build_restore_plan(manifest, config.tables)
    requires_passphrase = any(entry.get("encrypted") for entry in plan)
    passphrase = (
        resolve_passphrase(passphrase=config.passphrase, passphrase_env=config.passphrase_env)
        if requires_passphrase
        else None
    )

    preview = []
    for entry in plan:
        payload = load_table_payload(config.backup_dir, entry, passphrase=passphrase)
        preview.append({"name": entry["name"], "row_count": len(payload["rows"])})

    if config.dry_run:
        return preview

    if not config.yes:
        prompt_for_confirmation(
            "Restore will upsert rows into Supabase using primary key `id` where available."
        )

    creds = resolve_supabase_credentials(
        url=config.project_url,
        service_role_key=config.service_role_key,
    )
    sb = client or create_supabase_client(url=creds.url, service_role_key=creds.service_role_key)

    results = []
    for entry in plan:
        payload = load_table_payload(config.backup_dir, entry, passphrase=passphrase)
        restored = restore_rows(
            sb,
            table_name=entry["name"],
            rows=payload["rows"],
            batch_size=config.batch_size,
        )
        results.append({"name": entry["name"], "row_count": restored})
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup_dir", type=Path)
    parser.add_argument("--tables", nargs="*", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--passphrase", default=None)
    parser.add_argument("--passphrase-env", default=DEFAULT_GPG_PASSPHRASE_ENV)
    parser.add_argument("--project-url", default=None)
    parser.add_argument("--service-role-key", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        selected_tables = parse_tables(args.tables) if args.tables is not None else None
        results = restore_database(
            RestoreConfig(
                backup_dir=args.backup_dir,
                tables=selected_tables,
                dry_run=args.dry_run,
                yes=args.yes,
                batch_size=args.batch_size,
                passphrase=args.passphrase,
                passphrase_env=args.passphrase_env,
                project_url=args.project_url,
                service_role_key=args.service_role_key,
            )
        )
    except BackupError as exc:
        print(f"Restore failed: {exc}", file=sys.stderr)
        return 1

    prefix = "Would restore" if args.dry_run else "Restored"
    for result in results:
        print(f"{prefix} {result['name']}: {result['row_count']} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
