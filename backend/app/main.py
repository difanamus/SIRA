import asyncio
import logging
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from threading import RLock
from types import SimpleNamespace

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .ai import AIError, Relay
from .chat import Chat
from .config import ROOT, Settings
from .db import Database
from .ingestion import Ingestion, save_upload
from .security import Limiter, check_origin, digest, hasher, require_admin, verify_password
from .vectors import VectorStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(StrictModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class Title(StrictModel):
    title: str = Field(min_length=1, max_length=180)


class Question(StrictModel):
    session_id: str = Field(min_length=20, max_length=100)
    question: str = Field(min_length=1, max_length=3000)


class BodyTooLarge(HTTPException):
    def __init__(self):
        super().__init__(413, "Permintaan terlalu besar. PDF maksimal 100 MB.")


class RequestLimits:
    def __init__(self, app, max_upload):
        self.app, self.max_upload = app, max_upload

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = self.max_upload + 1024 * 1024 if scope["path"].startswith("/api/admin/documents") else 32768
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Ukuran request tidak valid."}, 400)(scope, receive, send)
        if length > limit:
            return await JSONResponse({"detail": "Permintaan terlalu besar. PDF maksimal 100 MB."}, 413)(
                scope, receive, send
            )
        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > limit:
                raise BodyTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except BodyTooLarge:
            await JSONResponse({"detail": "Permintaan terlalu besar. PDF maksimal 100 MB."}, 413)(scope, receive, send)


def create_app(settings=None, relay=None, vectors=None, start_ingestion=True):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        db = Database(settings.data_dir)
        db.recover()
        store = vectors or VectorStore(settings.data_dir)
        ai = relay or Relay(settings)
        ingestion = Ingestion(settings, db, store, ai)
        ctx = SimpleNamespace(
            settings=settings,
            db=db,
            vectors=store,
            relay=ai,
            ingestion=ingestion,
            limiter=Limiter(),
            mutation_lock=RLock(),
            chat=Chat(settings, db, store, ai),
            dummy_password=hasher.hash(secrets.token_urlsafe(20)),
        )
        app.state.ctx = ctx
        if start_ingestion:
            ingestion.start()
        yield
        if start_ingestion:
            await asyncio.to_thread(ingestion.close)

    app = FastAPI(
        title="SIRA API",
        description="Asisten Informasi SDM Polri - prototype RAG. Admin menggunakan cookie sesi dan X-CSRF-Token.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestLimits, max_upload=settings.max_upload)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        if request.url.path not in {"/docs", "/redoc"}:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
            )
        return response

    @app.exception_handler(AIError)
    async def ai_error(request, exc):
        return JSONResponse({"detail": str(exc)}, 503)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Pydantic's default error output can echo submitted passwords/tokens.
        return JSONResponse({"detail": "Isian tidak valid. Periksa format dan panjang input."}, 422)

    @app.get("/api/health", tags=["Status"])
    def health(request: Request):
        ctx = request.app.state.ctx
        return {
            "name": "SIRA",
            "status": "ok",
            "ai_ready": settings.ai_ready,
            "knowledge_documents": len(ctx.db.active_versions()),
            "kb_revision": ctx.db.revision,
            "admin_configured": bool(ctx.db.one("SELECT id FROM admin")),
        }

    @app.post("/api/admin/login", tags=["Admin"])
    def login(body: Login, request: Request, response: Response):
        ctx = request.app.state.ctx
        check_origin(request, settings)
        ctx.limiter.check("login:" + request.client.host, 5, 300)
        admin = ctx.db.one("SELECT * FROM admin WHERE username=?", (body.username,))
        valid = verify_password(admin["password_hash"] if admin else ctx.dummy_password, body.password)
        if not admin or not valid:
            raise HTTPException(401, "Nama pengguna atau password tidak sesuai.")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        ctx.db.execute("DELETE FROM admin_sessions WHERE expires<?", (time.time(),))
        ctx.db.execute("INSERT INTO admin_sessions VALUES (?,?,?)", (digest(token), csrf, time.time() + 8 * 3600))
        response.set_cookie(
            "sira_admin",
            token,
            httponly=True,
            secure=settings.secure_cookie,
            samesite="strict",
            max_age=8 * 3600,
            path="/api/admin",
        )
        return {"username": body.username, "csrf_token": csrf}

    @app.get("/api/admin/me", tags=["Admin"])
    def me(request: Request, session=Depends(require_admin)):
        return {
            "username": request.app.state.ctx.db.one("SELECT username FROM admin")["username"],
            "csrf_token": session["csrf"],
        }

    @app.post("/api/admin/logout", tags=["Admin"])
    def logout(request: Request, response: Response, session=Depends(require_admin)):
        request.app.state.ctx.db.execute("DELETE FROM admin_sessions WHERE token_hash=?", (session["token_hash"],))
        response.delete_cookie("sira_admin", path="/api/admin")
        return {"ok": True}

    @app.get("/api/admin/documents", tags=["Dokumen"], dependencies=[Depends(require_admin)])
    def list_documents(request: Request):
        return request.app.state.ctx.db.document_list()

    @app.post("/api/admin/check-ai", tags=["Admin"], dependencies=[Depends(require_admin)])
    def check_ai(request: Request):
        ctx = request.app.state.ctx
        ctx.limiter.check("check-ai", 2, 60)
        ctx.relay.embed(["Uji koneksi layanan SIRA."])
        return {"ok": True, "message": "Relay dan layanan embedding OpenAI berhasil dihubungi."}

    def register_upload(request, file, title, document_id=None):
        ctx = request.app.state.ctx
        if not settings.ai_ready and relay is None:
            raise HTTPException(503, "Relay AI belum dikonfigurasi. Hubungkan layanan AI sebelum mengunggah dokumen.")
        title = title.strip()
        if not title or len(title) > 180:
            raise HTTPException(422, "Judul dokumen harus berisi 1-180 karakter.")
        with ctx.mutation_lock:
            doc = (
                ctx.db.one("SELECT * FROM documents WHERE id=? AND deleted=0", (document_id,)) if document_id else None
            )
            if document_id and not doc:
                raise HTTPException(404, "Dokumen tidak ditemukan.")
            if doc and doc["pending_version"]:
                pending = ctx.db.one("SELECT status FROM versions WHERE id=?", (doc["pending_version"],))
                if pending and pending["status"] == "processing":
                    raise HTTPException(409, "Pemrosesan dokumen ini masih berjalan.")
            if ctx.ingestion.jobs.qsize() >= 5:
                raise HTTPException(429, "Antrean pemrosesan penuh. Tunggu hingga dokumen sebelumnya selesai.")
            version, path, checksum, size = save_upload(settings, file, settings.max_upload)
            filename = Path((file.filename or "dokumen.pdf").replace("\\", "/")).name[:180]
            document_id = document_id or uuid.uuid4().hex
            try:
                with ctx.db.connect() as conn:
                    if not doc:
                        conn.execute(
                            "INSERT INTO documents(id,title,filename,pending_version,created) VALUES (?,?,?,?,?)",
                            (document_id, title, filename, version, time.time()),
                        )
                    else:
                        conn.execute("UPDATE documents SET pending_version=? WHERE id=?", (version, document_id))
                    conn.execute(
                        "INSERT INTO versions(id,document_id,path,sha256,size,status,created) VALUES (?,?,?,?,?,'processing',?)",
                        (version, document_id, path, checksum, size, time.time()),
                    )
            except Exception:
                Path(path).unlink(missing_ok=True)
                raise
            ctx.ingestion.enqueue(version)
            return {"id": document_id, "status": "processing"}

    @app.post("/api/admin/documents", status_code=202, tags=["Dokumen"], dependencies=[Depends(require_admin)])
    def upload_document(request: Request, title: str = Form(...), file: UploadFile = File(...)):
        try:
            return register_upload(request, file, title)
        finally:
            file.file.close()

    @app.put(
        "/api/admin/documents/{document_id}/file",
        status_code=202,
        tags=["Dokumen"],
        dependencies=[Depends(require_admin)],
    )
    def replace_document(document_id: str, request: Request, file: UploadFile = File(...)):
        try:
            doc = request.app.state.ctx.db.one("SELECT title FROM documents WHERE id=? AND deleted=0", (document_id,))
            if not doc:
                raise HTTPException(404, "Dokumen tidak ditemukan.")
            return register_upload(request, file, doc["title"], document_id)
        finally:
            file.file.close()

    @app.patch("/api/admin/documents/{document_id}", tags=["Dokumen"], dependencies=[Depends(require_admin)])
    def rename_document(document_id: str, body: Title, request: Request):
        title = body.title.strip()
        if not title:
            raise HTTPException(422, "Judul tidak boleh kosong.")
        with request.app.state.ctx.db.connect() as conn:
            result = conn.execute("UPDATE documents SET title=? WHERE id=? AND deleted=0", (title, document_id))
            if not result.rowcount:
                raise HTTPException(404, "Dokumen tidak ditemukan.")
            conn.execute("UPDATE meta SET value=value+1 WHERE key='kb_revision'")
        return {"ok": True}

    @app.post("/api/admin/documents/{document_id}/retry", tags=["Dokumen"], dependencies=[Depends(require_admin)])
    def retry_document(document_id: str, request: Request):
        ctx = request.app.state.ctx
        with ctx.mutation_lock:
            doc = ctx.db.one("SELECT pending_version FROM documents WHERE id=? AND deleted=0", (document_id,))
            version = ctx.db.one("SELECT * FROM versions WHERE id=?", (doc["pending_version"],)) if doc else None
            if not version or version["status"] != "failed":
                raise HTTPException(409, "Tidak ada pemrosesan gagal yang dapat diulang.")
            if ctx.ingestion.jobs.qsize() >= 5:
                raise HTTPException(429, "Antrean pemrosesan penuh.")
            ctx.ingestion.update(
                version["id"], status="processing", stage="Menunggu antrean", progress=0, error="", warning=""
            )
            ctx.ingestion.enqueue(version["id"])
        return {"ok": True}

    @app.delete("/api/admin/documents/{document_id}", tags=["Dokumen"], dependencies=[Depends(require_admin)])
    def delete_document(document_id: str, request: Request):
        ctx = request.app.state.ctx
        with ctx.mutation_lock, ctx.db.connect() as conn:
            result = conn.execute(
                "UPDATE documents SET deleted=1,active_version=NULL,pending_version=NULL WHERE id=? AND deleted=0",
                (document_id,),
            )
            if not result.rowcount:
                raise HTTPException(404, "Dokumen tidak ditemukan.")
            conn.execute("UPDATE meta SET value=value+1 WHERE key='kb_revision'")
        # Cleanup runs on the same ingestion worker, after any currently open PDF closes.
        ctx.ingestion.enqueue("cleanup")
        return {"ok": True}

    @app.post("/api/chat/sessions", tags=["Chat"])
    def chat_session(request: Request):
        ctx = request.app.state.ctx
        check_origin(request, settings)
        ctx.limiter.check("sessions:" + request.client.host, 20)
        return {"session_id": ctx.chat.create()}

    @app.post("/api/chat", tags=["Chat"])
    async def ask(body: Question, request: Request):
        ctx = request.app.state.ctx
        check_origin(request, settings)
        question = body.question.strip()
        if not question:
            raise HTTPException(422, "Pertanyaan tidak boleh kosong.")
        session = ctx.chat.get(body.session_id)
        if not session:
            raise HTTPException(410, "Sesi telah berakhir. Mulai percakapan baru.")
        if session.lock.locked():
            raise HTTPException(409, "Tunggu hingga jawaban sebelumnya selesai.")
        ctx.limiter.check("chat:" + request.client.host, 15)
        return StreamingResponse(
            ctx.chat.stream(session, question), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
        )

    dist = ROOT / "frontend" / "dist"
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/admin", include_in_schema=False)
    def frontend():
        if not (dist / "index.html").exists():
            return JSONResponse({"detail": "Frontend belum dibangun. Ikuti README untuk menjalankan build."}, 503)
        return FileResponse(dist / "index.html")

    return app


app = create_app()
