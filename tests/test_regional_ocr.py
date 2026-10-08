"""Offline tests of escalation, crop isolation, persistent resume and review."""

import base64
import io
import json
import time

import pytest
from PIL import Image, ImageDraw

from backend.app.ai import AIError, OCRFormatError, Relay
from backend.app.config import Settings
from backend.app.db import Database
from backend.app.ingestion import Ingestion, OCRReviewRequired, fragments_agree, region_bounds

EASY = "Informasi administrasi personel tercatat secara jelas dalam dokumen resmi."
HARD = "Persyaratan nilai minimal 53 dan tidak lulus otomatis."


def scan_image():
    image = Image.new("RGB", (600, 1200), "white")
    draw = ImageDraw.Draw(image)
    for y in range(0, 1200, 200):
        draw.rectangle((30, y + 50, 500, y + 70), fill="black")
    return image


class Vision:
    def __init__(self, values):
        self.values = list(values)
        self.calls = []

    def vision(self, image, *, enhanced=False, fragment=False):
        assert isinstance(image, str) and image.startswith("data:image/jpeg;base64,")
        picture = Image.open(io.BytesIO(base64.b64decode(image.split(",", 1)[1])))
        self.calls.append((fragment, picture.size))
        assert enhanced
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def answer(text=HARD, uncertain=False):
    return {"text": text, "uncertain": uncertain}


def ingestion(tmp_path, ai, monkeypatch, local=None, persistent=False):
    settings = Settings(data_dir=tmp_path, relay_url="https://relay.example", relay_token="test")
    db = Database(tmp_path) if persistent else None
    owner = Ingestion(settings, db, None, ai)
    values = iter(local or [(HARD, 80)] + [(EASY, 99)] * 5)
    calls = []

    def extract(image):
        calls.append(image.size)
        return next(values)

    monkeypatch.setattr(owner, "extract_local", extract)
    if persistent:
        db.execute(
            "INSERT INTO documents(id,title,filename,pending_version,created) VALUES ('d','Uji','uji.pdf','v',?)",
            (time.time(),),
        )
        db.execute(
            "INSERT INTO versions(id,document_id,path,sha256,size,status,created) VALUES ('v','d','unused.pdf','hash',1,'processing',?)",
            (time.time(),),
        )
        owner.scan_context = ("v", 1)
    return owner, calls


def test_local_clean_regions_do_not_call_any_ai(tmp_path, monkeypatch):
    ai = Vision([])
    owner, calls = ingestion(tmp_path, ai, monkeypatch, local=[(EASY, 99)] * 6)
    text, method, _ = owner.extract_scan(scan_image())
    assert text == "\n\n".join([EASY] * 6)
    assert method == "ocr-local-regions-v2" and len(calls) == 6 and not ai.calls


def test_mini_agrees_with_local_without_calling_sol(tmp_path, monkeypatch):
    ai = Vision([answer()])
    owner, _ = ingestion(tmp_path, ai, monkeypatch)
    text, method, _ = owner.extract_scan(scan_image())
    assert text.startswith(HARD) and "4.1-mini" in method
    assert [call[0] for call in ai.calls] == [False]


def test_sol_repairs_only_disputed_crop_and_keeps_other_regions(tmp_path, monkeypatch):
    ai = Vision([answer(), answer(HARD.replace("53", "54")), answer()])
    owner, _ = ingestion(tmp_path, ai, monkeypatch, local=[(HARD.replace("53", "58"), 70)] + [(EASY, 99)] * 5)
    text, method, warning = owner.extract_scan(scan_image())
    assert text == HARD + "\n\n" + "\n\n".join([EASY] * 5)
    assert "5.6-sol" in method and "Bagian 1" in warning
    assert [call[0] for call in ai.calls] == [False, False, True]
    assert all(size[1] <= 1200 / 4 for _, size in ai.calls)


def test_mini_two_agreeing_corrections_skip_sol(tmp_path, monkeypatch):
    ai = Vision([answer(), answer()])
    owner, _ = ingestion(tmp_path, ai, monkeypatch, local=[(HARD.replace("53", "58"), 70)] + [(EASY, 99)] * 5)
    assert owner.extract_scan(scan_image())[0].startswith(HARD)
    assert [call[0] for call in ai.calls] == [False, False]


def test_unusable_mini_output_can_escalate_but_is_not_a_network_error(tmp_path, monkeypatch):
    ai = Vision([OCRFormatError("truncated"), answer(), answer()])
    owner, _ = ingestion(tmp_path, ai, monkeypatch)
    text, method, _ = owner.extract_scan(scan_image())
    assert text.startswith(HARD) and "sol" in method
    assert [call[0] for call in ai.calls] == [False, False, True]


def test_budget_failure_never_escalates_and_retry_reuses_paid_mini(tmp_path, monkeypatch):
    ai = Vision([answer(), AIError("Kuota total relay tidak mencukupi.")])
    owner, calls = ingestion(
        tmp_path, ai, monkeypatch, local=[(HARD.replace("53", "58"), 70)] + [(EASY, 99)] * 5, persistent=True
    )
    with pytest.raises(AIError, match="Kuota total"):
        owner.extract_scan(scan_image())
    assert [call[0] for call in ai.calls] == [False, False]
    stored = owner.db.one("SELECT state FROM ocr_regions")
    assert json.loads(stored["state"])["mini"]["text"] == HARD
    owner.db = Database(tmp_path)  # Simulate reopening the persistent store.
    ai.values = [answer()]
    text, _, _ = owner.extract_scan(scan_image())
    assert text.startswith(HARD) and len(calls) == 6
    assert len(ai.calls) == 3  # Only the missing second read; no Sol and no repeated first read.
    owner.extract_scan(scan_image())
    assert len(ai.calls) == 3 and len(calls) == 6


def test_uncertain_sol_or_third_disagreeing_answer_requires_review(tmp_path, monkeypatch):
    for final in [answer(uncertain=True), answer(HARD.replace("53", "59"))]:
        ai = Vision([answer(uncertain=True), answer(HARD.replace("53", "54")), final])
        owner, _ = ingestion(tmp_path, ai, monkeypatch)
        with pytest.raises(OCRReviewRequired) as caught:
            owner.extract_scan(scan_image())
        assert "Bagian 1" in str(caught.value) and caught.value.text.endswith(EASY)


def test_sol_limit_does_not_send_whole_unreadable_page_in_pieces(tmp_path, monkeypatch):
    values = []
    for index in range(6):
        values.extend([answer(uncertain=True), answer(uncertain=True)])
        if index < 2:
            values.append(answer())
    ai = Vision(values)
    owner, _ = ingestion(tmp_path, ai, monkeypatch, local=[(HARD, 80)] * 6)
    with pytest.raises(OCRReviewRequired):
        owner.extract_scan(scan_image())
    assert sum(fragment for fragment, _ in ai.calls) == 2


def test_explicit_ai_still_starts_local_and_checks_each_region(tmp_path, monkeypatch):
    ai = Vision([answer(EASY)] * 12)
    owner, calls = ingestion(tmp_path, ai, monkeypatch, local=[(EASY, 99)] * 6)
    owner.extract_with_ai(scan_image())
    assert len(calls) == 6 and len(ai.calls) == 12 and not any(fragment for fragment, _ in ai.calls)


def test_region_coverage_and_material_disagreements():
    bounds = region_bounds(scan_image())
    assert bounds[0][0] == 0 and bounds[-1][1] == 1200
    assert all(a[1] == b[0] for a, b in zip(bounds, bounds[1:]))
    assert all(0 < bottom - top <= 1200 / 4 for top, bottom in bounds)
    assert fragments_agree("Tidak lulus, SMT. II 2025", "tidak lulus SMT II 2025")
    assert not fragments_agree("nilai 53 untuk SMA dan 41 untuk S1", "nilai 41 untuk SMA dan 53 untuk S1")
    assert not fragments_agree("nilai 75 + 3", "nilai 75 - 3")
    assert not fragments_agree(HARD, HARD.replace("tidak ", ""))
    assert not fragments_agree("semester II 2025", "semester I 2025")


def test_table_merged_date_cell_is_never_split_into_different_crops():
    image = Image.new("RGB", (600, 1200), "white")
    draw = ImageDraw.Draw(image)
    for y in range(200, 1101, 100):
        draw.line((20, y, 320 if y == 400 else 580, y), fill="black", width=3)
    for x in [20, 320, 580]:
        draw.line((x, 200, x, 1100), fill="black", width=2)
    # Rows 300–400 and 400–500 share one date cell on the right.
    draw.text((350, 360), "21 SEPTEMBER 2026", fill="black")
    bounds = region_bounds(image)
    assert not any(305 < bottom < 495 for _, bottom in bounds)
    assert all(bottom - top <= image.height / 4 for top, bottom in bounds)


def test_relay_fragment_uses_fixed_route_and_rejects_whole_page_array(monkeypatch, tmp_path):
    relay = Relay(Settings(data_dir=tmp_path))
    sent = []

    def post(operation, payload):
        sent.append((operation, payload))
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(answer())}}]}

    monkeypatch.setattr(relay, "post", post)
    assert relay.vision("data:image/jpeg;base64,YWJj", fragment=True) == answer()
    assert sent == [("vision-fragment", {"image": "data:image/jpeg;base64,YWJj"})]
    with pytest.raises(AIError):
        relay.vision(["image", "image"], fragment=True)
