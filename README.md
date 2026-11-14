# BuildFlow AI

Local construction RFI portfolio prototype using React/Vite, FastAPI, and Claude.
All project data is synthetic sample data. This is not an official DeAngelis
Diamond or Future Bylt application. No live Procore connection or RAG is present.

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

The model and 300-token output limit are unchanged. Truncated responses now fail
cleanly rather than displaying partial answers. The existing single-tool round
trip remains; arbitrary multi-step/parallel-tool orchestration is not implemented.
Live model availability and answer quality require a separate operator-approved
smoke test. No authentication, persistence, or external workflow writes are added.
