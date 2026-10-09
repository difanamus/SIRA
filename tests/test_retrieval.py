import pytest

from backend.app.chat import Chat
from backend.app.db import Database
from backend.app.retrieval import LexicalIndex, fuse

SCHEDULE = "[TABEL 2 BARIS 4] 1: 20.; 2: KEP KELULUSAN DAN KIRIM SURAT PANGGIL; 3: 23 S.D. 26 NOVEMBER 2026; 4: 4 HARI"
PROCEDURE = (
    "Panda menetapkan kelulusan lalu mengirimkan berkas ke Panpus untuk penerbitan keputusan dan surat panggilan."
)


@pytest.fixture
def corpus(tmp_path):
    db = Database(tmp_path)
    for doc, title, version in (
        ("sbp", "Pengumuman SBP TA 2027", "active"),
        ("perpol", "Perpol 1 Tahun 2025", "other"),
    ):
        db.execute(
            "INSERT INTO documents(id,title,filename,active_version,created) VALUES (?,?,?,?,0)",
            (doc, title, "uji.pdf", version),
        )
        db.execute(
            "INSERT INTO versions(id,document_id,path,sha256,size,status,created) VALUES (?,?,?,'hash',1,'ready',0)",
            (version, doc, "uji.pdf"),
        )
    for index in range(40):
        db.execute("INSERT INTO chunks VALUES (?,?,7,'',?)", (f"procedure-{index:02}", "active", PROCEDURE))
    db.execute("INSERT INTO chunks VALUES ('schedule','active',12,'Jadwal',?)", (SCHEDULE,))
    db.execute(
        "INSERT INTO chunks VALUES ('performance','other',20,'',?)",
        ("Penilaian kinerja anggota Polri menggunakan indikator perilaku kerja dan hasil kerja.",),
    )
    return db


@pytest.mark.parametrize(
    "query",
    [
        "Untuk SBP 2027, kapan diputuskan siapa yang lolos sekaligus surat panggilnya dikirim?",
        "Kapan keputusan kelulusan SBP 2027 dan pengiriman surat panggilan?",
        "jadwal kep kelulusan dan kirim surat panggil SBP",
    ],
)
def test_lexical_evidence_outside_vector_candidates_is_sent_to_model(corpus, query):
    class AI:
        def embed(self, texts):
            return [[1.0]]

    class Vectors:
        def search(self, embedding, versions, limit):
            return [(f"procedure-{index:02}", 0.1) for index in range(limit)]

    chat = Chat(None, corpus, Vectors(), AI())
    sources = chat.retrieve(query)
    schedule = next(s for s in sources if s["id"] == "schedule")
    assert schedule["page"] == 12 and schedule["text"] == SCHEDULE
    assert len(sources) <= 10 and len({s["source_id"] for s in sources}) == len(sources)


def test_other_document_and_unrelated_query(corpus):
    index = LexicalIndex(corpus)
    assert index.search("Bagaimana penilaian kinerja anggota Polri?")[0][0]["id"] == "performance"
    assert index.search("Resep brownies cokelat panggang?") == []


def test_cache_excludes_deleted_and_replaced_versions(corpus):
    index = LexicalIndex(corpus)
    assert any(row["id"] == "schedule" for row, _ in index.search("jadwal surat panggil SBP"))
    corpus.execute("UPDATE documents SET deleted=1 WHERE id='sbp'")
    corpus.execute("UPDATE meta SET value=value+1 WHERE key='kb_revision'")
    assert not index.search("jadwal surat panggil SBP")
    corpus.execute("UPDATE documents SET deleted=0,active_version='other' WHERE id='sbp'")
    corpus.execute("UPDATE meta SET value=value+1 WHERE key='kb_revision'")
    assert not any(row["id"] == "schedule" for row, _ in index.search("jadwal surat panggil SBP"))


def test_explicit_page_is_a_hint_and_never_creates_source(corpus):
    index = LexicalIndex(corpus)
    assert index.search("SBP surat panggil halaman 12")[0][0]["page"] == 12
    assert not any(row["page"] == 99 for row, _ in index.search("SBP surat panggil halaman 99"))


def test_fusion_keeps_small_evidence_after_oversized_chunk_and_deduplicates():
    large = {"id": "large", "text": "x" * 24001}
    small = {"id": "small", "text": "bukti"}
    sources = fuse([large, small], [(small, 2)])
    assert sources == [{**small, "source_id": "S1"}]
