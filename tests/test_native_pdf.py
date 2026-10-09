import copy
import json

import pdfplumber
import pytest
from test_app import harness as harness
from test_layout_ocr import owner

from backend.app.native_pdf import NATIVE_LAYOUT, find_native_tables, native_layout, native_table
from backend.app.ocr_layout import table_records, validate_table
from backend.app.ocr_pipeline import DocumentOCR
from backend.app.review_evidence import review_page, score


def pdf_stream(stream):
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    result, offsets = b"%PDF-1.4\n", [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += str(number).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    start = len(result)
    result += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    result += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return result + f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode()


def table_pdf(merged=True, shading=False):
    lines = ["0 G 0.5 w"]
    if shading:
        lines.extend(["q 0.85 g 405 365 150 150 re f Q", "q 1 g 42 530 46 40 re f Q"])
    for x in [40, 90, 400, 560]:
        lines.append(f"{x} 360 m {x} 650 l S")
    for y in [360, 440, 520, 600, 650]:
        end = 400 if merged and y == 440 else 560
        lines.append(f"40 {y} m {end} {y} l S")
    for x, y, text in [
        (40, 710, "CATATAN SEBELUM TABEL: Ketentuan jadwal mengikuti sumber resmi."),
        (45, 620, "NO"),
        (95, 620, "KEGIATAN"),
        (405, 620, "TANGGAL"),
        (45, 570, "18"),
        (95, 570, "Kirim berkas"),
        (405, 570, "29 Oktober 2026"),
        (45, 490, "19"),
        (95, 490, "Verifikasi"),
        (405, 490, "23-26 November 2026"),
        (45, 410, "20"),
        (95, 410, "Kep kelulusan"),
        (40, 300, "CATATAN SESUDAH TABEL: Dokumen ditetapkan pada 14 September 2026."),
    ]:
        lines.append(f"BT /F1 10 Tf {x} {y} Td ({text}) Tj ET")
    return pdf_stream("\n".join(lines).encode())


class NoAI:
    def vision(self, *args, **kwargs):
        raise AssertionError("Valid native tables must not call vision")


def real_native_owner(tmp_path, monkeypatch, relay=None):
    original = pdfplumber.page.Page.extract_text
    instance, version = owner(tmp_path, monkeypatch, relay or NoAI())
    monkeypatch.setattr(pdfplumber.page.Page, "extract_text", original)
    with open(version["path"], "wb") as stream:
        stream.write(table_pdf())
    return instance, version


@pytest.mark.parametrize("merged", [True, False])
def test_native_cells_keep_merged_dates_and_do_not_fill_real_blank_cells(tmp_path, merged):
    path = tmp_path / "native.pdf"
    path.write_bytes(table_pdf(merged))
    with pdfplumber.open(path) as pdf:
        tables = find_native_tables(pdf.pages[0])
        assert len(tables) == 1
        result = native_layout(pdf.pages[0], tables)
    assert not result["failures"]
    block = result["blocks"][0]
    assert (block["rows"], block["columns"]) == (4, 3)
    text = result["text"]
    assert "CATATAN SEBELUM" in text and "CATATAN SESUDAH" in text
    assert text.index("CATATAN SEBELUM") < text.index("Kirim berkas") < text.index("CATATAN SESUDAH")
    row = next(line for line in text.splitlines() if "Kep kelulusan" in line)
    assert "29 Oktober" not in row
    assert ("23-26 November 2026" in row) == merged
    assert ("[KOSONG PADA SUMBER]" in row) != merged
    assert "14 September 2026" in text


def test_filled_backgrounds_and_white_masks_do_not_create_fake_columns(tmp_path):
    path = tmp_path / "native.pdf"
    path.write_bytes(table_pdf(shading=True))
    with pdfplumber.open(path) as pdf:
        result = native_layout(pdf.pages[0], find_native_tables(pdf.pages[0]))
    assert [(b["rows"], b["columns"]) for b in result["blocks"]] == [(4, 3)]
    assert not result["failures"]


def test_native_tables_can_exceed_vision_schema_column_limit_without_relaxing_it(tmp_path):
    lines = ["0 G 0.5 w"]
    for x in range(10, 589, 17):
        lines.append(f"{x} 450 m {x} 550 l S")
    for y in [450, 500, 550]:
        lines.append(f"10 {y} m 588 {y} l S")
    for c in range(34):
        lines.append(f"BT /F1 6 Tf {12 + c * 17} 520 Td (H{c + 1}) Tj ET")
    lines.append("BT /F1 6 Tf 573 470 Td (99) Tj ET")
    path = tmp_path / "wide.pdf"
    path.write_bytes(pdf_stream("\n".join(lines).encode()))
    with pdfplumber.open(path) as pdf:
        result = native_layout(pdf.pages[0], find_native_tables(pdf.pages[0]))
    block = result["blocks"][0]
    assert block["columns"] == 34 and not result["failures"]
    assert validate_table(block)  # Existing vision limit stays 30.
    assert not validate_table(block, maximum_columns=128)
    assert "Kolom 34: 99" in table_records(block)


def test_native_pipeline_upgrades_old_pending_table_checkpoint_without_ai(tmp_path, monkeypatch):
    instance, version = real_native_owner(tmp_path, monkeypatch)
    old_plan = {"pipeline": "layout-v3", "flags": ["tabel"], "zones": [], "words": [], "tables": []}
    instance.db.execute("INSERT INTO ocr_page_jobs VALUES ('v',1,?,'review',0)", (json.dumps(old_plan),))
    instance.db.execute("INSERT INTO pages VALUES ('v',1,'Old flattened table','ocr+4.1-mini-layout-v3','')")
    state = {"mini": {"blocks": []}, "done": True}
    instance.db.execute(
        "INSERT INTO ocr_regions VALUES ('v',1,1,0,1,?,'old','ocr+4.1-mini-layout-v3','Old grid warning',1)",
        (json.dumps(state),),
    )
    instance.db.execute(
        "INSERT INTO review_pages(version_id,number,text,method,warning) VALUES ('v',1,'old','text','old')"
    )
    assert not DocumentOCR(instance, version).extract()
    page = instance.db.one("SELECT * FROM pages")
    assert page["method"] == NATIVE_LAYOUT
    assert "Kep kelulusan" in page["text"] and "23-26 November 2026" in page["text"]
    draft = instance.db.one("SELECT * FROM review_pages")
    assert draft["required"] == 0 and draft["revision"] == 0
    historical = json.loads(instance.db.one("SELECT state FROM ocr_regions")["state"])
    assert historical["mini"] == state["mini"] and historical["superseded_by_native"] == NATIVE_LAYOUT
    review = review_page(instance.db, "v", draft)
    assert not review["hints"] and review["evidence"]["local_score"] is None
    # A completed native checkpoint is reusable, even with its parser unavailable.
    monkeypatch.setattr("backend.app.ocr_pipeline.find_native_tables", lambda p: pytest.fail("cached page reparsed"))
    assert not DocumentOCR(instance, version).extract()


def test_native_upgrade_does_not_replace_human_edits(tmp_path, monkeypatch):
    instance, version = real_native_owner(tmp_path, monkeypatch)
    instance.db.execute(
        "INSERT INTO review_pages(version_id,number,text,method,warning,revision,confirmed) "
        "VALUES ('v',1,'Human correction','text','',1,1)"
    )
    assert not DocumentOCR(instance, version).extract()
    instance.prepare_review("v")
    draft = instance.db.one("SELECT * FROM review_pages")
    assert draft["text"] == "Human correction" and draft["revision"] == 1 and draft["confirmed"]


def test_native_failure_sends_only_failed_table_pixels_to_existing_reader(tmp_path, monkeypatch):
    expected = []

    class Reader:
        def vision(self, image, **kwargs):
            assert image.startswith("data:image/jpeg;base64,")
            assert kwargs == {"enhanced": True, "fragment": False, "structured": True}
            return {"blocks": [copy.deepcopy(expected[0])]}

    instance, version = real_native_owner(tmp_path, monkeypatch, Reader())
    with pdfplumber.open(version["path"]) as pdf:
        expected.append(native_table(pdf.pages[0], find_native_tables(pdf.pages[0])[0]))
    monkeypatch.setattr("backend.app.native_pdf.native_table", lambda *args: (_ for _ in ()).throw(ValueError("Gap")))
    assert not DocumentOCR(instance, version).extract()
    plan = json.loads(instance.db.one("SELECT plan FROM ocr_page_jobs")["plan"])
    requests = [z for z in plan["zones"] if z["ai"]]
    assert len(requests) == 1 and requests[0]["table_required"]
    assert requests[0]["bbox"][3] - requests[0]["bbox"][1] < 0.5
    assert "CATATAN SEBELUM" in instance.db.one("SELECT text FROM pages")["text"]
    assert "CATATAN SESUDAH" in instance.db.one("SELECT text FROM pages")["text"]


def test_explicit_ai_read_still_reads_original_image_for_native_tables(tmp_path, monkeypatch):
    instance, version = real_native_owner(tmp_path, monkeypatch)
    assert not DocumentOCR(instance, version).extract()
    instance.update("v", ocr_mode="ai")
    forced = DocumentOCR(instance, instance.db.one("SELECT * FROM versions"))
    assert forced.cache(1) is None
    with pdfplumber.open(version["path"]) as pdf:
        plan = forced.analyze(pdf.pages[0], 1)
    assert not plan.get("native_source")
    assert "pembacaan AI diminta admin" in plan["flags"]
    assert any(z["ai"] for z in plan["zones"])


def test_native_positions_are_not_reported_as_100_percent_ocr_confidence():
    assert score([{"confidence": 100, "source": "native"}]) is None
    assert score([{"confidence": 100, "source": "native"}, {"confidence": 83}]) == 83


def test_native_caption_does_not_hide_scanned_content_on_same_page(tmp_path, monkeypatch):
    instance, version = real_native_owner(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(pdfplumber.page.Page, "images", property(lambda p: [{"width": 300, "height": 400}]))

    def local(image):
        calls.append(image)
        return "Isi gambar yang juga perlu diperiksa, bukan hanya teks native pada halaman.", 98, []

    instance.extract_local_evidence = local
    with pdfplumber.open(version["path"]) as pdf:
        plan = DocumentOCR(instance, version).analyze(pdf.pages[0], 1)
    assert len(calls) == 1 and not plan.get("native_source")
    assert "Isi gambar" in plan["text"] and "tabel" in plan["flags"]


@pytest.mark.parametrize("edited", [False, True])
def test_retry_from_failed_document_review_resumes_pipeline_and_preserves_edits(harness, edited):
    from test_app import wait_document

    client, ctx, ai, _ = harness
    ai.fail = True
    result = client.post(
        "/api/admin/documents",
        data={"title": "Native retry"},
        files={"file": ("native.pdf", table_pdf(), "application/pdf")},
    )
    assert result.status_code == 202
    doc_id = result.json()["id"]
    version_id = wait_document(ctx, doc_id, "failed")["pending_version"]
    base = f"/api/admin/documents/{doc_id}/review"
    assert client.post(base).status_code == 200
    wait_document(ctx, doc_id, "review")
    if edited:
        assert (
            client.put(
                base + "/pages/1",
                json={"version_id": version_id, "revision": 0, "text": "Human correction", "confirmed": True},
            ).status_code
            == 200
        )
    ai.fail = False
    assert client.post(f"/api/admin/documents/{doc_id}/retry").status_code == 200
    wait_document(ctx, doc_id, "review" if edited else "ready")
    assert ctx.db.one("SELECT ocr_mode FROM versions WHERE id=?", (version_id,))["ocr_mode"] == "auto"
    if edited:
        draft = ctx.db.one("SELECT * FROM review_pages WHERE version_id=?", (version_id,))
        assert draft["text"] == "Human correction" and draft["revision"] == 1 and draft["confirmed"]
    else:
        assert ctx.db.one("SELECT COUNT(*) AS n FROM chunks WHERE version_id=?", (version_id,))["n"] > 0
