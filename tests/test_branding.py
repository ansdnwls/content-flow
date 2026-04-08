from __future__ import annotations

from app.core.branding import (
    get_workspace_branding,
    render_email_template,
    render_webhook_payload,
)
from tests.fakes import FakeSupabase


async def test_get_workspace_branding_merges_defaults(monkeypatch) -> None:
    fake = FakeSupabase()
    workspace = fake.insert_row(
        "workspaces",
        {
            "owner_id": "user-1",
            "name": "Acme",
            "slug": "acme",
            "branding": {"primary_color": "#ff6600"},
        },
    )
    monkeypatch.setattr("app.core.branding.get_supabase", lambda: fake)

    branding = get_workspace_branding(workspace["id"])
    assert branding["primary_color"] == "#ff6600"
    assert branding["workspace_name"] == "Acme"
    assert "support_email" in branding


async def test_render_branding_helpers() -> None:
    workspace = {
        "name": "Acme",
        "branding": {"primary_color": "#ff6600", "support_email": "help@acme.dev"},
    }

    email = render_email_template(
        "Hello from ${workspace_name} (${primary_color})",
        workspace,
        {},
    )
    assert "Acme" in email
    assert "#ff6600" in email

    payload = render_webhook_payload("post.published", workspace, {"post_id": "p1"})
    assert payload["from_brand"] == "Acme"
    assert payload["branding"]["support_email"] == "help@acme.dev"
    assert payload["data"]["post_id"] == "p1"
