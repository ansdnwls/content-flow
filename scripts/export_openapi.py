"""Export the OpenAPI schema from the FastAPI app to docs/openapi.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402


def main() -> None:
    schema = app.openapi()
    output = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI schema exported to {output}")


if __name__ == "__main__":
    main()
