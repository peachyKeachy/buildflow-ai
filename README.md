# BuildFlow AI

Milestone 3B routing, cache, metrics configuration and demo commands:
[local operations guide](docs/MILESTONE3B.md).

Local construction RFI portfolio prototype using React/Vite, FastAPI, and Claude.
All project data is synthetic sample data. This is not an official DeAngelis
Diamond or Future Bylt application. No live Procore connection is present.
The assistant combines structured project tools with citation-validated synthetic
document retrieval. A small whitelist of simple RFI questions runs locally without Claude.

## Local development (PowerShell)

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Use `http://localhost:5173`; the API is `http://127.0.0.1:8000`.
The existing backend credential configuration is loaded only when an allowed
chat request first needs Claude. Tests do not load credential files or call Claude.

## Milestone 1 verification

```powershell
.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
npm run lint
```

With both servers running, run `frontend/tests/browser-smoke.js` through
Playwright MCP's `browser_run_code_unsafe` file argument. It uses actual project
API data and mocked chat responses. It covers responsive layouts, safe Markdown,
duplicate submissions, loading, network failures, navigation, and data errors.

Backend tests use a fresh copy of sample data per test and mock the provider.
They cover existing routes, criticality boundaries, missing projects, validation,
scope decisions, tool results, provider failures, and incomplete responses.
Project 101 has three RFIs: IDs 1 and 3 are critical. Critical means blocking
and open more than seven days. Project 999 is absent.

## Scope and errors

`backend/query_policy.py` locally declines recognizable unrelated English
requests before calling Claude. It deliberately lets ambiguous wording through
to avoid blocking legitimate construction questions. The system prompt reinforces
the construction scope. This is a conservative policy, not a comprehensive topic
classifier or prompt-injection security boundary.

Valid chat responses retain `{"answer": "..."}`. Errors use `{"detail": "..."}`:

| HTTP status | Meaning |
| --- | --- |
| 422 | Blank chat/title, negative RFI age, or invalid request fields |
| 429 | Provider rate limit; wait before retrying |
| 502 | Incomplete answer or provider request/configuration incompatibility |
| 503 | Provider unavailable, connection failure, or credentials need operator attention |
| 504 | Provider timeout |

Provider exception messages and response bodies are never copied into API errors.
The SDK uses a 30-second timeout and no automatic retries. A tool-backed answer
normally needs two provider calls. The dashboard retains its existing generic
recoverable error notice; no frontend source was changed in this milestone.

The model name is unchanged. Output defaults to 1200 tokens, configurable through
BUILDFLOW_MAX_OUTPUT_TOKENS. Truncated responses fail cleanly rather than displaying
partial answers. Orchestration supports three bounded rounds of up to four tools.
Live model availability and answer quality require a separate operator-approved
smoke test. No authentication, persistent RFI database, or external workflow writes are added.

## Milestone 2: local document retrieval

This pipeline retrieves evidence only. It never imports the Claude service,
loads credential files, generates answers, or calls a paid API. The eight documents
in `sample_docs/` explicitly label all policies, people, timelines, and details as
fictional samples. Project meeting notes are historical snapshots, not live status.

### Setup and manual demo (PowerShell, repository root)

```powershell
.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements-rag.txt
# Explicit one-time public model download; later commands use local files only.
.venv\Scripts\python.exe -m scripts.retrieve download-models
.venv\Scripts\python.exe -m scripts.retrieve ingest
.venv\Scripts\python.exe -m scripts.retrieve query "Who receives the Cedar escalation packet?"
.venv\Scripts\python.exe -m scripts.retrieve query "What clearance does BX-17 require?"
.venv\Scripts\python.exe -m scripts.retrieve query "What is the approved project budget in dollars?"
# Interactive questions keep models warm; blank input exits.
.venv\Scripts\python.exe -m scripts.retrieve query --project 101
```

Use `--json` on `query` to inspect all candidate scores, aliases, and stage timings.
Use `--no-rerank` only to inspect the weaker hybrid baseline: it can accept a
related passage that does not answer the question. The benchmark records those errors.
No API server is needed for the CLI. Models and SQLite files live under ignored
`.cache/`; setup never uses a Hugging Face account token. Public model downloads
are resumable/cached and are never triggered by ingestion, queries, or tests.

Verified environment: Windows 11 AMD64, Python 3.13.3, SQLite 3.49.1 with FTS5,
PyTorch 2.8.0 CPU, Sentence Transformers 5.1.2, Transformers 4.57.1, NumPy 2.2.6.
`requirements-rag.txt` pins the resolved retrieval dependencies without changing
the existing backend dependencies. On this Windows machine Hugging Face stores
copies rather than symlinks; it works, but can consume additional disk space.

### Ingestion and source identity

Markdown/TXT sources use a small explicit metadata header: `Document-ID`, `Title`,
`Project-ID` (positive integer or `all`), positive integer `Revision`, and
`Sample-Data: true`. UTF-8/BOM, line endings, Unicode NFC, and horizontal whitespace
are normalized. Markdown headings define sections; nested headings retain their
parent section names. Long sections split into at most 120 whitespace words with
20-word overlap. All current sample chunks fit the embedding model's token window,
which is verified with its actual tokenizer. Arbitrary long/unusual words can
still exceed the tokenizer limit; use token-aware splitting before larger imports.

Readable IDs follow `DOCUMENT-ID:rREVISION:section-slug:part`. They remain stable
across reruns and unrelated section edits. SQLite retains document hashes, titles,
project IDs, revisions, sample flags, relative source paths, chunks, and float32
embeddings. The embedding cache key hashes the exact title/section/passage input
and pinned embedding-model revision. Unchanged text reuses actual stored vectors.

`ingest` validates the complete source snapshot and computes missing vectors before
publishing replacement documents, chunks, and FTS indexes in one SQLite transaction.
`ingest --rebuild` regenerates the index structures while retaining reusable cached
embeddings. Removed files disappear from the next successful snapshot. Empty or
invalid directories fail without wiping an existing index. Same-ID/same-revision
duplicates, scope changes between revisions, invalid metadata, unreadable files,
and source links outside the document root fail clearly. Embedding failures also
preserve the previous index. Old cached vectors are retained; cache pruning is not
implemented for this small corpus.

### Retrieval and relevance policy

1. Validate the question and check the project against the existing sample registry.
   Project 999 receives `insufficient_evidence/project_not_found`, even for shared policies.
2. Select shared plus matching-project chunks, using the highest numeric revision
   per document ID. Lower revisions stay in SQLite but do not enter retrieval while
   the newer revision is present. The input folder is authoritative: removing a
   newer revision can make an older one the highest available. A production document
   lifecycle needs explicit retirement/approval metadata before importing real archives.
3. Embed the question with `sentence-transformers/all-MiniLM-L6-v2`, pinned to
   `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Its compact 384-dimensional normalized
   embeddings allow exact cosine search on this small corpus without a vector server.
4. Retrieve up to 20 dense and 20 keyword candidates. Each project has a separate
   SQLite FTS5 index containing its current eligible sources. Thus both candidate
   filtering and BM25 corpus statistics respect the project boundary. Questions
   become quoted OR terms, not executable SQL or arbitrary FTS expressions.
5. Merge using reciprocal rank fusion: `sum(1 / (60 + rank))`. Preserve original
   cosine/BM25 scores and ranks. Exact duplicate excerpts collapse to one result
   with the other chunk IDs retained as aliases. Near-duplicates remain distinct.
6. Rerank up to 20 fused candidates with the small CPU CrossEncoder
   `cross-encoder/ms-marco-MiniLM-L6-v2`, revision
   `233902d25c440f23af6f7d6e94d2946bac0bee0a`. Preserve its raw logit; it is not a
   probability or a calibrated confidence score.
7. Return up to five excerpts with cosine at least 0.40 and reranker logit at least
   1.0. Otherwise return `insufficient_evidence`. Obvious unrelated requests are
   declined before inference. Empty indexes and missing/incompatible models/indexes
   have explicit results or actionable setup errors, never fabricated vectors or
   silent fallback to keyword-only retrieval.

The relevance thresholds are conservative demonstration heuristics, not a guarantee
of answerability or complete grounding. A retrieved passage may still be only
partially relevant. All source passages are labeled `untrusted_source`: this stage
returns text as data and executes none of its instructions. Milestone 3 must enforce
claim grounding and source boundaries when generating answers.

Revision 2 supersedes the deliberately conflicting archived escalation procedure.
Equal-revision conflicts fail ingestion. Contradictions between different document
IDs are not automatically adjudicated; human source curation and later answer-stage
conflict handling remain necessary. Project filtering is not authentication or
document-level authorization. Rebuild the index after changing the project registry.

### Repeatable evaluation

```powershell
.venv\Scripts\python.exe -m scripts.retrieve eval --output evals/retrieval_report.json
.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
npm run lint
```

`evals/retrieval_cases.json` contains manually labeled questions and expected chunk
IDs: 17 answerable and nine missing-information/unrelated/missing-project cases.
`evals/retrieval_report.json` records per-case rankings, accepted evidence, baseline
versus reranked Recall@5, Hit@1, MRR@5, evidence hit rate, negative abstention rate,
and cold/warm timings. Ranking metrics use pre-threshold candidates; evidence hit
checks the final relevance gate. Exact duplicate source aliases count as retrieved
identities. Labels are not exhaustive relevance judgments of every candidate.

The first query includes imports and model loading from local disk; warm median and
p95 use subsequent answerable queries in the same process. No reboot/disk-cache
flush is performed. Reranking improves first place for one labeled question in the
recorded run and rejects a false-positive completion-date source accepted by the
baseline. Recall@5 is unchanged. These small, self-authored synthetic results are
not evidence of production accuracy or broad construction-domain quality.

Tests use real local embeddings/reranking plus temporary indexes and isolated RFI
fixtures. External socket connections are blocked; Windows asyncio's internal
loopback sockets are permitted. Missing dependencies or models fail the tests with
setup guidance rather than silently skipping real inference. Only the Windows
source-symlink test may skip when symlink creation privileges are unavailable.
The pre-existing Starlette/AnyIO deprecation warning remains.
