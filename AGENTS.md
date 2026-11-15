# Codex instructions — BuildFlow AI

BuildFlow AI is a **local sample-data portfolio prototype** for construction project RFI workflows, developed with React/TypeScript/Vite and Python/FastAPI/Anthropic. It is not an official DeAngelis Diamond product.

Read `BUILDFLOW_CONTEXT.md` and `DESIGN_BRIEF.md` before undertaking the UI redesign. Treat **the repository** as the source of truth if its code differs from those handoff files.

## Priorities

- Redesign frontend presentation with UI UX Pro Max guidance; preserve all backend routes, Claude tool schemas, and `POST /ai/chat` request/response shape.
- Brand direction: blue, navy, white, slate inspired by DeAngelis Diamond's public branding, not an official reproduction or endorsement. No unauthorized company logo.
- Preserve loading/error/validation functionality, existing tool outcomes, and sample-data transparency.
- Use safe Markdown + GFM rendering for Claude responses (including tables), no untrusted raw HTML.
- Responsive mobile + desktop, accessible controls and contrast, deliberate states for empty/error/loading/success.
- Do not introduce fabricated live data, pretend Procore/MCP is connected, or change from Vite/React to Next.js without user approval.
- Do not expose `.env`, API keys, or secrets. Never commit `.env` or `.venv`.
- Prefer small changes on a feature branch, explain architecture decisions to the user, run a production build and browser smoke tests before presenting success.

## Suggested validation

Ask: summary of project 101 (3 total/2 critical/2 blocking); all RFIs for project 101 (3); critical RFIs for project 101 (IDs 1,3); summary of project 999 (not found). Also verify blank input, duplicate submits, network failure, and markdown tables.
