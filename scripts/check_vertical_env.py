"""Pre-build validator for vertical environment variables.

Usage:
    python scripts/check_vertical_env.py verticals/ytboost
    python scripts/check_vertical_env.py verticals/shopsync
    python scripts/check_vertical_env.py  # checks all verticals
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REQUIRED_ENV_VARS = [
    "NEXT_PUBLIC_CF_API_URL",
    "NEXT_PUBLIC_CF_BRAND_NAME",
    "NEXT_PUBLIC_CF_PRIMARY_COLOR",
]

REQUIRED_CONFIG_FIELDS = ["id", "name", "brand", "domain"]

HEX_COLOR_PATTERN_LEN = {4, 7}

SKIP_DIRS = {"_template", "node_modules", ".next"}


def validate_hex_color(value: str) -> bool:
    """Check that a string is a valid hex color (#RGB or #RRGGBB)."""
    if not value.startswith("#"):
        return False
    hex_part = value[1:]
    if len(value) not in HEX_COLOR_PATTERN_LEN:
        return False
    return all(c in "0123456789abcdefABCDEF" for c in hex_part)


def validate_url(value: str) -> bool:
    """Basic URL format check."""
    return value.startswith("https://") or value.startswith("http://")


def check_config(vertical_dir: Path) -> list[str]:
    """Validate config.json in the vertical directory."""
    errors: list[str] = []
    config_path = vertical_dir / "config.json"
    if not config_path.exists():
        errors.append(f"Missing config.json in {vertical_dir.name}")
        return errors

    try:
        with open(config_path) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON in config.json: {e}")
        return errors

    for field in REQUIRED_CONFIG_FIELDS:
        if field not in config:
            errors.append(f"Missing required field '{field}' in config.json")

    brand = config.get("brand", {})
    colors = brand.get("colors", {})
    if "primary" in colors and not validate_hex_color(colors["primary"]):
        errors.append(f"Invalid primary color format: {colors['primary']}")

    domain = config.get("domain", {})
    if "primary" in domain:
        d = domain["primary"]
        if "." not in d or d.startswith("http"):
            errors.append(f"Invalid domain format: {d} (use bare domain, not URL)")

    return errors


def check_env(vertical_dir: Path) -> list[str]:
    """Check that required env vars are available (from .env.local or os.environ)."""
    errors: list[str] = []
    env_local = vertical_dir / ".env.local"

    local_vars: dict[str, str] = {}
    if env_local.exists():
        with open(env_local) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    local_vars[key.strip()] = val.strip()

    for var in REQUIRED_ENV_VARS:
        value = local_vars.get(var) or os.environ.get(var)
        if not value:
            errors.append(f"Missing env var: {var}")
            continue

        if var == "NEXT_PUBLIC_CF_API_URL" and not validate_url(value):
            errors.append(f"{var} must be a valid URL, got: {value}")
        if var == "NEXT_PUBLIC_CF_PRIMARY_COLOR" and not validate_hex_color(value):
            errors.append(f"{var} must be a hex color, got: {value}")

    return errors


def check_vercel_json(vertical_dir: Path) -> list[str]:
    """Validate vercel.json exists and has required fields."""
    errors: list[str] = []
    vercel_path = vertical_dir / "vercel.json"
    if not vercel_path.exists():
        errors.append("Missing vercel.json")
        return errors

    try:
        with open(vercel_path) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON in vercel.json: {e}")
        return errors

    if "framework" not in config:
        errors.append("vercel.json missing 'framework' field")
    if "buildCommand" not in config:
        errors.append("vercel.json missing 'buildCommand' field")

    return errors


def check_vertical(vertical_dir: Path) -> list[str]:
    """Run all checks for a single vertical."""
    errors: list[str] = []
    errors.extend(check_config(vertical_dir))
    errors.extend(check_env(vertical_dir))
    errors.extend(check_vercel_json(vertical_dir))
    return errors


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    verticals_dir = project_root / "verticals"

    if len(sys.argv) > 1:
        targets = [Path(sys.argv[1]).resolve()]
    else:
        targets = sorted(
            p
            for p in verticals_dir.iterdir()
            if p.is_dir() and p.name not in SKIP_DIRS
        )

    total_errors: list[str] = []
    for target in targets:
        print(f"Checking {target.name}...")
        errors = check_vertical(target)
        for e in errors:
            print(f"  ERROR: {e}")
        total_errors.extend(errors)

    if total_errors:
        print(f"\n{len(total_errors)} error(s) found.")
        return 1

    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
