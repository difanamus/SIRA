"""Bundled knowledge base: applied once, editable/deletable, never re-imported."""

import gzip
import json

from fastapi.testclient import TestClient

from backend.app import seed
from backend.app.config import Settings
from backend.app.db import Database
from backend.app.main import create_app
from backend.app.security import hasher
from backend.app.vectors import VectorStore


def write_seed(path):
    vector = seed.encode_vector([1.0] + [0.0] * 1535)
    payload = {
        "format": 1,
        "embedding_model": "text-embedding-3-small",
        "dimensions": 1536,
        "documents": [
            {
                "id": "doc-seed",
                "title": "Pengumuman Contoh",
                "filename": "contoh.pdf",
                "version": {
                    "id": "ver-seed",
                    "sha256": "0" * 64,
                    "size": 10,
                    "page_count": 1,
                    "warning": "",
                    "ocr_mode": "auto",
                },
                "pages": [{"number": 1, "text": "Syarat pangkat minimal Abripda.", "method": "text", "warning": ""}],
                "chunks": [
                    {"id": "ver-seed:1:0", "page": 1, "heading": "", "text": "Syarat pangkat minimal Abripda.",
                     "embedding": vector}
                ],
                "ocr_regions": [],
                "ocr_page_jobs": [],
            }
        ],
    }
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return path


def test_vector_roundtrip():
    values = [0.5, -1.25, 3.0]
    assert seed.decode_vector(seed.encode_vector(values)) == values


def test_seed_applies_once_and_not_after_delete(tmp_path):
    path = write_seed(tmp_path / "seed.json.gz")
    db, store = Database(tmp_path / "data"), VectorStore(tmp_path / "data")
    revision = db.revision
    assert seed.apply_seed(db, store, path=path) == 1
    doc = db.one("SELECT * FROM documents")
    version = db.one("SELECT * FROM versions WHERE id=?", (doc["active_version"],))
    assert version["status"] == "ready" and version["path"] == ""
    assert db.one("SELECT COUNT(*) AS n FROM chunks")["n"] == 1
    assert store.search([1.0] + [0.0] * 1535, ["ver-seed"]) and db.revision == revision + 1
    db.execute("UPDATE documents SET deleted=1")
    assert seed.apply_seed(db, store, path=path) == 0
    assert db.one("SELECT COUNT(*) AS n FROM documents WHERE deleted=0")["n"] == 0


def test_existing_installation_and_disabled_seed_are_untouched(tmp_path):
    path = write_seed(tmp_path / "seed.json.gz")
    db, store = Database(tmp_path / "a"), VectorStore(tmp_path / "a")
    assert seed.apply_seed(db, store, path=path, enabled=False) == 0
    db.execute("INSERT INTO documents(id,title,filename,created) VALUES ('own','Milik admin','a.pdf',0)")
    assert seed.apply_seed(db, store, path=path) == 0
    assert seed.apply_seed(db, store, path=path) == 0  # marked; never imports later
    assert [row["id"] for row in db.rows("SELECT id FROM documents")] == ["own"]


def test_seeded_document_is_editable_deletable_and_explains_missing_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(seed, "SEED_PATH", write_seed(tmp_path / "seed.json.gz"))
    settings = Settings(data_dir=tmp_path / "data", relay_url="https://relay.example", relay_token="test-only",
                        vision_enabled=False, seed_enabled=True)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        ctx = app.state.ctx
        ctx.db.execute("INSERT INTO admin VALUES (1,?,?)", ("admin", hasher.hash("test-password-only")))
        login = client.post("/api/admin/login", json={"username": "admin", "password": "test-password-only"})
        client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        documents = client.get("/api/admin/documents").json()
        assert [d["title"] for d in documents] == ["Pengumuman Contoh"] and documents[0]["available"] == 1
        assert client.patch("/api/admin/documents/doc-seed", json={"title": "Judul baru"}).status_code == 200
        for route in ("read-ai", "review"):
            response = client.post(f"/api/admin/documents/doc-seed/{route}")
            assert response.status_code == 409 and "Ganti file" in response.json()["detail"]
        assert client.delete("/api/admin/documents/doc-seed").status_code == 200
        ctx.ingestion.cleanup_deleted()
        assert ctx.db.one("SELECT COUNT(*) AS n FROM versions")["n"] == 0
        assert ctx.db.one("SELECT COUNT(*) AS n FROM chunks")["n"] == 0
    with TestClient(create_app(settings=settings)) as client:  # restart: deleted seed stays deleted
        assert client.app.state.ctx.db.one("SELECT COUNT(*) AS n FROM documents WHERE deleted=0")["n"] == 0
