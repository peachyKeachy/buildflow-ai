import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowDown,
  ArrowUpRight,
  Building2,
  Check,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  FileText,
  LayoutDashboard,
  LoaderCircle,
  MessageSquareText,
  PanelLeftClose,
  Send,
  ShieldCheck,
  TriangleAlert,
  X,
} from "lucide-react";
import "./App.css";

const API = "http://127.0.0.1:8000";
type RFI = {
  id: number;
  title: string;
  days_open: number;
  is_blocking: boolean;
};
type Project = { id: number; name: string; status: string; rfis: RFI[] };
type Summary = {
  project_name: string;
  total_rfis: number;
  critical_rfis: number;
  blocking_rfis: number;
};
type ProjectDetails = { summary: Summary; critical: RFI[] };

function isRfi(rfi: RFI): boolean {
  return Number.isInteger(rfi?.id) && typeof rfi?.title === "string" &&
    Number.isInteger(rfi?.days_open) && rfi.days_open >= 0 &&
    typeof rfi?.is_blocking === "boolean";
}

async function getData<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(15000)]),
  });
  if (!response.ok) throw new Error("Could not load project data");
  return response.json();
}

function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [details, setDetails] = useState<ProjectDetails | null>(null);
  const [dataLoading, setDataLoading] = useState(true);
  const [dataError, setDataError] = useState("");
  const [reload, setReload] = useState(0);
  const [criticalOnly, setCriticalOnly] = useState(false);
  const [message, setMessage] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeSection, setActiveSection] = useState(
    window.location.hash || "#overview",
  );
  const [navOpen, setNavOpen] = useState(false);
  const requestPending = useRef(false);
  const questionInput = useRef<HTMLInputElement>(null);
  const navigation = useRef<HTMLElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  const project = projects.find((item) => item.id === projectId);

  useEffect(() => {
    const controller = new AbortController();
    getData<Project[]>("/projects", controller.signal)
      .then((data) => {
        if (
          !Array.isArray(data) ||
          !data.every(
            (item) =>
              Number.isInteger(item?.id) &&
              typeof item?.name === "string" &&
              typeof item?.status === "string" &&
              Array.isArray(item?.rfis) && item.rfis.every(isRfi),
          )
        )
          throw new Error("Invalid project data");
        setProjects(data);
        setProjectId((current) =>
          data.some((item) => item.id === current)
            ? current
            : (data[0]?.id ?? null),
        );
        if (!data.length) setDataLoading(false);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setDataError(
            "Project data is unavailable. Check that the local FastAPI server is running, then retry.",
          );
          setDataLoading(false);
        }
      });
    return () => controller.abort();
  }, [reload]);

  useEffect(() => {
    if (projectId === null) return;
    const controller = new AbortController();
    Promise.all([
      getData<Summary>(`/projects/${projectId}/summary`, controller.signal),
      getData<RFI[]>(`/projects/${projectId}/rfis/critical`, controller.signal),
    ])
      .then(([summary, critical]) => {
        if (
          ![
            summary.total_rfis,
            summary.critical_rfis,
            summary.blocking_rfis,
          ].every((value) => Number.isInteger(value) && value >= 0) ||
          !Array.isArray(critical) || !critical.every(isRfi)
        )
          throw new Error("Invalid project summary");
        setDetails({ summary, critical });
        setDataLoading(false);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setDataError(
            "The project overview could not be loaded. Please retry.",
          );
          setDataLoading(false);
        }
      });
    return () => controller.abort();
  }, [projectId, reload]);

  useEffect(() => {
    const syncSection = () =>
      setActiveSection(window.location.hash || "#overview");
    window.addEventListener("hashchange", syncSection);
    return () => window.removeEventListener("hashchange", syncSection);
  }, []);

  useEffect(() => {
    if (navOpen)
      navigation.current?.querySelector<HTMLButtonElement>("button")?.focus();
  }, [navOpen]);

  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 768px)");
    const resetNavigation = () => setNavOpen(false);
    desktop.addEventListener("change", resetNavigation);
    return () => desktop.removeEventListener("change", resetNavigation);
  }, []);

  function closeNavigation() {
    setNavOpen(false);
    requestAnimationFrame(() => menuButton.current?.focus());
  }

  function navigate(href: string) {
    setNavOpen(false);
    requestAnimationFrame(() =>
      document.querySelector<HTMLElement>(href)?.focus({ preventScroll: true }),
    );
  }

  async function handleSend() {
    if (requestPending.current) return;
    const text = message.trim();
    if (!text) {
      setError("Please enter a project question.");
      setAnswer("");
      return;
    }
    requestPending.current = true;
    setLoading(true);
    setError("");
    setAnswer("");
    setQuestion(text);
    try {
      const response = await fetch(`${API}/ai/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
        signal: AbortSignal.timeout(90000),
      });
      if (!response.ok) throw new Error("Chat request failed");
      const data = await response.json();
      if (typeof data.answer !== "string" || !data.answer.trim())
        throw new Error("Empty answer");
      setAnswer(data.answer);
    } catch {
      setError(
        "Unable to get a response from BuildFlow. Check the local API connection and try again. Your question has been kept.",
      );
    } finally {
      requestPending.current = false;
      setLoading(false);
    }
  }

  function retryData() {
    setDataError("");
    setDataLoading(true);
    setDetails(null);
    setReload((value) => value + 1);
  }

  const prompts = [
    {
      label: "Get a project summary",
      detail: "The big picture, in a few seconds",
      icon: FileText,
      question: `Give me a summary of project ${projectId}.`,
    },
    {
      label: "Review all RFIs",
      detail: "See every request for information",
      icon: ClipboardList,
      question: `Show me all RFIs for project ${projectId}.`,
    },
    {
      label: "Identify critical RFIs",
      detail: "Find what needs your attention",
      icon: TriangleAlert,
      question: `Which RFIs are critical for project ${projectId}?`,
    },
  ];
  const criticalIds = new Set(details?.critical.map((rfi) => rfi.id));
  const visibleRFIs =
    project?.rfis.filter((rfi) => !criticalOnly || criticalIds.has(rfi.id)) ??
    [];

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to workspace
      </a>
      <aside
        ref={navigation}
        className={`sidebar ${navOpen ? "is-open" : ""}`}
        aria-label="Workspace navigation"
        role={navOpen ? "dialog" : undefined}
        aria-modal={navOpen || undefined}
        onKeyDown={(event) => {
          if (!navOpen) return;
          if (event.key === "Escape") closeNavigation();
          if (event.key === "Tab") {
            const controls =
              navigation.current?.querySelectorAll<HTMLElement>("a, button");
            const first = controls?.[0];
            const last = controls?.[controls.length - 1];
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last?.focus();
            }
            if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first?.focus();
            }
          }
        }}
      >
        <button
          className="drawer-close"
          aria-label="Close navigation"
          onClick={closeNavigation}
        >
          <X size={20} />
        </button>
        <a
          className="brand"
          href="#overview"
          onClick={() => navigate("#overview")}
        >
          <span className="brand-symbol">
            <Building2 size={25} strokeWidth={1.7} />
          </span>
          <span>
            BuildFlow<span className="brand-ai"> AI</span>
            <small>CONSTRUCTION INTELLIGENCE</small>
          </span>
        </a>
        <div className="workspace-label">
          WORKSPACE <span>01</span>
        </div>
        <nav>
          {[
            { href: "#overview", label: "Dashboard", icon: LayoutDashboard },
            {
              href: "#assistant",
              label: "AI Assistant",
              icon: MessageSquareText,
            },
            { href: "#rfis", label: "RFI Register", icon: ClipboardList },
          ].map(({ href, label, icon: Icon }) => (
            <a
              key={href}
              href={href}
              aria-current={activeSection === href ? "location" : undefined}
              className={activeSection === href ? "active" : ""}
              onClick={() => navigate(href)}
            >
              <Icon size={19} />
              <span>{label}</span>
              {href === "#assistant" && (
                <span className="nav-tag" aria-hidden="true">
                  AI
                </span>
              )}
            </a>
          ))}
        </nav>
        <div className="sidebar-project">
          <div className="workspace-label">SELECTED PROJECT</div>
          <Building2 size={21} />
          <strong>{project?.name ?? "No project selected"}</strong>
          <span>
            {project
              ? `Project ${project.id} · Sample data`
              : "Load a sample project to begin"}
          </span>
        </div>
        <div className="sidebar-bottom">
          <div className="demo-note">
            <span className="demo-dot" />
            LOCAL DEMO WORKSPACE
          </div>
          <p>
            Built for a clearer view of
            <br />
            construction operations.
          </p>
          <div className="version">
            <span>BuildFlow AI</span>
            <span>Portfolio prototype</span>
          </div>
        </div>
      </aside>
      {navOpen && <div className="nav-backdrop" onClick={closeNavigation} />}

      <div className="workspace" inert={navOpen}>
        <header className="topbar">
          <div className="topbar-location">
            <button
              ref={menuButton}
              className="mobile-toggle"
              aria-label="Open navigation"
              aria-expanded={navOpen}
              onClick={() => setNavOpen(true)}
            >
              <PanelLeftClose size={21} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>Project overview</strong>
          </div>
          <span className="sample-label">
            <span />
            Sample data <span className="desktop-only">environment</span>
          </span>
        </header>

        <main id="main" tabIndex={-1}>
          <section id="overview" tabIndex={-1} aria-labelledby="overview-title">
            <div className="page-heading">
              <div>
                <div className="eyebrow">PROJECT WORKSPACE</div>
                <h1 id="overview-title">
                  Project overview<span>.</span>
                </h1>
                <p>
                  Your project at a glance. The answers you need to keep it
                  moving.
                </p>
              </div>
              <a className="outline-button" href="#assistant">
                Ask BuildFlow <ArrowUpRight size={16} />
              </a>
            </div>

            <div className="project-context">
              <span className="project-icon">
                <Building2 size={23} />
              </span>
              <div className="project-name">
                <span className="eyebrow">
                  CURRENT PROJECT{" "}
                  {project && (
                    <span className="project-id">/ {project.id}</span>
                  )}
                </span>
                <h2>
                  {project?.name ??
                    (dataLoading
                      ? "Loading project…"
                      : "No projects available")}
                </h2>
              </div>
              {project && (
                <>
                  <span
                    className={`badge ${project.status === "active" ? "success" : "neutral"}`}
                  >
                    <span className="status-dot" />
                    {project.status}
                  </span>
                  <label className="project-select">
                    <span className="sr-only">Select project</span>
                    <select
                      value={projectId ?? ""}
                      disabled={dataLoading || loading}
                      onChange={(event) => {
                        setProjectId(Number(event.target.value));
                        setDetails(null);
                        setDataLoading(true);
                        setDataError("");
                        setCriticalOnly(false);
                        setAnswer("");
                        setQuestion("");
                        setMessage("");
                        setError("");
                      }}
                    >
                      {projects.map((item) => (
                        <option key={item.id} value={item.id}>
                          Project {item.id}
                        </option>
                      ))}
                    </select>
                  </label>
                </>
              )}
            </div>

            {dataError && (
              <div className="error-notice" role="alert">
                <TriangleAlert size={18} />
                <span>{dataError}</span>
                <button onClick={retryData}>Retry</button>
              </div>
            )}
            <div
              className="metrics"
              aria-label="Project RFI summary"
              aria-busy={dataLoading}
            >
              {[
                {
                  label: "Total RFIs",
                  value: details?.summary.total_rfis,
                  icon: ClipboardList,
                  tone: "blue",
                  note: "Requests for information",
                },
                {
                  label: "Critical RFIs",
                  value: details?.summary.critical_rfis,
                  icon: TriangleAlert,
                  tone: "red",
                  note: "Blocking & open over 7 days",
                },
                {
                  label: "Blocking RFIs",
                  value: details?.summary.blocking_rfis,
                  icon: ShieldCheck,
                  tone: "amber",
                  note: "Flagged as blocking work",
                },
              ].map(({ label, value, icon: Icon, tone, note }) => (
                <div className={`metric ${tone}`} key={label}>
                  <div className="metric-top">
                    <span>{label}</span>
                    <Icon size={19} />
                  </div>
                  <div className="metric-value">
                    {value ?? "—"}
                    <span>
                      {value === undefined
                        ? dataLoading
                          ? "Loading"
                          : "Unavailable"
                        : "RFIs"}
                    </span>
                  </div>
                  <div className="metric-note">{note}</div>
                </div>
              ))}
            </div>
          </section>

          <section
            className="assistant panel"
            id="assistant"
            tabIndex={-1}
            aria-labelledby="assistant-title"
          >
            <div className="panel-heading">
              <div className="section-title">
                <span className="assistant-icon">
                  <MessageSquareText size={21} />
                </span>
                <div>
                  <h2 id="assistant-title">Your construction copilot</h2>
                  <p>Less searching. More clarity.</p>
                </div>
              </div>
              <span className="powered-label">POWERED BY CLAUDE</span>
            </div>
            <div className="assistant-body">
              <div className="conversation">
                <div
                  className="response-area"
                  aria-live="polite"
                  aria-busy={loading}
                >
                  {question && (
                    <div className="asked-question">
                      <span>YOU ASKED</span>
                      <p>{question}</p>
                    </div>
                  )}
                  {loading && (
                    <div className="thinking" role="status">
                      <LoaderCircle size={22} className="spin" />
                      <div>
                        <strong>Reviewing your question…</strong>
                        <p>
                          BuildFlow is preparing a response from the local
                          project data.
                        </p>
                      </div>
                    </div>
                  )}
                  {error && (
                    <div className="error-notice" id="chat-error" role="alert">
                      <TriangleAlert size={20} />
                      <span>{error}</span>
                    </div>
                  )}
                  {answer && (
                    <div className="answer">
                      <div className="answer-label">
                        <span className="mini-symbol">
                          <Building2 size={14} />
                        </span>
                        BUILDFLOW RESPONSE
                        <Check size={14} />
                      </div>
                      <div className="markdown">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          skipHtml
                          components={{
                            table: ({ children }) => (
                              <div
                                className="table-scroll"
                                tabIndex={0}
                                role="region"
                                aria-label="AI response table"
                              >
                                <table>{children}</table>
                              </div>
                            ),
                          }}
                        >
                          {answer}
                        </ReactMarkdown>
                      </div>
                    </div>
                  )}
                  {!question && !loading && (
                    <div className="assistant-empty">
                      <div className="empty-symbol">
                        <MessageSquareText size={27} strokeWidth={1.5} />
                      </div>
                      <h3>A clearer picture starts with a question.</h3>
                      <p>
                        Ask about project summaries, open RFIs, or critical
                        issues.
                        <br className="desktop-only" /> BuildFlow turns project
                        information into practical answers.
                      </p>
                      <span className="context-hint">
                        <span className="status-dot" />
                        {project
                          ? `Sample project ${project.id} is available`
                          : "You can ask using a project ID"}
                      </span>
                    </div>
                  )}
                </div>
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    void handleSend();
                  }}
                >
                  <label htmlFor="question">Your project question</label>
                  <div className="composer">
                    <input
                      ref={questionInput}
                      id="question"
                      value={message}
                      onChange={(event) => setMessage(event.target.value)}
                      placeholder={
                        project
                        ? `Ask about project ${project.id}…`
                          : "Ask about a project by ID…"
                      }
                      aria-describedby={
                        error ? "chat-error question-help" : "question-help"
                      }
                      readOnly={loading}
                      autoComplete="off"
                    />
                    <button
                      className="primary-button"
                      type="submit"
                      aria-label={loading ? "Sending" : "Send question"}
                      disabled={loading || !message.trim()}
                    >
                      {loading ? (
                        <LoaderCircle size={17} className="spin" />
                      ) : (
                        <Send size={16} />
                      )}
                      <span>{loading ? "Sending…" : "Send"}</span>
                    </button>
                  </div>
                  <div id="question-help" className="input-help">
                    <span>
                      Include a project ID for the most useful answer.
                    </span>
                    <span className="desktop-only">
                      Enter to send <ArrowDown size={11} />
                    </span>
                  </div>
                </form>
              </div>
              <aside className="quick-start" aria-label="Example questions">
                <div className="eyebrow">A GOOD PLACE TO START</div>
                {prompts.map(
                  ({ label, detail, icon: Icon, question: prompt }) => (
                    <button
                      key={label}
                      disabled={!project || loading}
                      onClick={() => {
                        setMessage(prompt);
                        questionInput.current?.focus();
                      }}
                    >
                      <span className="prompt-icon">
                        <Icon size={18} />
                      </span>
                      <span>
                        <strong>{label}</strong>
                        <small>{detail}</small>
                      </span>
                      <ArrowUpRight size={15} />
                    </button>
                  ),
                )}
                <div className="assistant-footnote">
                  <CircleHelp size={16} />
                  <p>
                    Answers use local sample data.
                    <br />
                    Always verify before taking action.
                  </p>
                </div>
              </aside>
            </div>
          </section>

          <section
            className="rfi-panel panel"
            id="rfis"
            tabIndex={-1}
            aria-labelledby="rfis-title"
          >
            <div className="panel-heading">
              <div>
                <div className="heading-inline">
                  <h2 id="rfis-title">RFI register</h2>
                  {project && (
                    <span className="count-badge">{project.rfis.length}</span>
                  )}
                </div>
                <p>Track requests. Spot blockers. Keep work moving.</p>
              </div>
              <div className="filter-group" aria-label="Filter RFIs">
                <button
                  aria-pressed={!criticalOnly}
                  onClick={() => setCriticalOnly(false)}
                >
                  All RFIs
                </button>
                <button
                  aria-pressed={criticalOnly}
                  disabled={!details}
                  onClick={() => setCriticalOnly(true)}
                >
                  Critical only
                </button>
              </div>
            </div>
            <div
              className="table-scroll"
              role="region"
              aria-label="Project RFIs"
              tabIndex={0}
            >
              <table className="rfi-table">
                <thead>
                  <tr>
                    <th scope="col">RFI ID</th>
                    <th scope="col">SUBJECT</th>
                    <th scope="col">DAYS OPEN</th>
                    <th scope="col">BLOCKING</th>
                    <th scope="col">PRIORITY</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRFIs.map((rfi) => (
                    <tr key={rfi.id}>
                      <td className="rfi-id">
                        RFI-{String(rfi.id).padStart(3, "0")}
                      </td>
                      <td className="rfi-title">{rfi.title}</td>
                      <td>
                        <span
                          className={
                            criticalIds.has(rfi.id) ? "days-warning" : ""
                          }
                        >
                          {rfi.days_open} <span className="muted">days</span>
                        </span>
                      </td>
                      <td>
                        {rfi.is_blocking ? (
                          <span className="blocking">
                            <span className="status-dot" />
                            Blocking
                          </span>
                        ) : (
                          <span className="muted">Not blocking</span>
                        )}
                      </td>
                      <td>
                        <span
                          className={`badge ${details ? (criticalIds.has(rfi.id) ? "critical" : "neutral") : "neutral"}`}
                        >
                          {details ? (
                            criticalIds.has(rfi.id) ? (
                              <>
                                <TriangleAlert size={12} />
                                Critical
                              </>
                            ) : (
                              "Standard"
                            )
                          ) : (
                            "Unavailable"
                          )}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!visibleRFIs.length && (
              <p className="table-empty">
                {dataLoading
                  ? "Loading RFIs…"
                  : dataError
                    ? "RFI data is unavailable. Retry the project connection above."
                    : criticalOnly
                      ? "No critical RFIs for this project."
                      : "No RFIs to display."}
              </p>
            )}
            <div className="table-footer">
              <span>
                {visibleRFIs.length}{" "}
                {visibleRFIs.length === 1 ? "request" : "requests"}
                {project ? ` · Project ${project.id}` : ""}
              </span>
              <span>
                <CircleHelp size={13} />
                Critical = blocking + open more than 7 days
              </span>
            </div>
          </section>
          <footer className="page-footer">
            <span>
              <ShieldCheck size={14} />
              Local sample data · Independent portfolio prototype
            </span>
            <span>Not affiliated with DeAngelis Diamond</span>
          </footer>
        </main>
      </div>
    </div>
  );
}

export default App;
