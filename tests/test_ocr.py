"""Conservative OCR behavior tests; do not claim real AI transcription accuracy."""

import pytest
from PIL import Image

from backend.app.ai import AIError
from backend.app.config import Settings
from backend.app.ingestion import Ingestion, chunk_page, critical_signature, preprocess


def ocr_data(text, confidence=91):
    words = text.split()
    return {
        "text": words,
        "block_num": [1] * len(words),
        "par_num": [1] * len(words),
        "line_num": [1] * len(words),
        "conf": [confidence] * len(words),
    }


class Vision:
    def __init__(self, result):
        self.result = result

    def vision(self, image):
        assert len(image) == 2 and all(value.startswith("data:image/jpeg;base64,") for value in image)
        if isinstance(self.result, list):
            return self.result.pop(0)
        return self.result


def test_uncertain_vision_cannot_activate_source(monkeypatch, tmp_path):
    text = "Persyaratan pangkat untuk peserta adalah minimal 5 tahun menurut dokumen. " * 3
    monkeypatch.setattr("pytesseract.image_to_data", lambda *a, **kw: ocr_data(text))
    ingestion = Ingestion(
        Settings(data_dir=tmp_path, relay_url="https://relay.example", relay_token="test"),
        None,
        None,
        Vision({"text": text, "uncertain": True}),
    )
    with pytest.raises(AIError, match="belum dapat dibaca"):
        ingestion.extract_scan(Image.new("RGB", (300, 400), "white"))


def test_number_or_negation_disagreement_fails_closed(monkeypatch, tmp_path):
    local = "Persyaratan pangkat untuk peserta adalah minimal 5 tahun dan tidak berlaku otomatis. " * 2
    remote = local.replace("5 tahun", "3 tahun")
    monkeypatch.setattr("pytesseract.image_to_data", lambda *a, **kw: ocr_data(local))
    ingestion = Ingestion(
        Settings(data_dir=tmp_path, relay_url="https://relay.example", relay_token="test"),
        None,
        None,
        Vision([{"text": remote, "uncertain": False}, {"text": local, "uncertain": False}]),
    )
    with pytest.raises(AIError, match="berbeda pada angka, negasi"):
        ingestion.extract_scan(Image.new("RGB", (300, 400), "white"))


def test_disagreement_requires_consistent_fresh_vision_reading(monkeypatch, tmp_path):
    local = "Persyaratan pangkat untuk peserta adalah minimal 5 tahun dan tidak berlaku otomatis. " * 2
    corrected = local.replace("5 tahun", "3 tahun")
    monkeypatch.setattr("pytesseract.image_to_data", lambda *a, **kw: ocr_data(local))
    ai = Vision([{"text": corrected, "uncertain": False}, {"text": corrected, "uncertain": False}])
    ingestion = Ingestion(
        Settings(data_dir=tmp_path, relay_url="https://relay.example", relay_token="test"), None, None, ai
    )
    text, method, warning = ingestion.extract_scan(Image.new("RGB", (300, 400), "white"))
    assert text == corrected and method == "ocr+vision-recheck-crops-v1"
    assert not ai.result and "verifikasi manusia" in warning


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
