from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

LOCUSTFILE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "load_test" / "locustfile.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("contentflow_locustfile", LOCUSTFILE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_scenario_file_can_be_loaded() -> None:
    module = _load_module()

    assert module.LOCUSTFILE_PATH.name == "locustfile.py"
    assert set(module.SCENARIO_PROFILES) == {
        "normal_user",
        "spike",
        "sustained",
        "bulk_posting",
    }


def test_task_weight_sums_are_positive() -> None:
    module = _load_module()

    for scenario_name in module.SCENARIO_PROFILES:
        assert module.scenario_task_weight_sum(scenario_name) > 0


def test_task_definitions_are_valid() -> None:
    module = _load_module()

    for scenario_name in module.SCENARIO_PROFILES:
        for task in module.request_definitions_for(scenario_name):
            assert task["method"] in module.ALLOWED_METHODS
            assert task["path"].startswith("/")
            assert task["weight"] >= 1


def test_scenario_config_ranges_are_reasonable() -> None:
    module = _load_module()

    for scenario in module.SCENARIO_PROFILES.values():
        assert 1 <= scenario.users <= 5000
        assert 1 <= scenario.spawn_rate <= 2000
        assert scenario.run_time.endswith(("s", "m", "h"))
        assert 0 < scenario.thresholds["p95_ms"] <= scenario.thresholds["p99_ms"]
        assert 0 <= scenario.thresholds["error_rate"] <= 5.0


def test_import_does_not_require_docker_compose() -> None:
    source = LOCUSTFILE_PATH.read_text(encoding="utf-8")
    module = _load_module()

    assert "docker-compose" not in source
    assert "subprocess" not in source
    assert module.profile_as_dict("normal_user")["spawn_rate"] == 10
