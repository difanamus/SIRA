"""Export active documents (verified text, chunks, embeddings; no PDF) to seed/knowledge.json.gz.

Run while the backend is stopped:  .\\.venv\\Scripts\\python.exe scripts\\export-seed.py
No OCR, embedding, or AI request is made.
"""

import gzip
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import chromadb  # noqa: E402
from chromadb.config import Settings as ChromaSettings  # noqa: E402

from backend.app.config import Settings  # noqa: E402
from backend.app.seed import DIMENSIONS, EMBEDDING_MODEL, EXTRA_TABLES, FORMAT, SEED_PATH, encode_vector  # noqa: E402

data_dir = Settings().data_dir
db = sqlite3.connect((data_dir / "app.sqlite3").as_uri() + "?mode=ro", uri=True)
db.row_factory = sqlite3.Row
client = chromadb.PersistentClient(path=str(data_dir / "chroma"), settings=ChromaSettings(anonymized_telemetry=False))
collection = client.get_collection("sira_openai_3_small_v1")

documents = []
for doc in db.execute(
    "SELECT d.id,d.title,d.filename,v.id AS version_id,v.sha256,v.size,v.page_count,v.warning,v.ocr_mode "
    "FROM documents d JOIN versions v ON v.id=d.active_version "
    "WHERE d.deleted=0 AND v.status='ready' ORDER BY d.created"
):
    version_id = doc["version_id"]
    chunks = db.execute(
        "SELECT id,page,heading,text FROM chunks WHERE version_id=? ORDER BY page,id", (version_id,)
    ).fetchall()
    stored = collection.get(ids=[c["id"] for c in chunks], include=["embeddings"])
    vectors = dict(zip(stored["ids"], stored["embeddings"]))
    missing = [c["id"] for c in chunks if c["id"] not in vectors]
    if missing:
        raise SystemExit(f"Embedding tidak lengkap untuk {doc['title']}: {len(missing)} chunk.")
    entry = {
        "id": doc["id"],
        "title": doc["title"],
        "filename": doc["filename"],
        "version": {
            "id": version_id,
            "sha256": doc["sha256"],
            "size": doc["size"],
            "page_count": doc["page_count"],
            "warning": doc["warning"],
            "ocr_mode": doc["ocr_mode"],
        },
        "pages": [
            dict(row)
            for row in db.execute(
                "SELECT number,text,method,warning FROM pages WHERE version_id=? ORDER BY number", (version_id,)
            )
        ],
        "chunks": [
            {**dict(c), "embedding": encode_vector([float(x) for x in vectors[c["id"]]])} for c in chunks
        ],
    }
    for table in EXTRA_TABLES:
        entry[table] = [dict(row) for row in db.execute(f"SELECT * FROM {table} WHERE version_id=?", (version_id,))]
    documents.append(entry)
    print(f"{doc['title']}: {len(entry['pages'])} halaman, {len(chunks)} chunk")

if not documents:
    raise SystemExit("Tidak ada dokumen siap untuk diekspor.")
SEED_PATH.parent.mkdir(exist_ok=True)
payload = {"format": FORMAT, "embedding_model": EMBEDDING_MODEL, "dimensions": DIMENSIONS, "documents": documents}
with gzip.open(SEED_PATH, "wt", encoding="utf-8", compresslevel=9) as handle:
    json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
print(f"Seed: {SEED_PATH.relative_to(ROOT)} ({SEED_PATH.stat().st_size // 1024} KiB)")
