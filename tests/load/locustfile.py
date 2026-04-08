"""ContentFlow Load Testing — Locust scenarios.

Usage:
    locust -f tests/load/locustfile.py --host http://localhost:8000

Scenarios:
    1. PostsUser      — Posts API CRUD (weight-heavy writes)
    2. BulkBombUser   — Bulk posting + content bombs
    3. ReadHeavyUser  — Analytics, usage, trending reads
"""

from __future__ import annotations

import random
import string

from locust import HttpUser, between, task


def _random_text(length: int = 80) -> str:
    return "".join(random.choices(string.ascii_letters + " ", k=length))


# Default API key for load testing — override via environment variable
API_KEY = "cf_live_SEED_ADMIN_KEY_FOR_LOCAL_DEV_ONLY"

PLATFORMS = ["youtube", "tiktok", "instagram", "x", "facebook", "threads"]


class PostsUser(HttpUser):
    """Posts API load — creates, reads single, and lists posts."""

    weight = 10
    wait_time = between(0.5, 2.0)
    created_post_ids: list[str] = []

    def on_start(self) -> None:
        self.client.headers.update({"X-API-Key": API_KEY})

    @task(10)
    def create_post(self) -> None:
        platforms = random.sample(PLATFORMS, k=min(3, len(PLATFORMS)))
        resp = self.client.post(
            "/api/v1/posts",
            json={
                "text": _random_text(),
                "platforms": platforms,
                "media_type": "text",
            },
            name="/api/v1/posts [POST]",
        )
        if resp.status_code == 201:
            data = resp.json()
            post_id = data.get("id") or data.get("post_id")
            if post_id:
                self.created_post_ids.append(post_id)

    @task(5)
    def get_post(self) -> None:
        if not self.created_post_ids:
            return
        post_id = random.choice(self.created_post_ids)
        self.client.get(
            f"/api/v1/posts/{post_id}",
            name="/api/v1/posts/{id} [GET]",
        )

    @task(3)
    def list_posts(self) -> None:
        self.client.get(
            "/api/v1/posts",
            params={"limit": "20"},
            name="/api/v1/posts [GET]",
        )


class BulkBombUser(HttpUser):
    """Bulk posting and content bomb creation."""

    weight = 2
    wait_time = between(1.0, 3.0)

    def on_start(self) -> None:
        self.client.headers.update({"X-API-Key": API_KEY})

    @task(2)
    def bulk_create(self) -> None:
        posts = [
            {
                "text": _random_text(),
                "platforms": random.sample(PLATFORMS, k=2),
                "media_type": "text",
            }
            for _ in range(10)
        ]
        self.client.post(
            "/api/v1/posts/bulk",
            json={"posts": posts, "mode": "partial"},
            name="/api/v1/posts/bulk [POST]",
        )

    @task(1)
    def create_bomb(self) -> None:
        self.client.post(
            "/api/v1/bombs",
            json={
                "topic": _random_text(40),
                "platforms": random.sample(PLATFORMS, k=3),
            },
            name="/api/v1/bombs [POST]",
        )


class ReadHeavyUser(HttpUser):
    """Read-heavy scenario targeting analytics, usage, and trending."""

    weight = 5
    wait_time = between(0.5, 1.5)

    def on_start(self) -> None:
        self.client.headers.update({"X-API-Key": API_KEY})

    @task(5)
    def get_analytics(self) -> None:
        self.client.get(
            "/api/v1/analytics/dashboard",
            name="/api/v1/analytics/dashboard [GET]",
        )

    @task(5)
    def get_usage(self) -> None:
        self.client.get(
            "/api/v1/usage/summary",
            name="/api/v1/usage/summary [GET]",
        )

    @task(3)
    def get_trending(self) -> None:
        self.client.get(
            "/api/v1/trending",
            params={"region": "US", "limit": "20"},
            name="/api/v1/trending [GET]",
        )
