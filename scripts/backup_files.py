"""Download Supabase Storage buckets for disaster recovery."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts._backup_common import (
    BackupError,
    create_supabase_client,
    ensure_output_dir,
    utc_now,
    write_json,
)


@dataclass(frozen=True)
class StorageBackupConfig:
    output_dir: Path | None
    buckets: list[str] | None
    page_size: int
    project_url: str | None
    service_role_key: str | None


def _bucket_name(bucket: Any) -> str:
    if isinstance(bucket, dict):
        return str(bucket["name"])
    return str(bucket.name)


def iter_bucket_objects(bucket_proxy: Any, *, page_size: int, prefix: str = ""):
    cursor: str | None = None
    while True:
        options: dict[str, Any] = {
            "limit": page_size,
            "prefix": prefix,
            "with_delimiter": True,
        }
        if cursor:
            options["cursor"] = cursor
        page = bucket_proxy.list_v2(options)
        for folder in page.folders:
            yield from iter_bucket_objects(bucket_proxy, page_size=page_size, prefix=folder.key)
        for obj in page.objects:
            yield obj.key or f"{prefix.rstrip('/')}/{obj.name}".lstrip("/")
        if not page.hasNext:
            break
        cursor = page.nextCursor


def backup_storage(config: StorageBackupConfig, *, client: Any | None = None) -> dict[str, Any]:
    output_dir = ensure_output_dir(config.output_dir)
    sb = client or create_supabase_client(
        url=config.project_url,
        service_role_key=config.service_role_key,
    )

    available_buckets = [_bucket_name(bucket) for bucket in sb.storage.list_buckets()]
    bucket_names = config.buckets or available_buckets
    missing = sorted(set(bucket_names) - set(available_buckets))
    if missing:
        raise BackupError(f"Unknown storage buckets: {', '.join(missing)}")

    storage_root = output_dir / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)

    bucket_entries = []
    for bucket_name in bucket_names:
        proxy = sb.storage.from_(bucket_name)
        object_entries = []
        for object_key in iter_bucket_objects(proxy, page_size=config.page_size):
            content = proxy.download(object_key)
            destination = storage_root / bucket_name / Path(object_key)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            object_entries.append(
                {
                    "key": object_key,
                    "size_bytes": len(content),
                    "file": destination.relative_to(output_dir).as_posix(),
                }
            )
        bucket_entries.append(
            {
                "name": bucket_name,
                "object_count": len(object_entries),
                "objects": object_entries,
            }
        )

    manifest = {
        "backup_type": "supabase-storage-files",
        "format_version": 1,
        "created_at": utc_now().isoformat(),
        "bucket_count": len(bucket_entries),
        "buckets": bucket_entries,
    }
    write_json(output_dir / "storage_manifest.json", manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--buckets", nargs="*", default=None)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--project-url", default=None)
    parser.add_argument("--service-role-key", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = backup_storage(
            StorageBackupConfig(
                output_dir=args.output_dir,
                buckets=args.buckets,
                page_size=args.page_size,
                project_url=args.project_url,
                service_role_key=args.service_role_key,
            )
        )
    except BackupError as exc:
        print(f"Storage backup failed: {exc}", file=sys.stderr)
        return 1

    print(f"Storage backup created with {manifest['bucket_count']} buckets")
    for bucket in manifest["buckets"]:
        print(f"- {bucket['name']}: {bucket['object_count']} objects")
    return 0


if __name__ == "__main__":
    sys.exit(main())
