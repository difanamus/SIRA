import asyncio
import json
import logging
import re
import secrets
import time
from dataclasses import dataclass, field
from threading import RLock

from .ai import AIError
from .security import digest

log = logging.getLogger("sira.chat")
NOT_FOUND = "Maaf, informasi tersebut belum ditemukan dalam dokumen yang tersedia. Silakan perjelas pertanyaan atau hubungi pihak yang berwenang untuk memperoleh kepastian."
SAFE_REFUSAL = "Maaf, saya tidak dapat memenuhi permintaan untuk mengubah aturan atau mengungkap informasi internal."
FOLLOW_UP = re.compile(
    r"^(kalau|bagaimana dengan|lalu|dan untuk|yang tadi|itu|terus|untuk yang|masa sih|yakin|benarkah|"
    r"apa benar|bukankah|coba (?:cek|periksa)|periksa (?:lagi|ulang))\b",
    re.I,
)
GREETING = re.compile(
    r"\s*(?:sira|(?:sira[\s,!.:;-]+)?"
    r"(?:halo|hallo|hai|hi|hello|hei|hey|oy|oi|selamat\s+(?:pagi|siang|sore|malam)|terima\s+kasih)"
    r"(?:[\s,!.:;-]+sira)?)[\s!.,:;-]*",
    re.I,
)
IDENTITY = re.compile(
    r"\s*(?:(?:halo|hallo|hai|hi|hello|hei|hey|oy|oi)(?:[\s,!.:;-]+sira)?[\s,!.:;-]+|"
    r"sira[\s,!.:;-]+)?"
    r"(?:(?:kamu|anda)(?:\s+ini)?\s+(?:siapa|apa)|"
    r"siapa(?:kah)?\s+(?:kamu|anda|sira)|"
    r"apa(?:kah)?\s+(?:itu\s+)?sira|"
    r"sira(?:\s+(?:ini|itu))?\s+(?:siapa|apa)|"
    r"(?:apa\s+)?(?:kepanjangan|arti|singkatan(?:\s+dari)?)\s+sira|"
    r"sira\s+(?:singkatan(?:\s+dari)?|kepanjangan(?:nya)?)\s+apa|"
    r"apa\s+(?:fungsi|tugas|peran)(?:mu|\s+(?:kamu|anda|sira))|"
    r"(?:kamu|anda|sira)\s+(?:bisa|dapat)\s+(?:membantu|bantu)\s+apa)"
    r"[\s?!.,:;-]*",
    re.I,
)
IDENTITY_REPLY = (
    "Saya SIRA (Sistem Informasi dan Referensi Aparatur), asisten AI untuk informasi SDM Polri. "
    "Saya membantu Anda mencari dan memahami informasi dari dokumen yang tersedia, "
    "disertai referensi nama dokumen dan halaman sumber. "
    "Jika informasi belum ditemukan, saya akan menyampaikannya. Apa yang dapat saya bantu?"
)
GREETING_REPLY = (
    "Halo, saya SIRA (Sistem Informasi dan Referensi Aparatur), asisten informasi SDM Polri. "
    "Dengan senang hati saya membantu Anda mencari informasi dari dokumen yang tersedia. "
    "Silakan sampaikan pertanyaan Anda."
)


def event(kind, **values):
    return "data: " + json.dumps({"type": kind, **values}, ensure_ascii=False) + "\n\n"


@dataclass
class Session:
    updated: float
    revision: int
    token_hash: str
    questions: list[str] = field(default_factory=list)
    search_context: str = ""
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class Chat:
    def __init__(self, settings, db, vectors, relay):
        self.settings, self.db, self.vectors, self.relay = settings, db, vectors, relay
        self.sessions = {}
        self.cache_lock = RLock()

    def _cache(self, token, session):
        now = time.monotonic()
        self.sessions = {
            key: value
            for key, value in self.sessions.items()
            if value.lock.locked() or now - value.updated < self.settings.session_cache_ttl
        }
        if len(self.sessions) >= 100:
            idle = [key for key, value in self.sessions.items() if not value.lock.locked()]
            if not idle:
                raise AIError("Terlalu banyak percakapan sedang menjawab. Silakan coba beberapa saat lagi.")
            del self.sessions[min(idle, key=lambda key: self.sessions[key].updated)]
        self.sessions[token] = session

    def create(self, previous_token=None):
        with self.cache_lock:
            token = secrets.token_urlsafe(32)
            session = Session(time.monotonic(), self.db.revision, digest(token))
            with self.db.connect() as conn:
                if previous_token:
                    conn.execute("DELETE FROM chat_sessions WHERE token_hash=?", (digest(previous_token),))
                conn.execute(
                    "INSERT INTO chat_sessions(token_hash,revision,updated) VALUES (?,?,?)",
                    (session.token_hash, session.revision, time.time()),
                )
            if previous_token:
                self.sessions.pop(previous_token, None)
            self._cache(token, session)
            return token

    def get(self, token):
        with self.cache_lock:
            row = self.db.one("SELECT * FROM chat_sessions WHERE token_hash=?", (digest(token),))
            if not row:
                self.sessions.pop(token, None)
                return None
            session = self.sessions.get(token)
            if session is None:
                session = Session(
                    time.monotonic(),
                    row["revision"],
                    row["token_hash"],
                    json.loads(row["questions"]),
                    row["search_context"],
                )
                self._cache(token, session)
            session.updated = time.monotonic()
            return session

    def history(self, session):
        return [
            json.loads(row["content"])
            for row in self.db.rows(
                "SELECT content FROM chat_messages WHERE session_hash=? ORDER BY id", (session.token_hash,)
            )
        ]

    def _save_session(self, session):
        self.db.execute(
            "UPDATE chat_sessions SET revision=?,questions=?,search_context=?,updated=? WHERE token_hash=?",
            (session.revision, json.dumps(session.questions), session.search_context, time.time(), session.token_hash),
        )

    def retrieve(self, query):
        versions = self.db.active_versions()
        if not versions:
            return []
        started = time.monotonic()
        embedding = self.relay.embed([query])[0]
        embedded = time.monotonic()
        candidates = self.vectors.search(embedding, versions)
        found = []
        for chunk_id, distance in candidates:
            if distance > 0.85:
                continue
            row = self.db.one(
                """SELECT c.*,d.title,d.id AS document_id FROM chunks c JOIN documents d
                ON d.active_version=c.version_id WHERE c.id=? AND d.deleted=0""",
                (chunk_id,),
            )
            if row:
                row["distance"] = distance
                found.append(row)
        # Light lexical tie-break inside semantic candidates; no extra model request.
        terms = set(re.findall(r"\w{3,}", query.lower())) - {
            "yang",
            "dan",
            "untuk",
            "apa",
            "saja",
            "kalau",
            "bagaimana",
            "dengan",
        }
        found.sort(
            key=lambda c: c["distance"] - 0.025 * min(4, len(terms & set(re.findall(r"\w{3,}", c["text"].lower()))))
        )
        selected, used = [], 0
        for row in found:
            if len(selected) >= 10 or used + len(row["text"]) > 24000:
                break
            row["source_id"] = f"S{len(selected) + 1}"
            selected.append(row)
            used += len(row["text"])
        log.info(
            "retrieval embedding_ms=%s retrieval_ms=%s chunks=%s",
            round((embedded - started) * 1000),
            round((time.monotonic() - embedded) * 1000),
            len(selected),
        )
        return selected

    async def stream(self, session, question):
        async with session.lock:
            if not self.db.one("SELECT 1 FROM chat_sessions WHERE token_hash=?", (session.token_hash,)):
                yield event("error", message="Percakapan sudah diganti. Silakan muat ulang halaman.")
                return
            assistant = {"role": "assistant", "text": "", "sources": [], "pending": True}
            with self.db.connect() as conn:
                conn.execute(
                    "INSERT INTO chat_messages(session_hash,content) VALUES (?,?)",
                    (
                        session.token_hash,
                        json.dumps({"role": "user", "text": question}),
                    ),
                )
                message_id = conn.execute(
                    "INSERT INTO chat_messages(session_hash,content) VALUES (?,?)",
                    (
                        session.token_hash,
                        json.dumps(assistant),
                    ),
                ).lastrowid
            last_saved = 0.0

            def save():
                self.db.execute("UPDATE chat_messages SET content=? WHERE id=?", (json.dumps(assistant), message_id))

            try:
                async for packet in self._answer_stream(session, question):
                    value = json.loads(packet.removeprefix("data: "))
                    kind = value["type"]
                    if kind == "delta":
                        assistant["text"] += value["text"]
                    elif kind == "notice":
                        assistant["notice"] = value["message"]
                    elif kind == "reset_answer":
                        assistant.update(text="", sources=[])
                    elif kind == "done":
                        assistant.update(sources=value["sources"], pending=False)
                        self._save_session(session)
                    elif kind == "error":
                        assistant.update(error=value["message"], pending=False)
                    if kind != "status" and (kind != "delta" or time.monotonic() - last_saved >= 0.5):
                        save()
                        last_saved = time.monotonic()
                    yield packet
            finally:
                if assistant["pending"]:
                    assistant.update(
                        pending=False, error="Jawaban terputus sebelum selesai. Silakan kirim ulang pertanyaan."
                    )
                save()
                self._save_session(session)

    async def _answer_stream(self, session, question):
        started = time.monotonic()
        session.updated = time.monotonic()
        revision = self.db.revision
        if session.revision != revision:
            session.questions.clear()
            session.search_context = ""
            session.revision = revision
            yield event(
                "notice",
                message="Knowledge base telah berubah; konteks sebelumnya direset agar sumber lama tidak digunakan.",
            )
        # Only complete, allowlisted social messages take this fixed-response path.
        # Extra questions or instructions still pass through retrieval and relay policy.
        # These replies work with an empty KB and never replace the document topic.
        social_reply = IDENTITY_REPLY if IDENTITY.fullmatch(question) else None
        if social_reply is None and GREETING.fullmatch(question):
            social_reply = GREETING_REPLY
        if social_reply:
            yield event("delta", text=social_reply)
            yield event("done", sources=[])
            return
        if not self.db.active_versions():
            yield event(
                "delta",
                text="Saat ini belum ada dokumen yang tersedia. Silakan hubungi admin untuk menambahkan knowledge base.",
            )
            yield event("done", sources=[])
            return
        if FOLLOW_UP.match(question) and not session.questions:
            yield event(
                "delta",
                text="Mohon jelaskan topik atau ketentuan yang Anda maksud agar saya dapat mencari informasi yang sesuai.",
            )
            yield event("done", sources=[])
            return
        query = question
        if FOLLOW_UP.match(question) and len(question) < 180:
            query = session.search_context[-1400:] + "\nPertanyaan lanjutan: " + question
        try:
            yield event("status", message="Mencari informasi dalam dokumen...")
            sources = await asyncio.to_thread(self.retrieve, query)
            if self.db.revision != revision:
                raise AIError("Knowledge base berubah saat pencarian. Silakan kirim ulang pertanyaan.")
            if not sources:
                yield event("delta", text=NOT_FOUND)
                yield event("done", sources=[])
                return
            payload = {
                "question": question,
                "history": session.questions[-4:],
                "sources": [
                    {"id": s["source_id"], "title": s["title"], "page": s["page"], "text": s["text"]} for s in sources
                ],
            }
            first = True
            yield event("status", message="Menyusun jawaban berdasarkan sumber...")
            for attempt in range(2):
                answer = ""
                async for text in self.relay.answer(payload):
                    if self.db.revision != revision:
                        raise AIError(
                            "Knowledge base berubah. Jawaban ini belum selesai; silakan kirim ulang pertanyaan."
                        )
                    if first:
                        log.info("chat_first_text_ms=%s", round((time.monotonic() - started) * 1000))
                        first = False
                    answer += text
                    yield event("delta", text=text)
                cited = set(re.findall(r"\[(S\d+)\]", answer))
                valid = {s["source_id"] for s in sources}
                if cited - valid:
                    raise AIError("Referensi jawaban tidak valid. Silakan coba kembali.")
                missing = (
                    not cited
                    and answer.strip() != SAFE_REFUSAL
                    and not re.search(
                        r"belum (?:ditemukan|tersedia)|tidak (?:ditemukan|tersedia|dapat memastikan)|mohon.*jelas|perjelas",
                        answer,
                        re.I,
                    )
                )
                if not missing:
                    break
                if attempt:
                    raise AIError("Jawaban belum disertai referensi yang dapat diverifikasi. Silakan coba kembali.")
                payload["citation_retry"] = True
                yield event("reset_answer", message="Memeriksa ulang referensi jawaban...")
            references = [
                {"id": s["source_id"], "title": s["title"], "page": s["page"], "heading": s["heading"]}
                for s in sources
                if s["source_id"] in cited
            ]
            # The model may abstain without citations. Never label such a result as sourced.
            if not answer.strip():
                raise AIError("Layanan AI belum memberikan jawaban. Silakan coba kembali.")
            if answer.strip() == SAFE_REFUSAL:
                # A refused instruction must not replace the legitimate topic
                # or become additional instruction-bearing session history.
                yield event("done", sources=[])
                return
            session.questions = (session.questions + [question])[-4:]
            session.search_context = query[-1800:]
            session.updated = time.monotonic()
            yield event("done", sources=references)
            log.info("chat_complete_ms=%s sources=%s", round((time.monotonic() - started) * 1000), len(references))
        except AIError as exc:
            yield event("error", message=str(exc))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("chat_failed type=%s", type(exc).__name__)
            yield event("error", message="Jawaban belum dapat diselesaikan. Silakan coba kembali.")
