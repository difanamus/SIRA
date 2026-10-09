"""Table relationships, independent image input, scheduling, and durable resume."""

import copy
import json
import threading
import time

import pytest
from PIL import Image, ImageDraw, ImageOps
from test_app import pdf_bytes

from backend.app.ai import AIError, Relay
from backend.app.config import Settings
from backend.app.db import Database
from backend.app.ingestion import Ingestion, chunk_page, image_payload, render_page
from backend.app.ocr_layout import detect_tables, table_records, validate_table
from backend.app.ocr_pipeline import DocumentOCR, critical_problem, image_zones, issue, source_bounds

TEXT = "Ketentuan administrasi pendidikan personel mengikuti dokumen resmi yang telah ditetapkan."


def text_block(text=TEXT, uncertain=False, bounds=None):
    return {
        "kind": "text",
        "bbox": bounds or [0.05, 0.10, 0.95, 0.20],
        "text": text,
        "rows": 0,
        "columns": 0,
        "header_rows": 0,
        "cells": [],
        "uncertain": uncertain,
    }


def table_image():
    im = Image.new("RGB", (900, 1200), "white")
    draw = ImageDraw.Draw(im)
    for x in (60, 140, 540, 840):
        draw.line((x, 200, x, 800), fill="black", width=3)
    for y in (200, 300, 450, 600, 800):
        draw.line((60, y, 540 if y == 600 else 840, y), fill="black", width=3)
    return im


def table_block():
    grid = detect_tables(table_image())[0]
    cells = []
    values = [
        ["No", "Kegiatan", "Tanggal"],
        ["18", "Kirim berkas ke panitia pusat", "29 Oktober 2026"],
        ["19", "Verifikasi administrasi tingkat pusat", "23 S.D. 26 November 2026"],
        ["20", "Kep kelulusan dan kirim surat panggil", ""],
    ]
    for row, values_row in enumerate(values):
        for col, text in enumerate(values_row):
            if row == 3 and col == 2:
                continue
            cells.append(
                {
                    "row": row,
                    "column": col,
                    "rowspan": 2 if row == 2 and col == 2 else 1,
                    "colspan": 1,
                    "text": text,
                    "uncertain": False,
                }
            )
    return {
        "kind": "table",
        "bbox": grid["bbox"],
        "text": "",
        "rows": 4,
        "columns": 3,
        "header_rows": 1,
        "cells": cells,
        "uncertain": False,
    }


def owner(tmp_path, monkeypatch, relay, pages=1, workers=3, local=None):
    path = tmp_path / "source.pdf"
    path.write_bytes(pdf_bytes(pages=pages))
    settings = Settings(data_dir=tmp_path, relay_url="https://relay.example", relay_token="test", ocr_workers=workers)
    db = Database(tmp_path)
    db.execute(
        "INSERT INTO documents(id,title,filename,pending_version,created) VALUES ('d','Uji','source.pdf','v',?)",
        (time.time(),),
    )
    db.execute(
        "INSERT INTO versions(id,document_id,path,sha256,size,status,created) VALUES ('v','d',?,'hash',1,'processing',?)",
        (str(path), time.time()),
    )
    instance = Ingestion(settings, db, None, relay)
    monkeypatch.setattr("pdfplumber.page.Page.extract_text", lambda *args, **kwargs: "")
    monkeypatch.setattr(instance, "extract_local_evidence", local or (lambda image: ("Draft lokal berbeda", 70, [])))
    return instance, db.one("SELECT * FROM versions WHERE id='v'")


def test_merged_date_is_repeated_only_for_rows_covered_by_source_cell():
    grid = detect_tables(table_image())[0]
    block = table_block()
    assert (grid["rows"], grid["columns"]) == (4, 3)
    assert grid["horizontal"][2] == [True, True, False]
    assert validate_table(block, grid) == ""
    records = table_records(block)
    row = next(line for line in records.splitlines() if "Kep kelulusan" in line)
    assert "23 S.D. 26 November 2026" in row and "29 Oktober" not in row
    wrong = copy.deepcopy(block)
    wrong["cells"][-3]["rowspan"] = 1  # Explicitly undo the merged date cell.
    assert validate_table(wrong, grid)
    # A structurally complete but flattened date column must also be rejected.
    wrong = copy.deepcopy(block)
    date = next(cell for cell in wrong["cells"] if cell["row"] == 2 and cell["column"] == 2)
    date["rowspan"] = 1
    wrong["cells"].append({"row": 3, "column": 2, "rowspan": 1, "colspan": 1, "text": "", "uncertain": False})
    assert "gabungan" in validate_table(wrong, grid)


def test_blank_cells_are_not_filled_from_previous_row_and_rows_stay_atomic():
    block = table_block()
    next(cell for cell in block["cells"] if cell["row"] == 3 and cell["column"] == 1)["text"] = ""
    records = table_records(block)
    assert "Kegiatan: [KOSONG PADA SUMBER]" in records
    block = table_block()
    next(cell for cell in block["cells"] if cell["row"] == 3 and cell["column"] == 1)["text"] *= 35
    chunks = chunk_page(table_records(block), "v", 12)
    row_chunks = [chunk for chunk in chunks if "Kep kelulusan" in chunk["text"]]
    assert len(row_chunks) == 1 and "23 S.D. 26 November 2026" in row_chunks[0]["text"]


def test_faint_skewed_grid_keeps_merged_cell_and_ignores_scan_border():
    image = ImageOps.grayscale(table_image()).point(lambda value: 190 if value < 250 else 255)
    ImageDraw.Draw(image).line((3, 0, 3, image.height), fill=0, width=5)
    image = image.rotate(0.25, resample=Image.Resampling.BILINEAR, fillcolor=255)
    tables = detect_tables(image)
    assert len(tables) == 1
    assert (tables[0]["rows"], tables[0]["columns"]) == (4, 3)
    assert tables[0]["horizontal"][2] == [True, True, False]


def test_source_zones_preserve_notes_beside_table():
    image = Image.new("RGB", (1000, 1000), "white")
    draw = ImageDraw.Draw(image)
    draw.text((800, 400), "Catatan penting", fill="black")
    grid = {"bbox": [0.1, 0.2, 0.65, 0.8]}
    zones = image_zones(image, [grid], [], True)
    assert len(zones) == 2  # Table plus side note; whitespace does not call AI.
    assert sum(zone["grid"] is not None for zone in zones) == 1
    assert any(zone["bbox"][0] < 0.8 < zone["bbox"][2] and zone["bbox"][1] < 0.4 < zone["bbox"][3] for zone in zones)


def evidence(text, top, confidence=99):
    return [
        {"text": token, "confidence": confidence, "bbox": [0.1 + i * 0.04, top, 0.13 + i * 0.04, top + 0.02]}
        for i, token in enumerate(text.split())
    ]


def test_repeated_words_do_not_expand_heading_or_mix_dates_between_blocks():
    heading = "Ketentuan pendidikan personel Polri tahun 2027"
    body = "Pelaksanaan pendidikan personel Polri ditetapkan tanggal 29 Oktober 2026"
    words = evidence(heading, 0.1) + evidence(body, 0.6)
    zone = {"bbox": [0, 0, 1, 1], "grid": None}
    bounds = source_bounds(text_block(heading), zone, words)
    assert bounds[3] < 0.2
    assert critical_problem([text_block(heading), text_block(body)], zone, words, 1) == ""
    changed = [text_block(heading.replace("2027", "2028")), text_block(body)]
    assert critical_problem(changed, zone, words, 1)


def test_weak_local_digit_guess_does_not_veto_clear_vision_but_negation_still_matters():
    zone = {"bbox": [0, 0, 1, 1], "grid": None}
    words = evidence("Nomor Kep X11 Tahun 2026 tidak berubah", 0.3)
    next(word for word in words if word["text"] == "X11")["confidence"] = 80
    blocks = [text_block("Nomor Kep XII Tahun 2026 tidak berubah")]
    assert critical_problem(blocks, zone, words, 1) == ""
    assert critical_problem([text_block("Nomor Kep XII Tahun 2026 berubah")], zone, words, 1)
    blocks[0]["rows"] = 8  # Cosmetic line count on a text block, without cells.
    assert issue(blocks[0], {"tables": [], "words": words}) == ""
    blocks[0]["columns"] = 2
    assert issue(blocks[0], {"tables": [], "words": words})


def test_only_isolated_folio_is_excluded_from_critical_comparison():
    zone = {"bbox": [0, 0, 1, 1], "grid": None}
    body = "Kegiatan berlangsung tanggal 10 Oktober 2026"
    words = evidence("10", 0.04) + evidence(body, 0.4)
    assert critical_problem([text_block(body)], zone, words, 10) == ""
    assert critical_problem([text_block(body.replace("tanggal 10", "tanggal 11"))], zone, words, 10)
    words = evidence("tanggal 10 Oktober 2026", 0.04)
    assert critical_problem([text_block("tanggal 11 Oktober 2026")], zone, words, 10)


def test_local_finishes_while_three_image_readers_are_blocked(tmp_path, monkeypatch):
    local_finished, release = threading.Event(), threading.Event()
    active = []
    calls = []
    lock = threading.Lock()

    class SlowAI:
        def vision(self, image, **kwargs):
            assert kwargs == {"enhanced": True, "fragment": False, "structured": True}
            with lock:
                active.append(threading.get_ident())
            assert release.wait(8)
            return {"blocks": [text_block()]}

    def local(image):
        calls.append(1)
        if len(calls) == 5:
            local_finished.set()
        return "Hasil lokal belum pasti", 70, []

    instance, version = owner(tmp_path, monkeypatch, SlowAI(), pages=5, local=local)
    errors = []

    def run():
        try:
            assert not DocumentOCR(instance, version).extract()
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert local_finished.wait(6), "Producer waited for AI instead of scanning the rest of the document"
        assert instance.db.one("SELECT COUNT(*) n FROM ocr_page_jobs")["n"] >= 4
        assert len(active) == 3
        assert instance.db.one("SELECT COUNT(*) n FROM pages")["n"] == 0
    finally:
        release.set()
        thread.join(10)
    assert not thread.is_alive() and not errors
    assert len(active) == 5 and len(calls) == 5
    assert instance.db.one("SELECT COUNT(*) n FROM pages")["n"] == 5


def test_ai_gets_original_image_without_local_transcription(tmp_path, monkeypatch):
    sent = []

    class AI:
        def vision(self, image, **kwargs):
            sent.append((image, kwargs))
            return {"blocks": [text_block()]}

    instance, version = owner(tmp_path, monkeypatch, AI())
    assert not DocumentOCR(instance, version).extract()
    original = render_page(version["path"], 1)
    plan = json.loads(instance.db.one("SELECT plan FROM ocr_page_jobs")["plan"])
    bounds = plan["zones"][0]["bbox"]
    crop = original.crop(
        (
            round(bounds[0] * original.width),
            round(bounds[1] * original.height),
            round(bounds[2] * original.width),
            round(bounds[3] * original.height),
        )
    )
    assert sent[0][0] == image_payload(crop, (2400, 3000))
    assert len(sent) == 1 and sent[0][1]["structured"]
    assert "Draft lokal" not in instance.db.one("SELECT text FROM pages")["text"]


def test_good_local_page_does_not_call_ai(tmp_path, monkeypatch):
    class AI:
        def vision(self, *args, **kwargs):
            raise AssertionError("Clean local narrative needs no AI")

    instance, version = owner(
        tmp_path,
        monkeypatch,
        AI(),
        local=lambda image: (TEXT, 99, [{"text": TEXT, "confidence": 99, "bbox": [0, 0, 1, 1]}]),
    )
    assert not DocumentOCR(instance, version).extract()
    assert instance.db.one("SELECT method FROM pages")["method"] == "ocr-local-layout-v3"


def test_wrong_merged_span_escalates_only_whole_table_then_resumes(tmp_path, monkeypatch):
    sent = []
    valid = table_block()
    invalid = copy.deepcopy(valid)
    date = next(cell for cell in invalid["cells"] if cell["row"] == 2 and cell["column"] == 2)
    date["rowspan"] = 1
    invalid["cells"].append({"row": 3, "column": 2, "rowspan": 1, "colspan": 1, "text": "", "uncertain": False})

    class AI:
        fail = True

        def vision(self, image, **kwargs):
            sent.append((image, kwargs))
            if not kwargs["fragment"]:
                return {"blocks": [text_block(bounds=[0.05, 0.04, 0.95, 0.10]), copy.deepcopy(invalid)]}
            if self.fail:
                raise AIError("Koneksi uji putus")
            result = copy.deepcopy(valid)
            result["bbox"] = [0.01, 0.01, 0.99, 0.99]
            return {"blocks": [result]}

    ai = AI()
    instance, version = owner(tmp_path, monkeypatch, ai)
    monkeypatch.setattr("backend.app.ocr_pipeline.render_page", lambda *args: table_image())
    with pytest.raises(AIError, match="Koneksi uji putus"):
        DocumentOCR(instance, version).extract()
    assert len(sent) == 2 and sent[1][1]["fragment"]
    import base64
    import io

    from PIL import Image as PILImage

    crop = PILImage.open(io.BytesIO(base64.b64decode(sent[1][0].split(",")[1])))
    assert 600 <= crop.height < 700  # Entire table, including its merged date.
    ai.fail = False
    instance.db = Database(tmp_path)
    assert not DocumentOCR(instance, version).extract()
    assert len(sent) == 3 and sent[-1][1]["fragment"]  # No repeated mini or local job.
    text = instance.db.one("SELECT text FROM pages")["text"]
    assert "23 S.D. 26 November 2026" in next(line for line in text.splitlines() if "Kep kelulusan" in line)
    assert not DocumentOCR(instance, version).extract() and len(sent) == 3


def test_uncertain_sol_only_flags_its_page_for_review(tmp_path, monkeypatch):
    calls = []

    class AI:
        def vision(self, image, **kwargs):
            calls.append(kwargs)
            return {"blocks": [text_block(uncertain=True)]}

    instance, version = owner(tmp_path, monkeypatch, AI())
    assert DocumentOCR(instance, version).extract()
    instance.prepare_review("v")
    page = instance.db.one("SELECT * FROM review_pages")
    assert page["required"] == 1 and not page["confirmed"] and TEXT in page["text"]
    parts = instance.db.rows("SELECT * FROM ocr_regions WHERE required=1")
    assert len(parts) == 1 and parts[0]["bottom"] - parts[0]["top"] < 0.2
    assert len(calls) == 2 and calls[-1]["fragment"]


def test_structured_relay_transmits_only_images_and_fixed_flag(tmp_path, monkeypatch):
    relay = Relay(Settings(data_dir=tmp_path))
    sent = []

    def post(operation, payload):
        sent.append((operation, payload))
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"blocks": [text_block()]})}}]}

    monkeypatch.setattr(relay, "post", post)
    relay.vision("data:image/jpeg;base64,YWJj", structured=True)
    relay.vision("data:image/jpeg;base64,YWJj", structured=True, fragment=True)
    assert sent == [
        ("vision", {"image": "data:image/jpeg;base64,YWJj", "layout": True}),
        ("vision-fragment", {"image": "data:image/jpeg;base64,YWJj", "layout": True}),
    ]


def test_new_read_records_luna_but_paid_mini_checkpoint_keeps_its_identity(tmp_path, monkeypatch):
    from backend.app.ai import vision_method

    calls = []

    class AI:
        def vision(self, image, **kwargs):
            calls.append(kwargs)
            return {"blocks": [text_block()], "_model": "gpt-6-luna"}

    instance, version = owner(tmp_path, monkeypatch, AI())
    reader = DocumentOCR(instance, version)
    state = {}
    picture = Image.new("RGB", (600, 600), "white")
    reader.read(1, 1, picture, [0, 0, 1, 1], "mini", state)
    assert state["mini_model"] == "gpt-6-luna" and len(calls) == 1
    reader.read(1, 1, picture, [0, 0, 1, 1], "mini", state)
    assert len(calls) == 1
    legacy = {"mini": {"blocks": [text_block()]}}
    reader.read(1, 1, picture, [0, 0, 1, 1], "mini", legacy)
    assert len(calls) == 1 and "mini_model" not in legacy
    assert vision_method([legacy.get("mini_model", "gpt-4.1-mini")]) == "ocr+4.1-mini-layout-v3"


def test_revalidation_reuses_paid_results_and_preserves_uncertain_sol(tmp_path, monkeypatch):
    calls = []

    class AI:
        def vision(self, image, **kwargs):
            calls.append(kwargs)
            return {"blocks": [text_block(uncertain=True)]}

    instance, version = owner(tmp_path, monkeypatch, AI())
    assert DocumentOCR(instance, version).extract()
    saved = instance.db.one("SELECT state FROM ocr_regions")
    state = json.loads(saved["state"])
    state["validator"] = "previous-validator"
    state["mini"]["blocks"][0]["uncertain"] = False
    instance.db.execute("UPDATE ocr_regions SET state=?", (json.dumps(state),))
    # A new validator cannot discard a saved doubtful Sol response to make the
    # page appear clean. Neither paid request is repeated.
    assert DocumentOCR(instance, version).extract()
    instance.prepare_review("v")
    assert len(calls) == 2
    assert instance.db.one("SELECT required FROM review_pages")["required"] == 1
    assert instance.db.one("SELECT text FROM review_pages")["text"].count(TEXT) == 1


def test_bad_ai_coordinates_preserve_unverified_paid_draft_for_manual_review(tmp_path, monkeypatch):
    class AI:
        def vision(self, image, **kwargs):
            return {"blocks": [text_block(TEXT, bounds=[0.9, 0.1, 0.2, 0.5])]}

    instance, version = owner(tmp_path, monkeypatch, AI())
    assert DocumentOCR(instance, version).extract()
    instance.prepare_review("v")
    page = instance.db.one("SELECT * FROM review_pages")
    assert page["required"] and TEXT in page["text"]
    state = json.loads(instance.db.one("SELECT state FROM ocr_regions")["state"])
    assert state["mini"]["draft_text"] == TEXT and state["mini"]["format_error"]


def test_mixed_pdf_routes_native_and_image_pages_separately(tmp_path, monkeypatch):
    import io

    import pdfplumber
    import pypdfium2 as pdfium

    original_extract = pdfplumber.page.Page.extract_text

    class AI:
        def vision(self, *args, **kwargs):
            raise AssertionError("Clear native text and clean local OCR do not need AI")

    calls = []

    def local(image):
        calls.append(1)
        return TEXT, 99, [{"text": TEXT, "confidence": 99, "bbox": [0, 0, 1, 1]}]

    instance, version = owner(tmp_path, monkeypatch, AI(), pages=2, local=local)
    monkeypatch.setattr(pdfplumber.page.Page, "extract_text", original_extract)
    scan = Image.new("RGB", (900, 1200), "white")
    ImageDraw.Draw(scan).text((80, 120), TEXT, fill="black")
    image_pdf = io.BytesIO()
    scan.save(image_pdf, format="PDF")
    with pdfium.PdfDocument(pdf_bytes(TEXT)) as pdf, pdfium.PdfDocument(image_pdf.getvalue()) as scanned:
        pdf.import_pages(scanned)
        pdf.save(version["path"])
    assert not DocumentOCR(instance, version).extract()
    assert len(calls) == 1
    assert [p["method"] for p in instance.db.rows("SELECT method FROM pages ORDER BY number")] == [
        "text-layout-v3",
        "ocr-local-layout-v3",
    ]
