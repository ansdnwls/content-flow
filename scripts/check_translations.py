#!/usr/bin/env python3
"""Check that all translation files have consistent keys across locales."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def flatten_keys(obj: dict, prefix: str = "") -> set[str]:
    """Recursively flatten JSON keys into dot-separated paths."""
    keys: set[str] = set()
    for k, v in obj.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(flatten_keys(v, full))
        else:
            keys.add(full)
    return keys


def check_message_dir(label: str, messages_dir: Path) -> int:
    """Check one message directory, return number of issues found."""
    errors = 0
    locales: dict[str, set[str]] = {}
    for path in sorted(messages_dir.glob("*.json")):
        locale = path.stem
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        locales[locale] = flatten_keys(data)
        print(f"  {locale}: {len(locales[locale])} keys")

    if not locales:
        print(f"  WARNING: No JSON files in {messages_dir}")
        return 0

    reference_locale = sorted(locales.keys())[0]
    reference_keys = locales[reference_locale]

    for locale, keys in sorted(locales.items()):
        if locale == reference_locale:
            continue
        missing = reference_keys - keys
        extra = keys - reference_keys
        if missing:
            print(f"  MISSING in {locale} (present in {reference_locale}):")
            for k in sorted(missing):
                print(f"    - {k}")
            errors += len(missing)
        if extra:
            print(f"  EXTRA in {locale} (not in {reference_locale}):")
            for k in sorted(extra):
                print(f"    + {k}")
            errors += len(extra)

    if errors == 0:
        print(f"  OK - all {label} locales consistent")
    return errors


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    message_dirs = [
        ("dashboard", project_root / "dashboard" / "messages"),
        ("landing", project_root / "landing" / "messages"),
    ]

    errors = 0
    for label, messages_dir in message_dirs:
        if not messages_dir.exists():
            print(f"  SKIP: {label} messages directory not found")
            continue
        print(f"\n--- {label} ---")
        errors += check_message_dir(label, messages_dir)

    # Also check backend i18n consistency
    print("\n--- Backend i18n ---")
    try:
        sys.path.insert(0, str(project_root))
        from app.core.i18n import _MESSAGES, EMAIL_SUBJECTS

        en_msg_keys = set(_MESSAGES["en"].keys())
        en_subj_keys = set(EMAIL_SUBJECTS["en"].keys())
        for loc in ("ko", "ja"):
            msg_missing = en_msg_keys - set(_MESSAGES[loc].keys())
            subj_missing = en_subj_keys - set(EMAIL_SUBJECTS[loc].keys())
            if msg_missing:
                print(f"  MISSING messages in {loc}: {msg_missing}")
                errors += len(msg_missing)
            if subj_missing:
                print(f"  MISSING subjects in {loc}: {subj_missing}")
                errors += len(subj_missing)
        if errors == 0:
            print("  All backend locales consistent")
    except ImportError as e:
        print(f"  WARNING: Could not import backend i18n: {e}")

    if errors:
        print(f"\nFAILED: {errors} translation inconsistencies found")
        return 1

    print("\nOK: All translations are consistent across locales")
    return 0


if __name__ == "__main__":
    sys.exit(main())
