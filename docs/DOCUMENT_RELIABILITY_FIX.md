# Document-answer reliability fix

## Findings

Two deterministic reproductions explain how an available document can still lead
to a false insufficient-evidence response:

1. Claude can rewrite the retrieval question so that essential procedure wording
   disappears. With the real Project 303 index, the exact reported question
   retrieves `BF-COORD-303:r1:project-specific-release-procedure:1` (dense score
   approximately 0.443; reranker approximately 5.09). The plausible rewrite
   `release packet recipient timeline` returns no eligible evidence (the same
   document scores approximately 0.331 and -0.422). Thresholds remain 0.40 and
   1.0. A mocked tool call with that rewrite reproduced the incorrect abstention.
2. Claude can finish without searching at all. Previously a recognized document
   question then returned the generic fallback without inspecting the index.
   A mocked initial abstention reproduced this even with real evidence available.

The local historical Project 303 failures recorded one provider call, one tool
call, and retrieval time; successful requests recorded two provider calls and
one tool call. Those failures occurred after search and before answer generation.
That argues against tool omission or citation rejection for those recorded
failures. Old events did not record the query, retrieval reason, or error category,
so query rewriting versus a retrieval exception cannot be established for the
specific browser attempt. Refresh is not established as causal.

The exact question retrieves identical Project 303 evidence cold and warm and
after switching projects. Initialization is synchronous under the existing lock;
the index is explicitly ingested, not rebuilt lazily by a browser refresh.
No cold/warm race was reproduced.

## Lifecycle and fallback paths

`POST /ai/chat` validates selected context; `chat_with_buildflow` rejects context
conflicts and retains the existing deterministic structured routes/cache. Claude
selects tools for other questions. `execute_tool` validates tool arguments;
`search_documents` serializes access to the cached retriever. Retrieval reads a
transactional SQLite snapshot, filters project scope before dense/BM25 ranking,
fuses ranks, reranks, and applies unchanged thresholds. Model loading is local
and synchronous. Accepted source passages are returned as untrusted tool data.
Claude's final envelope then passes the existing citation/quotation validator.

All generic insufficient-evidence exits in `claude_service.py` are:

- `grounded_answer`: absent/unknown citations, invalid or nonmatching quotations,
  missing support, or malformed answer/support data.
- `unsupported_documents`: failed/empty retrieval, document answers without
  evidence, citations without evidence, or rejected grounded output. Successfully
  executed structured facts are preserved where available.
- Tool search without project context, a tool/project context mismatch, or
  evidence outside the permitted project/sample scope.
- Claude may itself return the same fallback text; recognized document questions
  now get the bounded omitted-search recovery before it can be accepted.

Truncated/malformed provider output and tool-loop/time limits raise the existing
provider-response error (HTTP 502), rather than being presented as missing evidence.
Provider connection, timeout, and status failures retain existing HTTP mappings.

## Changes

- `backend/claude_service.py`: validated document searches for a recognized
  single-project question use the original user question, rather than a model
  paraphrase. Tool arguments are still validated before this substitution.
- If Claude ends without searching, one server-created search tool call runs
  through the same execution, scope, and evidence checks. Only accepted evidence
  triggers a follow-up generation. The unsupported initial output is discarded.
  This consumes the existing loop/time budget; it is not an unbounded retry.
- Invalid citations after retrieval still abstain; there is no paid citation retry.
- Sanitized request events add `document_search` (not executed, model requested,
  or recovered omission), `document_query` (original request or model query),
  `evidence_count`, `document_failure`, and `tool_failure` where relevant.
  Failure categories distinguish missing evidence/index content, retrieval/model
  unavailability, context/scope mismatch, tool errors, and citation rejection.
  Existing outcomes distinguish provider failures. No prompt, query text,
  document excerpt, response, exception details, or credentials are logged.
- `tests/test_document_reliability.py`: real cold/warm retrieval, repetition,
  project switching, identical 202/303 wording, model query loss, omitted search,
  citation rejection, missing documents, scope isolation, initialization/tool
  failures, malformed/truncated output, mixed structured/RAG, and cache bypass.
- `tests/test_grounded_chat.py`: existing unsupported-prose test now covers the
  bounded recovery and confirms unsupported prose remains rejected.

No API contract, frontend, backend route, tool schema, relevance threshold,
model, project filter, source/quotation validator, or answer-cache policy changed.
Insufficient-evidence responses are not cached. No credentials were read or changed
and no paid Claude calls were made for this investigation.

## Verification

- Full backend suite: 220 passed, one skipped (Windows symlink privilege), one
  existing Starlette/AnyIO deprecation warning.
- Retrieval evaluations: 21 positive / 9 negative cases. Default reranked pipeline:
  recall@5, hit@1, MRR@5, evidence hit, and negative abstention all 1.0.
  Unreranked baseline negative abstention remains 0.8889; it is not the default.
- Frontend production build and ESLint: passed.
- Playwright: attempted the existing multi-project browser test; navigation to
  localhost:5173 failed. Later tool calls, including navigation to a separately
  started local Vite server, were cancelled. Browser tests did not complete.
- Evaluation output: `.cache/reliability-eval.json` (local generated artifact).

## Verify in the application

1. Restart the backend so it loads the changed service. From the repository root:
   `.venv\Scripts\python.exe -m uvicorn backend.main:app --reload`.
   Start the frontend with `cd frontend` then `npm run dev` and open its printed URL.
   Keep the existing local model cache/index; this fix needs no threshold or .env changes.
2. Select Project 303 and submit:
   "According to the project-specific release procedure, who receives the packet
   and when? Cite your source."
3. Verify Owen Reed, six working hours, Harbor release packet, and the synthetic
   Project 303 source citation. Repeat without refreshing.
4. Switch to 101, then 202, then 303. Repeat that wording in 202 and 303:
   202 must use its own procedure/Elena Vale; 303 must use Owen Reed. The same
   release question genuinely lacks matching evidence in 101 and should abstain.
5. Ask the question plus "Also list critical RFIs." Verify the structured project
   result and project-appropriate procedure citation. Try a nonexistent procedure
   and verify abstention. Existing deterministic count/critical prompts should
   continue bypassing Claude and using project-isolated caching.
6. Inspect the local sanitized operations events if a request fails. Distinguish
   `document_failure` from provider HTTP/outcome errors; a successful recovery is
   marked `document_search=recovered_omission`. Do not infer causality from refresh.

Remaining limits: document-intent detection is the existing keyword heuristic;
ambiguous/multiple-project requests do not get single-project recovery. Retrieval
thresholds can legitimately reject other wording. Invalid citations still fail
closed, provider errors still surface, and bounded loop/time limits still apply.
The synthetic evaluation is small and does not establish production accuracy.
