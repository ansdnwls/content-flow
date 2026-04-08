#!/usr/bin/env python3
"""Scan codebase for leaked secrets. Exit 1 if any pattern matches.

Usage:
    python scripts/secret_scan.py          # scan working tree
    python scripts/secret_scan.py --git    # also scan git history
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Stripe live key", re.compile(r"sk_live_[0-9a-zA-Z]{24,}")),
    ("Stripe test key", re.compile(r"sk_test_[0-9a-zA-Z]{24,}")),
    ("ContentFlow live key", re.compile(r"cf_live_[0-9a-zA-Z]{24,}")),
    ("ContentFlow test key", re.compile(r"cf_test_[0-9a-zA-Z]{24,}")),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("JWT token", re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.")),
    ("Private key header", re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")),
    ("Generic secret assignment", re.compile(
        r"""(?:secret|password|token)\s*=\s*['"][^'"]{8,}['"]""",
        re.IGNORECASE,
    )),
]

IGNORE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".mypy_cache", ".ruff_cache", ".pytest_cache", "dist", "build",
    ".omc", ".claude",
}

IGNORE_FILES = {
    "secret_scan.py",  # this file itself
    "SECURITY_AUDIT.md",
    "PENTEST_SCENARIOS.md",
}

SCAN_EXTENSIONS = {
    ".py", ".js", ".ts", ".json", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".env", ".sh", ".md",
}


def _should_scan(path: Path) -> bool:
    parts = set(path.parts)
    if parts & IGNORE_DIRS:
        return False
    if path.name in IGNORE_FILES:
        return False
    if path.suffix not in SCAN_EXTENSIONS:
        return False
    return True


def scan_file(path: Path) -> list[tuple[str, int, str]]:
    """Return list of (pattern_name, line_number, line_text) matches."""
    findings: list[tuple[str, int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings

    for line_no, line in enumerate(text.splitlines(), start=1):
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append((name, line_no, line.strip()[:120]))
    return findings


def scan_working_tree(root: Path) -> list[tuple[Path, str, int, str]]:
    """Scan all files under *root*."""
    results: list[tuple[Path, str, int, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if not _should_scan(path.relative_to(root)):
            continue
        for name, line_no, snippet in scan_file(path):
            results.append((path.relative_to(root), name, line_no, snippet))
    return results


def scan_git_history(root: Path) -> list[tuple[str, str, str]]:
    """Scan git log diffs for secret patterns."""
    results: list[tuple[str, str, str]] = []
    try:
        log = subprocess.run(
            ["git", "log", "-p", "--diff-filter=A", "--no-color", "-100"],
            capture_output=True, text=True, cwd=root, timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return results

    current_commit = ""
    for line in log.stdout.splitlines():
        if line.startswith("commit "):
            current_commit = line.split()[1][:12]
        if not line.startswith("+"):
            continue
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                results.append((current_commit, name, line[1:].strip()[:120]))
    return results


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    scan_history = "--git" in sys.argv

    print(f"Scanning {root} for secrets...")
    tree_findings = scan_working_tree(root)
    history_findings: list[tuple[str, str, str]] = []

    if scan_history:
        print("Scanning git history (last 100 commits)...")
        history_findings = scan_git_history(root)

    total = len(tree_findings) + len(history_findings)

    if tree_findings:
        print(f"\n{'='*60}")
        print(f"WORKING TREE: {len(tree_findings)} secret(s) found")
        print(f"{'='*60}")
        for path, name, line_no, snippet in tree_findings:
            print(f"  [{name}] {path}:{line_no}")
            print(f"    {snippet}")

    if history_findings:
        print(f"\n{'='*60}")
        print(f"GIT HISTORY: {len(history_findings)} secret(s) found")
        print(f"{'='*60}")
        for commit, name, snippet in history_findings:
            print(f"  [{name}] commit {commit}")
            print(f"    {snippet}")

    if total == 0:
        print("No secrets found.")
        return 0

    print(f"\nTotal: {total} potential secret(s) detected.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
