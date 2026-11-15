# BuildFlow AI — Visual Design Brief

**Target:** A polished, credible construction operations copilot for a live portfolio/demo. Inspiration: DeAngelis Diamond's website, its public **blue** logo and professional construction-management positioning. BuildFlow is independently developed, not an authorized official app.

## Brand-aware design direction

Design vocabulary: accurate, organized, confident, collaborative, architectural, enterprise-ready, readable. Choose a **predominantly light interface** with navy navigation and blue accents. Do not copy entire DeAngelis Diamond website layouts or claim its trademark; no unauthorized logo.

### Proposed palette (not verified official hex codes)

| Role | Proposed token | Hex |
|---|---|---|
| Deep navy navigation / headlines | `--navy` | `#102C4A` |
| Main action and link blue | `--blue` | `#17679F` |
| Pale blue highlight | `--blue-tint` | `#EAF3FA` |
| Page canvas | `--canvas` | `#F5F8FB` |
| Card surface | `--surface` | `#FFFFFF` |
| Primary body text | `--ink` | `#1D2939` |
| Border / rules | `--border` | `#DCE4EC` |
| Warning (critical, accessible) | `--critical` | `#B54708` |

Use accessible foreground/background pairs and contrast-check final design. Keep critical/orange limited to actual issue states and red for destructive/error states, not general branding. The palette is blue-inspired, **not a claim of official DD standards**.

## Experience concept

Desktop: narrow dark-blue app sidebar or rail for project context and quick actions; substantial bright main workspace with a clean top bar, page title, supporting context, sample-project identifier, visible AI question input, and structured results. Mobile: collapsible navigation/stacked responsive layout; no horizontal page scroll.

The main interaction should be obvious in the first viewport: 'Ask BuildFlow about your project' with a useful placeholder, a large enough accessible text input, and a clear Send action. Offer three contextual prompts (summary / all RFIs / critical RFIs) as clickable examples that populate or submit the real question. Style buttons and cards consistently.

## Desired components

- App header: BuildFlow AI wordmark as **text**, 'Construction Operations Copilot' subtitle, subtle 'Demo · Sample data' indicator.
- Project context: 'Naples Medical Center' with sample project ID 101; if sourced from backend, indicate actual API response. Do not assert current project updates or Procore sync.
- Query panel: clean input, responsive send button, disabled/loading states, keyboard accessibility.
- Answer display: a generous white content surface with typographic hierarchy, proper Markdown emphasis, bullet lists, and **formatted tables** (`react-markdown` + `remark-gfm` may be appropriate).
- Useful quick questions: summary / all RFIs / critical RFIs, wired to the same existing `/ai/chat` endpoint.
- User-facing friendly error and informative missing-project response; no stale answer after failure.
- Optional summary KPI cards should use **real sample project data from existing API**, not hardcoded marketing stats. Distinguish 'critical' and 'blocking'.
- Lucide or comparable SVG icons for functional navigation; avoid emojis as UI decoration.

## Do not build

- Unrelated multi-page marketing website or false DeAngelis Diamond affiliation.
- Fake live feeds, charts, project alerts, Procore integrations, user management, persistence, auth, or admin features.
- A full migration to Next.js or backend changes just to improve UI.
- Markdown-to-HTML rendering without appropriate sanitization/safety.
- Dark-on-black neon AI dashboard, purple/pink gradients, excessive animation, cluttered identical-card stacks.

## Required acceptance tests

1. `npm run build` works.
2. Three valid queries to project 101 produce the known answers; project 999 does not fabricate data.
3. Markdown bold, lists, and table pipes render as styled content, not raw characters.
4. Send is disabled for empty text and while waiting. Loading indicator always ends.
5. API unreachable shows visible error and does not leave stale previous answer.
6. Looks intentional at roughly 375px, 768px, 1280px+; tables remain readable on mobile.
7. Visible keyboard focus, labeled input, good contrast, no unwanted horizontal viewport overflow.
8. No accidental API key exposure, unauthorized logos, or claims of production integration.

## Skill strategy

Primary design intelligence: nextlevelbuilder/ui-ux-pro-max-skill. Secondary QA/audit: Vercel web-design-guidelines. Optional React implementation advice: Vercel React Best Practices. Optional components: shadcn/ui **only** if beneficial to existing Vite app (do not introduce it just for novelty). A real browser-based visual review is more important than accumulating many skills.
