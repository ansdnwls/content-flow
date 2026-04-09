from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import pyzipper
from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.main import app
from app.services.data_export_service import (
    build_export_archive,
    create_export_request,
)
from app.workers.data_export_worker import run_user_data_export
from tests.fakes import FakeSupabase


def _create_user(fake: FakeSupabase, email: str) -> tuple[str, str]:
    user_id = str(uuid4())
    fake.insert_row("users", {"id": user_id, "email": email, "plan": "build"})
    issued, record = build_api_key_record(user_id=uuid4(), name=email.split("@")[0])
    record["user_id"] = user_id
    fake.insert_row("api_keys", record)
    return user_id, issued.raw_key


def _seed_export_data(fake: FakeSupabase, user_id: str, *, posts: int = 2) -> None:
    for index in range(posts):
        fake.insert_row("posts", {
            "id": f"post-{index}",
            "owner_id": user_id,
            "text": f"Post {index}",
            "status": "published",
        })
    fake.insert_row("video_jobs", {
        "id": "video-1",
        "owner_id": user_id,
        "status": "completed",
        "output_url": "https://cdn.example.com/video.mp4",
        "topic": "Launch recap",
    })
    fake.insert_row("social_accounts", {
        "id": "acct-1",
        "owner_id": user_id,
        "platform": "youtube",
        "handle": "@contentflow",
        "encrypted_access_token": "secret-access",
        "encrypted_refresh_token": "secret-refresh",
        "token_expires_at": "2026-04-10T00:00:00+00:00",
    })
    fake.insert_row("analytics_snapshots", {
        "id": "ana-1",
        "owner_id": user_id,
        "metric": "views",
        "value": 1234,
    })
    fake.insert_row("notifications", {
        "id": "notif-1",
        "user_id": user_id,
        "type": "post_published",
        "title": "Published",
        "body": "Your post is live.",
    })
    fake.insert_row("audit_logs", {
        "id": "audit-1",
        "user_id": user_id,
        "action": "privacy.export_request",
        "resource": "privacy",
        "ip": "127.0.0.1",
        "metadata": {"source": "test"},
    })


@pytest.fixture()
def export_setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, object]:
    fake = FakeSupabase()
    export_root = tmp_path / "exports"
    queued: list[tuple[str, str, str, str | None]] = []
    sent_emails: list[dict[str, object]] = []

    user_id, raw_key = _create_user(fake, "owner@example.com")
    other_user_id, other_key = _create_user(fake, "other@example.com")

    def fake_get_supabase() -> FakeSupabase:
        return fake

    for mod in (
        "app.api.deps",
        "app.api.v1.privacy",
        "app.core.audit",
        "app.services.data_export_service",
        "app.workers.data_export_worker",
        "app.services.notification_service",
    ):
        monkeypatch.setattr(f"{mod}.get_supabase", fake_get_supabase)

    monkeypatch.setattr(
        "app.core.workspaces.resolve_workspace_id_for_user",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr("app.services.data_export_service.EXPORT_ROOT", export_root)

    class FakeExportTask:
        @staticmethod
        def delay(
            export_id: str,
            task_user_id: str,
            export_format: str,
            password: str | None,
        ) -> None:
            queued.append((export_id, task_user_id, export_format, password))

    async def fake_send_email(**kwargs):
        sent_emails.append(kwargs)
        return {"status": "sent"}

    monkeypatch.setattr("app.api.v1.privacy.generate_user_data_export_task", FakeExportTask)
    monkeypatch.setattr("app.workers.data_export_worker.send_email", fake_send_email)

    return {
        "fake": fake,
        "user_id": user_id,
        "raw_key": raw_key,
        "other_user_id": other_user_id,
        "other_key": other_key,
        "queued": queued,
        "sent_emails": sent_emails,
        "export_root": export_root,
    }


async def test_full_export_generation(export_setup) -> None:
    fake = export_setup["fake"]
    user_id = export_setup["user_id"]
    raw_key = export_setup["raw_key"]
    export_root = export_setup["export_root"]
    _seed_export_data(fake, user_id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        response = await client.post("/api/v1/privacy/export", json={"format": "zip"})
        assert response.status_code == 200
        export_id = response.json()["export_id"]

        await run_user_data_export(export_id, user_id, "zip")

        status = await client.get(f"/api/v1/privacy/export/{export_id}")
        assert status.status_code == 200
        assert status.json()["status"] == "ready"
        download_url = status.json()["download_url"]
        download = await client.get(download_url)

    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/zip")
    assert download.content
    assert not (export_root / f"{export_id}.zip").exists()
    assert not (export_root / f"{export_id}.json").exists()


def test_zip_structure_verification(export_setup) -> None:
    fake = export_setup["fake"]
    user_id = export_setup["user_id"]
    _seed_export_data(fake, user_id)

    metadata = create_export_request(user_id, export_format="zip", encrypted=False, sb=fake)
    manifest = build_export_archive(metadata["export_id"], user_id, export_format="zip", sb=fake)

    with zipfile.ZipFile(manifest["file_path"]) as archive:
        names = set(archive.namelist())

    assert {
        "profile.json",
        "posts/",
        "videos/",
        "accounts.json",
        "analytics.json",
        "notifications.json",
        "audit_log.csv",
        "summary.html",
    }.issubset(names)


def test_encrypted_export_option(export_setup) -> None:
    fake = export_setup["fake"]
    user_id = export_setup["user_id"]
    _seed_export_data(fake, user_id)

    metadata = create_export_request(user_id, export_format="zip", encrypted=True, sb=fake)
    manifest = build_export_archive(
        metadata["export_id"],
        user_id,
        export_format="zip",
        password="strong-pass",
        sb=fake,
    )

    with zipfile.ZipFile(manifest["file_path"]) as archive:
        with pytest.raises(RuntimeError):
            archive.read("profile.json")

    with pyzipper.AESZipFile(manifest["file_path"]) as archive:
        archive.setpassword(b"strong-pass")
        profile = json.loads(archive.read("profile.json"))

    assert profile["email"] == "owner@example.com"


def test_tokens_are_excluded_from_accounts(export_setup) -> None:
    fake = export_setup["fake"]
    user_id = export_setup["user_id"]
    _seed_export_data(fake, user_id)

    metadata = create_export_request(user_id, export_format="zip", encrypted=False, sb=fake)
    manifest = build_export_archive(metadata["export_id"], user_id, export_format="zip", sb=fake)

    with zipfile.ZipFile(manifest["file_path"]) as archive:
        accounts = json.loads(archive.read("accounts.json"))

    assert len(accounts) == 1
    assert not any("token" in key.lower() for key in accounts[0])


async def test_export_request_is_enqueued(export_setup) -> None:
    raw_key = export_setup["raw_key"]
    queued = export_setup["queued"]

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        response = await client.post("/api/v1/privacy/export", json={"format": "zip"})

    assert response.status_code == 200
    export_id = response.json()["export_id"]
    assert queued == [(export_id, export_setup["user_id"], "zip", None)]


async def test_worker_creates_notification_and_email(export_setup) -> None:
    fake = export_setup["fake"]
    user_id = export_setup["user_id"]
    sent_emails = export_setup["sent_emails"]
    _seed_export_data(fake, user_id)

    metadata = create_export_request(user_id, export_format="zip", encrypted=False, sb=fake)
    await run_user_data_export(metadata["export_id"], user_id, "zip")

    assert sent_emails
    assert metadata["export_id"] in sent_emails[0]["html"]
    assert fake.tables["notifications"][-1]["type"] == "export_ready"


async def test_url_expiry_returns_gone(export_setup) -> None:
    fake = export_setup["fake"]
    user_id = export_setup["user_id"]
    raw_key = export_setup["raw_key"]
    export_root = export_setup["export_root"]
    _seed_export_data(fake, user_id)

    metadata = create_export_request(user_id, export_format="zip", encrypted=False, sb=fake)
    await run_user_data_export(metadata["export_id"], user_id, "zip")

    manifest_path = export_root / f"{metadata['export_id']}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        response = await client.get(f"/api/v1/privacy/export/{metadata['export_id']}")

    assert response.status_code == 410
    assert not manifest_path.exists()
    assert not (export_root / f"{metadata['export_id']}.zip").exists()


async def test_other_user_export_access_forbidden(export_setup) -> None:
    fake = export_setup["fake"]
    user_id = export_setup["user_id"]
    other_key = export_setup["other_key"]
    _seed_export_data(fake, user_id)

    metadata = create_export_request(user_id, export_format="zip", encrypted=False, sb=fake)
    await run_user_data_export(metadata["export_id"], user_id, "zip")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": other_key},
    ) as client:
        response = await client.get(f"/api/v1/privacy/export/{metadata['export_id']}")

    assert response.status_code == 403


def test_empty_account_export(export_setup) -> None:
    fake = export_setup["fake"]
    user_id = export_setup["user_id"]

    metadata = create_export_request(user_id, export_format="zip", encrypted=False, sb=fake)
    manifest = build_export_archive(metadata["export_id"], user_id, export_format="zip", sb=fake)

    with zipfile.ZipFile(manifest["file_path"]) as archive:
        names = archive.namelist()

    assert "profile.json" in names
    assert "summary.html" in names
    assert not [name for name in names if name.startswith("posts/") and name.endswith(".json")]


def test_large_export_supports_many_posts(export_setup) -> None:
    fake = export_setup["fake"]
    user_id = export_setup["user_id"]
    _seed_export_data(fake, user_id, posts=1005)

    metadata = create_export_request(user_id, export_format="zip", encrypted=False, sb=fake)
    manifest = build_export_archive(metadata["export_id"], user_id, export_format="zip", sb=fake)

    with zipfile.ZipFile(manifest["file_path"]) as archive:
        post_files = [
            name
            for name in archive.namelist()
            if name.startswith("posts/") and name.endswith(".json")
        ]

    assert len(post_files) == 1005
