from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4


class FakeQuery:
    def __init__(self, client: FakeSupabase, table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.selected_columns = "*"
        self.filters: list[tuple[str, str, object]] = []
        self.insert_payload: dict | list[dict] | None = None
        self.upsert_payload: dict | list[dict] | None = None
        self.upsert_conflict: str = ""
        self.update_payload: dict | None = None
        self.delete_mode: bool = False
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

    def lte(self, field: str, value: object) -> FakeQuery:
        self.filters.append(("lte", field, value))
        return self

    def gte(self, field: str, value: object) -> FakeQuery:
        self.filters.append(("gte", field, value))
        return self

    def insert(self, payload: dict | list[dict]) -> FakeQuery:
        self.insert_payload = payload
        return self

    def upsert(self, payload: dict | list[dict], on_conflict: str = "") -> FakeQuery:
        self.upsert_payload = payload
        self.upsert_conflict = on_conflict
        return self

    def update(self, payload: dict) -> FakeQuery:
        self.update_payload = payload
        return self

    def delete(self) -> FakeQuery:
        self.delete_mode = True
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

        if self.upsert_payload is not None:
            rows = self.upsert_payload
            if isinstance(rows, dict):
                rows = [rows]
            conflict_fields = [f.strip() for f in self.upsert_conflict.split(",") if f.strip()]
            results = []
            for row in rows:
                existing = None
                if conflict_fields:
                    for stored in table:
                        if all(stored.get(f) == row.get(f) for f in conflict_fields):
                            existing = stored
                            break
                if existing:
                    existing.update(row)
                    existing["updated_at"] = self.client.now()
                    results.append(dict(existing))
                else:
                    results.append(self.client.insert_row(self.table_name, row))
            return SimpleNamespace(data=results, count=len(results))

        if self.delete_mode:
            matched = self._apply_filters(table)
            for row in matched:
                table.remove(row)
            return SimpleNamespace(data=[dict(r) for r in matched], count=len(matched))

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
            elif operator == "lte":
                filtered = [
                    row
                    for row in filtered
                    if row.get(field) is not None and row.get(field) <= value
                ]
            elif operator == "gte":
                filtered = [
                    row
                    for row in filtered
                    if row.get(field) is not None and row.get(field) >= value
                ]
        return filtered


class FakeSupabase:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict]] = {
            "users": [],
            "workspaces": [],
            "workspace_members": [],
            "api_keys": [],
            "analytics_snapshots": [],
            "bombs": [],
            "comments": [],
            "posts": [],
            "schedules": [],
            "post_deliveries": [],
            "video_jobs": [],
            "webhooks": [],
            "webhook_deliveries": [],
            "social_accounts": [],
            "video_templates": [],
            "trending_snapshots": [],
            "audit_logs": [],
            "payments": [],
            "subscription_events": [],
            "email_logs": [],
            "notification_preferences": [],
            "consents": [],
            "dpa_signatures": [],
            "data_breaches": [],
            "deletion_requests": [],
            "ytboost_subscriptions": [],
            "ytboost_shorts": [],
            "ytboost_channel_tones": [],
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
