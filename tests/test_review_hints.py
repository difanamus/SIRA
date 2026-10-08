import copy
import json

from test_layout_ocr import table_block, table_image, text_block

from backend.app.ocr_layout import detect_tables
from backend.app.review_hints import review_hints, text_position


def region(state):
    return {
        "number": 3,
        "top": 0.4,
        "bottom": 0.9,
        "method": "ocr+4.1-mini+5.6-sol-layout-v3",
        "warning": "AI belum yakin",
        "state": json.dumps(state),
    }


def test_uncertain_quote_locates_saved_sol_crop_and_editor_without_an_ai_call():
    quote = "Nama pejabat\nBRIGADIR JENDERAL POLISI"
    block = text_block(quote, uncertain=True, bounds=[0.1, 0.2, 0.9, 0.4])
    state = {"bbox": [0, 0.4, 1, 0.9], "sol_bbox": [0.4, 0.6, 0.95, 0.9], "sol": {"blocks": [block]}}
    text = "Paragraf lain.\n\nNama pejabat\nBRIGADIR JENDERAL POLISI\n\nPenutup."
    hints = review_hints({"text": text}, [region(state)])
    assert len(hints) == 1 and hints[0]["quote"] == quote
    start, end = hints[0]["text_range"]
    assert text[start:end] == quote
    assert hints[0]["locatable"] and hints[0]["approximate"]
    assert 0.6 < hints[0]["bbox"][1] < hints[0]["bbox"][3] < 0.9


def test_format_failure_explains_missing_location_instead_of_inventing_bad_words():
    state = {"mini": {"blocks": [], "format_error": "Posisi bagian di luar gambar."}}
    hints = review_hints({"text": "Draft lokal"}, [region(state)])
    assert "gagal divalidasi" in hints[0]["reason"]
    assert not hints[0]["locatable"] and not hints[0]["quote"] and hints[0]["text_range"] is None


def test_source_phrase_can_narrow_a_broad_model_position():
    quote = "Nama pejabat Polri"
    block = text_block(quote, uncertain=True, bounds=[0.1, 0, 0.9, 0.8])
    state = {"bbox": [0, 0.4, 1, 0.9], "sol_bbox": [0, 0.4, 1, 0.9], "sol": {"blocks": [block]}}
    words = [
        {"text": token, "confidence": 99, "bbox": [0.1 + i * 0.1, 0.65, 0.18 + i * 0.1, 0.67]}
        for i, token in enumerate(quote.split())
    ]
    finding = review_hints({"text": quote}, [region(state)], {"words": words, "tables": []})[0]
    assert finding["bbox"][1] > 0.6
    assert finding["bbox"][3] - finding["bbox"][1] < 0.1


def test_uncertain_merged_table_cell_hint_preserves_its_span():
    block = copy.deepcopy(table_block())
    cell = next(cell for cell in block["cells"] if cell["row"] == 2 and cell["column"] == 2)
    cell["uncertain"] = True
    grid = detect_tables(table_image())[0]
    state = {"bbox": grid["bbox"], "sol_bbox": [0, 0, 1, 1], "sol": {"blocks": [block]}}
    hints = review_hints({"text": cell["text"]}, [region(state)], {"words": [], "tables": [grid]})
    assert "baris 3, kolom 3" in hints[0]["reason"]
    assert hints[0]["quote"] == cell["text"]
    assert hints[0]["bbox"][3] == grid["bbox"][3]  # Merged date includes final activity row.
    assert hints[0]["bbox"][0] > grid["bbox"][0]


def test_editor_match_is_whitespace_tolerant_but_never_selects_ambiguous_or_edited_text():
    assert text_position("Teks\n  nama pejabat", "nama   pejabat") == [7, 19]
    assert text_position("Nama pejabat dan nama pejabat", "nama pejabat") is None
    assert text_position("Koreksi admin", "nama pejabat") is None
