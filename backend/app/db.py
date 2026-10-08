import sqlite3
import time
from contextlib import contextmanager

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value INTEGER NOT NULL);
INSERT OR IGNORE INTO meta VALUES ('schema_version',1),('kb_revision',0);
CREATE TABLE IF NOT EXISTS admin(id INTEGER PRIMARY KEY CHECK(id=1), username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS admin_sessions(token_hash TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, title TEXT NOT NULL, filename TEXT NOT NULL, active_version TEXT, pending_version TEXT, deleted INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS versions(id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id), path TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL DEFAULT 'Menunggu antrean', progress INTEGER NOT NULL DEFAULT 0, page_count INTEGER NOT NULL DEFAULT 0, warning TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '', created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS pages(version_id TEXT NOT NULL REFERENCES versions(id), number INTEGER NOT NULL, text TEXT NOT NULL, method TEXT NOT NULL, warning TEXT NOT NULL, PRIMARY KEY(version_id,number));
CREATE TABLE IF NOT EXISTS review_pages(version_id TEXT NOT NULL REFERENCES versions(id), number INTEGER NOT NULL, text TEXT NOT NULL, method TEXT NOT NULL, warning TEXT NOT NULL, confirmed INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(version_id,number));
CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES versions(id), page INTEGER NOT NULL, heading TEXT NOT NULL, text TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS chunks_version ON chunks(version_id);
CREATE INDEX IF NOT EXISTS versions_doc ON versions(document_id);
"""


class Database:
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "app.sqlite3"
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(versions)")}
            if "ocr_mode" not in columns:
                conn.execute("ALTER TABLE versions ADD COLUMN ocr_mode TEXT NOT NULL DEFAULT 'auto'")
            conn.execute("UPDATE meta SET value=3 WHERE key='schema_version' AND value<3")

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def rows(self, sql, args=()):
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, args)]

    def one(self, sql, args=()):
        rows = self.rows(sql, args)
        return rows[0] if rows else None

    def execute(self, sql, args=()):
        with self.connect() as conn:
            conn.execute(sql, args)

    @property
    def revision(self):
        return self.one("SELECT value FROM meta WHERE key='kb_revision'")["value"]

    def active_versions(self):
        return [
            r["active_version"]
            for r in self.rows("SELECT active_version FROM documents WHERE deleted=0 AND active_version IS NOT NULL")
        ]

    def recover(self):
        self.execute(
            "UPDATE versions SET status='failed', stage='Terputus', error='Pemrosesan terputus. Gunakan Proses ulang.' WHERE status='processing'"
        )
        self.execute("DELETE FROM admin_sessions WHERE expires < ?", (time.time(),))

    def document_list(self):
        return self.rows("""SELECT d.id,d.title,d.filename,d.active_version,d.pending_version,d.created,
            v.status,v.stage,v.progress,v.page_count,v.warning,v.error,v.size,v.ocr_mode,
            CASE WHEN d.active_version IS NOT NULL THEN 1 ELSE 0 END AS available
            FROM documents d LEFT JOIN versions v ON v.id=COALESCE(d.pending_version,d.active_version)
            WHERE d.deleted=0 ORDER BY d.created DESC""")
