from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.fakes import FakeSupabase


def _seed_supabase() -> FakeSupabase:
    fake = FakeSupabase()
    fake.insert_row("users", {"id": "user-1", "email": "owner@example.com", "plan": "build"})
    fake.insert_row(
        "posts",
        {
            "id": "post-1",
            "owner_id": "user-1",
            "status": "published",
            "media_urls": ["https://cdn.example.com/video.mp4"],
        },
    )
    return fake


def test_backup_creation_with_mock_supabase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backup_db = importlib.import_module("scripts.backup_db")
    fake = _seed_supabase()
    monkeypatch.setattr(backup_db, "create_supabase_client", lambda **_kwargs: fake)

    manifest = backup_db.backup_database(
        backup_db.BackupConfig(
            output_dir=tmp_path,
            tables=["users", "posts"],
            page_size=100,
            encrypt=False,
            passphrase=None,
            passphrase_env="BACKUP_GPG_PASSPHRASE",
            project_url="https://example.supabase.co",
            service_role_key="service-role",
        )
    )

    assert manifest["table_count"] == 2
    assert (tmp_path / "db_manifest.json").exists()
    assert (tmp_path / "db" / "users.json").exists()
    assert (tmp_path / "db" / "posts.json").exists()


def test_backup_file_format_contains_metadata_and_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backup_db = importlib.import_module("scripts.backup_db")
    fake = _seed_supabase()
    monkeypatch.setattr(backup_db, "create_supabase_client", lambda **_kwargs: fake)

    backup_db.backup_database(
        backup_db.BackupConfig(
            output_dir=tmp_path,
            tables=["users"],
            page_size=100,
            encrypt=False,
            passphrase=None,
            passphrase_env="BACKUP_GPG_PASSPHRASE",
            project_url="https://example.supabase.co",
            service_role_key="service-role",
        )
    )

    payload = json.loads((tmp_path / "db" / "users.json").read_text(encoding="utf-8"))
    assert payload["table"] == "users"
    assert payload["row_count"] == 1
    assert payload["rows"][0]["email"] == "owner@example.com"
    assert "exported_at" in payload


def test_restore_dry_run_only_reports_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    backup_db = importlib.import_module("scripts.backup_db")
    restore_db = importlib.import_module("scripts.restore_db")
    fake = _seed_supabase()
    monkeypatch.setattr(backup_db, "create_supabase_client", lambda **_kwargs: fake)

    backup_db.backup_database(
        backup_db.BackupConfig(
            output_dir=tmp_path,
            tables=["users"],
            page_size=100,
            encrypt=False,
            passphrase=None,
            passphrase_env="BACKUP_GPG_PASSPHRASE",
            project_url="https://example.supabase.co",
            service_role_key="service-role",
        )
    )

    restore_target = FakeSupabase()
    monkeypatch.setattr(restore_db, "create_supabase_client", lambda **_kwargs: restore_target)
    exit_code = restore_db.main([str(tmp_path), "--dry-run"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Would restore users: 1 rows" in output
    assert restore_target.tables["users"] == []


def test_invalid_backup_file_is_rejected(tmp_path: Path) -> None:
    restore_db = importlib.import_module("scripts.restore_db")
    (tmp_path / "db").mkdir(parents=True)
    (tmp_path / "db_manifest.json").write_text(
        json.dumps(
            {
                "backup_type": "supabase-table-json",
                "tables": [
                    {
                        "name": "users",
                        "file": "db/users.json",
                        "sha256": "bad",
                        "encrypted": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "db" / "users.json").write_text("{not-json", encoding="utf-8")

    with pytest.raises(restore_db.BackupError):
        restore_db.restore_database(
            restore_db.RestoreConfig(
                backup_dir=tmp_path,
                tables=None,
                dry_run=True,
                yes=False,
                batch_size=100,
                passphrase=None,
                passphrase_env="BACKUP_GPG_PASSPHRASE",
                project_url=None,
                service_role_key=None,
            )
        )


def test_encryption_and_decryption_helpers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    common = importlib.import_module("scripts._backup_common")
    source = tmp_path / "users.json"
    source.write_text('{"table":"users","rows":[{"id":"user-1"}]}', encoding="utf-8")

    monkeypatch.setattr(common.shutil, "which", lambda _name: "gpg")

    def fake_run(command: list[str], **_kwargs):
        if "--symmetric" in command:
            output_path = Path(command[command.index("--output") + 1])
            input_path = Path(command[-1])
            output_path.write_bytes(b"ENC:" + input_path.read_bytes())
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        encrypted_path = Path(command[-1])
        raw = encrypted_path.read_bytes()
        return SimpleNamespace(returncode=0, stdout=raw.replace(b"ENC:", b"", 1), stderr=b"")

    monkeypatch.setattr(common.subprocess, "run", fake_run)

    encrypted_path = common.encrypt_file(source, passphrase="secret")
    payload = common.load_json_file(encrypted_path, passphrase="secret")

    assert encrypted_path.exists()
    assert source.exists() is False
    assert payload["table"] == "users"
    assert payload["rows"][0]["id"] == "user-1"


def test_partial_restore_only_restores_selected_tables(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backup_db = importlib.import_module("scripts.backup_db")
    restore_db = importlib.import_module("scripts.restore_db")
    fake = _seed_supabase()
    monkeypatch.setattr(backup_db, "create_supabase_client", lambda **_kwargs: fake)

    backup_db.backup_database(
        backup_db.BackupConfig(
            output_dir=tmp_path,
            tables=["users", "posts"],
            page_size=100,
            encrypt=False,
            passphrase=None,
            passphrase_env="BACKUP_GPG_PASSPHRASE",
            project_url="https://example.supabase.co",
            service_role_key="service-role",
        )
    )

    restore_target = FakeSupabase()
    monkeypatch.setattr(restore_db, "create_supabase_client", lambda **_kwargs: restore_target)
    results = restore_db.restore_database(
        restore_db.RestoreConfig(
            backup_dir=tmp_path,
            tables=["users"],
            dry_run=False,
            yes=True,
            batch_size=100,
            passphrase=None,
            passphrase_env="BACKUP_GPG_PASSPHRASE",
            project_url="https://example.supabase.co",
            service_role_key="service-role",
        )
    )

    assert results == [{"name": "users", "row_count": 1}]
    assert len(restore_target.tables["users"]) == 1
    assert restore_target.tables["posts"] == []
