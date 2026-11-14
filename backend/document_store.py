"""Validated text ingestion, stable section chunks, and transactional SQLite indexing."""
import hashlib
import re
import sqlite3
import unicodedata
from contextlib import closing
from pathlib import Path

from backend import project_service


class RetrievalError(Exception):
    """An actionable local retrieval/setup failure; never an Anthropic failure."""


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(text):
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    return "\n".join(re.sub(r"[^\S\n]+", " ", line).strip() for line in text.splitlines()).strip()


def chunk_sections(body, document_id, revision):
    chunks, section, lines = [], "Overview", []
    seen_sections = set()

    def flush():
        text = normalize("\n".join(lines))
        if not text:
            return
        slug = re.sub(r"[^\w]+", "-", section.lower()).strip("-")
        if slug in seen_sections:
            raise RetrievalError(f"Repeated section heading in {document_id}: {section}")
        seen_sections.add(slug)
        words = text.split()
        for part, start in enumerate(range(0, len(words), 100), 1):
            excerpt = text if len(words) <= 120 else " ".join(words[start:start + 120])
            chunks.append({"chunk_id": f"{document_id}:r{revision}:{slug}:{part}",
                           "section": section, "excerpt": excerpt})
            if start + 120 >= len(words):
                break

    headings = []
    for line in body.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            flush()
            lines = []
            level, title = len(match[1]), match[2].strip()
            if level == 1:
                headings = []
                section = "Overview"
            else:
                headings = [(depth, name) for depth, name in headings if depth < level]
                headings.append((level, title))
                section = " / ".join(name for _, name in headings)
        else:
            lines.append(line)
    flush()
    return chunks


def read_documents(folder):
    folder = Path(folder)
    if not folder.is_dir():
        raise RetrievalError("Source document directory is missing.")
    paths = sorted(p for p in folder.rglob("*") if p.suffix.lower() in (".md", ".txt"))
    if not paths:
        raise RetrievalError("Source directory contains no Markdown or TXT documents.")
    documents, versions, scopes = [], set(), {}
    for path in paths:
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
                raise ValueError("Source links outside the document directory are not allowed")
            text = normalize(path.read_text(encoding="utf-8-sig"))
            header, body = text.split("\n\n", 1)
            metadata = dict(line.split(": ", 1) for line in header.splitlines())
            document_id = metadata["Document-ID"]
            revision = int(metadata["Revision"])
            project_id = None if metadata["Project-ID"] == "all" else int(metadata["Project-ID"])
            title = metadata["Title"].strip()
            if (not re.fullmatch(r"[A-Z0-9-]+", document_id) or revision < 1 or not title
                    or metadata["Sample-Data"] != "true" or (project_id is not None and project_id < 1)):
                raise ValueError("Invalid required metadata")
            if (document_id, revision) in versions:
                raise ValueError("Conflicting duplicate document revision")
            if document_id in scopes and scopes[document_id] != project_id:
                raise ValueError("A document cannot change project scope between revisions")
            chunks = chunk_sections(body, document_id, revision)
            if not chunks:
                raise ValueError("Document has no source passages")
            versions.add((document_id, revision))
            scopes[document_id] = project_id
            documents.append({"document_id": document_id, "revision": revision,
                              "project_id": project_id, "title": title, "sample_data": True,
                              "source_path": path.relative_to(folder).as_posix(),
                              "content_hash": digest(text), "chunks": chunks})
        except (OSError, UnicodeError, ValueError, KeyError) as error:
            raise RetrievalError(f"Invalid source document {path.name}: {error}") from error
    return documents


def schema(connection):
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS settings (signature TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT, revision INTEGER, project_id INTEGER, title TEXT,
            sample_data INTEGER, source_path TEXT, content_hash TEXT,
            PRIMARY KEY(document_id, revision));
        CREATE TABLE IF NOT EXISTS embeddings (
            embedding_key TEXT PRIMARY KEY, vector BLOB NOT NULL);
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY, document_id TEXT, revision INTEGER,
            section TEXT, excerpt TEXT, embedding_key TEXT);
        CREATE INDEX IF NOT EXISTS chunk_document ON chunks(document_id, revision);
        CREATE INDEX IF NOT EXISTS document_scope ON documents(project_id, document_id, revision);
    """)


def index_signature(models):
    return f"buildflow-v1:120words:20overlap:{models.embedding_key}"


def embedding_text(chunk, title):
    return f"{title}\n{chunk['section']}\n{chunk['excerpt']}"


def active_chunks(connection, project_id):
    connection.row_factory = sqlite3.Row
    return [dict(row) for row in connection.execute("""
        SELECT c.*, d.project_id, d.title, d.sample_data, d.source_path, d.content_hash, e.vector
        FROM chunks c JOIN documents d USING(document_id, revision)
        JOIN embeddings e USING(embedding_key)
        WHERE (d.project_id IS NULL OR d.project_id = ?)
        AND d.revision = (SELECT MAX(new.revision) FROM documents new WHERE new.document_id = d.document_id)
        ORDER BY c.chunk_id
    """, (project_id,))]


def ingest(folder, database, models, rebuild=False):
    documents = read_documents(folder)
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    try:
        with closing(sqlite3.connect(database)) as connection, connection:
            schema(connection)
            signature = index_signature(models)
            saved = connection.execute("SELECT signature FROM settings").fetchone()
            if saved and saved[0] != signature and not rebuild:
                raise RetrievalError("Index/model configuration changed; ingest with --rebuild.")
            previous = {tuple(row) for row in connection.execute("SELECT document_id, revision, content_hash, source_path FROM documents")}
            current = {(d["document_id"], d["revision"], d["content_hash"], d["source_path"]) for d in documents}
            prepared, missing, new_vectors = [], {}, {}
            for doc in documents:
                for chunk in doc["chunks"]:
                    text = embedding_text(chunk, doc["title"])
                    key = digest(f"{models.embedding_key}\n{text}")
                    chunk["embedding_key"] = key
                    prepared.append((doc, chunk))
                    if not connection.execute("SELECT 1 FROM embeddings WHERE embedding_key=?", (key,)).fetchone():
                        missing[key] = text
            if missing:
                import numpy as np

                vectors = models.embed(list(missing.values()))
                if vectors.shape != (len(missing), 384) or not np.isfinite(vectors).all():
                    raise RetrievalError("Embedding model returned invalid vectors; index was not replaced.")
                new_vectors = {key: vector.astype("float32").tobytes() for key, vector in zip(missing, vectors)}
            unchanged = len(previous & current)
            if previous == current and saved and saved[0] == signature and not rebuild:
                return {"documents": len(documents), "chunks": len(prepared), "unchanged_documents": unchanged, "embedded_chunks": 0}
            # Publish the complete validated snapshot and all FTS tables in one transaction.
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM chunks")
            connection.execute("DELETE FROM documents")
            connection.execute("DELETE FROM settings")
            connection.execute("INSERT INTO settings VALUES (?)", (signature,))
            connection.executemany("INSERT OR IGNORE INTO embeddings VALUES (?, ?)", new_vectors.items())
            for doc in documents:
                connection.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?)", tuple(doc[k] for k in
                    ("document_id", "revision", "project_id", "title", "sample_data", "source_path", "content_hash")))
            for doc, chunk in prepared:
                connection.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?)", (
                    chunk["chunk_id"], doc["document_id"], doc["revision"], chunk["section"], chunk["excerpt"], chunk["embedding_key"]))
            for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name GLOB 'fts_project_[0-9]*'").fetchall():
                if re.fullmatch(r"fts_project_\d+", table):
                    connection.execute(f"DROP TABLE {table}")
            scopes = {p["id"] for p in project_service.projects} | {d["project_id"] for d in documents if d["project_id"] is not None}
            for scope in sorted(scopes):
                table = f"fts_project_{int(scope)}"
                connection.execute(f"CREATE VIRTUAL TABLE {table} USING fts5(chunk_id UNINDEXED, text, tokenize='unicode61')")
                connection.executemany(f"INSERT INTO {table}(chunk_id,text) VALUES (?,?)", (
                    (c["chunk_id"], embedding_text(c, c["title"])) for c in active_chunks(connection, scope)))
            return {"documents": len(documents), "chunks": len(prepared), "unchanged_documents": unchanged, "embedded_chunks": len(missing)}
    except sqlite3.Error as error:
        raise RetrievalError("Could not build SQLite index; check its location, permissions, and FTS5 support.") from error
