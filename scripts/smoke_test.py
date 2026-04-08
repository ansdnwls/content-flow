"""Docker-compose oriented smoke test runner for ContentFlow."""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx

DEFAULT_BASE_URL = os.getenv("CONTENTFLOW_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_REPORT_TEMPLATE = Path(__file__).with_name("smoke_test_results.md")
DEFAULT_REPORT_OUTPUT = Path(__file__).with_name("smoke_test_results.generated.md")

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


@dataclass(frozen=True)
class StepResult:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class SmokeConfig:
    base_url: str
    start_compose: bool
    report_template: Path
    report_output: Path
    wait_seconds: int


def colorize(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def print_step(result: StepResult) -> None:
    prefix = colorize("OK", GREEN) if result.ok else colorize("FAIL", RED)
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


def parse_ready_payload(response: httpx.Response) -> dict[str, Any]:
    payload = response.json()
    if response.status_code == 503 and isinstance(payload, dict) and "detail" in payload:
        detail = payload["detail"]
        if isinstance(detail, dict):
            return detail
    return payload


def check_live(client: httpx.Client) -> StepResult:
    response = request(client, "GET", "/health/live")
    ok = response.status_code == 200 and response.json().get("status") == "ok"
    return StepResult("API live", ok, f"status={response.status_code}")


def check_ready(client: httpx.Client) -> tuple[StepResult, dict[str, Any]]:
    response = request(client, "GET", "/health/ready")
    payload = parse_ready_payload(response)
    ok = response.status_code == 200 and payload.get("status") == "ready"
    detail = f"status={response.status_code} readiness={payload.get('status', 'unknown')}"
    return StepResult("API ready", ok, detail), payload


def check_dependency(name: str, ready_payload: dict[str, Any], key: str) -> StepResult:
    checks = ready_payload.get("checks", {})
    ok = bool(checks.get(key))
    detail = f"{key}={'ok' if ok else 'down'}"
    return StepResult(name, ok, detail)


def docker_compose_command() -> list[str]:
    if shutil.which("docker"):
        return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    raise RuntimeError("docker compose is not installed")


def start_compose_services() -> StepResult:
    command = [*docker_compose_command(), "up", "-d", "--build"]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (completed.stdout or completed.stderr).strip().splitlines()
    detail = output[-1] if output else f"exit_code={completed.returncode}"
    return StepResult("docker compose up", completed.returncode == 0, detail)


def wait_for_api(base_url: str, wait_seconds: int) -> StepResult:
    deadline = time.monotonic() + wait_seconds
    last_error = "not started"
    while time.monotonic() < deadline:
        try:
            with httpx.Client(base_url=base_url, timeout=5.0) as client:
                response = request(client, "GET", "/health/live")
            if response.status_code == 200:
                return StepResult("API boot wait", True, "service responded to /health/live")
            last_error = f"status={response.status_code}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(2)
    return StepResult("API boot wait", False, last_error)


def bootstrap_smoke_identity() -> tuple[StepResult, str | None, str | None]:
    from app.core.auth import build_api_key_record
    from app.core.db import get_supabase

    owner_id = str(uuid4())
    issued, record = build_api_key_record(user_id=UUID(owner_id), name="smoke-bootstrap")
    record["user_id"] = owner_id

    sb = get_supabase()
    sb.table("users").insert(
        {
            "id": owner_id,
            "email": f"smoke-{owner_id[:8]}@contentflow.local",
            "plan": "build",
            "default_workspace_id": None,
        }
    ).execute()
    sb.table("api_keys").insert(record).execute()
    return StepResult("Bootstrap identity", True, f"user_id={owner_id}"), owner_id, issued.raw_key


def create_api_key_and_verify(
    client: httpx.Client,
    bootstrap_key: str,
) -> tuple[StepResult, str | None]:
    headers = {"X-API-Key": bootstrap_key}
    response = request(
        client,
        "POST",
        "/api/v1/keys",
        headers=headers,
        json_body={"name": "smoke-issued"},
    )
    if response.status_code != 201:
        return (
            StepResult(
                "API key create + persist",
                False,
                f"status={response.status_code} body={response.text[:200]}",
            ),
            None,
        )

    payload = response.json()
    ok, detail = ensure_json_keys(payload, ("id", "raw_key"))
    if not ok:
        return StepResult("API key create + persist", False, detail), None

    list_response = request(client, "GET", "/api/v1/keys", headers=headers)
    if list_response.status_code != 200:
        return (
            StepResult(
                "API key create + persist",
                False,
                f"created but list failed with status={list_response.status_code}",
            ),
            None,
        )

    stored = any(row["id"] == payload["id"] for row in list_response.json().get("data", []))
    detail = f"key_id={payload['id']} stored={'yes' if stored else 'no'}"
    return StepResult("API key create + persist", stored, detail), payload["raw_key"]


def create_workspace(
    client: httpx.Client,
    api_key: str,
) -> tuple[StepResult, str | None]:
    response = request(
        client,
        "POST",
        "/api/v1/workspaces",
        headers={"X-API-Key": api_key},
        json_body={"name": f"Smoke Workspace {uuid4().hex[:6]}"},
    )
    if response.status_code != 201:
        return (
            StepResult(
                "Workspace create",
                False,
                f"status={response.status_code} body={response.text[:200]}",
            ),
            None,
        )
    payload = response.json()
    ok, detail = ensure_json_keys(payload, ("id", "name", "slug"))
    if ok:
        detail = f"workspace_id={payload['id']} slug={payload['slug']}"
    return StepResult("Workspace create", ok, detail), payload.get("id")


def create_dry_run_post(
    client: httpx.Client,
    api_key: str,
    workspace_id: str,
) -> StepResult:
    response = request(
        client,
        "POST",
        "/api/v1/posts?dry_run=true",
        headers={"X-API-Key": api_key, "X-Workspace-Id": workspace_id},
        json_body={
            "text": "Smoke dry run",
            "platforms": ["youtube"],
            "media_urls": ["https://cdn.example.com/smoke.mp4"],
            "media_type": "video",
            "platform_options": {"youtube": {"title": "Smoke dry run"}},
        },
    )
    if response.status_code != 200:
        return StepResult(
            "Posts dry run",
            False,
            f"status={response.status_code} body={response.text[:200]}",
        )
    payload = response.json()
    ok, detail = ensure_json_keys(payload, ("dry_run", "validated", "expected_deliveries"))
    if ok:
        deliveries = len(payload["expected_deliveries"])
        detail = f"validated={payload['validated']} deliveries={deliveries}"
    return StepResult("Posts dry run", ok, detail)


class _WebhookServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler_cls) -> None:
        super().__init__(server_address, handler_cls)
        self.events: list[dict[str, Any]] = []


class _WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        self.server.events.append(  # type: ignore[attr-defined]
            {
                "path": self.path,
                "headers": dict(self.headers.items()),
                "body": body,
            }
        )
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, _format: str, *args: Any) -> None:
        return


def register_and_dispatch_webhook(owner_id: str) -> StepResult:
    from app.core.db import get_supabase
    from app.core.webhook_dispatcher import dispatch_event

    server = _WebhookServer(("127.0.0.1", 0), _WebhookHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    target_url = f"http://127.0.0.1:{server.server_port}/hook"
    webhook_id: str | None = None
    deliveries: list[dict[str, Any]] = []
    try:
        sb = get_supabase()
        inserted = (
            sb.table("webhooks")
            .insert(
                {
                    "owner_id": owner_id,
                    "target_url": target_url,
                    "signing_secret": "whsec_smoke",
                    "event_types": ["smoke.test"],
                    "is_active": True,
                    "failure_count": 0,
                }
            )
            .execute()
            .data[0]
        )
        webhook_id = inserted["id"]
        asyncio.run(dispatch_event(owner_id, "smoke.test", {"scope": "smoke"}))
        deliveries = (
            sb.table("webhook_deliveries")
            .select("*")
            .eq("webhook_id", webhook_id)
            .order("created_at", desc=True)
            .range(0, 0)
            .execute()
            .data
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    if not webhook_id:
        return StepResult("Webhook register + dispatch", False, "webhook insert failed")
    if not deliveries:
        return StepResult("Webhook register + dispatch", False, "no delivery row created")

    delivery = deliveries[0]
    received = len(server.events)
    ok = delivery.get("status") == "delivered" and received > 0
    detail = f"webhook_id={webhook_id} status={delivery.get('status')} received={received}"
    return StepResult("Webhook register + dispatch", ok, detail)


def load_template(template_path: Path) -> str:
    return template_path.read_text(encoding="utf-8")


def render_report(template_text: str, *, base_url: str, steps: list[StepResult]) -> str:
    generated_at = datetime.now(UTC).isoformat()
    passed = sum(1 for step in steps if step.ok)
    failed = len(steps) - passed
    summary = f"{passed} passed, {failed} failed"
    step_rows = "\n".join(
        f"| {step.name} | {'OK' if step.ok else 'FAIL'} | {step.detail} |"
        for step in steps
    )
    failure_lines = "\n".join(
        f"- `{step.name}`: {step.detail}" for step in steps if not step.ok
    ) or "- None"

    return (
        template_text.replace("{{generated_at}}", generated_at)
        .replace("{{base_url}}", base_url)
        .replace("{{summary}}", summary)
        .replace("{{step_rows}}", step_rows)
        .replace("{{failure_lines}}", failure_lines)
    )


def write_report(
    template_path: Path,
    output_path: Path,
    *,
    base_url: str,
    steps: list[StepResult],
) -> Path:
    output_path.write_text(
        render_report(load_template(template_path), base_url=base_url, steps=steps),
        encoding="utf-8",
    )
    return output_path


def run_smoke(config: SmokeConfig) -> list[StepResult]:
    steps: list[StepResult] = []

    if config.start_compose:
        compose_result = start_compose_services()
        steps.append(compose_result)
        print_step(compose_result)
        if not compose_result.ok:
            return steps

        wait_result = wait_for_api(config.base_url, config.wait_seconds)
        steps.append(wait_result)
        print_step(wait_result)
        if not wait_result.ok:
            return steps

    bootstrap_result, owner_id, bootstrap_key = bootstrap_smoke_identity()
    steps.append(bootstrap_result)
    print_step(bootstrap_result)
    if not bootstrap_result.ok or not owner_id or not bootstrap_key:
        return steps

    with httpx.Client(base_url=config.base_url, timeout=20.0) as client:
        live_result = check_live(client)
        steps.append(live_result)
        print_step(live_result)

        ready_result, ready_payload = check_ready(client)
        steps.append(ready_result)
        print_step(ready_result)

        db_result = check_dependency("DB connection", ready_payload, "supabase")
        steps.append(db_result)
        print_step(db_result)

        redis_result = check_dependency("Redis connection", ready_payload, "redis")
        steps.append(redis_result)
        print_step(redis_result)

        key_result, issued_key = create_api_key_and_verify(client, bootstrap_key)
        steps.append(key_result)
        print_step(key_result)
        if not key_result.ok or not issued_key:
            return steps

        workspace_result, workspace_id = create_workspace(client, issued_key)
        steps.append(workspace_result)
        print_step(workspace_result)
        if not workspace_result.ok or not workspace_id:
            return steps

        post_result = create_dry_run_post(client, issued_key, workspace_id)
        steps.append(post_result)
        print_step(post_result)

    webhook_result = register_and_dispatch_webhook(owner_id)
    steps.append(webhook_result)
    print_step(webhook_result)
    return steps


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--start-compose", action="store_true")
    parser.add_argument("--wait-seconds", type=int, default=90)
    parser.add_argument(
        "--report-template",
        type=Path,
        default=DEFAULT_REPORT_TEMPLATE,
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=DEFAULT_REPORT_OUTPUT,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = SmokeConfig(
        base_url=args.base_url,
        start_compose=args.start_compose,
        report_template=args.report_template,
        report_output=args.report_path,
        wait_seconds=args.wait_seconds,
    )
    steps = run_smoke(config)
    report_path = write_report(
        config.report_template,
        config.report_output,
        base_url=config.base_url,
        steps=steps,
    )
    failures = [step for step in steps if not step.ok]
    if failures:
        print(colorize(f"\nSmoke test completed with failures. Report: {report_path}", RED))
        return 1
    print(colorize(f"\nSmoke test completed successfully. Report: {report_path}", GREEN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
