"""Smoke test script for a locally running ContentFlow API."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_BASE_URL = os.getenv("CONTENTFLOW_BASE_URL", "http://localhost:8000")


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str


def print_step(result: StepResult) -> None:
    prefix = "OK" if result.ok else "FAIL"
    print(f"[{prefix}] {result.name}: {result.detail}")


def request(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> httpx.Response:
    return client.request(method, path, headers=headers, json=json_body)


def ensure_json_keys(payload: dict[str, Any], keys: tuple[str, ...]) -> tuple[bool, str]:
    missing = [key for key in keys if key not in payload]
    if missing:
        return False, f"missing keys: {', '.join(missing)}"
    return True, "schema looks valid"


def run() -> int:
    api_key = os.getenv("CONTENTFLOW_API_KEY")
    bootstrap_key = os.getenv("CONTENTFLOW_BOOTSTRAP_API_KEY")
    failures: list[StepResult] = []

    with httpx.Client(base_url=DEFAULT_BASE_URL, timeout=20.0) as client:
        health = request(client, "GET", "/health")
        health_ok = health.status_code == 200
        result = StepResult("Health check", health_ok, f"status={health.status_code}")
        print_step(result)
        if not health_ok:
            failures.append(result)

        seed_key = bootstrap_key or api_key
        issue_headers = {"X-API-Key": seed_key} if seed_key else None
        issue_resp = request(
            client,
            "POST",
            "/api/v1/keys",
            headers=issue_headers,
            json_body={"name": "smoke-test"},
        )
        if issue_resp.status_code in {200, 201}:
            body = issue_resp.json()
            api_key = body.get("raw_key") or api_key
            ok, detail = ensure_json_keys(body, ("id", "raw_key"))
            result = StepResult("API key issuance", ok, detail)
        else:
            result = StepResult(
                "API key issuance",
                False,
                f"status={issue_resp.status_code} body={issue_resp.text[:200]}",
            )
        print_step(result)
        if not result.ok:
            failures.append(result)

        if not api_key:
            skip = StepResult(
                "Authenticated flow",
                False,
                "No CONTENTFLOW_API_KEY available after issuance attempt",
            )
            print_step(skip)
            failures.append(skip)
            return 1

        auth_headers = {"X-API-Key": api_key}

        connect_resp = request(
            client,
            "POST",
            "/api/v1/accounts/connect/youtube",
            headers=auth_headers,
        )
        if connect_resp.status_code == 200:
            ok, detail = ensure_json_keys(connect_resp.json(), ("authorize_url",))
            result = StepResult("OAuth URL generation", ok, detail)
        else:
            result = StepResult(
                "OAuth URL generation",
                False,
                f"status={connect_resp.status_code} body={connect_resp.text[:200]}",
            )
        print_step(result)
        if not result.ok:
            failures.append(result)

        post_resp = request(
            client,
            "POST",
            "/api/v1/posts?dry_run=true",
            headers=auth_headers,
            json_body={
                "text": "Smoke dry run",
                "platforms": ["youtube"],
                "media_urls": ["https://cdn.example.com/video.mp4"],
                "media_type": "video",
                "platform_options": {"youtube": {"title": "Smoke dry run"}},
            },
        )
        if post_resp.status_code == 200:
            ok, detail = ensure_json_keys(
                post_resp.json(),
                ("dry_run", "validated", "expected_deliveries"),
            )
            result = StepResult("Posts dry run", ok, detail)
        else:
            result = StepResult(
                "Posts dry run",
                False,
                f"status={post_resp.status_code} body={post_resp.text[:200]}",
            )
        print_step(result)
        if not result.ok:
            failures.append(result)

        video_resp = request(
            client,
            "POST",
            "/api/v1/videos/generate",
            headers=auth_headers,
            json_body={
                "topic": "Smoke test topic",
                "mode": "general",
                "language": "en",
                "format": "shorts",
                "style": "realistic",
                "auto_publish": {"enabled": False, "platforms": []},
            },
        )
        if video_resp.status_code in {200, 201}:
            ok, detail = ensure_json_keys(video_resp.json(), ("id", "status", "topic"))
            result = StepResult("Videos generate", ok, detail)
        else:
            result = StepResult(
                "Videos generate",
                False,
                f"status={video_resp.status_code} body={video_resp.text[:200]}",
            )
        print_step(result)
        if not result.ok:
            failures.append(result)

        webhook_resp = request(
            client,
            "GET",
            "/api/v1/webhooks/dead-letters",
            headers=auth_headers,
        )
        if webhook_resp.status_code == 200:
            ok, detail = ensure_json_keys(
                webhook_resp.json(),
                ("data", "total", "page", "limit"),
            )
            result = StepResult("Webhook dead-letter listing", ok, detail)
        else:
            result = StepResult(
                "Webhook dead-letter listing",
                False,
                f"status={webhook_resp.status_code} body={webhook_resp.text[:200]}",
            )
        print_step(result)
        if not result.ok:
            failures.append(result)

        bomb_resp = request(
            client,
            "POST",
            "/api/v1/bombs",
            headers=auth_headers,
            json_body={"topic": "Smoke test topic"},
        )
        if bomb_resp.status_code in {200, 201}:
            ok, detail = ensure_json_keys(bomb_resp.json(), ("id", "status", "topic"))
            result = StepResult("Bomb creation", ok, detail)
        else:
            result = StepResult(
                "Bomb creation",
                False,
                f"status={bomb_resp.status_code} body={bomb_resp.text[:200]}",
            )
        print_step(result)
        if not result.ok:
            failures.append(result)

    if failures:
        print("\nSmoke test completed with failures:")
        for failure in failures:
            print(f"- {failure.name}: {failure.detail}")
        return 1

    print("\nSmoke test completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
