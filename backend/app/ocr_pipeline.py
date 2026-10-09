"""Independent local producer and persistent, concurrent image-reading jobs."""

import copy
import hashlib
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher

import numpy as np
import pdfplumber
from PIL import ImageFilter, ImageOps

from .ai import PRIMARY_VISION_MODEL, AIError, OCRFormatError, vision_method
from .ingestion import critical_signature, image_payload, readable, render_page
from .native_pdf import NATIVE_LAYOUT, find_native_tables, native_layout
from .ocr_layout import bbox, block_text, detect_tables, overlap, validate_table

log = logging.getLogger("sira.ocr")
PIPELINE = "layout-v3"
VALIDATOR = "zone-evidence-v3"


def words_in(words, bounds):
    x0, y0, x1, y1 = bounds
    return " ".join(
        word["text"]
        for word in words
        if x0 - 0.005 <= (word["bbox"][0] + word["bbox"][2]) / 2 <= x1 + 0.005
        and y0 - 0.005 <= (word["bbox"][1] + word["bbox"][3]) / 2 <= y1 + 0.005
    )


def image_zones(image, tables, words, force):
    """Crop by source geometry, never by a model's estimated coordinates."""
    zones, remaining = [], [[0, 0, 1, 1]]
    for grid in tables:
        left, y0, right, y1 = grid["bbox"]
        bounds = [max(0, left - 0.008), max(0, y0 - 0.008), min(1, right + 0.008), min(1, y1 + 0.008)]
        zones.append({"bbox": bounds, "grid": grid})
        # Subtract the table rectangle rather than discarding its whole vertical
        # band: notes beside a table and side-by-side tables must survive too.
        next_remaining = []
        for a, b, c, d in remaining:
            x, y, z, q = max(a, bounds[0]), max(b, bounds[1]), min(c, bounds[2]), min(d, bounds[3])
            if x >= z or y >= q:
                next_remaining.append([a, b, c, d])
                continue
            next_remaining.extend([[a, b, c, y], [a, q, c, d], [a, y, x, q], [z, y, c, q]])
        remaining = [rect for rect in next_remaining if rect[2] - rect[0] > 0.001 and rect[3] - rect[1] > 0.001]
    zones.extend({"bbox": rect, "grid": None} for rect in remaining)
    gray = np.asarray(ImageOps.grayscale(image))
    nonblank = []
    for zone in zones:
        if not zone["grid"]:
            bounds = zone["bbox"]
            a, b = round(bounds[1] * image.height), round(bounds[3] * image.height)
            left = round((bounds[0] + (bounds[2] - bounds[0]) * 0.05) * image.width)
            right = round((bounds[2] - (bounds[2] - bounds[0]) * 0.05) * image.width)
            ink = gray[a:b, left:right] < 170
            occupied = np.flatnonzero(ink.mean(axis=1) > 0.007) if ink.size else []
            if not len(occupied):
                continue
            if len(occupied):
                bounds[1] = max(bounds[1], (a + int(occupied[0]) - 12) / image.height)
                bounds[3] = min(bounds[3], (a + int(occupied[-1]) + 13) / image.height)
        relevant = [word for word in words if words_in([word], zone["bbox"])]
        text = " ".join(word["text"] for word in relevant)
        confident = bool(relevant) and min(word["confidence"] for word in relevant) >= 95
        zone["text"] = text
        zone["ai"] = bool(force or zone["grid"] or not confident or not text.strip())
        nonblank.append(zone)
    return sorted(nonblank, key=lambda zone: (zone["bbox"][1], zone["bbox"][0]))


def source_bounds(block, zone, words):
    if block["kind"] == "table" and zone["grid"]:
        return zone["grid"]["bbox"]
    # Match ordered phrases, not every occurrence of common words on the page.
    # Otherwise a small heading containing "Polri" can span the entire page.
    source = [
        (token, word)
        for word in words
        if words_in([word], zone["bbox"])
        for token in re.findall(r"\w+", word["text"].casefold())
    ]
    tokens = re.findall(r"\w+", block["text"].casefold())
    anchors = SequenceMatcher(None, [token for token, _ in source], tokens, autojunk=False).get_matching_blocks()
    anchor = max(anchors, key=lambda match: match.size)
    if anchor.size >= min(3, max(1, len(tokens))):
        offset = anchor.a - anchor.b
        aligned = [
            match
            for match in anchors
            if match.size >= 2 and abs(match.a - match.b - offset) <= max(4, len(tokens) * 0.2)
        ]
        aligned = aligned or [anchor]
        first = min(match.a for match in aligned)
        last = max(match.a + match.size for match in aligned)
        matches = [word for _, word in source[first:last]]
        x0, y0, x1, y1 = zone["bbox"]
        return [
            max(x0, min(w["bbox"][0] for w in matches) - 0.01),
            max(y0, min(w["bbox"][1] for w in matches) - 0.01),
            min(x1, max(w["bbox"][2] for w in matches) + 0.01),
            min(y1, max(w["bbox"][3] for w in matches) + 0.01),
        ]
    return zone["bbox"]


def critical_problem(blocks, zone, words, page):
    """Compare one source area once; weak OCR must not veto clear vision.

    This check runs after independent image reading. Strong local numbers are
    evidence requiring a reread when absent/changed, while uncertain local
    digit guesses are not ground truth. Negations/semesters remain conservative.
    """
    relevant = [word for word in words if words_in([word], zone["bbox"])]

    # An isolated folio is provenance, not a date/condition. Some vision models
    # omit it; the PDF page number is already stored separately as the source.
    def folio(word):
        if word["text"].strip(". ") != str(page) or word["bbox"][1] >= 0.1:
            return False
        a, b = word["bbox"][1], word["bbox"][3]
        return not any(
            other is not word
            and min(b, other["bbox"][3]) - max(a, other["bbox"][1]) > (b - a) * 0.5
            and max(other["bbox"][0] - word["bbox"][2], word["bbox"][0] - other["bbox"][2]) < 0.08
            for other in relevant
        )

    relevant = [word for word in relevant if not folio(word)]
    local = critical_signature(" ".join(word["text"] for word in relevant))
    strong = critical_signature(" ".join(word["text"] for word in relevant if word["confidence"] >= 95))
    vision = critical_signature(" ".join(block_text(block) for block in blocks))
    if strong[0] - vision[0] or (relevant and (local[1] != vision[1] or local[2] != vision[2])):
        return "Angka yang terbaca kuat, negasi, atau semester berbeda; perlu pembacaan gambar ulang."
    return ""


def valid_blocks(result):
    blocks = result.get("blocks") if isinstance(result, dict) else None
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 128:
        raise OCRFormatError("AI belum menghasilkan bagian dokumen yang dapat diverifikasi.")
    size = 0
    for block in blocks:
        if (
            not isinstance(block, dict)
            or block.get("kind") not in ("text", "table")
            or type(block.get("uncertain")) is not bool
        ):
            raise OCRFormatError("Struktur bagian AI tidak valid.")
        try:
            bbox(block.get("bbox"))
        except ValueError as exc:
            raise OCRFormatError(str(exc)) from exc
        if not isinstance(block.get("text"), str) or not isinstance(block.get("cells"), list):
            raise OCRFormatError("Format teks/sel AI tidak valid.")
        if len(block["cells"]) > 4000 or any(not isinstance(cell, dict) for cell in block["cells"]):
            raise OCRFormatError("Format sel AI tidak valid.")
        size += len(block["text"]) + sum(len(str(cell.get("text", ""))) for cell in block["cells"])
    if size > 100_000:
        raise OCRFormatError("Teks halaman terlalu besar.")
    return sorted(blocks, key=lambda block: (block["bbox"][1], block["bbox"][0]))


def table_grid(block, grids):
    matches = [(overlap(block["bbox"], grid["bbox"]), grid) for grid in grids]
    score, grid = max(matches, key=lambda pair: pair[0], default=(0, None))
    return grid if score > 0.35 else None


def issue(block, plan):
    if block["kind"] == "table":
        problem = validate_table(block, table_grid(block, plan["tables"]))
        if problem:
            return problem
        text = " ".join(cell["text"] for cell in block["cells"])
    else:
        text = block["text"]
        x0, y0, x1, y1 = block["bbox"]
        for grid in plan["tables"]:
            a, b, c, d = grid["bbox"]
            area = max(0, min(x1, c) - max(x0, a)) * max(0, min(y1, d) - max(y0, b))
            if area > 0.65 * (x1 - x0) * (y1 - y0) or area > 0.8 * (c - a) * (d - b):
                return "Tabel masih disajikan sebagai teks; struktur sel perlu dibaca dari gambar."
        if block.get("cells") or block.get("columns", 0) != 0 or block.get("header_rows", 0) != 0:
            return "Teks biasa memiliki struktur tabel yang tidak valid."
        if not text.strip():
            return "Bagian teks kosong."
    if block["uncertain"] or "[TIDAK TERBACA]" in text:
        return "AI belum yakin membaca teks atau hubungan antar sel."
    return ""


class DocumentOCR:
    def __init__(self, owner, version):
        self.owner, self.version = owner, version
        self.db = owner.db
        self.id = version["id"]
        self.force = version["ocr_mode"] == "ai"
        self.abort_ai = threading.Event()
        self.failure = None
        self.lock = threading.Lock()
        self.local_done = self.ai_done = self.ai_total = self.total = self.progress_value = 0
        self.table_total = self.area_total = 0

    def progress(self, *, local=False, queued=False, completed=False, tables=0, areas=0):
        with self.lock:
            self.local_done += int(local)
            self.ai_total += int(queued)
            self.ai_done += int(completed)
            self.table_total += tables
            self.area_total += areas
            prefix = f"Pemeriksaan lokal: {self.local_done}/{self.total} halaman"
            if self.local_done == self.total:
                prefix = "Pemeriksaan lokal selesai"
            stage = (
                prefix
                + f" · {self.table_total} tabel · AI: {self.ai_done}/{self.ai_total} halaman ({self.area_total} area)"
            )
            value = int(30 * self.local_done / max(1, self.total) + 35 * self.ai_done / max(1, self.ai_total))
            self.progress_value = max(self.progress_value, value)
            self.owner.update(self.id, stage=stage, progress=self.progress_value)

    def page(self, number, text, method, warning=""):
        self.owner.assert_live(self.id)
        self.db.execute("INSERT OR REPLACE INTO pages VALUES (?,?,?,?,?)", (self.id, number, text, method, warning))

    def cache(self, number):
        row = self.db.one("SELECT * FROM pages WHERE version_id=? AND number=?", (self.id, number))
        if not row:
            return None
        if self.version["ocr_mode"] == "manual" or row["method"] in {"manual-reviewed-v1", "blank"}:
            return row
        if row["method"] == NATIVE_LAYOUT:
            return row if not self.force else None
        job = self.db.one("SELECT plan FROM ocr_page_jobs WHERE version_id=? AND page=?", (self.id, number))
        if job and not self.force:
            plan = json.loads(job["plan"])
            if self.old_native_plan(plan):
                return None
        if row["method"].endswith(PIPELINE) and not (self.force and row["method"] == "ocr-local-layout-v3"):
            return row
        # Existing narrative text is reusable; old flattened OCR/table text must
        # be analyzed again, without modifying already-active document versions.
        return None

    @staticmethod
    def old_native_plan(plan):
        return (
            not plan.get("native_source")
            and "tabel" in plan.get("flags", [])
            and not plan.get("words")
            and set(plan["flags"]) <= {"tabel", "pembacaan AI diminta admin"}
        )

    def save_native(self, number, result, table_count, started):
        flags = ["struktur tabel native belum lengkap"] if result["failures"] else []
        plan = {
            "pipeline": PIPELINE,
            "native_source": NATIVE_LAYOUT,
            "native_blocks": result["blocks"],
            "native_table_count": table_count,
            "zones": result["zones"],
            "text": result["text"],
            "words": result["words"],
            "tables": [],
            "flags": flags,
            "confidence": None,
            "local_ms": round((time.monotonic() - started) * 1000),
        }
        self.db.execute(
            "INSERT OR REPLACE INTO ocr_page_jobs(version_id,page,plan,status) VALUES (?,?,?,?)",
            (self.id, number, json.dumps(plan, ensure_ascii=False), "queued" if flags else "done"),
        )
        if not flags:
            self.page(number, result["text"], NATIVE_LAYOUT)
            self.db.execute(
                "UPDATE review_pages SET text=?,method=?,warning='',required=0,confirmed=0 "
                "WHERE version_id=? AND number=? AND revision=0",
                (result["text"], NATIVE_LAYOUT, self.id, number),
            )
            # Retain paid historical readings, but they no longer describe the
            # accepted native text. Never present their old warnings as current.
            for region in self.db.rows("SELECT * FROM ocr_regions WHERE version_id=? AND page=?", (self.id, number)):
                state = json.loads(region["state"])
                state["superseded_by_native"] = NATIVE_LAYOUT
                self.db.execute(
                    "UPDATE ocr_regions SET state=?,required=0 WHERE version_id=? AND page=? AND number=?",
                    (json.dumps(state, ensure_ascii=False), self.id, number, region["number"]),
                )
        return plan

    def analyze(self, page, number):
        existing = self.db.one("SELECT plan FROM ocr_page_jobs WHERE version_id=? AND page=?", (self.id, number))
        if existing:
            plan = json.loads(existing["plan"])
            if (
                plan.get("pipeline") == PIPELINE
                and "zones" in plan
                and not (not self.force and self.old_native_plan(plan))
                and not (self.force and plan.get("native_source"))
            ):
                if self.force and "pembacaan AI diminta admin" not in plan["flags"]:
                    plan["flags"].append("pembacaan AI diminta admin")
                    for zone in plan["zones"]:
                        zone["ai"] = True
                    self.db.execute(
                        "UPDATE ocr_page_jobs SET plan=?,status='queued' WHERE version_id=? AND page=?",
                        (json.dumps(plan, ensure_ascii=False), self.id, number),
                    )
                return plan
        started = time.monotonic()
        if page.width * page.height > 10_000_000:
            raise AIError("Ukuran halaman terlalu besar untuk diproses dengan aman.")
        native = page.extract_text(layout=False) or ""
        # Native PDF tables also need layout extraction; text availability alone
        # does not mean the relationships between cells survived extraction.
        native_tables = page.find_tables() if page.lines or page.rects else []
        image_heavy = sum(im["width"] * im["height"] for im in page.images) > page.width * page.height * 0.5
        # A readable native caption must not hide a sizeable scanned region.
        mixed_image = bool(native.strip()) and any(
            im["width"] * im["height"] > page.width * page.height * 0.05 for im in page.images
        )
        image_heavy |= mixed_image
        if readable(native) and native_tables and not image_heavy and not self.force:
            try:
                tables = find_native_tables(page)
                result = native_layout(page, tables)
                if len(result["text"]) > 100_000:
                    raise AIError(f"Halaman {number}: teks terlalu panjang. Pisahkan dokumen.")
                return self.save_native(number, result, len(tables), started)
            except ValueError:
                # Unresolved geometry still uses the established image reader;
                # readable PDF text alone is not an acceptance guarantee.
                pass
        image = None
        words, tables, flags = [], [], []
        confidence = 100
        if not readable(native) or native_tables or image_heavy or self.force:
            image = render_page(self.version["path"], number)
            if ImageOps.grayscale(image).getextrema()[0] > 245:
                self.page(number, "", "blank")
                return None
            tables = detect_tables(image)
            if not readable(native) or image_heavy:
                # Keep word coordinates in the ORIGINAL image coordinate space.
                processed = ImageOps.autocontrast(ImageOps.grayscale(image)).filter(ImageFilter.SHARPEN)
                try:
                    native, confidence, words = self.owner.extract_local_evidence(processed)
                except AIError:
                    native, confidence = "", 0
                if confidence < 96 or not readable(native):
                    flags.append("kualitas teks")
                if any(
                    re.search(r"\d|\b(?:tidak|bukan|dilarang)\b", w["text"], re.I) and w["confidence"] < 95
                    for w in words
                ):
                    flags.append("angka/negasi meragukan")
                # Multiple word columns/large horizontal jumps may indicate a
                # borderless table. Be conservative, but do not split the page.
                bands = {}
                for word in words:
                    bands.setdefault(round(word["bbox"][1] * 100), []).append(word["bbox"])
                if (
                    sum(any(b[0] - a[2] > 0.10 for a, b in zip(sorted(row), sorted(row)[1:])) for row in bands.values())
                    >= 3
                ):
                    flags.append("kolom kompleks")
            if tables or native_tables:
                flags.append("tabel")
        if self.force:
            flags.append("pembacaan AI diminta admin")
        if len(native) > 100_000:
            raise AIError(f"Halaman {number}: teks terlalu panjang. Pisahkan dokumen.")
        plan = {
            "zones": image_zones(image, tables, words, self.force or "kolom kompleks" in flags) if image else [],
            "pipeline": PIPELINE,
            "text": native,
            "confidence": confidence,
            "words": words,
            "tables": tables,
            "flags": flags,
            "local_ms": round((time.monotonic() - started) * 1000),
        }
        self.db.execute(
            "INSERT OR REPLACE INTO ocr_page_jobs(version_id,page,plan,status) VALUES (?,?,?,?)",
            (self.id, number, json.dumps(plan, ensure_ascii=False), "queued" if flags else "done"),
        )
        if not flags:
            method = "text-layout-v3" if not words else "ocr-local-layout-v3"
            self.page(number, native, method)
        return plan

    def save_region(self, page, number, bounds, state, text, method, warning, required):
        self.owner.assert_live(self.id)
        self.db.execute(
            "INSERT OR REPLACE INTO ocr_regions VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                self.id,
                page,
                number,
                bounds[1],
                bounds[3],
                json.dumps(state, ensure_ascii=False),
                text,
                method,
                warning,
                int(required),
            ),
        )

    def read(self, page, number, image, bounds, key, state, *, sol=False):
        if key not in state:
            self.owner.assert_live(self.id)
            if self.abort_ai.is_set():
                raise AIError(
                    "Antrean AI ditunda karena layanan belum tersedia. Hasil lokal tetap tersimpan; gunakan Proses ulang."
                )
            # Only original rendered pixels are transmitted, never local text or
            # another model's output. Hash records which exact image was sent.
            payload = image_payload(image, (2400, 3000) if not sol else (2400, 2400))
            before = time.monotonic()
            result = None
            try:
                result = self.owner.relay.vision(payload, enhanced=True, fragment=sol, structured=True)
                valid_blocks(result)
                state[key] = result
            except OCRFormatError as exc:
                state[key] = {"blocks": [], "format_error": str(exc)}
                # A bad position must not discard the paid transcription draft.
                # It stays unverified and can only be used in manual review.
                if isinstance(result, dict) and isinstance(result.get("blocks"), list):
                    state[key]["draft_text"] = "\n\n".join(
                        block.get("text", "")
                        for block in result["blocks"][:128]
                        if isinstance(block, dict) and isinstance(block.get("text"), str)
                    )[:100_000]
            state[key + "_model"] = (result if isinstance(result, dict) else {}).get(
                "_model", "gpt-5.6-sol" if sol else PRIMARY_VISION_MODEL
            )
            state[key + "_input_sha256"] = hashlib.sha256(payload.encode()).hexdigest()
            state[key + "_ms"] = round((time.monotonic() - before) * 1000)
            state[key + "_bbox"] = bounds
            self.save_region(
                page, number, bounds, state, "", "ocr-layout-draft-v3", "Pembacaan gambar sedang diverifikasi.", True
            )
        return state[key]

    def process_page(self, number, plan):
        started = time.monotonic()
        try:
            self.owner.assert_live(self.id)
            image = None
            texts, unresolved, sol_used, ai_used = [], False, False, False
            ai_models = set()
            for part, zone in enumerate(plan["zones"], 1):
                self.owner.assert_live(self.id)
                prior = self.db.one(
                    "SELECT * FROM ocr_regions WHERE version_id=? AND page=? AND number=?", (self.id, number, part)
                )
                state = json.loads(prior["state"]) if prior else {}
                input_layout = NATIVE_LAYOUT if plan.get("native_source") else "source-zones-v1"
                if state.get("input_layout") != input_layout:
                    state = {"pipeline": PIPELINE, "input_layout": input_layout}
                if "mini" in state:
                    ai_models.add(state.get("mini_model", "gpt-4.1-mini"))
                requires_table = bool(zone["grid"] or zone.get("table_required"))
                if state.get("done") and state.get("validator") == VALIDATOR:
                    texts.append(prior["text"])
                    unresolved |= bool(prior["required"])
                    sol_used |= "sol" in state
                    ai_used |= "mini" in state
                    continue
                bounds = zone["bbox"]
                # Preserve the completed Sol composition, including any clear
                # mini blocks outside its crop. Re-adding mini here duplicates
                # text and can discard uncertainty from the final paid reading.
                if state.get("done") and "sol" in state and state.get("resolved_blocks"):
                    final_blocks = copy.deepcopy(valid_blocks({"blocks": state["resolved_blocks"]}))
                    problems = []
                    for block in final_blocks:
                        block["bbox"] = source_bounds(block, zone, plan["words"])
                        problems.append(issue(block, plan))
                        if block["kind"] == "table" and zone["grid"]:
                            problems.append(validate_table(block, zone["grid"]))
                    if requires_table and sum(b["kind"] == "table" for b in final_blocks) != 1:
                        problems.append("Tabel belum dibaca secara utuh.")
                    problem = "; ".join(dict.fromkeys(p for p in problems if p))
                    text = "\n\n".join(block_text(block, part) for block in final_blocks)
                    state.update(validator=VALIDATOR, resolved_blocks=final_blocks)
                    self.save_region(
                        number,
                        part,
                        bounds,
                        state,
                        text,
                        vision_method([state.get("mini_model", "gpt-4.1-mini")], sol=True),
                        f"Bagian {part}: {problem}" if problem else "",
                        bool(problem),
                    )
                    texts.append(text)
                    unresolved |= bool(problem)
                    sol_used = ai_used = True
                    continue
                if not zone["ai"]:
                    text, method, problem = zone["text"], "ocr-local-layout-v3", ""
                elif not self.owner.settings.vision_enabled or not self.owner.settings.ai_ready:
                    text, method, problem = (
                        zone["text"] or plan["text"],
                        "ocr-layout-draft-v3",
                        "Perlu review; bantuan pembacaan gambar AI belum aktif.",
                    )
                else:
                    ai_used = True
                    if image is None:
                        image = render_page(self.version["path"], number)
                    crop = image.crop(
                        (
                            round(bounds[0] * image.width),
                            round(bounds[1] * image.height),
                            round(bounds[2] * image.width),
                            round(bounds[3] * image.height),
                        )
                    )
                    result = self.read(number, part, crop, bounds, "mini", state)
                    ai_models.add(state["mini_model"] if "mini_model" in state else "gpt-4.1-mini")
                    method = vision_method([state.get("mini_model", "gpt-4.1-mini")])
                    try:
                        blocks = copy.deepcopy(valid_blocks(result))
                    except OCRFormatError:
                        blocks = []
                    problems = []
                    for block in blocks:
                        block["bbox"] = source_bounds(block, zone, plan["words"])
                        problem = issue(block, plan)
                        if block["kind"] == "table" and zone["grid"]:
                            problem = validate_table(block, zone["grid"]) or problem
                        problems.append(problem)
                    if requires_table and sum(b["kind"] == "table" for b in blocks) != 1:
                        problems = ["Tabel belum dibaca secara utuh."] * max(1, len(blocks))
                    if not blocks:
                        problems = ["Struktur AI belum lengkap; cocokkan draft dengan gambar sumber."]
                    critical = critical_problem(blocks, zone, plan["words"], number)
                    if critical:
                        problems = [problem or critical for problem in problems]
                    # Detect omitted source text using independent local evidence.
                    # This is only a warning signal; no local text is sent to AI.
                    zone_text = zone["text"]
                    extracted = " ".join(block_text(b, part) for b in blocks)
                    local_terms = set(re.findall(r"\w{4,}", zone_text.casefold()))
                    seen = set(re.findall(r"\w{4,}", extracted.casefold()))
                    if len(local_terms - seen) >= max(8, len(local_terms) * 0.35):
                        problems = ["Ada teks sumber yang belum tercakup dalam pembacaan gambar."] * max(1, len(blocks))
                    text = (
                        "\n\n".join(block_text(b, part) for b in blocks)
                        or result.get("draft_text")
                        or zone_text
                        or plan["text"]
                    )
                    problem = "; ".join(dict.fromkeys(p for p in problems if p))
                    if problem or "sol" in state:
                        # Only disputed blocks are sent to Sol. A whole table is
                        # retained even when one merged cell causes the dispute.
                        disputed = [b for i, b in enumerate(blocks) if i < len(problems) and problems[i]]
                        sol_bounds = bounds
                        if disputed and not requires_table:
                            sol_bounds = [
                                min(b["bbox"][0] for b in disputed),
                                min(b["bbox"][1] for b in disputed),
                                max(b["bbox"][2] for b in disputed),
                                max(b["bbox"][3] for b in disputed),
                            ]
                        if "sol" in state:
                            sol_bounds = state.get("sol_bbox", sol_bounds)
                        if "sol" in state or requires_table or sol_bounds[3] - sol_bounds[1] < 0.75:
                            sol_crop = image.crop(
                                (
                                    round(sol_bounds[0] * image.width),
                                    round(sol_bounds[1] * image.height),
                                    round(sol_bounds[2] * image.width),
                                    round(sol_bounds[3] * image.height),
                                )
                            )
                            final = self.read(number, part, sol_crop, sol_bounds, "sol", state, sol=True)
                            method, sol_used = vision_method([state.get("mini_model", "gpt-4.1-mini")], sol=True), True
                            try:
                                replacements = copy.deepcopy(valid_blocks(final))
                                if requires_table and sum(b["kind"] == "table" for b in replacements) != 1:
                                    raise OCRFormatError("Tabel belum ditemukan dengan utuh pada pembacaan Sol.")
                                final_problems = []
                                sol_zone = {"bbox": sol_bounds, "grid": zone["grid"]}
                                for replacement in replacements:
                                    replacement["bbox"] = source_bounds(replacement, sol_zone, plan["words"])
                                    final_problems.append(issue(replacement, plan))
                                    if replacement["kind"] == "table" and zone["grid"]:
                                        final_problems.append(validate_table(replacement, zone["grid"]))
                                problem = "; ".join(dict.fromkeys(p for p in final_problems if p))
                                kept = [b for i, b in enumerate(blocks) if i < len(problems) and not problems[i]]
                                if replacements:
                                    kept.extend(replacements)
                                kept.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
                                text = "\n\n".join(block_text(b, part) for b in kept)
                                state["resolved_blocks"] = kept
                            except OCRFormatError as exc:
                                problem = str(exc)
                warning = f"Bagian {part}: {problem}" if problem else ""
                state.update(done=True, bbox=bounds, validator=VALIDATOR)
                self.save_region(number, part, bounds, state, text, method, warning, bool(problem))
                texts.append(text)
                unresolved |= bool(problem)
            if not unresolved:
                text = "\n\n".join(texts)
                if not readable(text):
                    self.save_region(
                        number,
                        1,
                        [0, 0, 1, 1],
                        {"pipeline": PIPELINE, "done": True},
                        text,
                        "ocr-layout-draft-v3",
                        "Teks terlalu sedikit; cocokkan dengan gambar sumber.",
                        True,
                    )
                else:
                    method = "ocr-local-layout-v3"
                    if ai_used:
                        method = vision_method(ai_models, sol=sol_used)
                    self.page(number, text, method)
        except AIError as exc:
            with self.lock:
                if self.failure is None:
                    self.failure = exc
            self.abort_ai.set()
            raise
        finally:
            elapsed = round((time.monotonic() - started) * 1000)
            accepted = self.db.one("SELECT 1 FROM pages WHERE version_id=? AND number=?", (self.id, number))
            self.db.execute(
                "UPDATE ocr_page_jobs SET status=?,elapsed_ms=? WHERE version_id=? AND page=?",
                ("done" if accepted else "review", elapsed, self.id, number),
            )
            self.progress(completed=True)

    def extract(self):
        started, futures, errors = time.monotonic(), [], []
        # A producer never waits on an AI future. AI workers render on demand,
        # so hundreds of full-page bitmaps are not retained in the queue.
        with ThreadPoolExecutor(max_workers=self.owner.settings.ocr_workers, thread_name_prefix="sira-vision") as pool:
            with pdfplumber.open(self.version["path"]) as pdf:
                self.total = len(pdf.pages)
                if not 1 <= self.total <= self.owner.settings.max_pages:
                    raise AIError("Jumlah halaman PDF melewati batas.")
                self.owner.update(self.id, page_count=self.total, stage="Pemeriksaan lokal", progress=2)
                for number, page in enumerate(pdf.pages, 1):
                    self.owner.assert_live(self.id)
                    if self.cache(number):
                        self.progress(local=True)
                        continue
                    # Remove obsolete accepted OCR in this pending version only.
                    self.db.execute("DELETE FROM pages WHERE version_id=? AND number=?", (self.id, number))
                    plan = self.analyze(page, number)
                    self.progress(
                        local=True,
                        queued=bool(plan and plan["flags"]),
                        tables=plan.get("native_table_count", len(plan["tables"])) if plan else 0,
                        areas=sum(zone["ai"] for zone in plan["zones"]) if plan and plan["flags"] else 0,
                    )
                    if plan and plan["flags"]:
                        futures.append(pool.submit(self.process_page, number, plan))
            for future in as_completed(futures):
                try:
                    future.result()
                except AIError as exc:
                    errors.append(exc)
                except Exception:
                    self.abort_ai.set()
                    raise
        log.info(
            "ocr_pipeline pages=%s ai_pages=%s workers=%s elapsed_ms=%s",
            self.total,
            self.ai_total,
            self.owner.settings.ocr_workers,
            round((time.monotonic() - started) * 1000),
        )
        if errors:
            raise self.failure or errors[0]
        return len(self.db.rows("SELECT number FROM pages WHERE version_id=?", (self.id,))) != self.total
