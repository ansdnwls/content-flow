"""Create JSON backups for important Supabase tables."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts._backup_common import (
    DEFAULT_GPG_PASSPHRASE_ENV,
    DEFAULT_PAGE_SIZE,
    BackupError,
    create_supabase_client,
    encrypt_file,
    ensure_output_dir,
    fetch_all_rows,
    parse_tables,
    resolve_passphrase,
    resolve_supabase_credentials,
    sha256_file,
    utc_now,
    write_json,
)


@dataclass(frozen=True)
class BackupConfig:
    output_dir: Path | None
    tables: list[str]
    page_size: int
    encrypt: bool
    passphrase: str | None
    passphrase_env: str
    project_url: str | None
    service_role_key: str | None


def export_table(
    client: Any,
    *,
    table_name: str,
    output_dir: Path,
    page_size: int,
    encrypt: bool,
    passphrase: str | None,
) -> dict[str, Any]:
    table_dir = output_dir / "db"
    table_dir.mkdir(parents=True, exist_ok=True)

    rows = fetch_all_rows(client, table_name, page_size=page_size)
    payload = {
        "table": table_name,
        "row_count": len(rows),
        "exported_at": utc_now().isoformat(),
        "rows": rows,
    }
    file_path = table_dir / f"{table_name}.json"
    write_json(file_path, payload)

    stored_path = file_path
    if encrypt:
        if not passphrase:
            raise BackupError("Encrypted backup requested without a passphrase")
        stored_path = encrypt_file(file_path, passphrase=passphrase)

    return {
        "name": table_name,
        "row_count": len(rows),
        "file": stored_path.relative_to(output_dir).as_posix(),
        "sha256": sha256_file(stored_path),
        "encrypted": encrypt,
    }


def backup_database(config: BackupConfig, *, client: Any | None = None) -> dict[str, Any]:
    output_dir = ensure_output_dir(config.output_dir)
    creds = resolve_supabase_credentials(
        url=config.project_url,
        service_role_key=config.service_role_key,
    )
    sb = client or create_supabase_client(url=creds.url, service_role_key=creds.service_role_key)
    passphrase = (
        resolve_passphrase(passphrase=config.passphrase, passphrase_env=config.passphrase_env)
        if config.encrypt
        else None
    )

    table_entries = [
        export_table(
            sb,
            table_name=table_name,
            output_dir=output_dir,
            page_size=config.page_size,
            encrypt=config.encrypt,
            passphrase=passphrase,
        )
        for table_name in config.tables
    ]

    manifest = {
        "backup_type": "supabase-table-json",
        "format_version": 1,
        "created_at": utc_now().isoformat(),
        "source": {"supabase_url": creds.url},
        "table_count": len(table_entries),
        "page_size": config.page_size,
        "encrypted": config.encrypt,
        "tables": table_entries,
    }
    write_json(output_dir / "db_manifest.json", manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--tables", nargs="*", default=None)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--encrypt", action="store_true")
    parser.add_argument("--passphrase", default=None)
    parser.add_argument("--passphrase-env", default=DEFAULT_GPG_PASSPHRASE_ENV)
    parser.add_argument("--project-url", default=None)
    parser.add_argument("--service-role-key", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = backup_database(
            BackupConfig(
                output_dir=args.output_dir,
                tables=parse_tables(args.tables),
                page_size=args.page_size,
                encrypt=args.encrypt,
                passphrase=args.passphrase,
                passphrase_env=args.passphrase_env,
                project_url=args.project_url,
                service_role_key=args.service_role_key,
            )
        )
    except BackupError as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1

    print(f"Backup created at {args.output_dir or 'backups/<timestamp>'}")
    for table in manifest["tables"]:
        print(f"- {table['name']}: {table['row_count']} rows -> {table['file']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
