"""Generate OpenAPI specification from FastAPI app.

This script statically generates the OpenAPI specification (openapi.json) from the
FastAPI application without running the server or connecting to databases.

Usage:
    cd backend
    uv run python scripts/generate_openapi.py

The generated spec is saved to backend/openapi.json and should be committed to the
repository for frontend type generation.
"""

import json
import os
from pathlib import Path

# Disable OpenTelemetry during spec generation to avoid warnings
os.environ["OTEL_ENABLED"] = "false"

# Import app without triggering lifespan/database connections
from app.main import app


def main() -> None:
    """Generate openapi.json from FastAPI app."""
    output_path = Path(__file__).parent.parent / "openapi.json"
    spec = app.openapi()
    output_path.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"✅ Generated: {output_path}")
    print(f"📄 Title: {spec.get('info', {}).get('title')}")
    print(f"🔢 Version: {spec.get('info', {}).get('version')}")
    print(f"🛣️  Paths: {len(spec.get('paths', {}))}")
    print(f"📦 Schemas: {len(spec.get('components', {}).get('schemas', {}))}")


if __name__ == "__main__":
    main()
