from __future__ import annotations

from types import SimpleNamespace

from app.middleware.custom_domain import (
    normalize_host,
    resolve_workspace_by_host,
    verify_custom_domain_record,
)
from tests.fakes import FakeSupabase


async def test_resolve_workspace_by_host(monkeypatch) -> None:
    fake = FakeSupabase()
    workspace = fake.insert_row(
        "workspaces",
        {"owner_id": "user-1", "name": "Acme", "slug": "acme", "custom_domain": "api.acme.dev"},
    )
    monkeypatch.setattr("app.middleware.custom_domain.get_supabase", lambda: fake)

    resolved = resolve_workspace_by_host("Api.Acme.dev:443")
    assert resolved["id"] == workspace["id"]
    assert normalize_host("Api.Acme.dev:443") == "api.acme.dev"


async def test_verify_custom_domain_record(monkeypatch) -> None:
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout='text = "cf-verify-token"', stderr=""),
    )
    assert verify_custom_domain_record("api.acme.dev", "cf-verify-token") is True
