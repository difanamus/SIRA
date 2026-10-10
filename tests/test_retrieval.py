import pytest

from backend.app.chat import Chat
from backend.app.db import Database
from backend.app.retrieval import LexicalIndex, fuse, terms

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


def test_time_question_prefers_chunk_with_dates_over_frequent_mentions(corpus):
    mention = "Panda menyiapkan Tes Psikologi, Tes Psikologi CAT dan pengawas Tes Psikologi."
    for index in range(6):
        corpus.execute("INSERT INTO chunks VALUES (?,?,7,'',?)", (f"psy-{index}", "active", mention))
    table = "[TABEL 2 BARIS 13] NO / 1: 11.; KEGIATAN / 2: TES PSIKOLOGI; JADWAL / 3: 14 OKTOBER 2026; KET / 4: 1 HARI"
    corpus.execute(
        "INSERT INTO chunks VALUES ('psy-schedule','active',11,'',?)",
        (
            table
            + "\n\n[TABEL 2 BARIS 12] 10.; SIMULASI; 12 OKTOBER 2026\n\n[TABEL 2 BARIS 14] 12.; TPK; 15 OKTOBER 2026",
        ),
    )
    top = [row["id"] for row, _ in LexicalIndex(corpus).search("Kapan pelaksanaan Tes Psikologi SBP 2027?")[:3]]
    assert "psy-schedule" in top


def test_question_naming_two_documents_gets_evidence_from_both(corpus):
    class AI:
        def embed(self, texts):
            return [[1.0]]

    class Vectors:  # vector search only finds the announcement
        def search(self, embedding, versions, limit):
            return [(f"procedure-{index:02}", 0.1) for index in range(limit)]

    sources = Chat(None, corpus, Vectors(), AI()).retrieve(
        "Apa kaitan kelulusan pada Pengumuman SBP dengan penilaian kinerja menurut Perpol 2025?"
    )
    assert {s["document_id"] for s in sources} == {"sbp", "perpol"}
    assert len(sources) <= 10


def test_single_document_question_is_not_forced_to_other_documents(corpus):
    index = LexicalIndex(corpus)
    assert index.cross_document("Kapan keputusan kelulusan SBP 2027?") == ([], [])


def test_page_numbers_reads_lists_and_small_ranges():
    from backend.app.retrieval import page_numbers

    assert page_numbers("sarat daftar SBP ada di halaman 8 dan 9 kocak") == [8, 9]
    assert page_numbers("lihat hal. 3-5 dan halaman 12") == [3, 4, 5, 12]
    assert page_numbers("tanpa petunjuk halaman") == []


def test_named_page_only_counts_in_document_under_discussion(corpus):
    corpus.execute("INSERT INTO chunks VALUES ('sbp-9','active',9,'',?)", ("Berkas pendaftaran ijazah dan SKHP.",))
    corpus.execute("INSERT INTO chunks VALUES ('perpol-9','other',9,'',?)", ("Penilaian berkas kinerja dan SKHP.",))
    index = LexicalIndex(corpus)
    top = index.search("berkas SKHP halaman 9", pages=[9], page_document="sbp")[0][0]
    assert top["id"] == "sbp-9"


def test_rewritten_query_and_continued_page_reach_the_model(corpus):
    corpus.execute(
        "INSERT INTO chunks VALUES ('reg-8','active',8,'',?)",
        ("Calon peserta membawa berkas sebagai berikut:\n\n1) Ijazah .....",),
    )
    corpus.execute(
        "INSERT INTO chunks VALUES ('reg-9','active',9,'',?)",
        ("1) ijazah, transkrip; 2) Kep. pangkat terakhir; 5) SKHP (asli).",),
    )
    seen = []

    class AI:
        def embed(self, texts):
            seen.append(texts[0])
            return [[1.0]]

        def rewrite(self, question, history, documents):
            assert question == "apa aja saratnya?" and history == ["Apa itu SBP 2027?"]
            return {
                "query": "persyaratan berkas pendaftaran SBP 2027",
                "document": "Pengumuman SBP TA 2027",
                "pages": [8],
            }

    class Vectors:
        def search(self, embedding, versions, limit):
            return [("reg-8", 0.2)]

    class Session:
        questions = ["Apa itu SBP 2027?"]

    chat = Chat(None, corpus, Vectors(), AI())
    query, hints = chat.rewrite("apa aja saratnya?", Session())
    assert query == "persyaratan berkas pendaftaran SBP 2027" and hints == {"document_id": "sbp", "pages": [8]}
    sources = chat.retrieve(query, hints)
    ids = [s["id"] for s in sources]
    assert seen == [query] and ids.index("reg-9") == ids.index("reg-8") + 1
    assert [s["source_id"] for s in sources] == [f"S{i}" for i in range(1, len(sources) + 1)]


def test_rewrite_failure_falls_back_to_original_question(corpus):
    from backend.app.ai import AIError

    class AI:
        def rewrite(self, question, history, documents):
            raise AIError("relay lama tanpa /rewrite")

    class Session:
        questions = []

    assert Chat(None, corpus, None, AI()).rewrite("syarat SBP?", Session()) is None


def test_clear_question_skips_rewrite_but_typo_or_follow_up_uses_it(corpus):
    calls = []

    class AI:
        def rewrite(self, question, history, documents):
            calls.append(question)
            return {"query": "kep kelulusan surat panggil SBP", "document": "", "pages": []}

    class Fresh:
        questions = []

    class Ongoing:
        questions = ["Kapan kelulusan SBP?"]

    chat = Chat(None, corpus, None, AI())
    assert chat.rewrite("kep kelulusan dan kirim surat panggil SBP", Fresh()) is None  # all words known
    assert chat.rewrite("kpn kelulusan sbp bro", Fresh()) is not None  # typo/slang
    assert chat.rewrite("kalau surat panggilnya?", Ongoing()) is not None  # follow-up
    assert calls == ["kpn kelulusan sbp bro", "kalau surat panggilnya?"]


def test_continuations_only_extend_top_sources_and_keep_other_evidence(corpus):
    for page in range(1, 9):
        corpus.execute(
            "INSERT INTO chunks VALUES (?,?,?,'',?)",
            (f"ann-{page}", "active", page, f"Bagian {page}\n\n2) lanjut ....."),
        )
    chat = Chat(None, corpus, None, None)
    base = [
        dict(
            corpus.one(
                "SELECT c.*,d.title,d.id AS document_id FROM chunks c JOIN documents d ON d.active_version=c.version_id WHERE c.id=?",
                (f"ann-{p}",),
            )
        )
        for p in (1, 3, 5, 7)
    ]
    base.append(
        dict(
            corpus.one(
                "SELECT c.*,d.title,d.id AS document_id FROM chunks c JOIN documents d ON d.active_version=c.version_id WHERE c.id='performance'"
            )
        )
    )
    ids = [s["id"] for s in chat.with_continuations(base)]
    assert ids[:4] == ["ann-1", "ann-2", "ann-3", "ann-4"]  # only the two strongest are extended
    assert "performance" in ids and "ann-6" not in ids


def test_word_forms_of_terima_match_each_other():
    # "menerima penghargaan dari Kapolri" must match the rule text "penerima Penghargaan dari Kapolri".
    assert terms("menerima penghargaan") == terms("penerima Penghargaan") == terms("diterima penghargaan")
