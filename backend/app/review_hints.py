"""Explain review findings from saved evidence, without another AI request."""

import json
import re

from .ocr_layout import bbox, overlap
from .ocr_pipeline import source_bounds


def text_position(text, quote):
    if not quote.strip():
        return None
    pattern = r"\s+".join(re.escape(part) for part in quote.split())
    matches = list(re.finditer(pattern, text, re.I))
    return [matches[0].start(), matches[0].end()] if len(matches) == 1 else None


def review_hints(page, regions, plan=None):
    plan = plan or {"words": [], "tables": []}
    hints = []
    for region in regions:
        state = json.loads(region.get("state") or "{}")
        if state.get("superseded_by_native") and page.get("method") == state["superseded_by_native"]:
            continue
        bounds = state.get("bbox", [0, region["top"], 1, region["bottom"]])
        try:
            bbox(bounds)
        except ValueError:
            bounds = [0, region["top"], 1, region["bottom"]]
        method = region["method"]
        final = state.get("sol", state.get("mini", {}))
        blocks = final.get("blocks", [])

        def add(reason, quote="", position=None, locatable=False, approximate=True):
            quote = quote[:1500]
            hints.append(
                {
                    "id": f"r{region['number']}-h{len(hints) + 1}",
                    "region": region["number"],
                    "reason": reason,
                    "quote": quote,
                    "bbox": position or bounds,
                    "locatable": locatable,
                    "approximate": approximate,
                    "text_range": text_position(page["text"], quote),
                    "method": method,
                }
            )

        if final.get("format_error"):
            add(
                "Pembacaan AI gagal divalidasi: "
                + final["format_error"]
                + " Draft belum terverifikasi; kegagalan ini tidak menunjukkan satu kata tertentu yang salah."
            )
            continue
        for block in blocks:
            suspects = []
            if block.get("kind") == "table":
                suspects = [
                    (cell.get("text", ""), cell)
                    for cell in block.get("cells", [])
                    if cell.get("uncertain") or "[TIDAK TERBACA]" in cell.get("text", "")
                ]
                if block.get("uncertain") and not suspects:
                    suspects = [("", None)]
            elif block.get("uncertain") or "[TIDAK TERBACA]" in block.get("text", ""):
                suspects = [(block.get("text", ""), None)]
            for quote, cell in suspects:
                image_bounds = state.get("sol_bbox" if "sol" in state else "mini_bbox", bounds)
                position = bounds
                try:
                    raw = bbox(block.get("bbox"))
                    a, b, c, d = image_bounds
                    position = [a + raw[0] * (c - a), b + raw[1] * (d - b), a + raw[2] * (c - a), b + raw[3] * (d - b)]
                    # Ordered source phrases can improve estimated model positions.
                    zone = {"bbox": bounds, "grid": None}
                    located = (
                        source_bounds({"kind": "text", "text": quote}, zone, plan.get("words", [])) if quote else bounds
                    )
                    if located != bounds and located[3] - located[1] < (position[3] - position[1]) * 2:
                        position = located
                    bbox(position)
                except (ValueError, TypeError):
                    position = bounds
                reason = "AI belum yakin membaca teks berikut. Cocokkan ejaan atau angka dengan gambar."
                if block.get("kind") == "table":
                    reason = "Hubungan baris/kolom atau isi tabel belum pasti. Cocokkan dengan tabel pada gambar."
                    if cell:
                        row, column = cell.get("row"), cell.get("column")
                        if type(row) is int and type(column) is int:
                            reason = f"Sel tabel baris {row + 1}, kolom {column + 1} belum terbaca pasti."
                            grid = next(
                                (
                                    grid
                                    for grid in plan.get("tables", [])
                                    if overlap(grid["bbox"], bounds) > 0.3
                                    and grid["rows"] == block.get("rows")
                                    and grid["columns"] == block.get("columns")
                                ),
                                None,
                            )
                            rs, cs = cell.get("rowspan", 1), cell.get("colspan", 1)
                            if (
                                grid
                                and all(type(v) is int for v in (rs, cs))
                                and 0 <= row < row + rs <= grid["rows"]
                                and 0 <= column < column + cs <= grid["columns"]
                            ):
                                position = [
                                    grid["xs"][column],
                                    grid["ys"][row],
                                    grid["xs"][column + cs],
                                    grid["ys"][row + rs],
                                ]
                add(reason, quote, position, True)
        if not any(hint["region"] == region["number"] for hint in hints):
            add(
                region["warning"] or "Pembacaan bagian ini belum selesai. Cocokkan draft dengan gambar sumber.",
                locatable=True,
            )
    return hints
