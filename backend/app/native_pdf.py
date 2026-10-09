"""Read native PDF cells from vector geometry; never infer values for empty cells."""

import math

from pdfplumber.utils import extract_text

from .ocr_layout import table_records, validate_table

NATIVE_LAYOUT = "native-cells-v1"


def visible_rule(obj):
    if obj.get("object_type") != "rect":
        return True
    if obj.get("stroke"):
        return True
    # Filled backgrounds and white text masks are not cell borders. Filled,
    # thin dark rules are common in PDFs exported by word processors.
    color = obj.get("non_stroking_color")
    dark = isinstance(color, (int, float)) and color < 0.5
    if isinstance(color, (tuple, list)) and len(color) == 3:
        dark = max(color) < 0.5
    return bool(obj.get("fill") and dark and min(obj["width"], obj["height"]) <= 1.5)


def find_native_tables(page):
    tables = page.filter(visible_rule).find_tables()
    # A small detected box inside an enclosing table is already represented
    # by the parent geometry and must not duplicate its characters.
    return [
        t
        for t in tables
        if not any(
            parent is not t
            and parent.bbox[0] <= t.bbox[0]
            and parent.bbox[1] <= t.bbox[1]
            and parent.bbox[2] >= t.bbox[2]
            and parent.bbox[3] >= t.bbox[3]
            and parent.bbox != t.bbox
            for parent in tables
        )
    ]


def center_inside(char, bounds):
    x = (char["x0"] + char["x1"]) / 2
    y = (char["top"] + char["bottom"]) / 2
    return bounds[0] <= x < bounds[2] and bounds[1] <= y < bounds[3]


def boundaries(values):
    result = []
    for value in sorted(values):
        if not math.isfinite(value):
            raise ValueError("Koordinat sel PDF tidak valid.")
        if not result or value - result[-1] > 0.5:
            result.append(value)
    return result


def boundary_index(value, edges):
    index = min(range(len(edges)), key=lambda i: abs(edges[i] - value))
    if abs(edges[index] - value) > 0.5:
        raise ValueError("Batas sel PDF tidak sejajar.")
    return index


def native_table(page, table):
    cells = list(dict.fromkeys(table.cells))
    xs = boundaries([cell[i] for cell in cells for i in (0, 2)])
    ys = boundaries([cell[i] for cell in cells for i in (1, 3)])
    rows, columns = len(ys) - 1, len(xs) - 1
    if not 1 <= rows <= 300 or not 1 <= columns <= 128 or rows * columns > 4000:
        raise ValueError("Struktur tabel native melewati batas atau tidak lengkap.")
    source_chars = [c for c in page.chars if center_inside(c, table.bbox)]
    assigned = set()
    normalized = []
    for bounds in cells:
        row, column = boundary_index(bounds[1], ys), boundary_index(bounds[0], xs)
        bottom, right = boundary_index(bounds[3], ys), boundary_index(bounds[2], xs)
        indices = [i for i, c in enumerate(source_chars) if center_inside(c, bounds)]
        if assigned.intersection(indices):
            raise ValueError("Ada tulisan yang terpetakan ke lebih dari satu sel.")
        assigned.update(indices)
        chars = [source_chars[i] for i in indices]
        text = extract_text(chars, layout=False) if chars else ""
        if "\ufffd" in text or "\x00" in text:
            raise ValueError("Ada karakter sel PDF yang belum terbaca.")
        normalized.append(
            {
                "row": row,
                "column": column,
                "rowspan": bottom - row,
                "colspan": right - column,
                "text": text,
                "uncertain": False,
            }
        )
    if len(assigned) != len(source_chars):
        raise ValueError("Ada tulisan di dalam tabel yang belum terpetakan ke sel.")
    block = {
        "kind": "table",
        "bbox": [table.bbox[i] / (page.width if i % 2 == 0 else page.height) for i in range(4)],
        "text": "",
        "rows": rows,
        "columns": columns,
        # Preserve every row, including headers: do not guess where data starts.
        "header_rows": 0,
        "cells": normalized,
        "uncertain": False,
        "source": NATIVE_LAYOUT,
    }
    problem = validate_table(block, maximum_columns=128)
    if problem:
        raise ValueError(problem)
    return block


def native_layout(page, tables):
    """Return source-ordered text/table zones plus only the failed table crops.

    All non-whitespace native characters must belong to a cell or narrative zone.
    A geometry failure is an unresolved region, never an invented empty cell.
    """
    for i, first in enumerate(tables):
        for second in tables[i + 1 :]:
            a, b, c, d = first.bbox
            x, y, z, q = second.bbox
            if min(c, z) - max(a, x) > 0.5 and min(d, q) - max(b, y) > 0.5:
                raise ValueError("Kotak tabel native saling bertumpuk.")
    words = [
        {
            "text": w["text"],
            "confidence": 100,
            "source": "native",
            "bbox": [w["x0"] / page.width, w["top"] / page.height, w["x1"] / page.width, w["bottom"] / page.height],
        }
        for w in page.extract_words()
    ]
    blocks, zones, failures = [], [], []
    for index, table in enumerate(sorted(tables, key=lambda t: (t.bbox[1], t.bbox[0])), 1):
        bounds = [table.bbox[i] / (page.width if i % 2 == 0 else page.height) for i in range(4)]
        try:
            block = native_table(page, table)
            blocks.append(block)
            text = table_records(block, index)
            ai, reason = False, ""
        except ValueError as exc:
            text = extract_text([c for c in page.chars if center_inside(c, table.bbox)], layout=False)
            ai, reason = True, str(exc)
            failures.append(reason)
        zones.append(
            {"bbox": bounds, "grid": None, "text": text, "ai": ai, "table_required": ai, "native_issue": reason}
        )
    # Split outside text into bands so notes, titles, and signatures stay ordered.
    outside = [c for c in page.chars if not any(center_inside(c, t.bbox) for t in tables)]
    edges = sorted({0, page.height, *(t.bbox[i] for t in tables for i in (1, 3))})
    for top, bottom in zip(edges, edges[1:]):
        chars = [c for c in outside if top <= (c["top"] + c["bottom"]) / 2 < bottom]
        text = extract_text(chars, layout=False) if chars else ""
        if not text.strip():
            continue
        if "\ufffd" in text or "\x00" in text:
            raise ValueError("Ada tulisan di luar tabel yang belum terbaca.")
        zones.append(
            {
                "bbox": [0, top / page.height, 1, bottom / page.height],
                "grid": None,
                "text": text,
                "ai": False,
            }
        )
    if sum(
        len([c for c in outside if top <= (c["top"] + c["bottom"]) / 2 < bottom])
        for top, bottom in zip(edges, edges[1:])
    ) != len(outside):
        raise ValueError("Ada tulisan di luar tabel yang belum tercakup.")
    zones.sort(key=lambda z: (z["bbox"][1], z["bbox"][0]))
    return {
        "text": "\n\n".join(z["text"] for z in zones),
        "zones": zones,
        "blocks": blocks,
        "words": words,
        "failures": failures,
    }
