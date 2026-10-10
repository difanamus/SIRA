"""Bundled starter knowledge base, applied once to a fresh installation.

The seed holds verified page text, chunks, and embeddings of the sample documents, but not
the PDF files. Imported documents behave like uploaded ones: admins can rename, replace, or
delete them. Features that need the original PDF (page images, AI re-read) stay unavailable
until the admin replaces the file.
"""

import base64
import gzip
import json
import logging
import struct
import time

from .config import ROOT

log = logging.getLogger("sira.seed")
SEED_PATH = ROOT / "seed" / "knowledge.json.gz"
FORMAT = 1
EMBEDDING_MODEL = "text-embedding-3-small"
DIMENSIONS = 1536
EXTRA_TABLES = ("ocr_regions", "ocr_page_jobs")


def encode_vector(values):
    return base64.b64encode(struct.pack(f"<{len(values)}f", *values)).decode("ascii")


def decode_vector(text):
    raw = base64.b64decode(text)
    return list(struct.unpack(f"<{len(raw) // 4}f", raw))


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("format") != FORMAT:
        raise ValueError("Format seed tidak dikenal.")
    if data.get("embedding_model") != EMBEDDING_MODEL or data.get("dimensions") != DIMENSIONS:
        raise ValueError("Model embedding seed berbeda dari aplikasi.")
    return data


def _applied(db):
    return db.one("SELECT value FROM meta WHERE key='seed_applied'") is not None


def _mark(conn, value):
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('seed_applied',?)", (value,))


def apply_seed(db, vectors, path=None, enabled=True):
    """Import the seed once. Never runs again after admins edit or delete documents."""
    path = path or SEED_PATH
    if _applied(db):
        return 0
    if not enabled or not path.exists():
        return 0
    if db.one("SELECT 1 FROM documents LIMIT 1"):
        # Existing installation: keep its own knowledge base untouched.
        with db.connect() as conn:
            _mark(conn, 0)
        return 0
    data = load(path)
    chunks, embeddings = [], []
    for doc in data["documents"]:
        version_id = doc["version"]["id"]
        for chunk in doc["chunks"]:
            vector = decode_vector(chunk["embedding"])
            if len(vector) != DIMENSIONS:
                raise ValueError("Dimensi embedding seed tidak valid.")
            chunks.append({"id": chunk["id"], "version_id": version_id, "page": chunk["page"]})
            embeddings.append(vector)
    # Vectors first: upsert is idempotent if the database step later fails and is retried.
    if chunks:
        vectors.add(chunks, embeddings)
    now = time.time()
    with db.connect() as conn:
        for offset, doc in enumerate(data["documents"]):
            version = doc["version"]
            created = now + offset / 1000  # keep the seed order in the admin list
            conn.execute(
                "INSERT INTO documents(id,title,filename,active_version,deleted,created) VALUES (?,?,?,?,0,?)",
                (doc["id"], doc["title"], doc["filename"], version["id"], created),
            )
            conn.execute(
                "INSERT INTO versions(id,document_id,path,sha256,size,status,stage,progress,page_count,warning,"
                "ocr_mode,created) VALUES (?,?,'',?,?,'ready','Siap digunakan',100,?,?,?,?)",
                (
                    version["id"],
                    doc["id"],
                    version["sha256"],
                    version["size"],
                    version["page_count"],
                    version["warning"],
                    version["ocr_mode"],
                    created,
                ),
            )
            conn.executemany(
                "INSERT INTO pages(version_id,number,text,method,warning) VALUES (?,?,?,?,?)",
                [(version["id"], p["number"], p["text"], p["method"], p["warning"]) for p in doc["pages"]],
            )
            conn.executemany(
                "INSERT INTO chunks(id,version_id,page,heading,text) VALUES (?,?,?,?,?)",
                [(c["id"], version["id"], c["page"], c["heading"], c["text"]) for c in doc["chunks"]],
            )
            for table in EXTRA_TABLES:
                rows = doc.get(table, [])
                if rows:
                    columns = list(rows[0])
                    conn.executemany(
                        f"INSERT INTO {table}({','.join(columns)}) VALUES ({','.join('?' * len(columns))})",
                        [[version["id"] if column == "version_id" else row[column] for column in columns] for row in rows],
                    )
        _mark(conn, 1)
        conn.execute("UPDATE meta SET value=value+1 WHERE key='kb_revision'")
    log.info("seed_applied documents=%s chunks=%s", len(data["documents"]), len(chunks))
    return len(data["documents"])
