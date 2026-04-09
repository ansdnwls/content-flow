"""Locust scenarios for ContentFlow API load testing.

Usage:
    set LOAD_TEST_API_KEY=cf_live_xxx
    set LOAD_TEST_SCENARIO=normal_user
    locust -f scripts/load_test/locustfile.py --host http://localhost:8000
"""

from __future__ import annotations

import json
import os
import random
import string
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    from locust import HttpUser, between, events, task
except ImportError:  # pragma: no cover - allows unit tests to import without locust installed
    class HttpUser:  # type: ignore[no-redef]
        weight = 1
        wait_time = None

    def between(_min_wait: float, _max_wait: float):  # type: ignore[no-redef]
        return (_min_wait, _max_wait)

    def task(weight: int = 1):  # type: ignore[no-redef]
        def decorator(func):
            func.locust_task_weight = weight
            return func

        return decorator

    class _EventHook:
        def add_listener(self, func):
            return func

    class _Events:
        init = _EventHook()
        quitting = _EventHook()

    events = _Events()  # type: ignore[no-redef]


ALLOWED_METHODS = frozenset({"GET", "POST"})
SCENARIO_ENV_VAR = "LOAD_TEST_SCENARIO"
API_KEY_ENV_VAR = "LOAD_TEST_API_KEY"
DEFAULT_API_KEY = "cf_live_SEED_ADMIN_KEY_FOR_LOCAL_DEV_ONLY"
SUMMARY_PATH_ENV_VAR = "LOAD_TEST_SUMMARY_PATH"
LOCUSTFILE_PATH = Path(__file__).resolve()


@dataclass(frozen=True)
class TaskDefinition:
    name: str
    method: str
    path: str
    weight: int


@dataclass(frozen=True)
class ScenarioConfig:
    name: str
    description: str
    users: int
    spawn_rate: int
    run_time: str
    tags: tuple[str, ...]
    thresholds: dict[str, float]
    tasks: tuple[TaskDefinition, ...]


COMMON_TASKS: tuple[TaskDefinition, ...] = (
    TaskDefinition("health_live", "GET", "/health/live", 1),
    TaskDefinition("list_posts", "GET", "/api/v1/posts", 4),
    TaskDefinition("create_post_dry_run", "POST", "/api/v1/posts?dry_run=true", 3),
    TaskDefinition("get_analytics", "GET", "/api/v1/analytics", 2),
)

BULK_TASKS: tuple[TaskDefinition, ...] = (
    TaskDefinition("health_live", "GET", "/health/live", 1),
    TaskDefinition("create_post_dry_run", "POST", "/api/v1/posts?dry_run=true", 2),
    TaskDefinition("create_content_bomb", "POST", "/api/v1/bombs", 6),
    TaskDefinition("list_posts", "GET", "/api/v1/posts", 1),
)

SCENARIO_PROFILES: dict[str, ScenarioConfig] = {
    "normal_user": ScenarioConfig(
        name="normal_user",
        description="Steady mixed traffic at 10 users/sec across common authenticated endpoints.",
        users=100,
        spawn_rate=10,
        run_time="5m",
        tags=("read_write_mix", "steady"),
        thresholds={"p95_ms": 100.0, "p99_ms": 250.0, "error_rate": 0.1},
        tasks=COMMON_TASKS,
    ),
    "spike": ScenarioConfig(
        name="spike",
        description=(
            "Abrupt ramp to 1000 users/sec for one minute to reveal "
            "queueing and burst limits."
        ),
        users=1000,
        spawn_rate=1000,
        run_time="1m",
        tags=("burst", "capacity"),
        thresholds={"p95_ms": 200.0, "p99_ms": 500.0, "error_rate": 1.0},
        tasks=COMMON_TASKS,
    ),
    "sustained": ScenarioConfig(
        name="sustained",
        description="Longer steady-state traffic at 100 users/sec for ten minutes.",
        users=1000,
        spawn_rate=100,
        run_time="10m",
        tags=("steady", "ten_minute"),
        thresholds={"p95_ms": 100.0, "p99_ms": 300.0, "error_rate": 0.1},
        tasks=COMMON_TASKS,
    ),
    "bulk_posting": ScenarioConfig(
        name="bulk_posting",
        description="Content Bomb focused traffic with repeated bomb creation and dry-run posting.",
        users=250,
        spawn_rate=25,
        run_time="5m",
        tags=("bombs", "write_heavy"),
        thresholds={"p95_ms": 150.0, "p99_ms": 400.0, "error_rate": 0.5},
        tasks=BULK_TASKS,
    ),
}


def active_scenario_name() -> str:
    scenario = os.getenv(SCENARIO_ENV_VAR, "normal_user").strip() or "normal_user"
    if scenario not in SCENARIO_PROFILES:
        available = ", ".join(sorted(SCENARIO_PROFILES))
        msg = f"Unknown load test scenario '{scenario}'. Expected one of: {available}"
        raise ValueError(msg)
    return scenario


ACTIVE_SCENARIO = active_scenario_name()


def scenario_profile(name: str | None = None) -> ScenarioConfig:
    return SCENARIO_PROFILES[name or ACTIVE_SCENARIO]


def profile_as_dict(name: str | None = None) -> dict[str, Any]:
    return asdict(scenario_profile(name))


def scenario_task_weight_sum(name: str | None = None) -> int:
    return sum(task.weight for task in scenario_profile(name).tasks)


def random_text(length: int = 48) -> str:
    alphabet = string.ascii_letters + string.digits + " "
    return "".join(random.choices(alphabet, k=length)).strip() or "load-test"


def build_dry_run_post_payload() -> dict[str, Any]:
    return {
        "text": f"Load test {random_text(24)}",
        "platforms": ["youtube"],
        "media_type": "text",
        "platform_options": {
            "youtube": {
                "title": f"Load test {random_text(16)}",
                "privacy": "public",
            },
        },
    }


def build_bomb_payload() -> dict[str, Any]:
    return {"topic": f"Load test topic {random_text(20)}"}


def request_definitions_for(name: str | None = None) -> list[dict[str, Any]]:
    return [
        {
            "name": task.name,
            "method": task.method,
            "path": task.path,
            "weight": task.weight,
        }
        for task in scenario_profile(name).tasks
    ]


def performance_summary(environment) -> dict[str, Any]:
    total = environment.stats.total
    total_requests = total.num_requests or 0
    total_failures = total.num_failures or 0
    error_rate = (total_failures / total_requests * 100.0) if total_requests else 0.0
    return {
        "scenario": ACTIVE_SCENARIO,
        "requests": total_requests,
        "failures": total_failures,
        "error_rate_pct": round(error_rate, 4),
        "p50_ms": round(total.get_response_time_percentile(0.50) or 0.0, 2),
        "p95_ms": round(total.get_response_time_percentile(0.95) or 0.0, 2),
        "p99_ms": round(total.get_response_time_percentile(0.99) or 0.0, 2),
        "avg_ms": round(total.avg_response_time or 0.0, 2),
        "rps": round(total.current_rps or 0.0, 2),
        "timestamp": int(time.time()),
    }


@events.quitting.add_listener
def write_summary(environment, **_kwargs) -> None:
    summary = performance_summary(environment)
    print(f"LOAD_TEST_SUMMARY={json.dumps(summary, sort_keys=True)}")

    summary_path = os.getenv(SUMMARY_PATH_ENV_VAR)
    if not summary_path:
        return

    path = Path(summary_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")


class ApiScenarioUser(HttpUser):
    abstract = True
    host = os.getenv("LOAD_TEST_HOST")
    headers = {"Content-Type": "application/json"}

    def on_start(self) -> None:
        self.client.get("/health/live", name="/health/live [GET]")
        api_key = os.getenv(API_KEY_ENV_VAR, DEFAULT_API_KEY).strip()
        self.client.headers.update({"X-API-Key": api_key, **self.headers})

    def list_posts(self) -> None:
        self.client.get("/api/v1/posts", params={"limit": "20"}, name="/api/v1/posts [GET]")

    def create_post_dry_run(self) -> None:
        self.client.post(
            "/api/v1/posts?dry_run=true",
            json=build_dry_run_post_payload(),
            name="/api/v1/posts?dry_run=true [POST]",
        )

    def get_analytics(self) -> None:
        self.client.get(
            "/api/v1/analytics",
            params={"period": "30d"},
            name="/api/v1/analytics [GET]",
        )

    def create_content_bomb(self) -> None:
        self.client.post(
            "/api/v1/bombs",
            json=build_bomb_payload(),
            name="/api/v1/bombs [POST]",
        )


class NormalUserScenario(ApiScenarioUser):
    weight = 10 if ACTIVE_SCENARIO == "normal_user" else 0
    wait_time = between(0.2, 1.0)

    @task(4)
    def task_list_posts(self) -> None:
        self.list_posts()

    @task(3)
    def task_create_post_dry_run(self) -> None:
        self.create_post_dry_run()

    @task(2)
    def task_get_analytics(self) -> None:
        self.get_analytics()


class SpikeScenario(ApiScenarioUser):
    weight = 10 if ACTIVE_SCENARIO == "spike" else 0
    wait_time = between(0.0, 0.2)

    @task(5)
    def task_list_posts(self) -> None:
        self.list_posts()

    @task(3)
    def task_create_post_dry_run(self) -> None:
        self.create_post_dry_run()

    @task(2)
    def task_get_analytics(self) -> None:
        self.get_analytics()


class SustainedScenario(ApiScenarioUser):
    weight = 10 if ACTIVE_SCENARIO == "sustained" else 0
    wait_time = between(0.1, 0.5)

    @task(5)
    def task_list_posts(self) -> None:
        self.list_posts()

    @task(3)
    def task_get_analytics(self) -> None:
        self.get_analytics()

    @task(2)
    def task_create_post_dry_run(self) -> None:
        self.create_post_dry_run()


class BulkPostingScenario(ApiScenarioUser):
    weight = 10 if ACTIVE_SCENARIO == "bulk_posting" else 0
    wait_time = between(0.2, 0.8)

    @task(6)
    def task_create_content_bomb(self) -> None:
        self.create_content_bomb()

    @task(2)
    def task_create_post_dry_run(self) -> None:
        self.create_post_dry_run()

    @task(1)
    def task_list_posts(self) -> None:
        self.list_posts()
