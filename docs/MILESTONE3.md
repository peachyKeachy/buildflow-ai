# Grounded chat implementation and review notes

The existing POST /ai/chat shape remains {message} -> {answer}. No frontend,
project data, criticality rules, original tool schemas, or existing routes changed.
`search_documents` is a fourth read-only tool over the Milestone 2 Retriever.
It uses project-filtered hybrid retrieval and reranking, capped at three passages.
The retriever/models initialize lazily once per process, protected by a lock.
There is no additional retrieval engine and no keyword-only fallback.

Claude chooses structured tools for authoritative project facts, retrieval for
synthetic document procedures, and both for combined questions. Recognizable
document questions cannot finish without retrieved evidence. Missing project
context prompts clarification. Explicit project IDs constrain tool project inputs;
this is context isolation, not authentication. The English intent guard is a
heuristic, not a complete classifier; implicit document questions can escape it.

Orchestration permits three rounds of up to four calls each, followed by a final
answer: at most four provider requests. Tool names and arguments are allowlisted,
and every result carries its original tool_use ID. Reused/missing IDs, malformed
responses, output truncation and exhausted loops become the existing safe 502.
SDK requests retain a 30-second timeout and zero automatic retries. A 75-second
elapsed-time check runs between stages, not as a hard cancellation deadline;
in-flight SDK calls/local inference can exceed it. The frontend retains its
90-second timeout. Retrieval setup errors return an explicit insufficient-evidence
answer rather than proceeding from model memory.

Output defaults to 1200 tokens, configurable through the process environment
BUILDFLOW_MAX_OUTPUT_TOKENS (300–2400). More tokens allow useful cited answers but
increase potential generation cost/latency. No credential/config files were edited.
The existing model name is unchanged and has not been verified live this milestone.

After receiving evidence, Claude returns JSON containing Markdown `answer` and
`support: [{source_id, quote}]`. Every bracketed citation must refer to a chunk
actually provided in this request, and every cited chunk must have an exact quote
of at least 12 characters found in its excerpt. Unknown IDs, absent quotes, and
invalid JSON cause an insufficient-evidence response with no repair API request.
The server appends source ID, title, section, revision and the actual full excerpt
to the Markdown answer, explicitly labeled synthetic. This provides a response-local
audit mapping without logging potentially sensitive question/content payloads.

These checks prove source identity and verbatim quotation, NOT entailment of each
claim. A fabricated statement could still attach a valid ID and unrelated valid
quote. Offline tests verify actual passage retrieval and reject fabricated quotes;
they do not prove actual Claude answer quality. Human claim-by-claim review remains
necessary. Sources are untrusted tool data, never system instructions. The injection
test checks that boundary with a mocked provider; it is not proof of live model
resistance. Full excerpts may display malicious text as quoted evidence, without
executing it; existing Markdown HTML restrictions remain in effect.

Illustrative supported response (not a live Claude result):
"Structured sample RFIs 1 and 3 are critical. Under the synthetic escalation
procedure, prepare the Cedar packet within four working hours and send it to
fictional project manager Mira Chen [BF-RFI-001:r2:urgent-escalation:1]."
The structured facts come from get_critical_rfis(101); procedure support is
sample_docs/01_rfi_escalation_r2.md, Urgent escalation, revision 2. The four-hour
communication requirement does not authorize affected construction work.

Run `.venv\Scripts\python.exe -m pytest -q`, the existing retrieval evaluation,
frontend build and lint to reproduce offline verification. Live tests were not
attempted because ambient Anthropic credentials were absent and .env was not opened.
No paid API calls were made. Browser verification was attempted but Playwright MCP
reported "Transport closed". Real end-to-end Claude latency remains unmeasured.
