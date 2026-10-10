"""Export the OpenAPI schema to docs/openapi.json without starting the server or calling AI."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.main import create_app  # noqa: E402

schema = create_app(start_ingestion=False).openapi()
schema["servers"] = [{"url": "http://127.0.0.1:8000", "description": "SIRA lokal (start.ps1)"}]
target = ROOT / "docs" / "openapi.json"
target.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"OpenAPI {schema['openapi']}: {len(schema['paths'])} path -> {target.relative_to(ROOT)}")
