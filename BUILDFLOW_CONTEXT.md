# BuildFlow AI — Codex Project Handoff

**Prepared:** November 10, 2026  
**Purpose:** Preserve reliable context from the user's BuildFlow AI learning/build sessions so Codex can work against the *actual local repository* without reconstructing the product from guesswork.  
**Priority:** The repository is the source of truth for code and exact dependencies. This document describes the last working state discussed on September 16, 2026; inspect current files before editing.

## Product and objective

BuildFlow AI is an independently conceived construction-operations copilot, built to demonstrate practical AI-engineering skills relevant to DeAngelis Diamond / Future Bylt's interest in internal applications and reducing reliance on third-party SaaS tools. It is a portfolio prototype, **not** an official DeAngelis Diamond product or a deployed production system. Design branding should evoke the DeAngelis Diamond site without falsely claiming affiliation.

Primary current use cases: retrieve a construction project summary, list all its RFIs, identify critical RFIs, and gracefully handle nonexistent projects. A well-crafted UI and an honest working demo are the immediate goals. Procore, MCP, deployment, and additional real systems are future enhancements unless repository inspection proves otherwise.

## User and collaboration preferences

- User is learning by building and must be able to explain decisions and code in interviews. Give compact explanations of what changed and why; preserve their understanding instead of silently replacing everything with a black box.
- Prefer small, reversible changes, a Git branch, working code, and validation in a browser.
- Do not claim features not implemented or data connections not established.
- Keep Anthropic API keys private; never print `.env`, add `.env` to Git, or place API keys in frontend code.
- Make UI beautiful **and** functional; verify mobile layout, accessibility, loading, errors, successful response, missing project, and API unreachable.

## Learning history and technical concepts covered

The user pursued a hands-on AI-engineering bootcamp, proceeding in small increments. They want to understand and explain every feature rather than just copy finished code. Important educational milestones:

- **Day 1:** HTTP requests/responses, endpoints, methods, JSON, query/path parameters, status codes, Python `requests`, virtual environments and `pip`.
- **Day 2:** Python types, operators, conditionals, input validation, loops, exception handling. Built a simple RFI priority classifier.
- **Day 3:** Lists, dictionaries, loops, nested JSON, filtering/counting RFIs, API response handling.
- **Day 4:** Functions (`def`, parameters, return values, scope, type hints), separating business rules into `is_critical_rfi`, `get_critical_rfis`, `get_blocking_rfis`, `get_project_summary`.
- **Day 5:** FastAPI endpoints, Pydantic models, Uvicorn, Swagger, GET/POST, simple project in-memory data. `RFIInput` carries `title`, `days_open`, `is_blocking`.
- **Day 6:** Anthropic SDK and `.env`, tool definition versus execution, `tool_use` / `tool_result`, `tool_use_id`, `response.stop_reason`, Claude -> Python -> Claude orchestration, modularized `project_service.py`, `claude_service.py`, and `POST /ai/chat`.
- **Day 7 (last discussed 80–85% completed):** React/JSX, props vs state, `useState`, events, async/await/fetch, JSON conversion, CORS, `try/catch/finally`, failure/success loading handling, empty input and disabled submit, three-tool selection, missing project handling. Pending Procore, MCP, UI polishing, GitHub/README updates.

Critical mental models reinforced: **props are passed in; state is owned/stored in a component**; FastAPI is the API framework, Uvicorn runs the server; Claude *requests* a tool and Python *executes* the tool; `tool_result` is sent back for a final grounded answer; `finally` resets loading whether request succeeds or fails.

## Broader career/project context relevant to the design

The BuildFlow idea comes from the user's independent research into construction operations workflows and the target firm's innovation needs. The user wanted to show an AI Engineer interview panel that they can identify a real business pain point, build a practical internal tool, and integrate enterprise systems over time. The user has software-engineering training and practical IT-support experience with Microsoft 365/Entra, Teams administration, SharePoint, and Dynamics 365. Existing project content should emphasize internal workflow efficiency and reliable, grounded outputs, not inflated claims of deployed integrations.

## Last known stack and directory

Root on Windows was `C:\Users\mjbec\Desktop\Programming\BuildFlow-AI`.

```text
BuildFlow-AI/
  backend/
    main.py                 # FastAPI routes and CORS
    claude_service.py       # Anthropic client and tool orchestration
    project_service.py      # local project dataset and business rules
  frontend/
    src/
      App.tsx               # React TypeScript UI
      App.css
      index.css
      main.tsx
    package.json
  .env                      # private, ignored by Git
  .env.example              # sample variables, no secrets
  .gitignore
  requirements.txt
  README.md
```

Tech: Python/FastAPI/Uvicorn/Pydantic, Anthropic Claude SDK, `python-dotenv`, React + TypeScript + Vite, CSS. Development backend: `http://127.0.0.1:8000`; frontend: `http://localhost:5173`; CORS permits the frontend origin. `POST /ai/chat` accepts `{"message":"..."}` and returns `{"answer":"..."}`. The exact current model/config must be read from the repository (earlier used `claude-sonnet-5`, `max_tokens=300`, thinking disabled).

## Existing working behavior (last verified in chat)

- `GET /health`, `/projects`, `/projects/{project_id}`, project RFIs, summary, filtering, create RFI, as supported by `backend/main.py` (verify exact paths in repo).
- `POST /ai/chat` frontend-to-backend call works with CORS.
- Claude selects from three tool schemas: `get_project_summary`, `get_project_rfis`, `get_critical_rfis`.
- Python `execute_tool` resolves tool requests to code in `backend/project_service.py`, returns JSON-serialized `tool_result` using the matching `tool_use_id`, and sends it back to Claude for a grounded final response.
- React state: `message`, `answer`, `loading`, `error`. Input trims whitespace; empty requests are prevented, the send button disables while loading or input is empty, request errors show a friendly message, and `finally` resets loading. This must not be regressed by redesign.
- Missing project (tested project 999) returns a friendly 'not found' answer, without fabricated project details.
- In screenshots, all three tool requests on project 101 worked. Raw markdown (`**bold**`, pipe tables) appeared unformatted due to rendering the answer inside a plain `<p>` tag. Fix this.

### Local sample data and business rule

Project 101: **Naples Medical Center**. Last-known RFIs:

| ID | Title | Days open | Blocking | Critical |
|----|-------|-----------|----------|----------|
| 1 | Electrical routing conflict | 12 | Yes | Yes |
| 2 | Door hardware clarification | 3 | No | No |
| 3 | Mechanical duct conflict | 8 | Yes | Yes |

Critical means `is_blocking == True` **and** `days_open > 7`. Project summary should report 3 total, 2 blocking, 2 critical RFIs. Another sample project, 202, also existed; inspect the repo for its actual content.

### Tool-oriented workflow

```text
User asks in React
  -> POST /ai/chat (JSON) over HTTP
  -> FastAPI validates ChatInput
  -> chat_with_buildflow(message)
  -> Claude API receives message + tool definitions
  -> Claude may emit tool_use
  -> Python executes project_service business logic
  -> matching tool_result sent to Claude
  -> Claude generates human-readable answer
  -> FastAPI sends {answer: string}
  -> React displays answer, handles errors and loading
```

Note: The last-known orchestration code handled the first requested tool and one follow-up response. Do not claim it already supports arbitrary multi-step/multi-tool agent loops, persistent chat history, or autonomous agents.

## Visual direction (also see DESIGN_BRIEF.md)

- For a construction operations dashboard, use professional **blue, white, navy, slate** inspired by DeAngelis Diamond's public blue logo and clean website. Suggested hexes are *design proposals*, **not verified official brand hex codes**.
- Strong top bar, restrained left project navigation, main answer/results area, clear project context, three tool-related sample query chips/buttons, tasteful count cards, critical/blocking alerts. Avoid gimmicks, neon gradients, emojis as icons, fake metrics, fabricated charts, and claiming real-time Procore sync.
- Render Markdown correctly with safe React Markdown + GFM support for tables and lists, and style tables for narrow screens. Do not enable raw HTML from untrusted model output.
- Functional demos must use actual existing React/FastAPI APIs. If visual project cards are based on backend data, fetch real sample endpoints and label it 'Sample project data'. Do not invent a live connection.
- Accessible inputs/buttons, keyboard focus, `aria-live` for responses if appropriate, responsive breakpoints, sensible loading/empty/error states.

## Demo flows to preserve

1. `Give me a summary of project 101.` -> Naples Medical Center, 3 total RFIs, 2 blocking, 2 critical.
2. `Show me all RFIs for project 101.` -> lists the 3 above.
3. `Which RFIs are critical for project 101?` -> electrical + mechanical (IDs 1,3).
4. `Give me a summary of project 999.` -> clean not-found message.
5. Empty input -> no request/disabled Send.
6. Backend offline -> clear friendly error and loading terminates.

## Known limitations and work remaining

- Local sample/in-memory project data, not a database or live construction platform.
- No verified live Procore integration, MCP server, Azure/M365 connector, production hosting, or CI/CD completed in the last discussed build.
- Raw Markdown was not rendered and overall UI was a centered simple text layout.
- Chat view previously displayed only one response instead of a message transcript. A visually convincing conversation history can be implemented client-side, but don't claim server-side persistence.
- Existing tool orchestration may assume first text block; avoid incidental backend refactors during a UI-only task.
- Investigate errors only if they appear in the current repository; historical screenshots had a transient indentation error that was already fixed with later successful HTTP 200 requests.

## Useful commands (Windows PowerShell, from repo root)

```powershell
# Activate Python environment and run backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload

# In another terminal
cd frontend
npm install          # only if dependencies not already installed
npm run dev
npm run build

# Before editing
cd ..
git status
```

Do not place the `.env` file contents into any docs or issue, prompt, screenshot, or commit. If API access fails, diagnose safely with redacted error details.

## Codex implementation instructions

1. Inspect `git status`, frontend package/dependencies, existing styles and components, FastAPI CORS/API contract, and the latest repo commit before editing.
2. Create a new branch `feat/buildflow-ui-redesign` if appropriate. Preserve all existing backend functionality. Work primarily in `frontend/`.
3. Install/read `ui-ux-pro-max` if trusted and available, then use its design-system planning guidance to implement `DESIGN_BRIEF.md`.
4. Add/keep a lean component architecture; make it look like a credible construction operations tool, not a generic ChatGPT clone. Use restrained animations and responsive design.
5. Render GFM Markdown safely. If introducing shadcn/ui, Tailwind, or other packages, justify and verify compatibility with the existing Vite project. No need to migrate to Next.js.
6. Run `npm run build`, validate in browser, then smoke-test existing backend prompts and error cases if credentials and local environment permit.
7. Report actual files changed, install commands, tests run, and known limitations. Don't mark an untested feature as working.
