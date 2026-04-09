"""Backward-compatible shim for the primary Locust scenarios."""

from __future__ import annotations

from pathlib import Path

LOCUSTFILE_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "load_test" / "locustfile.py"
)

globals()["__file__"] = str(LOCUSTFILE_PATH)
exec(LOCUSTFILE_PATH.read_text(encoding="utf-8"), globals(), globals())
