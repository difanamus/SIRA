import asyncio
import json
import logging
import re
import secrets
import time
from dataclasses import dataclass, field

from .ai import AIError

log = logging.getLogger("sira.chat")
NOT_FOUND = "Maaf, informasi tersebut belum ditemukan dalam dokumen yang tersedia. Silakan perjelas pertanyaan atau hubungi pihak yang berwenang untuk memperoleh kepastian."
SAFE_REFUSAL = "Maaf, saya tidak dapat memenuhi permintaan untuk mengubah aturan atau mengungkap informasi internal."
FOLLOW_UP = re.compile(r"^(kalau|bagaimana dengan|lalu|dan untuk|yang tadi|itu|terus|untuk yang)\b", re.I)


def event(kind, **values):
    return "data: " + json.dumps({"type": kind, **values}, ensure_ascii=False) + "\n\n"


@dataclass
class Session:
    updated: float
    revision: int
    questions: list[str] = field(default_factory=list)
    search_context: str = ""
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class Chat:
    def __init__(self, settings, db, vectors, relay):
        self.settings, self.db, self.vectors, self.relay = settings, db, vectors, relay
        self.sessions = {}

    def create(self):
        now = time.monotonic()
        self.sessions = {
            key: value for key, value in self.sessions.items() if now - value.updated < self.settings.session_ttl
        }
        if len(self.sessions) >= 100:
            raise AIError("Terlalu banyak sesi aktif. Silakan coba beberapa saat lagi.")
        token = secrets.token_urlsafe(32)
        self.sessions[token] = Session(now, self.db.revision)
        return token

    def get(self, token):
        session = self.sessions.get(token)
        if not session or time.monotonic() - session.updated > self.settings.session_ttl:
            return None
        return session

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
        started = time.monotonic()
        async with session.lock:
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
            if re.fullmatch(r"\s*(halo|hai|selamat (pagi|siang|sore|malam)|terima kasih)[!.\s]*", question, re.I):
                yield event(
                    "delta",
                    text="Selamat datang. Saya SIRA, Asisten Informasi SDM Polri. Silakan ajukan pertanyaan mengenai dokumen yang tersedia.",
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
                        {"id": s["source_id"], "title": s["title"], "page": s["page"], "text": s["text"]}
                        for s in sources
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
