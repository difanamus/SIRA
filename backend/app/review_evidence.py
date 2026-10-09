"""Advisory review evidence. Never changes OCR acceptance or calls a model."""

import json
import re

from .ocr_pipeline import source_bounds
from .review_hints import review_hints, text_position

DATE = re.compile(
    r"\b(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+(\d{4})\b",
    re.I,
)


def score(words):
    values = [
        w["confidence"]
        for w in words
        if w.get("source") != "native" and isinstance(w.get("confidence"), (int, float)) and 0 <= w["confidence"] <= 100
    ]
    return round(sum(values) / len(values), 1) if values else None


def page_evidence(page, regions, plan=None):
    plan = plan or {}
    words = plan.get("words", [])
    hints, details = [], []
    corrected = bool(page.get("confirmed") or page.get("method") == "manual-reviewed-v1")
    edited = bool(page.get("revision") or page.get("method", "").startswith("manual"))
    zones = plan.get("zones", [])
    for region in regions:
        if region["number"] <= 0:
            continue
        state = json.loads(region.get("state") or "{}")
        if state.get("superseded_by_native") and page.get("method") == state["superseded_by_native"]:
            continue
        bounds = state.get("bbox", [0, region["top"], 1, region["bottom"]])
        local_words = [
            w
            for w in words
            if bounds[1] <= (w["bbox"][1] + w["bbox"][3]) / 2 <= bounds[3]
            and bounds[0] <= (w["bbox"][0] + w["bbox"][2]) / 2 <= bounds[2]
        ]
        final = state.get("sol", state.get("mini", {}))
        blocks = final.get("blocks", [])
        uncertain = any(
            b.get("uncertain")
            or any(c.get("uncertain") for c in b.get("cells", []))
            or "[TIDAK TERBACA]" in b.get("text", "")
            for b in blocks
        )
        models = [name for key, name in (("mini", "GPT-4.1 mini"), ("sol", "GPT-5.6 Sol")) if key in state]
        local_score = score(local_words)
        if local_score is None:
            value = state.get("local", {}).get("confidence")
            local_score = round(value, 1) if isinstance(value, (int, float)) and 0 <= value <= 100 else None
        details.append(
            {
                "number": region["number"],
                "local_score": local_score,
                "models": models,
                "ai_uncertain": bool(uncertain) if models and not final.get("format_error") else None,
                "corrected": corrected,
            }
        )
        if corrected or edited:
            continue
        if uncertain or final.get("format_error"):
            hints.extend(review_hints(page, [region], plan))
        # Compare only uniquely paired dates in the same saved source region.
        # This is an optional warning, not a new rejection/AI escalation rule.
        zone = zones[region["number"] - 1] if region["number"] <= len(zones) else None
        local_text = zone.get("text", "") if zone else state.get("local", {}).get("text", "")
        source_dates = list(DATE.finditer(local_text))
        result_dates = list(DATE.finditer(region.get("text", "")))
        for original in source_dates:
            key = (original[2].casefold(), original[3])
            same_source = [m for m in source_dates if (m[2].casefold(), m[3]) == key]
            candidates = [m for m in result_dates if (m[2].casefold(), m[3]) == key]
            if len(same_source) != 1 or len(candidates) != 1 or int(original[1]) == int(candidates[0][1]):
                continue
            quote = candidates[0][0]
            position = source_bounds({"kind": "text", "text": original[0]}, {"bbox": bounds, "grid": None}, words)
            hints.append(
                {
                    "id": f"e{region['number']}-date{original.start()}",
                    "region": region["number"],
                    "reason": f"Pembacaan awal lokal: {original[0]}; hasil tersimpan: {quote}. Perbedaan tanggal disarankan diperiksa pada gambar; belum menentukan hasil mana yang benar.",
                    "quote": quote,
                    "bbox": position,
                    "locatable": True,
                    "approximate": True,
                    "text_range": text_position(page["text"], quote),
                    "method": region["method"],
                }
            )
    return {"local_score": score(words), "regions": details, "corrected": corrected, "edited": edited}, hints


def review_page(db, version_id, page):
    regions = db.rows(
        "SELECT * FROM ocr_regions WHERE version_id=? AND page=? ORDER BY number", (version_id, page["number"])
    )
    job = db.one("SELECT plan FROM ocr_page_jobs WHERE version_id=? AND page=?", (version_id, page["number"]))
    plan = json.loads(job["plan"]) if job else None
    evidence, advisory = page_evidence(page, regions, plan)
    unresolved = bool(page.get("required") and not page.get("confirmed"))
    needed = [r for r in regions if r["required"]] if unresolved else []
    mandatory = review_hints(page, needed, plan) if unresolved else []
    ids = {hint["id"] for hint in mandatory}
    page["hints"] = mandatory + [h for h in advisory if h["id"] not in ids]
    page["evidence"] = evidence
    page["recommended"] = bool(advisory) and not unresolved
    page["regions"] = [{k: v for k, v in r.items() if k not in {"state", "text"}} for r in needed]
    return page


def verification_summary(db, version_id):
    pages = db.rows("SELECT number,text,method,warning FROM pages WHERE version_id=? ORDER BY number", (version_id,))
    scores, recommendations = [], 0
    for page in pages:
        review_page(db, version_id, page)
        if page["evidence"]["local_score"] is not None:
            scores.append(page["evidence"]["local_score"])
        recommendations += len({hint["region"] for hint in page["hints"]})
    return {
        "accepted_pages": len(pages),
        "recommended_parts": recommendations,
        "local_score": round(sum(scores) / len(scores), 1) if scores else None,
        "scored_pages": len(scores),
    }
