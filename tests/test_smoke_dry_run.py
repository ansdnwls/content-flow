from __future__ import annotations

import importlib
from pathlib import Path

import httpx


def test_smoke_test_module_importable() -> None:
    module = importlib.import_module("scripts.smoke_test")
    assert module.DEFAULT_BASE_URL.startswith("http")


def test_health_check_helpers() -> None:
    smoke = importlib.import_module("scripts.smoke_test")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health/live":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/health/ready":
            return httpx.Response(
                200,
                json={
                    "status": "ready",
                    "checks": {"supabase": True, "redis": True, "celery": True},
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://testserver",
    ) as client:
        live = smoke.check_live(client)
        ready, payload = smoke.check_ready(client)
        db = smoke.check_dependency("DB connection", payload, "supabase")
        redis = smoke.check_dependency("Redis connection", payload, "redis")

    assert live.ok is True
    assert ready.ok is True
    assert db.ok is True
    assert redis.ok is True


def test_write_report_renders_markdown(tmp_path: Path) -> None:
    smoke = importlib.import_module("scripts.smoke_test")
    template = tmp_path / "template.md"
    output = tmp_path / "report.md"
    template.write_text(
        "Generated {{generated_at}}\n{{summary}}\n{{step_rows}}\n{{failure_lines}}\n",
        encoding="utf-8",
    )

    report_path = smoke.write_report(
        template,
        output,
        base_url="http://testserver",
        steps=[
            smoke.StepResult("API live", True, "status=200"),
            smoke.StepResult("Webhook", False, "status=500"),
        ],
    )

    text = report_path.read_text(encoding="utf-8")
    assert report_path == output
    assert "1 passed, 1 failed" in text
    assert "| API live | OK | status=200 |" in text
    assert "- `Webhook`: status=500" in text


def test_main_returns_exit_code_one_on_failure(tmp_path: Path, monkeypatch) -> None:
    smoke = importlib.import_module("scripts.smoke_test")
    template = tmp_path / "template.md"
    template.write_text("{{summary}}\n{{step_rows}}\n{{failure_lines}}\n", encoding="utf-8")

    monkeypatch.setattr(
        smoke,
        "run_smoke",
        lambda _config: [smoke.StepResult("API live", False, "boom")],
    )

    code = smoke.main(
        [
            "--report-template",
            str(template),
            "--report-path",
            str(tmp_path / "report.md"),
        ]
    )

    assert code == 1


def test_main_returns_exit_code_zero_on_success(tmp_path: Path, monkeypatch) -> None:
    smoke = importlib.import_module("scripts.smoke_test")
    template = tmp_path / "template.md"
    template.write_text("{{summary}}\n{{step_rows}}\n{{failure_lines}}\n", encoding="utf-8")

    monkeypatch.setattr(
        smoke,
        "run_smoke",
        lambda _config: [smoke.StepResult("API live", True, "ok")],
    )

    code = smoke.main(
        [
            "--report-template",
            str(template),
            "--report-path",
            str(tmp_path / "report.md"),
        ]
    )

    assert code == 0
