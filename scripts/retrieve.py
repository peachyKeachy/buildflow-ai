"""No paid APIs: python -m scripts.retrieve {download-models,ingest,query,eval}."""
import argparse
import json
import statistics
import platform
from datetime import datetime, timezone
from pathlib import Path

from backend.document_store import RetrievalError, ingest
from backend.retrieval_models import EMBEDDING_KEY, RERANK_MODEL, RERANK_REVISION, ROOT, LocalModels, download_models
from backend.retrieval_service import Retriever


def evaluate(retriever, cases):
    # First query includes NumPy/PyTorch imports, model load, and inference from cached files.
    cold = retriever.search(cases[0]["question"], cases[0]["project_id"])
    runs, metrics = [], {}
    for rerank in (False, True):
        rows, timings = [], []
        for case in cases:
            result = retriever.search(case["question"], case["project_id"], rerank=rerank)
            expected = set(case["relevant"])
            top = result["candidates"][:5]
            retrieved = set()
            first = None
            for rank, candidate in enumerate(top, 1):
                identities = {candidate["chunk_id"], *candidate["duplicate_chunk_ids"]}
                retrieved |= identities
                if first is None and identities & expected:
                    first = rank
            accepted = {c["chunk_id"] for c in result["evidence"]}
            for candidate in result["evidence"]:
                accepted.update(candidate["duplicate_chunk_ids"])
            row = {"id": case["id"], "reranked": rerank, "status": result["status"],
                   "question": case["question"], "expected": case["relevant"],
                   "top5": [c["chunk_id"] for c in top], "evidence": [c["chunk_id"] for c in result["evidence"]],
                   "recall_at_5": len(retrieved & expected) / len(expected) if expected else None,
                   "hit_at_1": int(bool(first == 1)) if expected else None,
                   "mrr_at_5": 1 / first if first else 0,
                   "evidence_hit": bool(accepted & expected) if expected else None,
                   "correct_abstention": result["status"] == "insufficient_evidence" if not expected else None,
                   "timings_ms": result["timings_ms"]}
            rows.append(row)
            if expected:
                timings.append(result["timings_ms"]["total"])
        positive = [row for row in rows if row["recall_at_5"] is not None]
        negative = [row for row in rows if row["correct_abstention"] is not None]
        metrics["hybrid_reranked" if rerank else "hybrid"] = {
            **{key: round(statistics.mean(row[key] for row in positive), 4) for key in
               ("recall_at_5", "hit_at_1", "mrr_at_5", "evidence_hit")},
            "negative_abstention_rate": round(statistics.mean(row["correct_abstention"] for row in negative), 4),
            "warm_median_ms": round(statistics.median(timings), 3),
            "warm_p95_ms": round(sorted(timings)[min(len(timings) - 1, int(len(timings) * .95))], 3),
        }
        runs.extend(rows)
    return {"embedding_model": EMBEDDING_KEY, "reranker": f"{RERANK_MODEL}@{RERANK_REVISION}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "environment": {"python": platform.python_version(), "platform": platform.platform(), "device": "CPU", "torch_threads": 2},
            "positive_cases": len(positive), "negative_cases": len(negative),
            "first_query_with_model_load_ms": cold["timings_ms"], "metrics": metrics, "cases": runs,
            "limitations": "Small manually labeled synthetic corpus; descriptive results, not production accuracy. "
            "Ranking metrics use pre-threshold candidates; evidence_hit measures post-threshold retrieval. "
            "Duplicate source IDs count as aliases. Labels are not exhaustive judgments of every passage's relevance."}


def print_evidence(result):
    print(f"{result['status']} ({result['reason'] or 'relevant sources found'})")
    for rank, source in enumerate(result["evidence"], 1):
        print(f"\n{rank}. {source['title']} / {source['section']}")
        print(f"   {source['chunk_id']} | project={source['project_id'] or 'shared'} | revision={source['revision']} | SYNTHETIC SAMPLE")
        print(f"   cosine={source['dense_score']:.3f} BM25={source['bm25_score']} RRF={source['rrf_score']:.5f} rerank={source['rerank_score']}")
        print(source["excerpt"])
    print("\nTiming (ms):", json.dumps(result["timings_ms"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download-models", help="Explicit one-time network setup; never uses an account token")
    ingest_parser = sub.add_parser("ingest")
    ingest_parser.add_argument("--docs", type=Path, default=ROOT / "sample_docs")
    ingest_parser.add_argument("--rebuild", action="store_true")
    query_parser = sub.add_parser("query")
    query_parser.add_argument("question", nargs="?")
    query_parser.add_argument("--project", type=int, default=101)
    query_parser.add_argument("--no-rerank", action="store_true")
    query_parser.add_argument("--json", action="store_true")
    eval_parser = sub.add_parser("eval")
    eval_parser.add_argument("--cases", type=Path, default=ROOT / "evals" / "retrieval_cases.json")
    eval_parser.add_argument("--output", type=Path)
    for command in (ingest_parser, query_parser, eval_parser):
        command.add_argument("--index", type=Path, default=ROOT / ".cache" / "retrieval.sqlite3")
    args = parser.parse_args()
    try:
        if args.command == "download-models":
            print(*download_models(), sep="\n")
            return 0
        models = LocalModels()
        if args.command == "ingest":
            print(json.dumps(ingest(args.docs, args.index, models, args.rebuild), indent=2))
        elif args.command == "eval":
            cases = json.loads(args.cases.read_text(encoding="utf-8"))
            report = evaluate(Retriever(args.index, models), cases)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2))
        else:
            retriever = Retriever(args.index, models)
            question = args.question
            while True:
                if question is None:
                    question = input("Construction question (blank to exit): ").strip()
                    if not question:
                        break
                result = retriever.search(question, args.project, rerank=not args.no_rerank)
                print(json.dumps(result, indent=2) if args.json else "")
                if not args.json:
                    print_evidence(result)
                if args.question is not None:
                    break
                question = None
        return 0
    except (RetrievalError, OSError, ValueError) as error:
        print(f"Retrieval unavailable: {error}")
        return 2
    except (KeyboardInterrupt, EOFError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
