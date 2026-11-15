"""Project-scoped dense + BM25 retrieval, reciprocal rank fusion, and reranking."""
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from time import perf_counter

from backend.document_store import RetrievalError, active_chunks, digest, embedding_text, index_signature
from backend.project_service import get_project_by_id
from backend.query_policy import is_clearly_unrelated


class Retriever:
    def __init__(self, database, models):
        self.database = Path(database)
        self.models = models

    def search(self, question, project_id, rerank=True, limit=5):
        started = perf_counter()
        result = {"status": "insufficient_evidence", "reason": "no_relevant_sources",
                  "evidence": [], "candidates": [], "timings_ms": {}}

        def finish():
            result["timings_ms"]["total"] = round((perf_counter() - started) * 1000, 3)
            return result

        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise RetrievalError("Enter a nonblank retrieval question of at most 4000 characters.")
        if type(project_id) is not int or project_id < 1 or not 1 <= limit <= 20:
            raise RetrievalError("Use a positive integer project ID and a result limit from 1 to 20.")
        if get_project_by_id(project_id) is None:
            result["reason"] = "project_not_found"
            return finish()
        if is_clearly_unrelated(question):
            result["reason"] = "out_of_scope"
            return finish()
        if not self.database.is_file():
            raise RetrievalError("Retrieval index is missing. Run the ingest command first.")
        try:
            with closing(sqlite3.connect(self.database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
                # Keep metadata, vectors, and FTS on one snapshot during concurrent rebuilds.
                connection.execute("BEGIN")
                saved = connection.execute("SELECT signature FROM settings").fetchone()
                if not saved or saved[0] != index_signature(self.models):
                    raise RetrievalError("Retrieval index configuration is missing or incompatible; rebuild the index.")
                rows = active_chunks(connection, project_id)
                if not rows:
                    result["reason"] = "empty_index"
                    return finish()
                terms = list(dict.fromkeys(re.findall(r"\w+", question.lower())))[:50]
                expression = " OR ".join('"' + term + '"' for term in terms)
                # Each project has its own FTS corpus, including shared current policies.
                # BM25 statistics therefore cannot be influenced by another project's documents.
                table = f"fts_project_{project_id}"
                keyword = connection.execute(
                    f"SELECT chunk_id, bm25({table}) AS score FROM {table} WHERE {table} MATCH ? ORDER BY score, chunk_id LIMIT 20",
                    (expression,),
                ).fetchall() if expression else []
        except sqlite3.Error as error:
            raise RetrievalError("Could not read retrieval index. Rebuild it with the current project list.") from error
        result["timings_ms"]["sqlite_bm25"] = round((perf_counter() - started) * 1000, 3)
        try:
            import numpy as np
        except ImportError as error:
            raise RetrievalError("Install requirements-rag.txt to enable semantic retrieval.") from error
        stage = perf_counter()
        query_vector = self.models.embed([question])[0]
        vectors = np.stack([np.frombuffer(c["vector"], dtype="float32") for c in rows])
        similarities = vectors @ query_vector
        dense = sorted(range(len(rows)), key=lambda i: (-float(similarities[i]), rows[i]["chunk_id"]))[:20]
        candidates = {}
        for rank, index in enumerate(dense, 1):
            row = {k: v for k, v in rows[index].items() if k not in ("vector", "embedding_key")}
            row.update(dense_rank=rank, dense_score=float(similarities[index]), bm25_rank=None,
                       bm25_score=None, rrf_score=1 / (60 + rank), rerank_score=None,
                       duplicate_chunk_ids=[], sample_data=bool(row["sample_data"]), trust="untrusted_source")
            candidates[row["chunk_id"]] = row
        by_id = {row["chunk_id"]: (index, row) for index, row in enumerate(rows)}
        for rank, match in enumerate(keyword, 1):
            chunk_id, score = match
            if chunk_id not in candidates:
                index, row = by_id[chunk_id]
                candidates[chunk_id] = {k: v for k, v in row.items() if k not in ("vector", "embedding_key")}
                candidates[chunk_id].update(dense_rank=None, dense_score=float(similarities[index]),
                    rrf_score=0, rerank_score=None, duplicate_chunk_ids=[], trust="untrusted_source",
                    sample_data=bool(row["sample_data"]))
            candidates[chunk_id].update(bm25_rank=rank, bm25_score=float(score))
            candidates[chunk_id]["rrf_score"] += 1 / (60 + rank)
        ranked = sorted(candidates.values(), key=lambda c: (-c["rrf_score"], c["chunk_id"]))
        unique = {}
        for candidate in ranked:
            key = digest(candidate["excerpt"])
            if key in unique:
                unique[key]["duplicate_chunk_ids"].append(candidate["chunk_id"])
            else:
                unique[key] = candidate
        ranked = list(unique.values())[:20]
        result["timings_ms"]["dense_fusion"] = round((perf_counter() - stage) * 1000, 3)
        if rerank:
            stage = perf_counter()
            scores = self.models.rerank(question, [embedding_text(c, c["title"]) for c in ranked])
            if len(scores) != len(ranked) or not np.isfinite(scores).all():
                raise RetrievalError("Reranker returned invalid scores.")
            for candidate, score in zip(ranked, scores):
                candidate["rerank_score"] = float(score)
            ranked.sort(key=lambda c: (-c["rerank_score"], -c["rrf_score"], c["chunk_id"]))
            result["timings_ms"]["rerank"] = round((perf_counter() - stage) * 1000, 3)
        result["candidates"] = ranked
        # Scores are corpus-specific heuristics, not calibrated confidence probabilities.
        result["evidence"] = [c for c in ranked if c["dense_score"] >= 0.40 and
                              (not rerank or c["rerank_score"] >= 1.0)][:limit]
        if result["evidence"]:
            result.update(status="ok", reason=None)
        return finish()
