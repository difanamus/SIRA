"""Local lexical search alongside vector search; never rewrites source facts."""

import math
import re
from collections import Counter
from threading import RLock

STOP = set(
    "yang dan untuk apa saja kalau bagaimana dengan kapan berapa siapa saya kamu anda itu ini "
    "di ke dari pada dalam adalah ada atau apakah bro lah kan dong coba benar bukan bukannya "
    "halaman pertanyaan lanjutan sekaligus nya tahun".split()
)
ALIASES = {}
for group in (
    "kelulusan lulus lolos meluluskan diluluskan",
    "keputusan putusan diputuskan memutuskan penetapan ditetapkan menetapkan kep",
    "kirim dikirim mengirim pengiriman dikirimkan mengirimkan",
    "panggil panggilan pemanggilan",
    "syarat persyaratan",
    "pendidikan sekolah",
    "nilai penilaian",
):
    words = group.split()
    ALIASES.update(dict.fromkeys(words, words[0]))


def terms(text):
    result = []
    for word in re.findall(r"\w+", text.lower()):
        if word.endswith("nya") and len(word) > 5:
            word = word[:-3]
        if len(word) >= 3 and word not in STOP:
            result.append(ALIASES.get(word, word))
    return result


class LexicalIndex:
    def __init__(self, db):
        self.db = db
        self.lock = RLock()
        self.revision = None
        self.rows = []

    def snapshot(self):
        with self.lock:
            revision = self.db.revision
            if self.revision != revision:
                rows = self.db.rows(
                    """SELECT c.*,d.title,d.id AS document_id FROM chunks c JOIN documents d
                    ON d.active_version=c.version_id WHERE d.deleted=0 ORDER BY c.id"""
                )
                counts = [Counter(terms(row["text"] + " " + row["heading"] + " " + row["title"])) for row in rows]
                frequency = Counter(term for count in counts for term in count)
                lengths = [sum(count.values()) for count in counts]
                self.rows, self.counts, self.frequency, self.lengths = rows, counts, frequency, lengths
                self.average = sum(lengths) / max(1, len(lengths)) or 1
                self.revision = revision
            return self.rows, self.counts, self.frequency, self.lengths, self.average

    def search(self, query, limit=20):
        rows, counts, frequency, lengths, average = self.snapshot()
        wanted = set(terms(query))
        explicit_page = re.search(r"\b(?:halaman|hal\.?|page)\s*(\d{1,4})\b", query, re.I)
        page = int(explicit_page[1]) if explicit_page else None
        scores = []
        for row, count, length in zip(rows, counts, lengths):
            overlap = wanted & count.keys()
            # Do not introduce candidates solely on a broad document title.
            if len(overlap) < min(2, len(wanted)) or not overlap:
                continue
            if not overlap & set(terms(row["text"] + " " + row["heading"])):
                continue
            score = 0.0
            for term in overlap:
                idf = math.log(1 + (len(rows) - frequency[term] + 0.5) / (frequency[term] + 0.5))
                tf = count[term]
                score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / average))
            if page == row["page"]:
                score += 4
            scores.append((row, score))
        scores.sort(key=lambda item: (-item[1], item[0]["id"]))
        distinct, seen = [], set()
        for row, score in scores:
            identity = (row["version_id"], row["text"])
            if identity not in seen:
                distinct.append((row, score))
                seen.add(identity)
            if len(distinct) >= limit:
                break
        return distinct


def fuse(semantic, lexical, max_sources=10, max_chars=24000):
    rows, scores = {}, Counter()
    for weight, candidates in ((1.0, semantic), (1.15, [row for row, _ in lexical])):
        for rank, row in enumerate(candidates, 1):
            rows[row["id"]] = row
            scores[row["id"]] += weight / (30 + rank)
    ordered = sorted(rows, key=lambda key: (-scores[key], key))
    # Reserve space for independently found lexical evidence outside vector top-k.
    reserved = [row["id"] for row, _ in lexical[:3]]
    chosen, used = [], 0
    for key in dict.fromkeys(reserved + ordered):
        row = rows[key]
        if len(chosen) >= max_sources:
            break
        if used + len(row["text"]) > max_chars:
            continue  # A long chunk must not hide all later, smaller evidence.
        chosen.append(key)
        used += len(row["text"])
    return [dict(rows[key], source_id=f"S{index}") for index, key in enumerate(chosen, 1)]


def verification_query(query, question):
    """One broader search only when the answer reports absent evidence."""
    extra = "jadwal tanggal waktu periode" if re.search(r"\b(kapan|tanggal|jadwal|waktu)\b", query, re.I) else ""
    return query[-7000:] + "\nPeriksa sumber tambahan: " + question + " " + extra
