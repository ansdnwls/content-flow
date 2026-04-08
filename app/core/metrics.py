"""In-process metrics registry with Prometheus text rendering."""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from threading import Lock


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _format_labels(label_names: tuple[str, ...], label_values: tuple[str, ...]) -> str:
    if not label_names:
        return ""
    rendered = ",".join(
        f'{name}="{_escape(value)}"'
        for name, value in zip(label_names, label_values, strict=True)
    )
    return f"{{{rendered}}}"


class CounterMetric:
    def __init__(self, name: str, description: str, label_names: tuple[str, ...]) -> None:
        self.name = name
        self.description = description
        self.label_names = label_names
        self._values: defaultdict[tuple[str, ...], float] = defaultdict(float)
        self._lock = Lock()

    def inc(self, labels: dict[str, str], amount: float = 1.0) -> None:
        key = tuple(labels[name] for name in self.label_names)
        with self._lock:
            self._values[key] += amount

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.description}", f"# TYPE {self.name} counter"]
        for key, value in sorted(self._values.items()):
            lines.append(f"{self.name}{_format_labels(self.label_names, key)} {value}")
        return lines


class GaugeMetric:
    def __init__(self, name: str, description: str, label_names: tuple[str, ...]) -> None:
        self.name = name
        self.description = description
        self.label_names = label_names
        self._values: dict[tuple[str, ...], float] = {}
        self._lock = Lock()

    def set(self, labels: dict[str, str], value: float) -> None:
        key = tuple(labels[name] for name in self.label_names)
        with self._lock:
            self._values[key] = value

    def get(self, labels: dict[str, str]) -> float:
        key = tuple(labels[name] for name in self.label_names)
        return self._values.get(key, 0.0)

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.description}", f"# TYPE {self.name} gauge"]
        for key, value in sorted(self._values.items()):
            lines.append(f"{self.name}{_format_labels(self.label_names, key)} {value}")
        return lines


class HistogramMetric:
    def __init__(
        self,
        name: str,
        description: str,
        label_names: tuple[str, ...],
        buckets: tuple[float, ...],
    ) -> None:
        self.name = name
        self.description = description
        self.label_names = label_names
        self.buckets = buckets
        self._bucket_counts: defaultdict[tuple[str, ...], list[int]] = defaultdict(
            lambda: [0 for _ in range(len(self.buckets) + 1)],
        )
        self._count: defaultdict[tuple[str, ...], int] = defaultdict(int)
        self._sum: defaultdict[tuple[str, ...], float] = defaultdict(float)
        self._lock = Lock()

    def observe(self, labels: dict[str, str], value: float) -> None:
        key = tuple(labels[name] for name in self.label_names)
        bucket_index = bisect_right(self.buckets, value)
        with self._lock:
            self._bucket_counts[key][bucket_index] += 1
            self._count[key] += 1
            self._sum[key] += value

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.description}", f"# TYPE {self.name} histogram"]
        for key, counts in sorted(self._bucket_counts.items()):
            cumulative = 0
            for bucket, count in zip(self.buckets, counts[:-1], strict=True):
                cumulative += count
                labels = dict(zip(self.label_names, key, strict=True))
                labels["le"] = str(bucket)
                all_label_names = (*self.label_names, "le")
                all_label_values = (*key, str(bucket))
                lines.append(
                    f"{self.name}_bucket"
                    f"{_format_labels(all_label_names, all_label_values)} {cumulative}"
                )
            cumulative += counts[-1]
            inf_label_names = (*self.label_names, "le")
            inf_label_values = (*key, "+Inf")
            lines.append(
                f"{self.name}_bucket"
                f"{_format_labels(inf_label_names, inf_label_values)} {cumulative}"
            )
            labels_text = _format_labels(self.label_names, key)
            lines.append(f"{self.name}_count{labels_text} {self._count[key]}")
            lines.append(f"{self.name}_sum{labels_text} {self._sum[key]}")
        return lines


HTTP_REQUESTS_TOTAL = CounterMetric(
    "http_requests_total",
    "Total HTTP requests served.",
    ("method", "path", "status"),
)
HTTP_REQUEST_DURATION_SECONDS = HistogramMetric(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "path"),
    (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
CELERY_TASKS_TOTAL = CounterMetric(
    "celery_tasks_total",
    "Total Celery task executions.",
    ("task_name", "status"),
)
PLATFORM_POSTS_TOTAL = CounterMetric(
    "platform_posts_total",
    "Platform post outcomes.",
    ("platform", "status"),
)
WEBHOOK_DELIVERIES_TOTAL = CounterMetric(
    "webhook_deliveries_total",
    "Webhook delivery state transitions.",
    ("status",),
)
ACTIVE_WORKERS = GaugeMetric(
    "contentflow_active_workers",
    "Number of active Celery workers.",
    tuple(),
)
QUEUE_DEPTH = GaugeMetric(
    "contentflow_queue_depth",
    "Approximate queued Celery jobs.",
    tuple(),
)
DB_CONNECTIONS = GaugeMetric(
    "contentflow_db_connections",
    "Basic database connectivity indicator.",
    tuple(),
)


def record_http_request(method: str, path: str, status: int, duration_seconds: float) -> None:
    labels = {"method": method, "path": path, "status": str(status)}
    HTTP_REQUESTS_TOTAL.inc(labels)
    HTTP_REQUEST_DURATION_SECONDS.observe({"method": method, "path": path}, duration_seconds)


def record_celery_task(task_name: str, status: str) -> None:
    CELERY_TASKS_TOTAL.inc({"task_name": task_name, "status": status})


def record_platform_post(platform: str, status: str) -> None:
    PLATFORM_POSTS_TOTAL.inc({"platform": platform, "status": status})


def record_webhook_delivery(status: str) -> None:
    WEBHOOK_DELIVERIES_TOTAL.inc({"status": status})


def set_runtime_gauges(*, active_workers: int, queue_depth: int, db_connections: int) -> None:
    ACTIVE_WORKERS.set({}, active_workers)
    QUEUE_DEPTH.set({}, queue_depth)
    DB_CONNECTIONS.set({}, db_connections)


def render_prometheus_text() -> str:
    chunks: list[str] = []
    for metric in (
        HTTP_REQUESTS_TOTAL,
        HTTP_REQUEST_DURATION_SECONDS,
        CELERY_TASKS_TOTAL,
        PLATFORM_POSTS_TOTAL,
        WEBHOOK_DELIVERIES_TOTAL,
        ACTIVE_WORKERS,
        QUEUE_DEPTH,
        DB_CONNECTIONS,
    ):
        chunks.extend(metric.render())
    return "\n".join(chunks) + "\n"
