"""OCR utilities; escalation is covered in test_regional_ocr.py."""

from PIL import Image

from backend.app.ingestion import chunk_page, critical_signature, preprocess


def test_chunk_preserves_page_and_negation_with_bounded_tokens():
    from backend.app.ingestion import ENCODING

    text = "Pasal 4\nTidak memenuhi syarat bila nilai 0. " * 500
    chunks = chunk_page(text, "version", 7)
    assert len(chunks) > 1
    assert all(chunk["page"] == 7 and chunk["version_id"] == "version" for chunk in chunks)
    assert all(len(ENCODING.encode(chunk["text"])) <= 651 for chunk in chunks)
    assert any("Tidak memenuhi syarat" in chunk["text"] for chunk in chunks)


def test_preprocessing_handles_blank_image_without_rotating_noise():
    image = Image.new("RGB", (200, 300), "white")
    result = preprocess(image)
    assert result.size == image.size and result.mode == "L"


def test_numeric_crosscheck_ignores_separator_spacing_but_detects_changed_year():
    assert critical_signature("nilai 61 - 70; (90)/100; tidak lulus") == critical_signature(
        "nilai 61–70; 90/100; tidak lulus"
    )
    assert critical_signature("17 Oktober 2025") != critical_signature("17 Oktober 2026")
    assert critical_signature("tidak lulus") != critical_signature("lulus")
    assert critical_signature("SMT II T.A. 2025") != critical_signature("SMT I T.A. 2025")
