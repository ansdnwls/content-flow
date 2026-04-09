"""Tests for vertical configuration integrity."""

from __future__ import annotations

import json
from pathlib import Path

VERTICALS_DIR = Path(__file__).resolve().parent.parent / "verticals"
SKIP_DIRS = {"_template", "node_modules", ".next"}

REQUIRED_CONFIG_FIELDS = ["id", "name", "brand", "domain", "pricing", "features"]
REQUIRED_BRAND_FIELDS = ["colors"]
REQUIRED_COLOR_FIELDS = ["primary", "secondary", "accent", "bg", "text"]
REQUIRED_DOMAIN_FIELDS = ["primary"]

HEX_COLOR_LEN = {4, 7}


def _get_verticals() -> list[Path]:
    return sorted(
        p
        for p in VERTICALS_DIR.iterdir()
        if p.is_dir() and p.name not in SKIP_DIRS
    )


def _load_config(vertical_dir: Path) -> dict:
    with open(vertical_dir / "config.json") as f:
        return json.load(f)


def test_config_has_required_fields() -> None:
    for vertical in _get_verticals():
        config = _load_config(vertical)
        for field in REQUIRED_CONFIG_FIELDS:
            assert field in config, (
                f"{vertical.name}/config.json missing '{field}'"
            )


def test_brand_color_format() -> None:
    for vertical in _get_verticals():
        config = _load_config(vertical)
        colors = config.get("brand", {}).get("colors", {})
        for key in REQUIRED_COLOR_FIELDS:
            assert key in colors, (
                f"{vertical.name} missing brand.colors.{key}"
            )
            value = colors[key]
            assert value.startswith("#"), (
                f"{vertical.name} brand.colors.{key} must start with #"
            )
            assert len(value) in HEX_COLOR_LEN, (
                f"{vertical.name} brand.colors.{key} invalid length: {value}"
            )
            hex_part = value[1:]
            assert all(c in "0123456789abcdefABCDEF" for c in hex_part), (
                f"{vertical.name} brand.colors.{key} invalid hex: {value}"
            )


def test_env_injection_variables() -> None:
    for vertical in _get_verticals():
        env_example = vertical / ".env.example"
        assert env_example.exists(), (
            f"{vertical.name} missing .env.example"
        )
        content = env_example.read_text(encoding="utf-8")
        assert "NEXT_PUBLIC_CF_API_URL" in content, (
            f"{vertical.name} .env.example missing NEXT_PUBLIC_CF_API_URL"
        )
        assert "NEXT_PUBLIC_CF_BRAND_NAME" in content, (
            f"{vertical.name} .env.example missing NEXT_PUBLIC_CF_BRAND_NAME"
        )
        assert "NEXT_PUBLIC_CF_PRIMARY_COLOR" in content, (
            f"{vertical.name} .env.example missing NEXT_PUBLIC_CF_PRIMARY_COLOR"
        )


def test_build_command_valid() -> None:
    for vertical in _get_verticals():
        vercel_path = vertical / "vercel.json"
        assert vercel_path.exists(), (
            f"{vertical.name} missing vercel.json"
        )
        with open(vercel_path) as f:
            vercel_config = json.load(f)
        assert "buildCommand" in vercel_config, (
            f"{vertical.name} vercel.json missing buildCommand"
        )
        build_cmd = vercel_config["buildCommand"]
        assert "build" in build_cmd, (
            f"{vertical.name} buildCommand doesn't contain 'build': {build_cmd}"
        )


def test_domain_format() -> None:
    for vertical in _get_verticals():
        config = _load_config(vertical)
        domain = config.get("domain", {})
        for key in REQUIRED_DOMAIN_FIELDS:
            assert key in domain, (
                f"{vertical.name} missing domain.{key}"
            )
        primary = domain.get("primary", "")
        assert "." in primary, (
            f"{vertical.name} domain.primary must contain a dot: {primary}"
        )
        assert not primary.startswith("http"), (
            f"{vertical.name} domain.primary should be bare domain, not URL: {primary}"
        )


def test_vertical_independence() -> None:
    configs = {}
    for vertical in _get_verticals():
        config = _load_config(vertical)
        vid = config.get("id", "")
        assert vid, f"{vertical.name} config.json missing 'id'"
        assert vid not in configs, (
            f"Duplicate vertical id '{vid}' in {vertical.name} "
            f"and {configs[vid]}"
        )
        configs[vid] = vertical.name

    domains = {}
    for vertical in _get_verticals():
        config = _load_config(vertical)
        primary = config.get("domain", {}).get("primary", "")
        if primary and primary != "example.com":
            assert primary not in domains, (
                f"Duplicate domain '{primary}' in {vertical.name} "
                f"and {domains[primary]}"
            )
            domains[primary] = vertical.name
