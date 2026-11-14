import sqlite3

import pytest


def write_doc(folder, name="policy.md", revision=1, body=None, project="all"):
    path = folder / name
    path.write_text(
        f"Document-ID: TEST-POLICY\nTitle: Sample escalation\nProject-ID: {project}\n"
        f"Revision: {revision}\nSample-Data: true\n\n"
        + (body or "# Sample escalation\n\n## Urgent escalation\nNotify the fictional coordinator within four hours.\n\n## Records\nRecord the RFI number and drawing reference."),
        encoding="utf-8",
    )
    return path


def test_heading_chunks_and_metadata(tmp_path):
    from backend.document_store import read_documents

    write_doc(tmp_path)
    documents = read_documents(tmp_path)
    doc = documents[0]
    assert doc["document_id"] == "TEST-POLICY"
    assert doc["revision"] == 1 and doc["project_id"] is None and doc["sample_data"] is True
    assert doc["title"] == "Sample escalation"
    assert [c["section"] for c in doc["chunks"]] == ["Urgent escalation", "Records"]
    assert doc["chunks"][0]["chunk_id"] == "TEST-POLICY:r1:urgent-escalation:1"
    assert "four hours" in doc["chunks"][0]["excerpt"]
    assert read_documents(tmp_path) == documents


def test_txt_unicode_normalization_and_bounded_chunks(tmp_path):
    from backend.document_store import read_documents

    write_doc(tmp_path, "policy.txt", body="## Re\u0301cords\n" + "field coordination " * 500, project="101")
    doc = read_documents(tmp_path)[0]
    assert doc["project_id"] == 101
    assert doc["chunks"][0]["section"] == "R\u00e9cords"
    assert len(doc["chunks"]) > 1
    assert all(len(c["excerpt"].split()) <= 120 for c in doc["chunks"])


@pytest.mark.parametrize("failure", ["missing", "empty", "invalid_metadata", "duplicate_revision", "empty_body", "scope_change", "symlink"])
def test_invalid_sources_fail_clearly(tmp_path, failure):
    from backend.document_store import read_documents, RetrievalError

    folder = tmp_path / "docs"
    if failure != "missing":
        folder.mkdir()
    if failure in ("invalid_metadata", "empty_body"):
        path = write_doc(folder)
        path.write_text("not a supported document" if failure == "invalid_metadata" else
                        "Document-ID: EMPTY\nTitle: Empty\nProject-ID: all\nRevision: 1\nSample-Data: true\n\n# Empty", encoding="utf-8")
    elif failure == "duplicate_revision":
        write_doc(folder)
        write_doc(folder, "duplicate.txt")
    elif failure == "scope_change":
        write_doc(folder)
        write_doc(folder, "new.md", revision=2, project="101")
    elif failure == "symlink":
        # A file outside the source root must never be followed.
        target = write_doc(tmp_path)
        try:
            (folder / "linked.md").symlink_to(target)
        except OSError:
            pytest.skip("Windows symlink privilege unavailable")
    with pytest.raises(RetrievalError):
        read_documents(folder)


def test_real_ingestion_cache_rebuild_and_rollback(tmp_path, local_models):
    from backend.document_store import ingest, read_documents, RetrievalError

    folder = tmp_path / "docs"
    folder.mkdir()
    path = write_doc(folder)
    database = tmp_path / "index.sqlite3"
    first = ingest(folder, database, local_models)
    assert first["embedded_chunks"] == 2
    assert ingest(folder, database, local_models)["embedded_chunks"] == 0
    assert ingest(folder, database, local_models, rebuild=True)["embedded_chunks"] == 0
    with sqlite3.connect(database) as conn:
        before = conn.execute("SELECT chunk_id FROM chunks ORDER BY chunk_id").fetchall()
    path.write_text("invalid", encoding="utf-8")
    with pytest.raises(RetrievalError):
        ingest(folder, database, local_models, rebuild=True)
    with sqlite3.connect(database) as conn:
        assert conn.execute("SELECT chunk_id FROM chunks ORDER BY chunk_id").fetchall() == before
    write_doc(folder, body="## Urgent escalation\nNotify the sample coordinator within six hours.\n\n## Records\nRecord the RFI number and drawing reference.")
    assert ingest(folder, database, local_models)["embedded_chunks"] == 1
    assert read_documents(folder)[0]["chunks"][0]["chunk_id"] == before[1][0]


def test_embedding_failure_preserves_index(tmp_path, local_models, monkeypatch):
    from backend.document_store import ingest, RetrievalError

    folder = tmp_path / "docs"
    folder.mkdir()
    write_doc(folder)
    database = tmp_path / "index.sqlite3"
    ingest(folder, database, local_models)
    before = database.read_bytes()
    write_doc(folder, body="## Records\nA completely changed sample document.")
    monkeypatch.setattr(local_models, "embed", lambda texts: (_ for _ in ()).throw(RetrievalError("Embedding unavailable")))
    with pytest.raises(RetrievalError):
        ingest(folder, database, local_models, rebuild=True)
    assert database.read_bytes() == before


def test_publication_failure_rolls_back_documents_and_fts(tmp_path, local_models, monkeypatch):
    from backend import document_store

    folder = tmp_path / "docs"
    folder.mkdir()
    write_doc(folder)
    database = tmp_path / "index.sqlite3"
    document_store.ingest(folder, database, local_models)
    with sqlite3.connect(database) as conn:
        before = conn.execute("SELECT chunk_id, excerpt FROM chunks ORDER BY chunk_id").fetchall()
        before_fts = conn.execute("SELECT chunk_id FROM fts_project_101 ORDER BY chunk_id").fetchall()
    write_doc(folder, body="## Changed\nAn updated construction issue record.")

    def fail_fts(*args):
        raise document_store.RetrievalError("Injected FTS publication failure")

    monkeypatch.setattr(document_store, "active_chunks", fail_fts)
    with pytest.raises(document_store.RetrievalError):
        document_store.ingest(folder, database, local_models, rebuild=True)
    with sqlite3.connect(database) as conn:
        assert conn.execute("SELECT chunk_id, excerpt FROM chunks ORDER BY chunk_id").fetchall() == before
        assert conn.execute("SELECT chunk_id FROM fts_project_101 ORDER BY chunk_id").fetchall() == before_fts
