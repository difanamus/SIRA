"""Evaluasi nyata SIRA terhadap pertanyaan acuan (docs/evaluasi-cases.json).

Menggunakan knowledge base aktif di data/ secara read-only (tanpa ingestion, tanpa sesi chat tersimpan)
dan relay AI dari .env. Biaya: sekitar satu embedding dan satu jawaban per pertanyaan, dibatasi plafon.
Hentikan backend terlebih dahulu, lalu jalankan:

    .\\.venv\\Scripts\\python.exe scripts\\eval-live.py
"""

import asyncio
import json
import re
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.ai import Relay  # noqa: E402
from backend.app.chat import Chat, Session  # noqa: E402
from backend.app.config import Settings  # noqa: E402
from backend.app.db import Database  # noqa: E402
from backend.app.vectors import VectorStore  # noqa: E402

MAX_ANSWERS, MAX_EMBEDDINGS = 60, 70
PAUSE_SECONDS = 9  # relay allows 30 requests/minute shared by all demo users (rewrite + embedding + answer)
OUT = ROOT / "tmp" / "eval-live"


class ReadOnly(Database):
    def __init__(self, path):
        self.path = path

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


class BoundedRelay(Relay):
    def __init__(self, settings):
        super().__init__(settings)
        self.embeddings = self.answers = 0
        self.sent = []  # (doc, page) of sources given to the model, per answer call

    def embed(self, texts):
        self.embeddings += 1
        if self.embeddings > MAX_EMBEDDINGS:
            raise RuntimeError("Plafon embedding evaluasi tercapai")
        return super().embed(texts)

    async def answer(self, payload):
        self.answers += 1
        if self.answers > MAX_ANSWERS:
            raise RuntimeError("Plafon jawaban evaluasi tercapai")
        self.sent.append([f"{doc_kind(s['title'])} {s['page']}" for s in payload["sources"]])
        async for text in super().answer(payload):
            yield text


def doc_kind(title):
    return "Perpol" if "perpol" in title.lower() else "SBP" if "sbp" in title.lower() else title


def check(case, text, sources, final):
    checks = {"selesai": final.get("type") == "done"}
    for pattern in case.get("expect", []):
        checks[f"memuat /{pattern}/"] = bool(re.search(pattern, text, re.I))
    for pattern in case.get("forbid", []):
        checks[f"tanpa /{pattern}/"] = not re.search(pattern, text, re.I)
    kinds = {doc_kind(s["title"]) for s in sources}
    wanted = case.get("sources")
    if wanted in ("SBP", "Perpol"):
        checks[f"sumber hanya {wanted}"] = kinds == {wanted}
    elif wanted == "both":
        checks["sumber SBP dan Perpol"] = kinds == {"SBP", "Perpol"}
    elif wanted == "none":
        checks["tanpa referensi"] = not sources
    if case.get("pages") and wanted in ("SBP", "Perpol"):
        checks[f"halaman {case['pages']}"] = any(s["page"] in case["pages"] for s in sources)
    return checks


async def main():
    settings = Settings()
    if not settings.ai_ready:
        raise SystemExit("Konfigurasi relay AI belum ada di .env.")
    cases = json.loads((ROOT / "docs" / "evaluasi-cases.json").read_text(encoding="utf-8"))
    only = set(sys.argv[1:])
    if only:
        cases = [c for c in cases if c["id"] in only]
    db = ReadOnly(settings.data_dir / "app.sqlite3")
    relay = BoundedRelay(settings)
    chat = Chat(settings, db, VectorStore(settings.data_dir), relay)
    OUT.mkdir(parents=True, exist_ok=True)
    results, failures = [], []
    for case in cases:
        session = Session(time.monotonic(), db.revision, "evaluasi-tanpa-sesi-db")
        turns = []
        for question in case["turns"]:
            started = time.monotonic()
            relay.sent.clear()
            text, final, rewrites, first_text = "", {}, 0, None
            try:
                async for raw in chat._answer_stream(session, question):
                    value = json.loads(raw[5:])
                    if value["type"] == "reset_answer":
                        text = ""
                        rewrites += 1
                    elif value["type"] == "delta":
                        text += value["text"]
                        if first_text is None:
                            first_text = round(time.monotonic() - started, 2)
                    elif value["type"] == "replace_answer":
                        text = value["text"]
                    final = value
            except RuntimeError as exc:
                final = {"type": "error", "message": str(exc)}
            turns.append(
                {
                    "question": question,
                    "answer": text,
                    "final": final.get("type"),
                    "error": final.get("message", ""),
                    "sources": [(s["title"], s["page"]) for s in final.get("sources", [])],
                    "seconds": round(time.monotonic() - started, 2),
                    "sent_to_model": [list(x) for x in relay.sent],
                    "visible_rewrites": rewrites,
                    "first_text_seconds": first_text,
                }
            )
        last = turns[-1]
        checks = check(
            case,
            last["answer"],
            [{"title": t, "page": p} for t, p in last["sources"]],
            {"type": last["final"]},
        )
        passed = all(checks.values())
        if not passed:
            failures.append(case["id"])
        item = {
            **{k: case[k] for k in ("id", "kategori", "acuan", "halaman")},
            "turns": turns,
            "checks": checks,
            "lulus": passed,
        }
        results.append(item)
        (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        mark = "LULUS" if passed else "GAGAL"
        rewrites = sum(t["visible_rewrites"] for t in turns)
        print(
            f"[{mark}] {case['id']} (teks pertama {last['first_text_seconds']} s, selesai {last['seconds']} s, "
            f"tulis ulang: {rewrites}) {last['sources']}",
            flush=True,
        )
        if not passed:
            print("       ", {k: v for k, v in checks.items() if not v}, flush=True)
        await asyncio.sleep(PAUSE_SECONDS)
    summary = {
        "total": len(results),
        "lulus": len(results) - len(failures),
        "gagal": failures,
        "jawaban_ai": relay.answers,
        "embedding": relay.embeddings,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


asyncio.run(main())
