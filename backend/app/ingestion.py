import base64
import hashlib
import io
import json
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

from .ai import PRIMARY_VISION_MODEL, AIError, OCRFormatError, vision_method, vision_name
from .config import ROOT

log = logging.getLogger("sira.ingestion")
os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(ROOT / "data" / "tokenizer"))
ENCODING = tiktoken.get_encoding("cl100k_base")
PDF_RENDER_LOCK = threading.RLock()


def render_page(path, number, maximum=3000):
    # PDFium is not thread-safe. Serialize native rendering in ingestion and admin preview.
    with PDF_RENDER_LOCK, pdfium.PdfDocument(path) as pdf:
        page = pdf[number - 1]
        try:
            bitmap = page.render(scale=min(3.0, maximum / max(page.get_size())))
            try:
                return bitmap.to_pil().copy()
            finally:
                bitmap.close()
        finally:
            page.close()


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
    negations = Counter(word.casefold() for word in re.findall(r"\b(?:tidak|bukan|dilarang)\b", normalized, re.I))
    semesters = Counter(
        match.upper().replace("|", "I").replace("L", "I")
        for match in re.findall(r"\b(?:SMT|semester)\.?\s+([Il|]{1,3})(?=\s|[.,;:]|$)", normalized, re.I)
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


def consistent_readings(candidate, confirmation):
    def plain(value):
        return re.sub(r"\W+", "", value).casefold()

    similarity = SequenceMatcher(None, plain(candidate), plain(confirmation), autojunk=False).ratio()
    if critical_signature(candidate) != critical_signature(confirmation) or similarity < 0.94:
        raise AIError(
            "Pembacaan ulang OCR/AI masih berbeda pada angka, negasi, atau isi. "
            "Dokumen belum diaktifkan; gunakan scan lebih jelas atau koreksi teks yang diverifikasi."
        )


def region_bounds(image):
    """Disjoint bands at text gaps or full table rules; never split merged cells."""
    ink = (np.asarray(ImageOps.grayscale(image)) < 190).mean(axis=1)
    height = image.height

    def runs(mask):
        padded = np.pad(mask.astype(int), (1, 1))
        starts = np.where(np.diff(padded) == 1)[0]
        ends = np.where(np.diff(padded) == -1)[0]
        return list(zip(starts, ends))

    gaps = [(a + 1, b - 1) for a, b in runs(ink < 0.012) if b - a >= 3]
    # Partial rules inside a vertically merged cell are shorter. Only full rules
    # are safe cut points; blank lines inside that cell must not split it.
    rules = [int(b) for a, b in runs(ink > 0.6)]
    table = (min(rules), max(rules)) if len(rules) >= 8 else None
    paths = [(0, 0.0, [0])]
    for index in range(1, 6):
        target = round(height * index / 6)
        candidates = set(rules if table else [])
        for a, b in gaps:
            y = min(max(target, a), b)
            if not table or not table[0] <= y <= table[1]:
                candidates.add(int(y))
        next_paths = []
        for y in sorted(candidates):
            if not 0 < y < height or abs(y - target) > height / 10:
                continue
            options = [
                (cost + abs(y - target), path + [y])
                for last, cost, path in paths
                if height / 30 <= y - last <= height / 4
            ]
            if options:
                cost, path = min(options, key=lambda item: item[0])
                next_paths.append((y, cost, path))
        paths = next_paths
    options = [(cost, path + [height]) for last, cost, path in paths if 0 < height - last <= height / 4]
    if not options:
        raise AIError("Batas baris atau sel tabel tidak dapat dipisahkan dengan aman. Gunakan review dan koreksi.")
    _, boundaries = min(options, key=lambda item: item[0])
    return list(zip(boundaries, boundaries[1:]))


def fragment_readable(result):
    return (
        isinstance(result, dict)
        and not result.get("uncertain", True)
        and isinstance(result.get("text"), str)
        and len(re.findall(r"\w", result["text"])) >= 3
        and "[TIDAK TERBACA]" not in result["text"]
    )


def fragments_agree(first, second):
    # Compare positions as well as counts: moving a number to another row matters.
    if critical_signature(first) != critical_signature(second):
        return False

    def tokens(value):
        return re.findall(
            r"\w+|[+%=<>*/-]", unicodedata.normalize("NFKC", value).casefold().replace("–", "-").replace("−", "-")
        )

    a, b = tokens(first), tokens(second)
    if len(a) != len(b):
        return False
    return all(
        x == y or (x.isalpha() and y.isalpha() and SequenceMatcher(None, x, y).ratio() >= 0.9) for x, y in zip(a, b)
    )


class OCRReviewRequired(AIError):
    def __init__(self, text, warning):
        super().__init__(warning)
        self.text = text


class RegionalOCR:
    """Legacy v2 reader for older diagnostic scripts; document jobs use DocumentOCR."""

    def __init__(self, ingestion, force_ai=False):
        self.owner = ingestion
        self.context = ingestion.scan_context
        self.force_ai = force_ai

    def save(self, number, top, bottom, state, text, method, warning, required):
        if self.context:
            version, page = self.context
            self.owner.assert_live(version)
            self.owner.db.execute(
                "INSERT OR REPLACE INTO ocr_regions VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    version,
                    page,
                    number,
                    top,
                    bottom,
                    json.dumps(state, ensure_ascii=False),
                    text,
                    method,
                    warning,
                    int(required),
                ),
            )

    def extract(self, image):
        bounds = region_bounds(image)
        texts, warnings, methods, unresolved = [], [], set(), False
        sol_calls = 0
        for number, (top, bottom) in enumerate(bounds, 1):
            state, method, warning = {}, "ocr-local-regions-v2", ""
            cached = None
            if self.context:
                version, page = self.context
                self.owner.assert_live(version)
                self.owner.update(version, stage=f"OCR bertahap: halaman {page}, bagian {number}/{len(bounds)}")
                cached = self.owner.db.one(
                    "SELECT * FROM ocr_regions WHERE version_id=? AND page=? AND number=?", (version, page, number)
                )
            if cached:
                state = json.loads(cached["state"])
                sol_calls += int("sol" in state)
                if state.get("done") and not (self.force_ai and cached["method"] == "ocr-local-regions-v2"):
                    texts.append(cached["text"])
                    methods.add(cached["method"])
                    if cached["warning"]:
                        warnings.append(cached["warning"])
                    unresolved |= bool(cached["required"])
                    continue
            crop = image.crop((0, top, image.width, bottom))
            # No overlap: accepted text is merged in original spatial order exactly once.
            if ImageOps.grayscale(crop).getextrema()[0] > 245:
                continue
            processed = preprocess(crop)
            if "local" not in state:
                try:
                    local, confidence = self.owner.extract_local(processed)
                except AIError:
                    local, confidence = "", 0
                state["local"] = {"text": local, "confidence": confidence}
                self.save(number, top / image.height, bottom / image.height, state, local, method, "", True)
            local, confidence = state["local"]["text"], state["local"]["confidence"]
            text = local
            doubtful = (
                self.force_ai
                or confidence < 95
                or len(re.findall(r"\w", local)) < 3
                or bool(re.search(r"\d|\b(?:tidak|bukan|dilarang|pangkat|ijazah|syarat|semester)\b", local, re.I))
            )
            required = False
            if doubtful and self.owner.settings.vision_enabled and self.owner.settings.ai_ready:

                def read(key, picture, fragment=False):
                    if key not in state:
                        if self.context:
                            self.owner.update(
                                self.context[0],
                                stage=f"{'GPT-5.6 Sol' if fragment else vision_name(PRIMARY_VISION_MODEL)}: halaman {self.context[1]}, bagian {number}/{len(bounds)}",
                            )
                        # Network/budget errors propagate; they must never trigger a dearer model.
                        try:
                            state[key] = self.owner.relay.vision(
                                image_payload(picture, (2400, 1200)), enhanced=True, fragment=fragment
                            )
                        except OCRFormatError:
                            state[key] = {"text": "", "uncertain": True}
                        state[key + "_model"] = state[key].get(
                            "_model", "gpt-5.6-sol" if fragment else PRIMARY_VISION_MODEL
                        )
                        self.save(
                            number,
                            top / image.height,
                            bottom / image.height,
                            state,
                            state[key]["text"],
                            method,
                            "",
                            True,
                        )
                    return state[key]

                first = read("mini", processed)
                model = state.get("mini_model", "gpt-4.1-mini")
                text, method = first["text"], vision_method([model], pipeline="regions-v2")
                agreed = fragment_readable(first) and not self.force_ai and fragments_agree(local, text)
                if not agreed:
                    second = read("mini_check", crop)
                    agreed = (
                        fragment_readable(first)
                        and fragment_readable(second)
                        and fragments_agree(first["text"], second["text"])
                    )
                    if not agreed:
                        # If most of a page is unreadable, stop escalating rather than send
                        # its entirety piecemeal to the expensive last-resort model.
                        if "sol" in state or sol_calls < 2:
                            new_call = "sol" not in state
                            final = read("sol", crop, fragment=True)
                            sol_calls += int(new_call)
                            text, method = final["text"], vision_method([model], sol=True, pipeline="regions-v2")
                            agreed = fragment_readable(final) and any(
                                candidate["text"].strip() and fragments_agree(text, candidate["text"])
                                for candidate in (first, second)
                            )
                        required = not agreed
                warning = f"Bagian {number} ({top / image.height:.0%}–{bottom / image.height:.0%} tinggi halaman): "
                warning += (
                    "masih perlu koreksi admin."
                    if required
                    else f"diperiksa dengan {('GPT-5.6 Sol setelah ' if '5.6-sol' in method else '') + vision_name(model)}."
                )
            elif doubtful:
                required = True
                warning = f"Bagian {number} ({top / image.height:.0%}–{bottom / image.height:.0%}): perlu review; bantuan AI belum aktif."
            state["done"] = True
            self.save(number, top / image.height, bottom / image.height, state, text, method, warning, required)
            texts.append(text)
            methods.add(method)
            if warning:
                warnings.append(warning)
            unresolved |= required
        text = "\n\n".join(texts)
        if not readable(text):
            unresolved = True
            warnings.append("Teks halaman terlalu sedikit; cocokkan dengan gambar asli.")
        if unresolved:
            raise OCRReviewRequired(text, "\n".join(warnings))
        models = {
            "gpt-6-luna" if "6-luna" in method else "gpt-4.1-mini"
            for method in methods
            if "mini" in method or "6-luna" in method
        }
        method = (
            vision_method(models, sol=any("sol" in value for value in methods), pipeline="regions-v2")
            if models
            else "ocr-local-regions-v2"
        )
        return text, method, "\n".join(warnings)


def chunk_page(text, version_id, page, target=650, overlap=100):
    # Keep source pages explicit. Prefer paragraph boundaries while bounding tokens.
    paragraphs = re.split(r"\n\s*\n", text.strip())
    pieces = []
    for paragraph in paragraphs:
        tokens = ENCODING.encode(paragraph)
        if paragraph.startswith("[TABEL "):
            # A normalized row is an atomic evidence unit, with its headers and
            # explicit merged-cell values. Never separate an activity/date pair.
            pieces.append(paragraph)
        elif len(tokens) > target:
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
        self.scan_context = None
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
                row = self.db.one("SELECT ocr_mode FROM versions WHERE id=?", (version,))
                if row and row["ocr_mode"] == "review":
                    self.prepare_review(version)
                else:
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
                if row["path"]:  # bundled seed versions have no PDF file
                    Path(row["path"]).unlink(missing_ok=True)
                with self.db.connect() as conn:
                    conn.execute("DELETE FROM chunks WHERE version_id=?", (row["id"],))
                    conn.execute("DELETE FROM pages WHERE version_id=?", (row["id"],))
                    conn.execute("DELETE FROM review_pages WHERE version_id=?", (row["id"],))
                    conn.execute("DELETE FROM ocr_regions WHERE version_id=?", (row["id"],))
                    conn.execute("DELETE FROM ocr_page_jobs WHERE version_id=?", (row["id"],))
                    conn.execute("DELETE FROM versions WHERE id=?", (row["id"],))
            except (OSError, RuntimeError):
                log.warning("cleanup_pending")

    def extract_local(self, image):
        text, confidence, _ = self.extract_local_evidence(image)
        return text, confidence

    def extract_local_evidence(self, image):
        try:
            data = pytesseract.image_to_data(
                image, lang=self.settings.ocr_lang, config="--psm 3", output_type=pytesseract.Output.DICT, timeout=60
            )
        except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError, RuntimeError) as exc:
            raise AIError(
                "OCR lokal belum siap atau melewati batas waktu. Pasang Tesseract beserta bahasa ind dan eng, lalu proses ulang."
            ) from exc
        lines, confidences, words = {}, [], []
        for i, word in enumerate(data["text"]):
            if not word.strip():
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(word)
            if float(data["conf"][i]) >= 0:
                confidences.append(float(data["conf"][i]))
            words.append(
                {
                    "text": word,
                    "confidence": float(data["conf"][i]),
                    "bbox": [
                        data["left"][i] / image.width,
                        data["top"][i] / image.height,
                        (data["left"][i] + data["width"][i]) / image.width,
                        (data["top"][i] + data["height"][i]) / image.height,
                    ],
                }
            )
        text = "\n".join(" ".join(words) for words in lines.values())
        confidence = sum(confidences) / max(1, len(confidences))
        return text, confidence, words

    def extract_scan(self, image):
        return RegionalOCR(self).extract(image)

    def extract_with_ai(self, image):
        # Admin action checks every nonblank region with AI, still after local OCR.
        return RegionalOCR(self, force_ai=True).extract(image)

    def prepare_review(self, version_id):
        version = self.db.one("SELECT * FROM versions WHERE id=?", (version_id,))
        self.assert_live(version_id)
        total_size = 0
        with pdfplumber.open(version["path"]) as pdf:
            if not 1 <= len(pdf.pages) <= self.settings.max_pages:
                raise AIError("Jumlah halaman PDF melewati batas.")
            self.update(version_id, page_count=len(pdf.pages))
            for number, page in enumerate(pdf.pages, 1):
                self.assert_live(version_id)
                existing = self.db.one(
                    "SELECT * FROM review_pages WHERE version_id=? AND number=?", (version_id, number)
                )
                if existing and existing["revision"] > 0:
                    total_size += len(existing["text"])
                    continue
                accepted = self.db.one("SELECT * FROM pages WHERE version_id=? AND number=?", (version_id, number))
                if (
                    accepted
                    and accepted["method"].startswith("ocr")
                    and not (
                        accepted["method"].endswith("regions-v2")
                        or accepted["method"].endswith("ai-4.1-mini-crops-v1")
                        or accepted["method"].endswith("layout-v3")
                    )
                ):
                    accepted = None
                regions = self.db.rows(
                    "SELECT * FROM ocr_regions WHERE version_id=? AND page=? ORDER BY number", (version_id, number)
                )
                v3_job = self.db.one(
                    "SELECT plan FROM ocr_page_jobs WHERE version_id=? AND page=?", (version_id, number)
                )
                is_v3 = bool(v3_job)
                if not accepted and regions and not is_v3:
                    # A budget/network failure may have stopped mid-page. Complete only
                    # the missing draft regions locally, without another API request.
                    image = render_page(version["path"], number)
                    by_number = {row["number"]: row for row in regions}
                    for region_number, (top, bottom) in enumerate(region_bounds(image), 1):
                        if region_number in by_number:
                            continue
                        crop = image.crop((0, top, image.width, bottom))
                        blank = ImageOps.grayscale(crop).getextrema()[0] > 245
                        try:
                            draft, confidence = ("", 100) if blank else self.extract_local(preprocess(crop))
                        except AIError:
                            draft, confidence = "", 0
                        self.db.execute(
                            "INSERT OR IGNORE INTO ocr_regions VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (
                                version_id,
                                number,
                                region_number,
                                top / image.height,
                                bottom / image.height,
                                json.dumps({"local": {"text": draft, "confidence": confidence}, "done": blank}),
                                draft,
                                "blank" if blank else "ocr-local-draft",
                                ""
                                if blank
                                else f"Bagian {region_number}: pemeriksaan belum selesai; cocokkan dengan gambar.",
                                int(not blank),
                            ),
                        )
                    regions = self.db.rows(
                        "SELECT * FROM ocr_regions WHERE version_id=? AND page=? ORDER BY number", (version_id, number)
                    )
                text = accepted["text"] if accepted else (page.extract_text(layout=False) or "")
                method = accepted["method"] if accepted else "text"
                required = not accepted
                warning = (
                    "Halaman lolos pemeriksaan otomatis; review tambahan bersifat opsional."
                    if accepted
                    else "Periksa teks yang belum terverifikasi, terutama angka, periode, negasi, dan tabel."
                )
                self.update(
                    version_id,
                    stage=f"Menyiapkan review: halaman {number}/{len(pdf.pages)}",
                    progress=int(number / len(pdf.pages) * 95),
                )
                if not accepted and is_v3:
                    from .ocr_layout import block_text

                    plan = json.loads(v3_job["plan"])
                    parts = {r["number"]: r for r in regions if r["number"] > 0}
                    drafts = []
                    for part, zone in enumerate(plan.get("zones", []), 1):
                        saved = parts.get(part)
                        draft = saved["text"] if saved else ""
                        if saved and not draft:
                            state = json.loads(saved["state"])
                            draft = "\n\n".join(
                                block_text(block, part) for block in state.get("mini", {}).get("blocks", [])
                            ) or state.get("mini", {}).get("draft_text", "")
                        drafts.append(draft or zone["text"])
                        if not saved:
                            self.db.execute(
                                "INSERT OR IGNORE INTO ocr_regions VALUES (?,?,?,?,?,?,?,?,?,?)",
                                (
                                    version_id,
                                    number,
                                    part,
                                    zone["bbox"][1],
                                    zone["bbox"][3],
                                    json.dumps({"pipeline": "layout-v3", "input_layout": "source-zones-v1"}),
                                    zone["text"],
                                    "ocr-layout-draft-v3",
                                    "Pembacaan gambar belum selesai; cocokkan dengan sumber.",
                                    int(zone["ai"]),
                                ),
                            )
                    text = "\n\n".join(drafts) or plan["text"]
                    method = "ocr-layout-draft-v3"
                    warning = (
                        "\n".join(r["warning"] for r in regions if r["required"])
                        or "Pembacaan gambar belum lengkap; cocokkan draft dengan sumber."
                    )
                elif not accepted and regions:
                    text = "\n\n".join(row["text"] for row in regions)
                    method = "ocr-regions-draft"
                    warning = (
                        "\n".join(row["warning"] for row in regions if row["required"])
                        or "Pemrosesan belum selesai; periksa draft halaman."
                    )
                elif not accepted and not readable(text):
                    if page.width * page.height > 10_000_000:
                        raise AIError("Ukuran halaman terlalu besar untuk diproses dengan aman.")
                    image = render_page(version["path"], number)
                    if ImageOps.grayscale(image).getextrema()[0] > 245:
                        text, method = "", "blank"
                    else:
                        try:
                            text, _ = self.extract_local(preprocess(image))
                            method = "ocr-local-draft"
                        except AIError:
                            text, method = "", "unreadable"
                            warning = "OCR lokal tidak tersedia atau gagal. Salin teks dari gambar secara manual."
                if len(text) > 100_000:
                    raise AIError(f"Halaman {number}: teks terlalu panjang untuk review. Pisahkan PDF.")
                total_size += len(text)
                if total_size > 5_000_000:
                    raise AIError("Teks PDF terlalu besar. Pisahkan PDF.")
                self.db.execute(
                    "INSERT INTO review_pages(version_id,number,text,method,warning,required) VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(version_id,number) DO UPDATE SET text=excluded.text,method=excluded.method,warning=excluded.warning,required=excluded.required WHERE review_pages.revision=0",
                    (version_id, number, text, method, warning, int(required)),
                )
        self.assert_live(version_id)
        self.update(
            version_id,
            status="review",
            stage="Menunggu review admin",
            progress=100,
            error="",
            warning="Teks belum menjadi knowledge base. Konfirmasi halaman yang ditandai perlu review; halaman lolos otomatis tidak wajib dikonfirmasi ulang.",
        )

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
        from .ocr_pipeline import DocumentOCR

        needs_review = DocumentOCR(self, version).extract()
        warnings, pending_chunks, text_size = [], [], 0
        for saved in self.db.rows("SELECT * FROM pages WHERE version_id=? ORDER BY number", (version_id,)):
            number = saved["number"]
            if saved["warning"]:
                warnings.append(f"Halaman {number}: {saved['warning']}")
            page_chunks = chunk_page(saved["text"], version_id, number)
            pending_chunks.extend(page_chunks)
            text_size += sum(len(chunk["text"]) for chunk in page_chunks)
            if text_size > 5_000_000:
                raise AIError("Teks PDF terlalu besar. Pisahkan dokumen menjadi beberapa PDF.")
        self.update(version_id, warning="\n".join(warnings))
        if version["ocr_mode"] != "manual" and self.db.one(
            "SELECT 1 FROM review_pages WHERE version_id=? AND revision>0", (version_id,)
        ):
            needs_review = True
        if needs_review:
            self.prepare_review(version_id)
            return
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
