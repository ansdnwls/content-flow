from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.main import app


class FakeQuery:
    def __init__(self, client: FakeSupabase, table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.selected_columns = "*"
        self.filters: list[tuple[str, str, object]] = []
        self.insert_payload: dict | list[dict] | None = None
        self.update_payload: dict | None = None
        self.single_mode: str | None = None
        self.include_count = False
        self.order_field: str | None = None
        self.order_desc = False
        self.range_start: int | None = None
        self.range_end: int | None = None

    def select(self, _columns: str = "*", count: str | None = None) -> FakeQuery:
        self.selected_columns = _columns
        self.include_count = count == "exact"
        return self

    def eq(self, field: str, value: object) -> FakeQuery:
        self.filters.append(("eq", field, value))
        return self

    def in_(self, field: str, values: list[object]) -> FakeQuery:
        self.filters.append(("in", field, values))
        return self

    def insert(self, payload: dict | list[dict]) -> FakeQuery:
        self.insert_payload = payload
        return self

    def update(self, payload: dict) -> FakeQuery:
        self.update_payload = payload
        return self

    def maybe_single(self) -> FakeQuery:
        self.single_mode = "maybe_single"
        return self

    def single(self) -> FakeQuery:
        self.single_mode = "single"
        return self

    def order(self, field: str, desc: bool = False) -> FakeQuery:
        self.order_field = field
        self.order_desc = desc
        return self

    def range(self, start: int, end: int) -> FakeQuery:
        self.range_start = start
        self.range_end = end
        return self

    def execute(self) -> SimpleNamespace:
        self.client.query_counts[self.table_name] = (
            self.client.query_counts.get(self.table_name, 0) + 1
        )
        table = self.client.tables[self.table_name]

        if self.insert_payload is not None:
            rows = self.insert_payload
            if isinstance(rows, dict):
                rows = [rows]
            inserted = [self.client.insert_row(self.table_name, row) for row in rows]
            return SimpleNamespace(data=inserted, count=len(inserted))

        if self.update_payload is not None:
            updated = []
            for row in self._apply_filters(table):
                row.update(self.update_payload)
                row["updated_at"] = self.client.now()
                updated.append(dict(row))
            if self.single_mode:
                return SimpleNamespace(data=updated[0] if updated else None, count=len(updated))
            return SimpleNamespace(data=updated, count=len(updated))

        rows = [dict(row) for row in self._apply_filters(table)]
        if self.table_name == "posts" and "post_deliveries(" in self.selected_columns:
            for row in rows:
                row["post_deliveries"] = [
                    dict(delivery)
                    for delivery in self.client.tables["post_deliveries"]
                    if delivery.get("post_id") == row["id"]
                ]
        total_count = len(rows)

        if self.order_field:
            rows.sort(key=lambda row: row[self.order_field], reverse=self.order_desc)
        if self.range_start is not None and self.range_end is not None:
            rows = rows[self.range_start : self.range_end + 1]
        if self.single_mode:
            return SimpleNamespace(data=rows[0] if rows else None, count=total_count)
        return SimpleNamespace(data=rows, count=total_count if self.include_count else None)

    def _apply_filters(self, rows: list[dict]) -> list[dict]:
        filtered = rows
        for operator, field, value in self.filters:
            if operator == "eq":
                filtered = [row for row in filtered if row.get(field) == value]
            elif operator == "in":
                filtered = [row for row in filtered if row.get(field) in value]
        return filtered


class FakeSupabase:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict]] = {
            "users": [],
            "api_keys": [],
            "posts": [],
            "post_deliveries": [],
            "social_accounts": [],
        }
        self.query_counts: dict[str, int] = {}

    def table(self, table_name: str) -> FakeQuery:
        return FakeQuery(self, table_name)

    def insert_row(self, table_name: str, row: dict) -> dict:
        timestamp = self.now()
        stored = {
            "id": row.get("id", str(uuid4())),
            "created_at": row.get("created_at", timestamp),
            "updated_at": row.get("updated_at", timestamp),
            **row,
        }
        self.tables[table_name].append(stored)
        return dict(stored)

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat()


async def test_posts_crud_round_trip(monkeypatch) -> None:
    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    fake_supabase.insert_row(
        "users",
        {"id": user_id, "email": "owner@example.com", "plan": "free"},
    )

    issued, record = build_api_key_record(user_id=uuid4(), name="default")
    record["user_id"] = user_id
    fake_supabase.insert_row("api_keys", record)

    queued: list[tuple[str, str]] = []

    def fake_get_supabase() -> FakeSupabase:
        return fake_supabase

    class FakeTask:
        @staticmethod
        def delay(post_id: str, owner_id: str) -> None:
            queued.append((post_id, owner_id))

    monkeypatch.setattr("app.api.deps.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.posts.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.posts.publish_post_task", FakeTask)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": issued.raw_key},
    ) as client:
        create_response = await client.post(
            "/api/v1/posts",
            json={
                "text": "Launch post",
                "platforms": ["youtube", "tiktok"],
                "media_urls": ["https://example.com/video.mp4"],
                "media_type": "video",
                "platform_options": {"youtube": {"title": "Launch"}},
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["status"] == "pending"
        assert created["platforms"]["youtube"]["status"] == "pending"
        assert created["platforms"]["tiktok"]["status"] == "pending"
        assert len(queued) == 1
        assert queued[0][1] == user_id

        post_id = created["id"]

        get_response = await client.get(f"/api/v1/posts/{post_id}")
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["id"] == post_id
        assert fetched["text"] == "Launch post"
        assert fetched["media_urls"] == ["https://example.com/video.mp4"]

        cancel_response = await client.delete(f"/api/v1/posts/{post_id}")
        assert cancel_response.status_code == 200
        cancelled = cancel_response.json()
        assert cancelled["status"] == "cancelled"
        assert cancelled["platforms"]["youtube"]["status"] == "cancelled"
        assert cancelled["platforms"]["tiktok"]["status"] == "cancelled"


async def test_posts_dry_run_preview(monkeypatch) -> None:
    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    fake_supabase.insert_row(
        "users",
        {"id": user_id, "email": "owner@example.com", "plan": "free"},
    )

    issued, record = build_api_key_record(user_id=uuid4(), name="default")
    record["user_id"] = user_id
    fake_supabase.insert_row("api_keys", record)
    fake_supabase.insert_row(
        "social_accounts",
        {"owner_id": user_id, "platform": "youtube", "handle": "@yt"},
    )

    queued: list[tuple[str, str]] = []

    def fake_get_supabase() -> FakeSupabase:
        return fake_supabase

    class FakeTask:
        @staticmethod
        def delay(post_id: str, owner_id: str) -> None:
            queued.append((post_id, owner_id))

    monkeypatch.setattr("app.api.deps.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.posts.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.posts.publish_post_task", FakeTask)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": issued.raw_key},
    ) as client:
        response = await client.post(
            "/api/v1/posts?dry_run=true",
            json={
                "text": "Dry run post",
                "platforms": ["youtube", "tiktok"],
                "media_urls": ["https://example.com/video.mp4"],
                "media_type": "video",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["validated"] is True
    assert body["will_enqueue"] is True
    assert body["missing_accounts"] == ["tiktok"]
    assert len(fake_supabase.tables["posts"]) == 0
    assert queued == []


async def test_list_posts_uses_joined_deliveries(monkeypatch) -> None:
    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    fake_supabase.insert_row(
        "users",
        {"id": user_id, "email": "owner@example.com", "plan": "free"},
    )

    issued, record = build_api_key_record(user_id=uuid4(), name="default")
    record["user_id"] = user_id
    fake_supabase.insert_row("api_keys", record)

    post = fake_supabase.insert_row(
        "posts",
        {"owner_id": user_id, "text": "Joined list", "status": "published"},
    )
    fake_supabase.insert_row(
        "post_deliveries",
        {"post_id": post["id"], "owner_id": user_id, "platform": "youtube", "status": "published"},
    )
    fake_supabase.insert_row(
        "post_deliveries",
        {"post_id": post["id"], "owner_id": user_id, "platform": "tiktok", "status": "failed"},
    )

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr("app.api.v1.posts.get_supabase", lambda: fake_supabase)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": issued.raw_key},
    ) as client:
        response = await client.get("/api/v1/posts")

    assert response.status_code == 200
    body = response.json()
    assert body["data"][0]["platforms"]["youtube"]["status"] == "published"
    assert body["data"][0]["platforms"]["tiktok"]["status"] == "failed"
    assert fake_supabase.query_counts.get("post_deliveries", 0) == 0
