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
    "terima menerima penerima diterima",
):
    words = group.split()
    ALIASES.update(dict.fromkeys(words, words[0]))


TEMPORAL = re.compile(r"\b(?:kapan|tanggal|jadwal|waktu|bilamana|periode)\b", re.I)
DATE = re.compile(
    r"\b\d{1,2}\s+(?:januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember)\b", re.I
)


PAGE_LIST = re.compile(
    r"\b(?:halaman|hal\.?|hlm\.?|page)\s*(\d{1,4}(?:\s*(?:,|&|-|–|dan|s\.?\s?d\.?|sampai)\s*\d{1,4})*)", re.I
)


def page_numbers(text):
    """Pages a user names: "halaman 8 dan 9", "hal. 8-10", "halaman 3, 5" (small ranges only)."""
    pages = set()
    for group in PAGE_LIST.findall(text):
        numbers = [int(n) for n in re.findall(r"\d+", group)]
        if len(numbers) == 2 and re.search(r"-|–|s\.?\s?d|sampai", group) and 0 < numbers[1] - numbers[0] <= 5:
            pages.update(range(numbers[0], numbers[1] + 1))
        else:
            pages.update(numbers)
    return sorted(page for page in pages if 1 <= page <= 1000)[:6]


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
                self.dates = [len(DATE.findall(row["text"])) for row in rows]
                self.titles = {row["document_id"]: set(terms(row["title"])) for row in rows}
                self.average = sum(lengths) / max(1, len(lengths)) or 1
                self.revision = revision
            return self.rows, self.counts, self.frequency, self.lengths, self.average

    def unknown_terms(self, text):
        """Query words that never occur in the knowledge base (typos, slang, off-topic words)."""
        frequency = self.snapshot()[2]
        return [term for term in terms(text) if term not in frequency and not term.isdigit()]

    def search(self, query, limit=20, document=None, exclude=frozenset(), pages=None, page_document=None):
        rows, counts, frequency, lengths, average = self.snapshot()
        wanted = set(terms(query)) - exclude
        # Time questions ("kapan", "jadwal") favour evidence that actually contains dates.
        temporal = bool(TEMPORAL.search(query))
        # Named pages only count in the document under discussion, when it is known.
        pages = set(page_numbers(query) if pages is None else pages)
        scores = []
        for row, count, length, dates in zip(rows, counts, lengths, self.dates):
            if document and row["document_id"] != document:
                continue
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
            if row["page"] in pages and (page_document is None or row["document_id"] == page_document):
                score += 4
            if temporal:
                score += min(dates, 8) * 0.75
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

    def cross_document(self, query, per_document=1):
        """Documents named explicitly by a question that names two or more, with their best lexical chunk.

        Example: a question comparing an announcement with a regulation must receive evidence from
        both, even if one document dominates the general ranking.
        """
        self.snapshot()
        wanted = set(terms(query))
        titles = self.titles
        named = []
        for document, words in titles.items():
            others = set().union(*(w for d, w in titles.items() if d != document))
            if (words - others) & wanted:
                named.append(document)
        if len(named) < 2:
            return [], []
        title_words = set().union(*(titles[d] for d in named))
        picks = []
        for document in named:
            picks.extend(row for row, _ in self.search(query, per_document, document, frozenset(title_words)))
        return named, picks


def fuse(semantic, lexical, max_sources=10, max_chars=24000, focused=(), documents=(), per_document=2):
    rows, scores = {}, Counter()
    for weight, candidates in ((1.0, semantic), (1.15, [row for row, _ in lexical])):
        for rank, row in enumerate(candidates, 1):
            rows[row["id"]] = row
            scores[row["id"]] += weight / (30 + rank)
    ordered = sorted(rows, key=lambda key: (-scores[key], key))
    # Reserve space for independently found lexical evidence outside vector top-k.
    rows.update({row["id"]: row for row in focused})
    # A question naming several documents keeps the strongest evidence of each of them.
    covered = [
        key
        for document in documents
        for key in [k for k in ordered if rows[k]["document_id"] == document][:per_document]
    ]
    reserved = [row["id"] for row in focused] + covered + [row["id"] for row, _ in lexical[:3]]
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
