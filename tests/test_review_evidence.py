import json

from backend.app.review_evidence import page_evidence


def evidence():
    original, saved = "14 September 2026", "19 September 2026"
    page = {"number": 1, "text": saved, "method": "ocr+4.1-mini-layout-v3", "required": 0, "confirmed": 0}
    words = [
        {"text": word, "confidence": confidence, "bbox": [0.6 + i * 0.1, 0.8, 0.7 + i * 0.1, 0.82]}
        for i, (word, confidence) in enumerate(zip(original.split(), [77, 96, 95]))
    ]
    plan = {"words": words, "zones": [{"text": original, "bbox": [0, 0.7, 1, 1]}]}
    region = {
        "number": 1,
        "top": 0.7,
        "bottom": 1,
        "method": page["method"],
        "warning": "",
        "text": saved,
        "required": 0,
        "state": json.dumps({"mini": {"blocks": [{"text": saved, "uncertain": False}]}}),
    }
    return page, [region], plan


def test_date_difference_is_advisory_with_real_local_score_and_model_scope():
    page, regions, plan = evidence()
    details, hints = page_evidence(page, regions, plan)
    assert page["required"] == 0 and regions[0]["required"] == 0
    assert details["local_score"] == 89.3
    assert details["regions"][0]["models"] == ["GPT-4.1 mini"]
    assert details["regions"][0]["ai_uncertain"] is False
    assert len(hints) == 1 and hints[0]["quote"] == page["text"]
    assert "14 September" in hints[0]["reason"] and "19 September" in hints[0]["reason"]
    assert hints[0]["text_range"] == [0, len(page["text"])]
    assert hints[0]["bbox"][1] >= 0.7


def test_saved_model_identity_distinguishes_luna_from_historical_mini():
    page, regions, plan = evidence()
    historical = regions[0]["state"]
    details, _ = page_evidence(page, regions, plan)
    assert details["regions"][0]["models"] == ["GPT-4.1 mini"]
    state = json.loads(historical)
    state["mini_model"] = "gpt-6-luna"
    regions[0]["state"] = json.dumps(state)
    details, _ = page_evidence(page, regions, plan)
    assert details["regions"][0]["models"] == ["GPT-6 Luna"]


def test_native_text_has_no_fabricated_score_or_recommendation():
    details, hints = page_evidence({"text": "Teks native", "method": "text"}, [])
    assert details["local_score"] is None and details["regions"] == [] and not hints


def test_human_confirmation_retains_evidence_without_stale_recommendations():
    page, regions, plan = evidence()
    page.update(text="14 September 2026", confirmed=1, method="manual")
    details, hints = page_evidence(page, regions, plan)
    assert details["corrected"] and details["local_score"] == 89.3 and not hints


def test_unconfirmed_manual_edit_does_not_claim_human_confirmation():
    page, regions, plan = evidence()
    page.update(text="Draft baru", confirmed=0, method="manual", revision=1)
    details, hints = page_evidence(page, regions, plan)
    assert details["edited"] and not details["corrected"] and not hints


def test_dates_with_multiple_candidates_are_not_paired_arbitrarily():
    page, regions, plan = evidence()
    plan["zones"][0]["text"] += " sampai 20 September 2026"
    assert not page_evidence(page, regions, plan)[1]


def test_no_uncertainty_report_does_not_mean_model_verified_every_region():
    page, regions, plan = evidence()
    state = json.loads(regions[0]["state"])
    state["sol"] = {"blocks": [{"text": page["text"], "uncertain": True}]}
    regions[0]["state"] = json.dumps(state)
    details, hints = page_evidence(page, regions, plan)
    assert details["regions"][0]["models"] == ["GPT-4.1 mini", "GPT-5.6 Sol"]
    assert details["regions"][0]["ai_uncertain"] is True and hints
