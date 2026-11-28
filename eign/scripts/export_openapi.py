"""Export the OpenAPI schema of the Eign API into ``eign/api/openapi.yaml``.

The schema is generated from the FastAPI application and committed, so that
clients (the Next.js frontend and any other consumer) can generate types from a
stable file and see contract changes in code review.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

EIGN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EIGN_DIR))

from app.main import create_app  # noqa: E402  (path setup must come first)

OPENAPI_VERSION = "3.2.0"
OUTPUT = EIGN_DIR / "api" / "openapi.yaml"


def build_schema() -> dict[str, object]:
    """Generate the OpenAPI schema with the requested document version."""
    app = create_app()
    app.openapi_version = OPENAPI_VERSION
    return app.openapi()


def main() -> None:
    """Write the schema next to the backend sources."""
    schema = build_schema()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        yaml.safe_dump(schema, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    paths = schema["paths"]
    print(f"wrote {OUTPUT} ({len(paths)} paths, OpenAPI {schema['openapi']})")


if __name__ == "__main__":
    main()
