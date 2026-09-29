import { useEffect, useState } from "react";
import {
  Activity,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Brain,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Code2,
  Database,
  FileText,
  GitCompareArrows,
  Layers3,
  Loader2,
  Plus,
  Radio,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Terminal,
  TriangleAlert,
  X,
} from "lucide-react";
import { request, post } from "./services/api";
import { scenarios, sampleAnalysis } from "./scenarios";

const NAV = [
  ["overview", "Overview", Layers3],
  ["workspace", "Incident workspace", Activity],
  ["compare", "Memory comparison", GitCompareArrows],
  ["memory", "Memory explorer", Database],
  ["insights", "Learning journal", BookOpen],
];
const emptyForm = {
  title: "",
  service: "",
  environment: "production",
  severity: "P2",
  symptoms: "",
  error_logs: "",
};
const human = (s) => (s || "").replaceAll("_", " ");
const date = (s) =>
  s
    ? new Date(
        s.endsWith("Z") || /[+-]\d\d:\d\d$/.test(s) ? s : `${s}Z`,
      ).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
function Badge({ children, tone = "" }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
function Notice({ children, tone = "" }) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`notice ${tone}`}
    >
      <TriangleAlert size={16} />
      <span>{children}</span>
    </div>
  );
}
function Heading({ eyebrow, title, description, children }) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {children}
    </div>
  );
}
function List({ items }) {
  return (
    <ol className="steps">
      {(items || []).map((text, i) => (
        <li key={i}>
          <span>{String(i + 1).padStart(2, "0")}</span>
          <p>{text}</p>
        </li>
      ))}
    </ol>
  );
}
function Busy({ text = "Analyzing current evidence and operational memory…" }) {
  const [sec, setSec] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setSec((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="busy" role="status">
      <Loader2 className="spin" size={22} />
      <div>
        <strong>{text}</strong>
        <p>
          {sec}s elapsed · Waiting for a verified response. You can keep this
          tab open.
        </p>
      </div>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState("overview");
  const [health, setHealth] = useState(null),
    [rows, setRows] = useState([]),
    [stats, setStats] = useState(null);
  const [incident, setIncident] = useState(null),
    [sample, setSample] = useState(false);
  const [error, setError] = useState(""),
    [connections, setConnections] = useState(null),
    [checking, setChecking] = useState(false);
  async function refresh() {
    try {
      const [h, r, s] = await Promise.all([
        request("/health"),
        request("/incidents"),
        request("/memory/stats"),
      ]);
      setHealth(h);
      setRows(r);
      setStats(s);
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    refresh();
  }, []);
  function navigate(next) {
    setPage(next);
    setError("");
  }
  function open(item) {
    setIncident(item);
    setSample(false);
    navigate("workspace");
  }
  function fresh() {
    setIncident(null);
    setSample(false);
    navigate("workspace");
  }
  async function check() {
    setChecking(true);
    try {
      setConnections(await request("/connections"));
    } catch (e) {
      setError(e.message);
    } finally {
      setChecking(false);
    }
  }
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button
          className="brand"
          onClick={() => navigate("overview")}
          aria-label="Command Center overview"
        >
          <span className="brand-mark">
            <Layers3 size={22} />
          </span>
          <span>
            RECALL<span className="brand-sub">INCIDENT COMMAND CENTER</span>
          </span>
        </button>
        <div className="team-box">
          <span className="team-avatar">O</span>
          <div>
            Operations workspace<small>Single-team workspace</small>
          </div>
          <span className="live-dot" />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {NAV.map(([id, label, Icon]) => (
            <button
              key={id}
              aria-label={label}
              title={label}
              className={`nav-item ${page === id ? "selected" : ""}`}
              onClick={() => navigate(id)}
              aria-current={page === id ? "page" : undefined}
            >
              <Icon size={18} />
              <span>{label}</span>
              {id === "workspace" && (
                <span className="nav-count">
                  {stats?.active_incidents || 0}
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="memory-mini">
            <Brain size={19} />
            <div>
              Powered by Hindsight<small>Experience that stays with you.</small>
            </div>
          </div>
          <button
            className="connection-link"
            onClick={check}
            disabled={checking}
          >
            <Radio size={14} />
            {checking ? "Checking…" : "Check connections"}
            <ArrowUpRight size={14} />
          </button>
          {connections && (
            <p className="connection-status">
              Groq: {connections.groq}
              <br />
              Hindsight: {connections.hindsight}
            </p>
          )}
          <div className="profile">
            <span className="avatar">OC</span>
            <div>
              On-call engineer<small>Local workspace</small>
            </div>
            <Badge>v3.0</Badge>
          </div>
        </div>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace
            <ChevronRight size={13} />
            <strong>{NAV.find((n) => n[0] === page)?.[1]}</strong>
          </div>
          <div className="topbar-right">
            <span
              className={`status-dot ${health?.status === "ready" ? "good" : ""}`}
            />
            {health?.status === "ready"
              ? "Providers configured"
              : "Setup required"}
            <button
              className="icon-button"
              aria-label="Refresh workspace"
              onClick={refresh}
            >
              <RefreshCw size={16} />
            </button>
          </div>
        </header>
        <main>
          {error && <Notice tone="error">{error}</Notice>}
          {health?.status === "setup_required" && (
            <Notice>
              Live AI awaits API keys. Add your Groq and Hindsight keys to{" "}
              <code>backend/.env</code>, then restart. The sample walkthrough is
              available below.
            </Notice>
          )}
          {page === "overview" && (
            <>
              <Heading
                eyebrow="OPERATIONS / OVERVIEW"
                title="Every incident. A little wiser."
                description="Turn your team's past resolutions into a better next step."
              >
                <button className="button primary" onClick={fresh}>
                  <Plus size={17} />
                  Investigate incident
                </button>
              </Heading>
              <div className="overview-grid">
                <section className="hero-panel">
                  <Badge tone="teal">
                    <Brain size={13} /> PERSISTENT OPERATIONAL MEMORY
                  </Badge>
                  <h2>
                    Your last incident
                    <br />
                    should help solve
                    <br />
                    <span>your next one.</span>
                  </h2>
                  <p>
                    Recall what happened. Check what still applies.
                    <br />
                    Keep the lesson when the incident ends.
                  </p>
                  <div className="hero-actions">
                    <button className="button primary" onClick={fresh}>
                      Start investigation
                      <ArrowRight size={16} />
                    </button>
                    <button
                      className="text-button"
                      onClick={() => {
                        setSample(true);
                        setIncident({
                          ...scenarios[0],
                          incident_id: "SAMPLE-ONLY",
                          analysis: sampleAnalysis,
                          updates: [],
                          status: "investigating",
                        });
                        navigate("workspace");
                      }}
                    >
                      Sample walkthrough
                      <ArrowUpRight size={15} />
                    </button>
                  </div>
                  <div className="hero-flow">
                    <span>
                      <Search size={14} />
                      Recall
                    </span>
                    <ChevronRight size={14} />
                    <span>
                      <Brain size={14} />
                      Reason
                    </span>
                    <ChevronRight size={14} />
                    <span>
                      <CheckCircle2 size={14} />
                      Remember
                    </span>
                  </div>
                </section>
                <section className="panel memory-panel">
                  <div className="panel-heading">
                    <h3>Operational memory</h3>
                    <Brain size={18} />
                  </div>
                  <div className="memory-orbit" aria-hidden="true">
                    <div className="orbit o1" />
                    <div className="orbit o2" />
                    <span className="orbit-node n1">
                      <FileText size={17} />
                    </span>
                    <span className="orbit-node n2">
                      <Terminal size={17} />
                    </span>
                    <span className="orbit-node n3">
                      <Check size={17} />
                    </span>
                    <div className="orbit-center">
                      <Brain size={36} />
                    </div>
                  </div>
                  <div className="memory-caption">
                    <strong>Context, connected.</strong>
                    <p>
                      Past attempts. Current evidence.
                      <br />A recommendation you can inspect.
                    </p>
                  </div>
                  <div className="bank-line">
                    <span>Hindsight bank</span>
                    <code>{health?.bank_id || "Awaiting backend"}</code>
                  </div>
                </section>
              </div>
              <div className="metrics-grid">
                {[
                  [
                    Activity,
                    "Active incidents",
                    stats?.active_incidents,
                    "Awaiting confirmed recovery",
                  ],
                  [
                    Database,
                    "Memory delivered",
                    stats?.retained_incidents,
                    "Local records saved to Hindsight",
                  ],
                  [
                    FileText,
                    "Recorded incidents",
                    stats?.total_incidents,
                    "Persisted in this workspace",
                  ],
                ].map(([Icon, label, value, note]) => (
                  <div className="metric" key={label}>
                    <div className="metric-top">
                      <span>{label}</span>
                      <Icon size={17} />
                    </div>
                    <strong>{value ?? "—"}</strong>
                    <small>{note}</small>
                  </div>
                ))}
              </div>
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h3>Incident timeline</h3>
                    <p>
                      Your investigations and the outcomes they leave behind.
                    </p>
                  </div>
                  <Badge>{rows.length} records</Badge>
                </div>
                {rows.length ? (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>INCIDENT</th>
                          <th>SERVICE</th>
                          <th>STATUS</th>
                          <th>MEMORY</th>
                          <th>REPORTED</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((r) => (
                          <tr key={r.incident_id}>
                            <td>
                              <button
                                className="row-link"
                                onClick={() => open(r)}
                              >
                                {r.title}
                                <small>{r.incident_id}</small>
                              </button>
                            </td>
                            <td>
                              <Badge>{r.service}</Badge>
                            </td>
                            <td>
                              <Badge
                                tone={
                                  r.status === "resolved" ? "teal" : "amber"
                                }
                              >
                                {human(r.status)}
                              </Badge>
                            </td>
                            <td>
                              {r.memory_retained ? (
                                <span className="teal-text">
                                  <Check size={13} />
                                  Saved
                                </span>
                              ) : (
                                <span className="muted">
                                  {r.outcome || r.updates?.length
                                    ? "Pending"
                                    : "Not recorded"}
                                </span>
                              )}
                            </td>
                            <td className="muted">{date(r.timestamp)}</td>
                            <td>
                              <button
                                className="icon-button"
                                onClick={() => open(r)}
                                aria-label={`Open ${r.incident_id}`}
                              >
                                <ArrowUpRight size={16} />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty-state">
                    <Activity size={28} />
                    <h3>A fresh start for your incident history.</h3>
                    <p>
                      Start an investigation or explore the clearly labelled
                      sample walkthrough.
                    </p>
                    <button className="button" onClick={fresh}>
                      Create your first incident
                      <ArrowRight size={15} />
                    </button>
                  </div>
                )}
              </section>
              <div className="footer-note">
                <ShieldCheck size={14} />
                Recommendations support your investigation. Changes stay under
                your control.
              </div>
            </>
          )}
          {page === "workspace" && (
            <Workspace
              key={incident?.incident_id || "new"}
              incident={incident}
              sample={sample}
              onSaved={(item) => {
                setIncident(item);
                refresh();
              }}
              onNew={fresh}
            />
          )}
          {page === "compare" && <Comparison />}
          {(page === "memory" || page === "insights") && (
            <Memory key={page} reflection={page === "insights"} />
          )}
        </main>
      </div>
    </div>
  );
}

function IncidentForm({ onSubmit, busy, compare = false }) {
  const [form, setForm] = useState(emptyForm);
  function change(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h3>
            {compare
              ? "One incident. Two perspectives."
              : "What are you seeing?"}
          </h3>
          <p>
            Start with symptoms and measurements. You can add new evidence
            later.
          </p>
        </div>
        <Badge>01 / INPUT</Badge>
      </div>
      <div className="scenario-row">
        <span>TRY A SYNTHETIC SCENARIO</span>
        {scenarios.map((s) => (
          <button
            type="button"
            key={s.name}
            onClick={() => setForm(s)}
            disabled={busy}
          >
            {s.name}
            <ArrowUpRight size={12} />
          </button>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(form);
        }}
        className="incident-form"
      >
        <label className="full">
          Incident title
          <input
            name="title"
            value={form.title}
            onChange={change}
            minLength={5}
            maxLength={500}
            required
            placeholder="e.g. Checkout latency spikes during peak traffic"
          />
        </label>
        <label>
          Service
          <input
            name="service"
            value={form.service}
            onChange={change}
            minLength={2}
            maxLength={100}
            required
            placeholder="payment-api"
          />
        </label>
        <div className="field-pair">
          <label>
            Environment
            <select
              name="environment"
              value={form.environment}
              onChange={change}
            >
              <option>production</option>
              <option>staging</option>
              <option>development</option>
            </select>
          </label>
          <label>
            Severity
            <select name="severity" value={form.severity} onChange={change}>
              <option value="P1">P1 · Critical</option>
              <option value="P2">P2 · High</option>
              <option value="P3">P3 · Medium</option>
              <option value="P4">P4 · Low</option>
            </select>
          </label>
        </div>
        <label className="full">
          Symptoms & current measurements
          <textarea
            name="symptoms"
            value={form.symptoms}
            onChange={change}
            minLength={10}
            maxLength={12000}
            required
            rows={4}
            placeholder="What changed? Which requests fail? Include actual measurements and when it started."
          />
        </label>
        <label className="full">
          Relevant logs{" "}
          <span className="optional">
            optional · remove credentials and personal data
          </span>
          <textarea
            className="mono"
            name="error_logs"
            value={form.error_logs}
            onChange={change}
            maxLength={20000}
            rows={3}
            placeholder="Paste a short, relevant log excerpt…"
          />
        </label>
        <div className="form-footer full">
          <span>
            <ShieldCheck size={14} />
            No infrastructure changes are executed.
          </span>
          <button className="button primary" disabled={busy}>
            {busy ? (
              <Loader2 size={16} className="spin" />
            ) : (
              <Sparkles size={16} />
            )}
            {compare
              ? "Compare with / without memory"
              : "Investigate with memory"}
            <ArrowRight size={15} />
          </button>
        </div>
      </form>
    </section>
  );
}

function Workspace({ incident, sample, onSaved, onNew }) {
  const [item, setItem] = useState(incident),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const [note, setNote] = useState(""),
    [kind, setKind] = useState("evidence"),
    [showOutcome, setShowOutcome] = useState(false);
  async function load(id) {
    const updated = await request(`/incidents/${id}`);
    setItem(updated);
    onSaved(updated);
    return updated;
  }
  async function run(action) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function analyze(form) {
    await run(async () => {
      const result = await post("/incidents/analyze", form);
      await load(result.incident_id);
    });
  }
  async function update() {
    await run(async () => {
      const updated = await post(`/incidents/${item.incident_id}/updates`, {
        note,
        kind,
      });
      setItem(updated);
      onSaved(updated);
      setNote("");
      setMessage(
        updated.memory_retained
          ? "Update saved locally and in Hindsight. Re-analyze to use the new evidence."
          : "Update saved locally. Hindsight delivery failed; retry memory when connected.",
      );
    });
  }
  const a = item?.analysis;
  return (
    <>
      <Heading
        eyebrow="OPERATIONS / INVESTIGATION"
        title={item ? "Evidence before action." : "Start with the signal."}
        description={
          item
            ? `${item.incident_id} · ${item.service} · ${item.environment}`
            : "A focused investigation, informed by what your team has already learned."
        }
      >
        {item && (
          <button className="button" onClick={onNew}>
            <Plus size={16} />
            New incident
          </button>
        )}
      </Heading>
      {sample && (
        <Notice>
          This is a static, synthetic walkthrough—not live AI or Hindsight
          output. Start a new incident to run the real integration.
        </Notice>
      )}
      {error && <Notice tone="error">{error}</Notice>}
      {message && <Notice>{message}</Notice>}
      {!item && <IncidentForm onSubmit={analyze} busy={busy} />}
      {busy && (
        <Busy
          text={
            item ? "Saving evidence or requesting a fresh analysis…" : undefined
          }
        />
      )}
      {item && (
        <>
          <div className="incident-strip">
            <div>
              <Badge tone="red">{item.severity}</Badge>
              <h2>{item.title}</h2>
            </div>
            <Badge tone={item.status === "resolved" ? "teal" : "amber"}>
              {human(item.status)}
            </Badge>
          </div>
          {!sample && (
            <div className="action-bar">
              <button
                className="button"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    await post(`/incidents/${item.incident_id}/analyze`);
                    await load(item.incident_id);
                  })
                }
              >
                <RefreshCw size={15} />
                Re-analyze current evidence
              </button>
              <button
                className="button primary"
                disabled={busy}
                onClick={() => setShowOutcome(!showOutcome)}
              >
                <CheckCircle2 size={15} />
                Record outcome
              </button>
              {(item.outcome || item.updates?.length > 0) &&
                !item.memory_retained && (
                  <button
                    className="button"
                    disabled={busy}
                    onClick={() =>
                      run(async () => {
                        const r = await post(
                          `/incidents/${item.incident_id}/retry-memory`,
                        );
                        setItem(r);
                        onSaved(r);
                        setMessage(
                          r.memory_retained
                            ? "Memory delivered."
                            : "Memory remains pending. Check Hindsight connectivity.",
                        );
                      })
                    }
                  >
                    Retry memory save
                  </button>
                )}
            </div>
          )}
          {showOutcome && !sample && (
            <Outcome
              incidentId={item.incident_id}
              onSaved={async (message) => {
                await load(item.incident_id);
                setMessage(message);
                setShowOutcome(false);
              }}
              onClose={() => setShowOutcome(false)}
            />
          )}
          {a ? (
            <Analysis analysis={a} sample={sample} />
          ) : (
            <Notice>
              This incident is saved. Re-analyze once your providers are
              connected.
            </Notice>
          )}
          {!sample && (
            <div className="workspace-grid">
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h3>Add what happened next</h3>
                    <p>Failed attempts are useful experience too.</p>
                  </div>
                  <Plus size={17} />
                </div>
                <div className="panel-body">
                  <label>
                    Type
                    <select
                      value={kind}
                      onChange={(e) => setKind(e.target.value)}
                    >
                      <option value="evidence">New evidence</option>
                      <option value="failed_attempt">
                        Attempt that did not work
                      </option>
                    </select>
                  </label>
                  <label>
                    Observation
                    <textarea
                      rows={3}
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      placeholder="What did you check or try, and what did you observe?"
                      maxLength={5000}
                    />
                  </label>
                  <button
                    className="button"
                    onClick={update}
                    disabled={busy || note.trim().length < 10}
                  >
                    <Brain size={15} />
                    Save evidence to memory
                  </button>
                </div>
              </section>
              <section className="panel">
                <div className="panel-heading">
                  <h3>Investigation history</h3>
                  <Clock3 size={17} />
                </div>
                <div className="panel-body">
                  {item.updates?.length ? (
                    item.updates.map((u, i) => (
                      <div className="timeline-entry" key={i}>
                        <span className="timeline-dot" />
                        <div>
                          <small>
                            {human(u.kind)} · {date(u.timestamp)}
                          </small>
                          <p>{u.note}</p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="muted">
                      No updates yet. Record the next observation so the next
                      engineer can pick up here.
                    </p>
                  )}
                  {item.outcome && (
                    <div className="timeline-entry">
                      <CheckCircle2 size={16} />
                      <div>
                        <small>{human(item.outcome)}</small>
                        <p>{item.resolution}</p>
                        <Badge tone={item.memory_retained ? "teal" : "amber"}>
                          {item.memory_retained
                            ? "Memory saved"
                            : "Memory pending"}
                        </Badge>
                      </div>
                    </div>
                  )}
                </div>
              </section>
            </div>
          )}
          <details className="panel details">
            <summary>
              <Terminal size={16} />
              Original incident evidence
            </summary>
            <p>{item.symptoms}</p>
            {item.error_logs && <pre>{item.error_logs}</pre>}
          </details>
        </>
      )}
    </>
  );
}

function Analysis({ analysis: a, sample = false, compact = false }) {
  return (
    <div className={compact ? "analysis-compact" : "workspace-grid"}>
      <div className="analysis-main">
        <section className="panel hypothesis">
          <div className="panel-heading">
            <div className="section-label">
              <span className="number-box">01</span>
              <h3>Working hypothesis</h3>
            </div>
            <Badge tone="amber">Unconfirmed</Badge>
          </div>
          <div className="panel-body">
            <h2>{a.likely_root_cause}</h2>
            <p>{a.summary}</p>
            <div className="evidence-assessment">
              <ShieldCheck size={16} />
              <p>{a.evidence_assessment}</p>
            </div>
          </div>
        </section>
        <section className="panel">
          <div className="panel-heading">
            <div className="section-label">
              <span className="number-box">02</span>
              <h3>Check this first</h3>
            </div>
            <Search size={17} />
          </div>
          <div className="panel-body">
            <List items={a.investigation_steps} />
          </div>
        </section>
        <section className="panel">
          <div className="panel-heading">
            <h3>What could change this diagnosis?</h3>
            <GitCompareArrows size={17} />
          </div>
          <div className="panel-body">
            <List items={a.disconfirming_checks} />
          </div>
        </section>
        <details className="panel details" open={compact || undefined}>
          <summary>
            Conditional remediation & recovery
            <ChevronRight size={16} />
          </summary>
          <List items={a.recommended_actions} />
          <h4>Verify recovery</h4>
          <List items={a.verification_steps} />
          {a.risk_notes && <Notice>{a.risk_notes}</Notice>}
        </details>
      </div>
      <aside className="evidence-column">
        <section className="panel evidence-panel">
          <div className="panel-heading">
            <div className="section-label">
              <Brain size={18} />
              <h3>Memory behind the answer</h3>
            </div>
          </div>
          <div className="panel-body">
            <Badge tone={a.used_memory ? "teal" : "amber"}>
              {sample ? "Illustrative memory" : human(a.memory_status)}
            </Badge>
            <p className="muted">
              {a.used_memory
                ? "Historical context influenced this hypothesis. Verify it against today’s evidence."
                : "No historical source was cited in this recommendation."}
            </p>
            {a.warnings?.map((w, i) => (
              <Notice key={i}>{w}</Notice>
            ))}
            {a.memory_insights?.length > 0 && (
              <div className="memory-delta">
                <div className="eyebrow">WHAT MEMORY CHANGED</div>
                {a.memory_insights.map((x, i) => (
                  <p key={i}>{x}</p>
                ))}
              </div>
            )}
            {a.historical_evidence?.map((x, i) => (
              <p className="evidence-claim" key={i}>
                <span>↳</span>
                {x}
              </p>
            ))}
            <div className="source-label">
              {a.historical_incidents?.length || 0} RETRIEVED MEMORY FRAGMENTS
            </div>
            {a.historical_incidents?.map((m, i) => (
              <details className="source-card" key={m.source_id || i}>
                <summary>
                  <FileText size={15} />
                  <span>
                    Source {i + 1}
                    <small>
                      {a.cited_sources?.includes(m.source_id)
                        ? "Cited in analysis"
                        : "Retrieved context"}
                    </small>
                  </span>
                  <ChevronRight size={14} />
                </summary>
                <code>{m.source_id}</code>
                <p>{m.memory_text}</p>
              </details>
            ))}
            {!a.historical_incidents?.length && (
              <p className="muted">No matching history to display.</p>
            )}
          </div>
        </section>
        {!sample && a.timings_ms && (
          <div className="timings">
            <Clock3 size={14} />
            <span>Recall {(a.timings_ms.recall / 1000).toFixed(1)}s</span>
            <span>Model {(a.timings_ms.model / 1000).toFixed(1)}s</span>
            <strong>{(a.timings_ms.total / 1000).toFixed(1)}s total</strong>
          </div>
        )}
      </aside>
    </div>
  );
}

function Outcome({ incidentId, onSaved, onClose }) {
  const [form, setForm] = useState({
    outcome: "successfully_resolved",
    root_cause: "",
    resolution: "",
    actions_taken: "",
    lessons_learned: "",
  });
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await post(`/incidents/${incidentId}/resolve`, {
        ...form,
        actions_taken: form.actions_taken
          .split("\n")
          .map((x) => x.trim())
          .filter(Boolean),
      });
      await onSaved(r.message);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel outcome-panel">
      <div className="panel-heading">
        <div>
          <h3>Record the outcome</h3>
          <p>
            Save what actually happened, including partial or unsuccessful
            fixes.
          </p>
        </div>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close outcome form"
        >
          <X size={17} />
        </button>
      </div>
      <form className="incident-form" onSubmit={save}>
        {error && (
          <div className="full">
            <Notice tone="error">{error}</Notice>
          </div>
        )}
        <label className="full">
          Outcome
          <select
            value={form.outcome}
            onChange={(e) => setForm({ ...form, outcome: e.target.value })}
          >
            <option value="successfully_resolved">
              Resolved — recovery verified
            </option>
            <option value="partially_resolved">
              Mitigated — issue remains
            </option>
            <option value="unresolved_escalated">Unresolved — escalated</option>
          </select>
        </label>
        {[
          ["root_cause", "Confirmed cause or remaining uncertainty"],
          ["resolution", "Result observed"],
          ["actions_taken", "Actions taken (one per line)"],
          ["lessons_learned", "Lesson for the next incident (optional)"],
        ].map(([key, label]) => (
          <label key={key}>
            {label}
            <textarea
              value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              minLength={key === "lessons_learned" ? undefined : 10}
              required={key !== "lessons_learned"}
              rows={3}
            />
          </label>
        ))}
        <div className="form-footer full">
          <span>Outcome stays local if memory delivery fails.</span>
          <button className="button primary" disabled={busy}>
            {busy ? (
              <Loader2 className="spin" size={16} />
            ) : (
              <Brain size={16} />
            )}
            Save outcome & remember
          </button>
        </div>
      </form>
    </section>
  );
}

function Comparison() {
  const [result, setResult] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function run(form) {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await post("/incidents/compare", { incident: form }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        eyebrow="MEMORY / CONTROLLED COMPARISON"
        title="See the difference memory makes."
        description="Same incident. Same model and instructions. Only the retrieved history changes."
      />
      <details className="panel details" open={!result}>
        <summary>
          Incident input � edit and run comparison
          <ChevronRight size={16} />
        </summary>
        <IncidentForm compare onSubmit={run} busy={busy} />
      </details>
      {busy && <Busy text="Running both analyses concurrently…" />}
      {error && <Notice tone="error">{error}</Notice>}
      {result && (
        <div className="comparison-grid">
          {[
            ["without_memory", "Current evidence only"],
            ["with_memory", "With operational memory"],
          ].map(([key, title]) => (
            <section key={key}>
              <div className="comparison-title">
                <h2>{title}</h2>
                <Badge tone={key === "with_memory" ? "teal" : ""}>
                  {key === "with_memory" ? "Hindsight enabled" : "Baseline"}
                </Badge>
              </div>
              <Analysis compact analysis={result[key]} />
            </section>
          ))}
        </div>
      )}
    </>
  );
}

function Memory({ reflection }) {
  const [query, setQuery] = useState(
      reflection
        ? "Which incident resolutions failed, and what evidence should we check before reusing an old fix?"
        : "",
    ),
    [data, setData] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setData(null);
    try {
      setData(
        await post(reflection ? "/memory/reflect" : "/memory/recall", {
          query,
          budget: "low",
          ...(!reflection ? { max_tokens: 2400 } : {}),
        }),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        eyebrow={reflection ? "MEMORY / REFLECTION" : "MEMORY / RETRIEVAL"}
        title={
          reflection
            ? "Make experience useful."
            : "Find the context worth keeping."
        }
        description={
          reflection
            ? "Reflect across recorded incidents to identify patterns, failures and open questions."
            : "Search persistent operational memory. Results are evidence fragments, not incident counts."
        }
      />
      <section className="panel">
        <form className="search-form" onSubmit={submit}>
          <label>
            {reflection
              ? "What would you like to learn?"
              : "Search your operational history"}
            <textarea
              rows={2}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              minLength={reflection ? 10 : 5}
              maxLength={3000}
              required
              placeholder="e.g. Failed Redis fixes in the payment service"
            />
          </label>
          <button className="button primary" disabled={busy}>
            {reflection ? <Sparkles size={16} /> : <Search size={16} />}
            {reflection ? "Reflect on memory" : "Search memory"}
          </button>
        </form>
      </section>
      {busy && (
        <Busy
          text={
            reflection
              ? "Reflecting across retained evidence…"
              : "Retrieving matching memories…"
          }
        />
      )}
      {error && <Notice tone="error">{error}</Notice>}
      {data &&
        (reflection ? (
          <section className="panel">
            <div className="panel-heading">
              <h3>Reflection</h3>
              <Badge tone="amber">Review against source records</Badge>
            </div>
            <div className="panel-body reflection-text">{data.reflection}</div>
          </section>
        ) : (
          <>
            <div className="result-count">
              {data.count} memory fragments retrieved
            </div>
            {data.memories.length ? (
              data.memories.map((m, i) => (
                <section className="panel memory-result" key={m.source_id || i}>
                  <div className="panel-heading">
                    <div className="section-label">
                      <FileText size={16} />
                      <h3>Memory {i + 1}</h3>
                    </div>
                    <Badge>{m.memory_type || "memory"}</Badge>
                  </div>
                  <div className="panel-body">
                    <code className="source-id">{m.source_id}</code>
                    <p>{m.memory_text}</p>
                  </div>
                </section>
              ))
            ) : (
              <div className="empty-state">
                <Search size={26} />
                <h3>No matching memories.</h3>
                <p>
                  Try a different query, or record an incident outcome first.
                </p>
              </div>
            )}
          </>
        ))}
    </>
  );
}
