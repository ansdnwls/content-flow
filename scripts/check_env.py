#!/usr/bin/env python3
"""CLI tool to check environment readiness before deployment.

Usage:
    python scripts/check_env.py          # uses current env / .env
    python scripts/check_env.py --env production
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.core.config_validator import (  # noqa: E402
    OPTIONAL_VARS,
    RECOMMENDED_VARS,
    REQUIRED_VARS,
    validate_config,
)


def _mask(value: str | None) -> str:
    """Mask a secret value for display (show first 4 chars)."""
    if value is None or value == "":
        return "(not set)"
    if len(value) <= 6:
        return "****"
    return value[:4] + "****"


def main() -> None:
    parser = argparse.ArgumentParser(description="Check ContentFlow environment variables.")
    parser.add_argument(
        "--env",
        default=None,
        help="Override APP_ENV for validation (e.g. production, staging, development).",
    )
    args = parser.parse_args()

    settings = get_settings()

    if args.env:
        # Temporarily override APP_ENV on the settings object for validation.
        object.__setattr__(settings, "app_env", args.env)

    result = validate_config(settings)

    print(f"\n{'='*60}")
    print(f"  ContentFlow Environment Check  (APP_ENV={getattr(settings, 'app_env', 'unknown')})")
    print(f"{'='*60}\n")

    # --- Required ---
    print("Required variables:")
    for var in REQUIRED_VARS:
        val = getattr(settings, var.lower(), None)
        status = "OK" if val not in (None, "") else "MISSING"
        print(f"  {status:>7}  {var} = {_mask(str(val) if val else None)}")

    # --- Recommended ---
    print("\nRecommended variables:")
    for var in RECOMMENDED_VARS:
        val = getattr(settings, var.lower(), None)
        status = "OK" if val not in (None, "") else "MISSING"
        print(f"  {status:>7}  {var} = {_mask(str(val) if val else None)}")

    # --- Optional ---
    print("\nOptional variables:")
    for var in OPTIONAL_VARS:
        val = getattr(settings, var.lower(), None)
        status = "OK" if val not in (None, "") else "---"
        print(f"  {status:>7}  {var} = {_mask(str(val) if val else None)}")

    # --- Summary ---
    print(f"\n{'='*60}")
    if result.errors:
        print(f"  ERRORS ({len(result.errors)}):")
        for e in result.errors:
            print(f"    - {e}")
    if result.warnings:
        print(f"  WARNINGS ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"    - {w}")
    if result.ok and not result.warnings:
        print("  All checks passed!")
    print(f"{'='*60}\n")

    sys.exit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
