"""Image layout evidence and table normalization; no model is trusted to invent spans."""

import math
import re

import numpy as np
from PIL import ImageOps


def runs(mask):
    edges = np.diff(np.pad(np.asarray(mask, dtype=np.int8), (1, 1)))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))


def line_segments(ink, minimum):
    segments = []
    for y, row in enumerate(ink):
        # Close one-pixel scanning gaps without joining separate words.
        closed = row.copy()
        closed[1:-1] |= row[:-2] & row[2:]
        for a, b in runs(~closed):
            if a > 0 and b < len(row) and b - a <= 3:
                closed[a:b] = True
        for a, b in runs(closed):
            if b - a >= minimum:
                segments.append((y, int(a), int(b)))
    grouped = []
    for y, a, b in segments:
        match = next(
            (g for g in reversed(grouped[-12:]) if y - g[0] <= 3 and abs(a - g[1]) < 8 and abs(b - g[2]) < 8), None
        )
        if match:
            match[0] = y
            match[1], match[2] = min(a, match[1]), max(b, match[2])
        else:
            grouped.append([y, a, b, y])
    return [[(first + last) // 2, a, b] for last, a, b, first in grouped]


def detect_tables(image):
    """Detect ruled grids, including partial rules inside vertically merged cells.

    This is geometric evidence, not a general table detector. Borderless tables
    are also requested from the vision model when a page needs AI.
    """
    sample = ImageOps.grayscale(image)
    sample.thumbnail((1400, 1800))
    ink = np.asarray(sample) < 205
    h, w = ink.shape
    # A slight scan skew moves thin rules by a few pixels. Allow that drift
    # perpendicular to a rule; retain the original pixels for span validation.
    horizontal_ink = np.logical_or.reduce([np.roll(ink, offset, axis=0) for offset in range(-2, 3)])
    vertical_ink = np.logical_or.reduce([np.roll(ink, offset, axis=1) for offset in range(-8, 9)])
    horizontal = line_segments(horizontal_ink, max(45, int(w * 0.18)))
    vertical = line_segments(vertical_ink.T, max(60, int(h * 0.065)))
    # Scanned page edges are often dark; they are not table columns.
    vertical = [line for line in vertical if w * 0.025 < line[0] < w * 0.975]
    groups = []
    for x, a, b in sorted(vertical, key=lambda line: line[2] - line[1], reverse=True):
        group = next(
            (g for g in groups if min(b, g["bottom"]) - max(a, g["top"]) > 0.8 * max(b - a, g["bottom"] - g["top"])),
            None,
        )
        if group is None:
            groups.append({"top": a, "bottom": b, "xs": [x]})
        else:
            group["xs"].append(x)
    tables = []
    for group in groups:
        xs = sorted(group["xs"])
        clusters = []
        for x in xs:
            if clusters and x - clusters[-1][-1] <= max(6, w * 0.012):
                clusters[-1].append(x)
            else:
                clusters.append([x])
        xs = [round(float(np.median(cluster))) for cluster in clusters]
        if len(xs) < 3:
            continue
        left, right = xs[0], xs[-1]
        lines = [
            (y, a, b)
            for y, a, b in horizontal
            if group["top"] - 8 <= y <= group["bottom"] + 8 and min(b, right) - max(a, left) > (right - left) * 0.25
        ]
        ys = sorted({y for y, _, _ in lines})
        ys = [y for i, y in enumerate(ys) if i == 0 or y - ys[i - 1] > 5]
        if len(ys) < 3 or right - left < w * 0.3:
            continue
        # Long verticals must end near outer rules. Faint/broken outer rules
        # must not truncate a table into overlapping partial detections.
        if abs(ys[0] - group["top"]) > 12 or abs(ys[-1] - group["bottom"]) > 12:
            continue
        # Separator evidence for each elementary cell boundary.
        rules = []
        for y in ys[1:-1]:
            row = []
            for a, b in zip(xs, xs[1:]):
                band = ink[max(0, y - 6) : min(h, y + 7), a + 7 : b - 7]
                projection = band.any(axis=0) if band.size else np.zeros(1, dtype=bool)
                density = float(projection.mean())
                longest = max((b - a for a, b in runs(projection)), default=0) / len(projection)
                row.append(True if density > 0.75 and longest > 0.6 else (False if longest < 0.4 else None))
            rules.append(row)
        column_rules = []
        for a, b in zip(ys, ys[1:]):
            row = []
            for x in xs[1:-1]:
                band = ink[a + 7 : b - 7, max(0, x - 9) : min(w, x + 10)]
                projection = band.any(axis=1) if band.size else np.zeros(1, dtype=bool)
                density = float(projection.mean())
                longest = max((b - a for a, b in runs(projection)), default=0) / len(projection)
                row.append(True if density > 0.75 and longest > 0.6 else (False if longest < 0.4 else None))
            column_rules.append(row)
        tables.append(
            {
                "bbox": [left / w, ys[0] / h, right / w, ys[-1] / h],
                "rows": len(ys) - 1,
                "columns": len(xs) - 1,
                "xs": [x / w for x in xs],
                "ys": [y / h for y in ys],
                "horizontal": rules,
                "vertical": column_rules,
            }
        )
    # Skew can yield shorter segments of the same grid. Retain the enclosing
    # table rather than reading overlapping fragments as separate tables.
    unique = []
    for table in sorted(
        tables, key=lambda t: (t["bbox"][2] - t["bbox"][0]) * (t["bbox"][3] - t["bbox"][1]), reverse=True
    ):
        a, b, c, d = table["bbox"]
        if any(
            x - 0.015 <= a and y - 0.015 <= b and z + 0.015 >= c and q + 0.015 >= d
            for x, y, z, q in (t["bbox"] for t in unique)
        ):
            continue
        unique.append(table)
    return sorted(unique, key=lambda table: table["bbox"][1])


def bbox(value):
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)
    ):
        raise ValueError("Posisi bagian tidak valid.")
    x0, y0, x1, y1 = value
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("Posisi bagian di luar gambar.")
    return value


def overlap(first, second):
    a, b, c, d = first
    x, y, z, q = second
    intersection = max(0, min(c, z) - max(a, x)) * max(0, min(d, q) - max(b, y))
    return intersection / max(0.00001, (c - a) * (d - b) + (z - x) * (q - y) - intersection)


def validate_table(block, grid=None, *, maximum_columns=30):
    rows, columns = block.get("rows"), block.get("columns")
    cells = block.get("cells")
    if (
        type(rows) is not int
        or type(columns) is not int
        or not 1 <= rows <= 300
        or not 1 <= columns <= maximum_columns
        or rows * columns > 4000
    ):
        return "Jumlah baris/kolom tabel tidak valid."
    if not isinstance(cells, list) or not cells or len(cells) > 4000:
        return "Isi sel tabel tidak lengkap."
    headers = block.get("header_rows", 0)
    if type(headers) is not int or not 0 <= headers < rows:
        return "Posisi judul kolom tidak valid."
    if grid and (rows != grid["rows"] or columns != grid["columns"]):
        return "Jumlah baris/kolom AI berbeda dari garis tabel pada gambar."
    occupied = {}
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            return "Format sel tidak valid."
        r, c, rs, cs = (cell.get(k) for k in ("row", "column", "rowspan", "colspan"))
        if (
            any(type(v) is not int for v in (r, c, rs, cs))
            or min(r, c) < 0
            or min(rs, cs) < 1
            or r + rs > rows
            or c + cs > columns
        ):
            return "Rentang sel tabel tidak valid."
        if (
            not isinstance(cell.get("text"), str)
            or len(cell["text"]) > 10000
            or type(cell.get("uncertain")) is not bool
        ):
            return "Teks atau kepastian sel tidak valid."
        if cell["uncertain"] or "[TIDAK TERBACA]" in cell["text"]:
            return "Ada isi sel yang belum terbaca dengan pasti."
        for y in range(r, r + rs):
            for x in range(c, c + cs):
                if (y, x) in occupied:
                    return "Ada sel tabel bertumpuk."
                occupied[y, x] = index
    if len(occupied) != rows * columns:
        return "Ada sel tabel hilang; sel kosong harus dicatat eksplisit."
    if grid:
        for y, rule in enumerate(grid["horizontal"]):
            for x, exists in enumerate(rule):
                if exists is None:
                    continue
                same = occupied[y, x] == occupied[y + 1, x]
                if exists == same:
                    return "Hubungan sel gabungan tidak sesuai garis horizontal pada gambar."
        for y, rule in enumerate(grid["vertical"]):
            for x, exists in enumerate(rule):
                if exists is None:
                    continue
                same = occupied[y, x] == occupied[y, x + 1]
                if exists == same:
                    return "Hubungan sel gabungan tidak sesuai garis vertikal pada gambar."
    return ""


def table_records(block, index=1):
    """Repeat values only over explicit, validated spans; never fill blank cells."""
    matrix = [[""] * block["columns"] for _ in range(block["rows"])]
    for cell in block["cells"]:
        for row in range(cell["row"], cell["row"] + cell["rowspan"]):
            for col in range(cell["column"], cell["column"] + cell["colspan"]):
                matrix[row][col] = re.sub(r"\s+", " ", cell["text"]).strip()
    headers = block["header_rows"]
    labels = [
        " / ".join(dict.fromkeys(matrix[r][c] for r in range(headers) if matrix[r][c])) or f"Kolom {c + 1}"
        for c in range(block["columns"])
    ]
    records = []
    for row in range(headers, block["rows"]):
        values = "; ".join(f"{label}: {value or '[KOSONG PADA SUMBER]'}" for label, value in zip(labels, matrix[row]))
        records.append(f"[TABEL {index} BARIS {row + 1}] {values}")
    return "\n\n".join(records)


def block_text(block, index=1):
    if block.get("kind") == "table":
        if not validate_table(block):
            return table_records(block, index)
        # Review draft: preserve AI cells without silently assigning invalid spans.
        return "[TABEL BELUM TERVERIFIKASI]\n" + "\n".join(
            f"Sel ({cell.get('row')}, {cell.get('column')}): {cell.get('text', '')}"
            for cell in block.get("cells", [])
            if isinstance(cell, dict)
        )
    return block.get("text", "")
