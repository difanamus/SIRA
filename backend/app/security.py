import hashlib
import secrets
import time
from collections import defaultdict, deque
from threading import Lock

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException, Request

hasher = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Limiter:
    def __init__(self):
        self.events = defaultdict(deque)
        self.lock = Lock()

    def check(self, key, maximum, window=60):
        now = time.monotonic()
        with self.lock:
            if len(self.events) > 2000:
                self.events = defaultdict(deque, {k: v for k, v in self.events.items() if v and v[-1] > now - window})
            events = self.events[key]
            while events and events[0] <= now - window:
                events.popleft()
            if len(events) >= maximum:
                raise HTTPException(429, "Terlalu banyak permintaan. Silakan coba beberapa saat lagi.")
            events.append(now)


def check_origin(request: Request, settings):
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != settings.origin.rstrip("/"):
        raise HTTPException(403, "Asal permintaan tidak diizinkan.")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Permintaan lintas situs ditolak.")


def require_admin(request: Request):
    ctx = request.app.state.ctx
    token = request.cookies.get("sira_admin", "")
    session = ctx.db.one("SELECT * FROM admin_sessions WHERE token_hash=? AND expires>?", (digest(token), time.time()))
    if not session:
        raise HTTPException(401, "Silakan masuk sebagai admin.")
    if request.method not in {"GET", "HEAD"}:
        check_origin(request, ctx.settings)
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), session["csrf"]):
            raise HTTPException(403, "Sesi formulir tidak valid. Silakan muat ulang halaman.")
    return session


def verify_password(encoded, password):
    try:
        return hasher.verify(encoded, password)
    except VerificationError:
        return False
