# Milestone 3B: local routing, caching, and operational measurements

The public chat request/response shapes, selected project context, dashboard,
document retrieval, source validation, and criticality business rule are preserved.
No dependencies, public metrics endpoints, authentication, or external integrations
were added. This does not investigate the intermittent 502 issue.

## Conservative router

Only these whole questions match (case and whitespace insensitive), optionally
followed by `for project N` and a single question mark or period:

- How many RFIs are open?
- Which RFIs are critical?
- How many RFIs are blocking?
- Give me the project RFI counts.

Scope, project existence, and explicit/selected context conflict checks run first.
The selected project or an explicit message project is required. No default project
is invented. Additional clauses, explanations, policy questions, and mixed intents
fall through to the existing Claude/tool workflow. This is not a general classifier.
Deterministic answers call the existing project functions against a copied snapshot.
The sample register has no closed-status field: the open-count answer explicitly
describes the current register rather than inventing a lifecycle status.

## Deterministic answer cache only

SQLite under `.cache/operations.sqlite3` stores the cache and sanitized request
events in separate tables. Cache identity hashes the whitespace/case-normalized
question, project ID, complete structured snapshot, exact route, business-source
fingerprint, and explicit router/answer validation version. TTL and capacity also
affect the identity. Punctuation and additional words are not discarded. Formatter
or validation changes require bumping `operations.VERSION`. Business-source/data
changes invalidate automatically. Defaults: 300 seconds and 256 entries.

`BUILDFLOW_ANSWER_TTL_SECONDS` configures 0–86400 seconds; `BUILDFLOW_ANSWER_CACHE_SIZE`
configures 0–5000 entries. Zero disables reuse. Invalid values use defaults.
Expired entries cannot hit; expired/oldest entries are removed on insertion.
Separate connections and short `BEGIN IMMEDIATE` transactions serialize concurrent
cache updates, with a ten-second SQLite busy timeout. Capacity reduction is enforced
by subsequent insertion. Storage failures bypass caching and do not change answers.

Only successful deterministic rendering is stored. Claude answers, document answers,
errors, partial/insufficient answers, citations, refusals, and conflicts are never
cached. Model/prompt/document versions are explicitly not applicable to these keys:
those inputs do not affect deterministic answers. Document caching remains disabled;
every document question uses the current retrieval index and server citation checks.
Tests rebuild a temporary document index and verify fresh revision 3 provenance.

This is not access-aware caching. Project IDs are context, not authorization.
Real deployment requires authentication, document/project permissions, a user or
permission-scope cache identity, storage controls, and a formal document lifecycle.
The database contains sample answer text even though metrics contain no answer text.

## Usage and estimated API cost

Each existing SDK call is measured without extra API requests or retries. Records
contain requested model ID, call latency, and actual provider usage metadata:
input/output tokens, cache-read tokens, total cache-write tokens, and available
five-minute/one-hour write breakdowns. Missing usage stays unknown; token counts
are not inferred from strings. Failed attempts are counted, with unknown usage/cost.

Set `BUILDFLOW_MODEL_PRICING_JSON` in the process environment to a mapping keyed by
the exact requested model ID. Values are USD per million tokens, using category
names `input`, `output`, `cache_read`, `cache_write`, `cache_write_5m`, and
`cache_write_1h`. `cache_write` prices unclassified writes when the TTL breakdown
is unavailable. Do not add the total-write charge again when using the breakdown.
Only positive-volume categories require a configured rate. Missing, inconsistent,
invalid, or unpriced usage yields unknown cost, not zero. Default pricing is empty;
no current price is assumed for the repository's existing model identifier.

Estimate = sum(reported category tokens × configured category USD/million) / 1e6.
This is a configurable estimate, not an invoice: billing agreements, regional/tier
adjustments and unreported charges are outside this calculation. Use the provider's
[pricing reference](https://platform.claude.com/docs/en/about-claude/pricing) and
[usage-category reference](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
to set rates appropriate to your account/model. No credential files are opened by
the report or mocked demo. No provider prompt-caching feature is enabled here;
reported prompt-cache tokens are distinct from the application's answer-cache hits.
Avoiding generation does not eliminate local compute, model, or infrastructure costs.

## Sanitized observability

POST /ai/chat middleware creates a private request ID/timestamp and measures total
latency, route, selected/resolved project IDs, cache status, tool count, retrieval
latency, reranking latency, provider calls, actual usage, and safe outcome category.
Request latency stops when the response is built, before metrics persistence and
network delivery; it is not a measured end-to-end browser round trip.
Retrieval duration includes lock wait/model loading/reranking; reranking duration
is a subset, so do not sum them. Pricing/token aggregation is local only. The logger
`buildflow.operations` emits structured JSON when INFO logging is configured; the
SQLite report works regardless of logger configuration. Retention is 10,000 events.

No raw prompt, tool/document content, provider exception text, full model response,
credential, client IP, or user ID enters these records. No diagnostic endpoint or
request-ID response header was added. The report summarizes known priced spend and
unpriced calls separately. Missing token fields contribute nothing to the sum of
reported tokens; calls with missing input/output usage are separately counted.
Reported zero new generation calls is an observed count; hypothetical calls avoided
are explicitly labeled against a simulated two-call baseline.

## Commands and live demonstration

From the repository root (PowerShell):

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m scripts.operations_report demo --output .cache/operations-demo.json
.venv\Scripts\python.exe -m scripts.operations_report report
.venv\Scripts\python.exe -m scripts.retrieve eval --output .cache/milestone3b-retrieval.json
cd frontend
npm run build
npm run lint
```

The demo uses an isolated temporary database, mocked SDK usage/prices, and 25 ms
simulated latency per provider call. Ten requests with the router disabled are
compared with ten normal requests. Expected: 20 mocked calls before; zero after;
one deterministic miss and nine hits after. Local elapsed times are measured, but
the before latency and all estimated cost reductions are simulated, never actual
provider billing savings. Cache hits avoid repeated local rendering only: the
deterministic route already avoids Claude on the first request.

Restart FastAPI and the existing Vite app using the README commands. Select project
101 and ask `Which RFIs are critical?`, then repeat with different whitespace/case.
Run the report to see deterministic miss/hit and zero generation calls. Try the
other three exact questions above. Ask `Which RFIs are critical and what escalation
procedure applies?` to see the Claude route (normal configured credentials needed).
Try an unrelated question or conflicting explicit project: neither is cached.
Do not assume project 202 exists; use another available project to demonstrate
isolation, or use the automated synthetic fixture. Metrics measure only new
requests since this implementation, not historical calls or billing.

Mock-specific regression tests now use more complex questions where necessary to
keep exercising Claude parsing, malformed outputs, and citation validation rather
than being intercepted by the intentionally new deterministic route.
