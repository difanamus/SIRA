import base64
import hashlib
import io
import logging
import os
import queue
import re
import threading
import time
import unicodedata
import uuid
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pdfplumber
import pypdfium2 as pdfium
import pytesseract
import tiktoken
from PIL import ImageFilter, ImageOps

from .ai import AIError
from .config import ROOT

log = logging.getLogger("sira.ingestion")
os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(ROOT / "data" / "tokenizer"))
ENCODING = tiktoken.get_encoding("cl100k_base")


def preprocess(image):
    image = ImageOps.autocontrast(ImageOps.grayscale(image))
    thumbnail = image.copy()
    thumbnail.thumbnail((1000, 1400))

    def projection_score(candidate):
        pixels = np.asarray(candidate) < 170
        rows = pixels.mean(axis=1)
        return float(np.square(np.diff(rows)).sum())

    original = projection_score(thumbnail)
    best_angle, best_score = 0, original
    for angle in (-3, -2, -1, 1, 2, 3):
        rotated = thumbnail.rotate(angle, expand=False, fillcolor=255)
        score = projection_score(rotated)
        if score > best_score:
            best_angle, best_score = angle, score
    if best_angle and best_score > original * 1.12:
        image = image.rotate(best_angle, expand=True, fillcolor=255)
    return image.filter(ImageFilter.SHARPEN)


def readable(text):
    return len(re.findall(r"[\w]", text)) >= 70 and text.count("\ufffd") / max(1, len(text)) < 0.01


def critical_signature(text):
    normalized = unicodedata.normalize("NFKC", text).replace("–", "-").replace("—", "-")
    # Compare digit groups rather than punctuation: "61 - 70" and "61-70"
    # must agree, while a changed year or missing number must still differ.
    numbers = Counter(re.findall(r"\d+", normalized))
    negations = Counter(re.findall(r"\b(?:tidak|bukan|dilarang)\b", normalized, re.I))
    semesters = Counter(
        match.upper().replace("|", "I").replace("L", "I")
        for match in re.findall(r"\b(?:SMT|semester)\s+([Il|]{1,3})(?=\s|[.,;:]|$)", normalized, re.I)
    )
    return numbers, negations, semesters


def image_payload(image, maximum):
    preview = image.copy()
    preview.thumbnail(maximum)
    buffer = io.BytesIO()
    preview.convert("RGB").save(buffer, format="JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def vision_images(image):
    # Separate crops retain readable text after the vision service resizes images.
    # A small overlap prevents a line cut at the midpoint from being lost.
    middle, overlap = image.height // 2, max(20, image.height // 40)
    return [
        image_payload(image.crop((0, 0, image.width, middle + overlap)), (2600, 2600)),
        image_payload(image.crop((0, middle - overlap, image.width, image.height)), (2600, 2600)),
    ]


def verified_transcription(result):
    if result["uncertain"] or "[TIDAK TERBACA]" in result["text"] or not readable(result["text"]):
        raise AIError("Halaman scan belum dapat dibaca dengan yakin. Gunakan scan yang lebih jelas dan proses ulang.")
    return result["text"]


def chunk_page(text, version_id, page, target=650, overlap=100):
    # Keep source pages explicit. Prefer paragraph boundaries while bounding tokens.
    paragraphs = re.split(r"\n\s*\n", text.strip())
    pieces = []
    for paragraph in paragraphs:
        tokens = ENCODING.encode(paragraph)
        if len(tokens) > target:
            pieces.extend(ENCODING.decode(tokens[i : i + target]) for i in range(0, len(tokens), target - overlap))
        elif paragraph.strip():
            pieces.append(paragraph)
    chunks, current = [], ""
    for piece in pieces:
        candidate = current + "\n\n" + piece if current else piece
        if current and len(ENCODING.encode(candidate)) > target:
            chunks.append(current)
            current = piece
        else:
            current = candidate
    if current:
        chunks.append(current)
    heading_match = re.search(r"(?im)^\s*(?:pasal\s+\d+|bab\s+[ivxlcdm]+|\d+[.)]\s+[^\n]{5,100})", text)
    heading = heading_match.group(0).strip() if heading_match else ""
    return [
        {"id": f"{version_id}:{page}:{i}", "version_id": version_id, "page": page, "heading": heading, "text": content}
        for i, content in enumerate(chunks)
    ]


class Ingestion:
    def __init__(self, settings, db, vectors, relay):
        self.settings, self.db, self.vectors, self.relay = settings, db, vectors, relay
        self.jobs = queue.Queue()
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self.run, name="sira-ingestion", daemon=True)
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    def start(self):
        self.thread.start()

    def close(self):
        self.stopping.set()
        self.jobs.put(None)
        self.thread.join(timeout=5)

    def update(self, version, **fields):
        columns = ",".join(f"{name}=?" for name in fields)
        self.db.execute(f"UPDATE versions SET {columns} WHERE id=?", (*fields.values(), version))

    def enqueue(self, version):
        self.jobs.put(version)

    def assert_live(self, version):
        row = self.db.one(
            "SELECT d.deleted FROM documents d JOIN versions v ON v.document_id=d.id WHERE v.id=?", (version,)
        )
        if self.stopping.is_set() or not row or row["deleted"]:
            raise AIError("Pemrosesan dihentikan.")

    def run(self):
        self.cleanup_deleted()
        while not self.stopping.is_set():
            version = self.jobs.get()
            if version is None:
                break
            try:
                self.process(version)
            except Exception as exc:
                message = (
                    str(exc)
                    if isinstance(exc, AIError)
                    else "Dokumen gagal diproses. Periksa PDF dan instalasi OCR, lalu proses ulang."
                )
                self.update(version, status="failed", stage="Gagal", error=message)
                log.warning("ingestion_failed type=%s", type(exc).__name__)
            finally:
                self.cleanup_deleted()
                self.jobs.task_done()

    def cleanup_deleted(self):
        for row in self.db.rows(
            "SELECT v.id,v.path FROM versions v JOIN documents d ON v.document_id=d.id WHERE d.deleted=1 OR (v.status='ready' AND v.id<>COALESCE(d.active_version,''))"
        ):
            try:
                self.vectors.delete(row["id"])
                Path(row["path"]).unlink(missing_ok=True)
                with self.db.connect() as conn:
                    conn.execute("DELETE FROM chunks WHERE version_id=?", (row["id"],))
                    conn.execute("DELETE FROM pages WHERE version_id=?", (row["id"],))
                    conn.execute("DELETE FROM versions WHERE id=?", (row["id"],))
            except (OSError, RuntimeError):
                log.warning("cleanup_pending")

    def extract_scan(self, image):
        original = image.copy()
        image = preprocess(image)
        try:
            data = pytesseract.image_to_data(
                image, lang=self.settings.ocr_lang, config="--psm 3", output_type=pytesseract.Output.DICT, timeout=60
            )
        except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError, RuntimeError) as exc:
            raise AIError(
                "OCR lokal belum siap atau melewati batas waktu. Pasang Tesseract beserta bahasa ind dan eng, lalu proses ulang."
            ) from exc
        lines, confidences = {}, []
        for i, word in enumerate(data["text"]):
            if not word.strip():
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(word)
            if float(data["conf"][i]) >= 0:
                confidences.append(float(data["conf"][i]))
        text = "\n".join(" ".join(words) for words in lines.values())
        confidence = sum(confidences) / max(1, len(confidences))
        warning = ""
        method = "ocr"
        doubtful = (
            not readable(text)
            or confidence < 88
            or bool(re.search(r"\b(?:tidak|pangkat|ijazah|syarat|tanggal|tahun)\b", text, re.I))
        )
        if doubtful:
            warning = "Halaman scan: hasil OCR otomatis perlu verifikasi, terutama angka dan ketentuan."
            if self.settings.vision_enabled and self.settings.ai_ready:
                candidate = verified_transcription(self.relay.vision(vision_images(image)))
                if critical_signature(text) != critical_signature(candidate):
                    # Read the untouched image afresh without showing either transcript to the model.
                    # Agreement is a cross-check, never a guarantee of correctness.
                    confirmation = verified_transcription(self.relay.vision(vision_images(original)))

                    def plain(value):
                        return re.sub(r"\W+", "", value).casefold()

                    similarity = SequenceMatcher(None, plain(candidate), plain(confirmation), autojunk=False).ratio()
                    if critical_signature(candidate) != critical_signature(confirmation) or similarity < 0.94:
                        raise AIError(
                            "Pembacaan ulang OCR/AI masih berbeda pada angka, negasi, atau isi. Perlu scan lebih jelas sebelum dokumen dapat diaktifkan."
                        )
                    method = "ocr+vision-recheck-crops-v1"
                    warning += (
                        " Perbedaan OCR diperiksa melalui dua pembacaan vision; tetap memerlukan verifikasi manusia."
                    )
                else:
                    method = "ocr+vision-crops-v1"
                text = candidate
        if not readable(text):
            raise AIError("Teks halaman scan terlalu sedikit atau tidak terbaca. Dokumen belum diaktifkan.")
        return text, method, warning

    def process(self, version_id):
        started = time.monotonic()
        version = self.db.one("SELECT * FROM versions WHERE id=?", (version_id,))
        if not version:
            return
        self.assert_live(version_id)
        self.vectors.delete(version_id)
        with self.db.connect() as conn:
            conn.execute("DELETE FROM chunks WHERE version_id=?", (version_id,))
        # The uploaded version is immutable. Resume from accepted page transcripts
        # after a network/embedding failure instead of charging for OCR again.
        warnings, pending_chunks, text_size = [], [], 0
        try:
            with pdfplumber.open(version["path"]) as pdf:
                if not 1 <= len(pdf.pages) <= self.settings.max_pages:
                    raise AIError(f"PDF harus berisi 1-{self.settings.max_pages} halaman.")
                self.update(version_id, page_count=len(pdf.pages), stage="Ekstraksi halaman", progress=2)
                with pdfium.PdfDocument(version["path"]) as rendered:
                    for number, page in enumerate(pdf.pages, 1):
                        self.assert_live(version_id)
                        if page.width * page.height > 10_000_000:
                            raise AIError("Ukuran halaman terlalu besar untuk diproses dengan aman.")
                        cached = self.db.one(
                            "SELECT * FROM pages WHERE version_id=? AND number=?", (version_id, number)
                        )
                        if cached and cached["method"].startswith("ocr") and not cached["method"].endswith("crops-v1"):
                            cached = None
                        text = cached["text"] if cached else (page.extract_text(layout=False) or "")
                        method, warning = (cached["method"], cached["warning"]) if cached else ("text", "")
                        if not cached and not readable(text):
                            bitmap_page = rendered[number - 1]
                            scale = min(3.0, 3000 / max(bitmap_page.get_size()))
                            bitmap = bitmap_page.render(scale=scale)
                            try:
                                image = bitmap.to_pil().copy()
                            finally:
                                bitmap.close()
                                bitmap_page.close()
                            # Truly blank pages are recorded, never guessed.
                            if ImageOps.grayscale(image).getextrema()[0] > 245:
                                text, method = "", "blank"
                            else:
                                try:
                                    text, method, warning = self.extract_scan(image)
                                except AIError as exc:
                                    raise AIError(f"Halaman {number}: {exc}") from exc
                        if warning:
                            warnings.append(f"Halaman {number}: {warning}")
                        self.db.execute(
                            "INSERT OR REPLACE INTO pages VALUES (?,?,?,?,?)",
                            (version_id, number, text, method, warning),
                        )
                        page_chunks = chunk_page(text, version_id, number)
                        pending_chunks.extend(page_chunks)
                        text_size += sum(len(chunk["text"]) for chunk in page_chunks)
                        if text_size > 5_000_000:
                            raise AIError("Teks PDF terlalu besar. Pisahkan dokumen menjadi beberapa PDF.")
                        self.update(
                            version_id,
                            stage=f"Halaman {number}/{len(pdf.pages)}",
                            progress=min(70, int(number / len(pdf.pages) * 70)),
                            warning="\n".join(warnings),
                        )
        except AIError:
            raise
        except Exception as exc:
            raise AIError(
                "PDF tidak dapat diproses. Pastikan file tidak rusak/terkunci dan instalasi OCR tersedia."
            ) from exc
        if not pending_chunks:
            raise AIError("Tidak ada teks yang dapat dijadikan knowledge base.")
        # Batch across page boundaries while retaining each chunk's page metadata.
        # A long PDF should not consume one upstream request for every page.
        for start in range(0, len(pending_chunks), 12):
            self.assert_live(version_id)
            batch = pending_chunks[start : start + 12]
            self.update(
                version_id,
                stage=f"Embedding {min(start + 12, len(pending_chunks))}/{len(pending_chunks)} chunk",
                progress=70 + int(start / len(pending_chunks) * 25),
            )
            embeddings = self.relay.embed([chunk["text"] for chunk in batch])
            self.vectors.add(batch, embeddings)
            with self.db.connect() as conn:
                conn.executemany("INSERT INTO chunks VALUES (:id,:version_id,:page,:heading,:text)", batch)
        self.assert_live(version_id)
        with self.db.connect() as conn:
            doc = conn.execute("SELECT * FROM documents WHERE id=?", (version["document_id"],)).fetchone()
            if not doc or doc["deleted"] or doc["pending_version"] != version_id:
                raise AIError("Versi dokumen tidak lagi aktif untuk diproses.")
            conn.execute(
                "UPDATE versions SET status='ready', stage='Siap digunakan', progress=100,error='' WHERE id=?",
                (version_id,),
            )
            conn.execute(
                "UPDATE documents SET active_version=?, pending_version=NULL WHERE id=?",
                (version_id, version["document_id"]),
            )
            conn.execute("UPDATE meta SET value=value+1 WHERE key='kb_revision'")
        log.info(
            "ingestion_complete pages=%s chunks=%s elapsed_ms=%s",
            number,
            len(pending_chunks),
            round((time.monotonic() - started) * 1000),
        )


def save_upload(settings, upload, limit):
    directory = settings.data_dir / "documents"
    directory.mkdir(parents=True, exist_ok=True)
    version = uuid.uuid4().hex
    path = directory / (version + ".pdf")
    size, checksum = 0, hashlib.sha256()
    try:
        with path.open("xb") as output:
            signature = upload.file.read(5)
            if signature != b"%PDF-":
                raise AIError("File harus berupa PDF yang valid.")
            output.write(signature)
            checksum.update(signature)
            size = len(signature)
            while block := upload.file.read(1024 * 1024):
                size += len(block)
                if size > limit:
                    raise AIError("Ukuran PDF maksimal 100 MB.")
                output.write(block)
                checksum.update(block)
        with pdfplumber.open(path) as pdf:
            if not 1 <= len(pdf.pages) <= settings.max_pages:
                raise AIError(f"PDF harus berisi 1-{settings.max_pages} halaman.")
    except Exception as exc:
        path.unlink(missing_ok=True)
        if isinstance(exc, AIError):
            raise
        raise AIError("PDF tidak dapat dibuka. File mungkin rusak atau dilindungi password.") from exc
    return version, str(path), checksum.hexdigest(), size
