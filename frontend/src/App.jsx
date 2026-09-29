import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Brain,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
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
  Trash2,
  TriangleAlert,
  X,
} from "lucide-react";
import { get, post, del } from "./services/api";
import { scenarios, sampleAnalysis, FORM_FIELDS } from "./scenarios";

/* ─────────────────────────── constants ─────────────────────────── */
const NAV = [
  ["overview", "Overview", Layers3],
  ["workspace", "Incident workspace", Activity],
  ["compare", "Memory comparison", GitCompareArrows],
  ["memory", "Memory explorer", Database],
  ["insights", "Learning journal", BookOpen],
];

const EMPTY_FORM = {
  title: "", service: "", environment: "production",
  severity: "P2", symptoms: "", error_logs: "",
};

/* ─────────────────────────── helpers ───────────────────────────── */
const human = (s) => (s || "").replaceAll("_", " ");

const date = (s) =>
  s
    ? new Date(
        s.endsWith("Z") || /[+-]\d\d:\d\d$/.test(s) ? s : `${s}Z`,
      ).toLocaleString([], {
        month: "short", day: "numeric",
        hour: "2-digit", minute: "2-digit",
      })
    : "—";

/** Map a status string to a badge tone. */
function statusTone(status) {
  if (status === "resolved") return "teal";
  if (status === "mitigated") return "blue";
  if (status === "escalated") return "purple";
  if (status === "closed") return "grey";
  return "amber";
}

/** Map memory_retained + memory_status to a chip. */
function MemoryChip({ retained, status }) {
  if (retained) {
    const s = status || "accepted";
    if (s === "pending") return <span className="badge blue memory-chip">Queued</span>;
    return <span className="badge teal memory-chip"><Check size={10} /> Saved</span>;
  }
  if (status === "failed") return <span className="badge red memory-chip">Failed</span>;
  return <span className="muted">—</span>;
}

/* ─────────────────────────── primitive components ──────────────── */
function Badge({ children, tone = "" }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

/** Auto-focuses on mount when tone==="error" for screen-reader users. */
function Notice({ children, tone = "" }) {
  const ref = useRef(null);
  useEffect(() => {
    if (tone === "error" && ref.current) ref.current.focus();
  }, [tone, children]);
  return (
    <div
      ref={ref}
      tabIndex={tone === "error" ? -1 : undefined}
      role={tone === "error" ? "alert" : "status"}
      aria-live={tone === "error" ? "assertive" : "polite"}
      className={`notice ${tone}`}
    >
      <TriangleAlert size={16} aria-hidden="true" />
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
        {description && <p>{description}</p>}
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
    <div className="busy" role="status" aria-live="polite">
      <Loader2 className="spin" size={22} aria-hidden="true" />
      <div>
        <strong>{text}</strong>
        <p>{sec}s elapsed · Waiting for a verified response. You can keep this tab open.</p>
      </div>
    </div>
  );
}

/* ─────────────────────────── App root ──────────────────────────── */
export default function App() {
  const [page, setPage] = useState("overview");
  const [health, setHealth] = useState(null);
  const [rows, setRows] = useState([]);
  const [rowsError, setRowsError] = useState("");
  const [stats, setStats] = useState(null);
  const [statsError, setStatsError] = useState("");
  const [incident, setIncident] = useState(null);
  const [sample, setSample] = useState(false);
  const [globalError, setGlobalError] = useState("");
  const [connections, setConnections] = useState(null);
  const [checking, setChecking] = useState(false);

  /** Promise.allSettled — a failing stats call never blanks the incident list. */
  async function refresh() {
    const [hRes, rRes, sRes] = await Promise.allSettled([
      get("/health"),
      get("/incidents"),
      get("/memory/stats"),
    ]);
    if (hRes.status === "fulfilled") setHealth(hRes.value);
    if (rRes.status === "fulfilled") { setRows(rRes.value); setRowsError(""); }
    else setRowsError(rRes.reason?.message || "Failed to load incidents.");
    if (sRes.status === "fulfilled") { setStats(sRes.value); setStatsError(""); }
    else setStatsError(sRes.reason?.message || "Failed to load stats.");
  }

  useEffect(() => { refresh(); }, []);

  function navigate(next) { setPage(next); setGlobalError(""); }

  function open(item) { setIncident(item); setSample(false); navigate("workspace"); }
  function fresh() { setIncident(null); setSample(false); navigate("workspace"); }

  async function check() {
    setChecking(true);
    try { setConnections(await get("/connections")); }
    catch (e) { setGlobalError(e.message); }
    finally { setChecking(false); }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => navigate("overview")} aria-label="Command Center overview">
          <span className="brand-mark"><Layers3 size={22} /></span>
          <span>RECALL<span className="brand-sub">INCIDENT COMMAND CENTER</span></span>
        </button>
        <div className="team-box">
          <span className="team-avatar">O</span>
          <div>Operations workspace<small>Single-team workspace</small></div>
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
              <Icon size={18} aria-hidden="true" />
              <span>{label}</span>
              {id === "workspace" && (
                <span className="nav-count" aria-label={`${stats?.active_incidents || 0} active`}>
                  {stats?.active_incidents || 0}
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="memory-mini">
            <Brain size={19} aria-hidden="true" />
            <div>Powered by Hindsight<small>Experience that stays with you.</small></div>
          </div>
          <button className="connection-link" onClick={check} disabled={checking}>
            <Radio size={14} aria-hidden="true" />
            {checking ? "Checking…" : "Check connections"}
            <ArrowUpRight size={14} aria-hidden="true" />
          </button>
          {connections && (
            <p className="connection-status" aria-live="polite">
              Groq: {connections.groq}<br />Hindsight: {connections.hindsight}
            </p>
          )}
          <div className="profile">
            <span className="avatar" aria-hidden="true">OC</span>
            <div>On-call engineer<small>Local workspace</small></div>
            <Badge>v3.1</Badge>
          </div>
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace
            <ChevronRight size={13} aria-hidden="true" />
            <strong>{NAV.find((n) => n[0] === page)?.[1]}</strong>
          </div>
          <div className="topbar-right">
            <span className={`status-dot ${health?.status === "ready" ? "good" : ""}`} aria-hidden="true" />
            <span aria-live="polite">
              {health?.status === "ready" ? "Providers configured" : "Setup required"}
            </span>
            <button className="icon-button" aria-label="Refresh workspace" onClick={refresh}>
              <RefreshCw size={16} aria-hidden="true" />
            </button>
          </div>
        </header>

        <main id="main-content">
          {globalError && <Notice tone="error">{globalError}</Notice>}
          {health?.status === "setup_required" && (
            <Notice>
              Live AI awaits API keys. Add your Groq and Hindsight keys to{" "}
              <code>backend/.env</code>, then restart. The sample walkthrough is available below.
            </Notice>
          )}

          {page === "overview" && (
            <Overview
              health={health}
              rows={rows}
              rowsError={rowsError}
              stats={stats}
              statsError={statsError}
              onOpen={open}
              onNew={fresh}
              onRefresh={refresh}
              onDelete={async (id) => {
                await del(`/incidents/${id}`);
                await refresh();
              }}
              setSample={setSample}
              setIncident={setIncident}
              navigate={navigate}
            />
          )}
          {page === "workspace" && (
            <Workspace
              key={incident?.incident_id || "new"}
              incident={incident}
              sample={sample}
              onSaved={(item) => { setIncident(item); refresh(); }}
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

/* ─────────────────────────── Overview page ─────────────────────── */
function Overview({ health, rows, rowsError, stats, statsError, onOpen, onNew, onRefresh, onDelete, setSample, setIncident, navigate }) {
  const [confirmDelete, setConfirmDelete] = useState(null); // incident_id to confirm

  async function handleDelete(id) {
    await onDelete(id);
    setConfirmDelete(null);
  }

  return (
    <>
      <Heading
        eyebrow="OPERATIONS / OVERVIEW"
        title="Every incident. A little wiser."
        description="Turn your team's past resolutions into a better next step."
      >
        <button className="button primary" onClick={onNew}>
          <Plus size={17} aria-hidden="true" />
          Investigate incident
        </button>
      </Heading>

      <div className="overview-grid">
        <section className="hero-panel">
          <Badge tone="teal"><Brain size={13} aria-hidden="true" /> PERSISTENT OPERATIONAL MEMORY</Badge>
          <h2>
            Your last incident<br />should help solve<br /><span>your next one.</span>
          </h2>
          <p>Recall what happened. Check what still applies.<br />Keep the lesson when the incident ends.</p>
          <div className="hero-actions">
            <button className="button primary" onClick={onNew}>
              Start investigation<ArrowRight size={16} aria-hidden="true" />
            </button>
            <button
              className="text-button"
              onClick={() => {
                setSample(true);
                setIncident({ ...scenarios[0], incident_id: "SAMPLE-ONLY", analysis: sampleAnalysis, updates: [], status: "investigating" });
                navigate("workspace");
              }}
            >
              Sample walkthrough<ArrowUpRight size={15} aria-hidden="true" />
            </button>
          </div>
          <div className="hero-flow" aria-hidden="true">
            <span><Search size={14} />Recall</span>
            <ChevronRight size={14} />
            <span><Brain size={14} />Reason</span>
            <ChevronRight size={14} />
            <span><CheckCircle2 size={14} />Remember</span>
          </div>
        </section>
        <section className="panel memory-panel" aria-label="Operational memory">
          <div className="panel-heading">
            <h3>Operational memory</h3>
            <Brain size={18} aria-hidden="true" />
          </div>
          <div className="memory-orbit" aria-hidden="true">
            <div className="orbit o1" /><div className="orbit o2" />
            <span className="orbit-node n1"><FileText size={17} /></span>
            <span className="orbit-node n2"><Terminal size={17} /></span>
            <span className="orbit-node n3"><Check size={17} /></span>
            <div className="orbit-center"><Brain size={36} /></div>
          </div>
          <div className="memory-caption">
            <strong>Context, connected.</strong>
            <p>Past attempts. Current evidence.<br />A recommendation you can inspect.</p>
          </div>
          <div className="bank-line">
            <span>Hindsight bank</span>
            <code>{health?.bank_id || "Awaiting backend"}</code>
          </div>
        </section>
      </div>

      <div className="metrics-grid" role="region" aria-label="Workspace metrics">
        {[
          [Activity, "Active incidents", stats?.active_incidents, "Awaiting confirmed recovery"],
          [Database, "Memory delivered", stats?.retained_incidents, "Local records saved to Hindsight"],
          [FileText, "Recorded incidents", stats?.total_incidents, "Persisted in this workspace"],
        ].map(([Icon, label, value, note]) => (
          <div className="metric" key={label}>
            <div className="metric-top"><span>{label}</span><Icon size={17} aria-hidden="true" /></div>
            <strong>{value ?? "—"}</strong>
            <small>{note}</small>
          </div>
        ))}
        {statsError && <p className="panel-error" role="alert">{statsError}</p>}
      </div>

      <section className="panel" aria-label="Incident timeline">
        <div className="panel-heading">
          <div>
            <h3>Incident timeline</h3>
            <p>Your investigations and the outcomes they leave behind.</p>
          </div>
          <Badge>{rows.length} records</Badge>
        </div>
        {rowsError && <p className="panel-error" role="alert">{rowsError}</p>}
        {!rowsError && rows.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">INCIDENT</th>
                  <th scope="col">SERVICE</th>
                  <th scope="col">STATUS</th>
                  <th scope="col">MEMORY</th>
                  <th scope="col">REPORTED</th>
                  <th scope="col"><span className="visually-hidden">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <>
                    {confirmDelete === r.incident_id && (
                      <tr key={`confirm-${r.incident_id}`}>
                        <td colSpan={6}>
                          <div className="confirm-bar" role="alertdialog" aria-labelledby={`del-label-${r.incident_id}`}>
                            <span id={`del-label-${r.incident_id}`}>
                              Delete <strong>{r.incident_id}</strong>? This removes the local record and attempts to remove the memory document.
                            </span>
                            <button className="button" style={{background:"#6e3444",borderColor:"#a04060",color:"#ffc8d2"}} onClick={() => handleDelete(r.incident_id)}>
                              Delete
                            </button>
                            <button className="button" onClick={() => setConfirmDelete(null)}>Cancel</button>
                          </div>
                        </td>
                      </tr>
                    )}
                    <tr key={r.incident_id}>
                      <td>
                        <button className="row-link" onClick={() => onOpen(r)}>
                          {r.title}<small>{r.incident_id}</small>
                        </button>
                      </td>
                      <td><Badge>{r.service}</Badge></td>
                      <td>
                        <Badge tone={statusTone(r.status)}>{human(r.status)}</Badge>
                      </td>
                      <td>
                        <MemoryChip retained={r.memory_retained} status={r.memory_status} />
                      </td>
                      <td className="muted">{date(r.timestamp)}</td>
                      <td style={{display:"flex",gap:"4px",alignItems:"center"}}>
                        <button className="icon-button" onClick={() => onOpen(r)} aria-label={`Open ${r.incident_id}`}>
                          <ArrowUpRight size={16} aria-hidden="true" />
                        </button>
                        <button
                          className="icon-button"
                          onClick={() => setConfirmDelete(r.incident_id)}
                          aria-label={`Delete ${r.incident_id}`}
                          style={{color:"#f498a8"}}
                        >
                          <Trash2 size={15} aria-hidden="true" />
                        </button>
                      </td>
                    </tr>
                  </>
                ))}
              </tbody>
            </table>
          </div>
        ) : !rowsError ? (
          <div className="empty-state">
            <Activity size={28} aria-hidden="true" />
            <h3>A fresh start for your incident history.</h3>
            <p>Start an investigation or explore the clearly labelled sample walkthrough.</p>
            <button className="button" onClick={onNew}>Create your first incident<ArrowRight size={15} aria-hidden="true" /></button>
          </div>
        ) : null}
      </section>

      <div className="footer-note">
        <ShieldCheck size={14} aria-hidden="true" />
        Recommendations support your investigation. Changes stay under your control.
      </div>
    </>
  );
}

/* ─────────────────────────── IncidentForm ──────────────────────── */
function IncidentForm({ onSubmit, busy, compare = false, initialForm, initialCRI }) {
  const [form, setForm] = useState(initialForm || EMPTY_FORM);
  // Persist client_request_id across retries; only cleared on successful submit
  const [clientRequestId, setClientRequestId] = useState(initialCRI || null);
  const [measurements, setMeasurements] = useState("");

  function change(e) { setForm({ ...form, [e.target.name]: e.target.value }); }

  function loadScenario(s) {
    // Only set the visible form fields
    const next = { ...EMPTY_FORM };
    for (const f of FORM_FIELDS) if (s[f] !== undefined) next[f] = s[f];
    setForm(next);
    setMeasurements(s.measurements || "");
  }

  function handleSubmit(e) {
    e.preventDefault();
    // Attach existing client_request_id for idempotent retry
    const payload = clientRequestId
      ? { ...form, client_request_id: clientRequestId }
      : { ...form };
    onSubmit(payload, { setClientRequestId });
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h3>{compare ? "One incident. Two perspectives." : "What are you seeing?"}</h3>
          <p>Start with symptoms and measurements. You can add new evidence later.</p>
        </div>
        <Badge>01 / INPUT</Badge>
      </div>
      <div className="scenario-row" role="group" aria-label="Try a synthetic scenario">
        <span>TRY A SYNTHETIC SCENARIO</span>
        {scenarios.map((s) => (
          <button type="button" key={s.name} onClick={() => loadScenario(s)} disabled={busy}>
            {s.name}<ArrowUpRight size={12} aria-hidden="true" />
          </button>
        ))}
      </div>
      <form onSubmit={handleSubmit} className="incident-form" noValidate>
        <label className="full" htmlFor="title">
          Incident title
          <input
            id="title" name="title" value={form.title} onChange={change}
            minLength={5} maxLength={500} required
            placeholder="e.g. Checkout latency spikes during peak traffic"
            aria-required="true"
          />
        </label>
        <label htmlFor="service">
          Service
          <input
            id="service" name="service" value={form.service} onChange={change}
            minLength={2} maxLength={100} required placeholder="payment-api"
            aria-required="true"
          />
        </label>
        <div className="field-pair">
          <label htmlFor="environment">
            Environment
            <select id="environment" name="environment" value={form.environment} onChange={change}>
              <option>production</option>
              <option>staging</option>
              <option>development</option>
            </select>
          </label>
          <label htmlFor="severity">
            Severity
            <select id="severity" name="severity" value={form.severity} onChange={change}>
              <option value="P1">P1 · Critical</option>
              <option value="P2">P2 · High</option>
              <option value="P3">P3 · Medium</option>
              <option value="P4">P4 · Low</option>
            </select>
          </label>
        </div>
        <label className="full" htmlFor="symptoms">
          Symptoms &amp; current measurements
          <textarea
            id="symptoms" name="symptoms" value={form.symptoms} onChange={change}
            minLength={10} maxLength={12000} required rows={4}
            placeholder="What changed? Which requests fail? Include actual measurements and when it started."
            aria-required="true"
          />
        </label>
        <label className="full" htmlFor="error_logs">
          Relevant logs{" "}
          <span className="optional">optional · remove credentials and personal data</span>
          <textarea
            id="error_logs" className="mono" name="error_logs"
            value={form.error_logs} onChange={change}
            maxLength={20000} rows={3}
            placeholder="Paste a short, relevant log excerpt…"
          />
        </label>
        {measurements && (
          <div className="full">
            <label>
              Measurements <span className="optional">from scenario — read only</span>
              <div className="measurements-box" aria-readonly="true">{measurements}</div>
            </label>
          </div>
        )}
        <div className="form-footer full">
          <span><ShieldCheck size={14} aria-hidden="true" />No infrastructure changes are executed.</span>
          <button className="button primary" disabled={busy} type="submit">
            {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Sparkles size={16} aria-hidden="true" />}
            {compare ? "Compare with / without memory" : "Investigate with memory"}
            <ArrowRight size={15} aria-hidden="true" />
          </button>
        </div>
      </form>
    </section>
  );
}

/* ─────────────────────────── Workspace ─────────────────────────── */
function Workspace({ incident, sample, onSaved, onNew }) {
  const [item, setItem] = useState(incident);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [note, setNote] = useState("");
  const [kind, setKind] = useState("evidence");
  const [showOutcome, setShowOutcome] = useState(false);
  // Saved form + client_request_id for retry-safe resubmission
  const [savedForm, setSavedForm] = useState(null);
  const [savedCRI, setSavedCRI] = useState(null);
  const [pendingIncidentId, setPendingIncidentId] = useState(null);

  async function load(id) {
    const updated = await get(`/incidents/${id}`);
    setItem(updated); onSaved(updated);
    return updated;
  }

  async function run(action) {
    setBusy(true); setError(""); setMessage("");
    try { await action(); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function analyze(form, { setClientRequestId } = {}) {
    // Generate a fresh CRI only when there's no existing one (i.e. first attempt)
    let cri = form.client_request_id;
    if (!cri) {
      cri = `cri-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      form = { ...form, client_request_id: cri };
      if (setClientRequestId) setClientRequestId(cri);
    }
    setSavedForm(form);
    setSavedCRI(cri);
    setPendingIncidentId(null);

    await run(async () => {
      const result = await post("/incidents/analyze", form);
      setSavedForm(null); setSavedCRI(null); // clear on success
      await load(result.incident_id);
    });
  }

  async function update() {
    await run(async () => {
      const updated = await post(`/incidents/${item.incident_id}/updates`, { note, kind });
      setItem(updated); onSaved(updated); setNote("");
      setMessage(
        updated.memory_retained
          ? "Update saved locally and in Hindsight. Re-analyze to use the new evidence."
          : "Update saved locally. Hindsight delivery failed; retry memory when connected.",
      );
    });
  }

  // Extract incident_id from error message if it came from a failed analyze
  const errorIncidentMatch = error?.match(/INC-[A-Z0-9]+/);
  const errorIncidentId = errorIncidentMatch ? errorIncidentMatch[0] : null;

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
        {item && <button className="button" onClick={onNew}><Plus size={16} aria-hidden="true" />New incident</button>}
      </Heading>

      {sample && (
        <Notice>
          This is a static, synthetic walkthrough—not live AI or Hindsight output. Start a new incident to run the real integration.
        </Notice>
      )}
      {error && (
        <Notice tone="error">
          {error}
          {errorIncidentId && (
            <>
              {" "}—{" "}
              <button
                className="text-button"
                style={{ display: "inline", padding: "0 4px", fontSize: "inherit", color: "#f1a5b5", textDecoration: "underline" }}
                onClick={async () => { try { await load(errorIncidentId); } catch {} }}
              >
                open {errorIncidentId}
              </button>
            </>
          )}
        </Notice>
      )}
      {message && <Notice>{message}</Notice>}

      {!item && (
        <IncidentForm
          onSubmit={analyze}
          busy={busy}
          initialForm={savedForm}
          initialCRI={savedCRI}
        />
      )}
      {busy && <Busy text={item ? "Saving evidence or requesting a fresh analysis…" : undefined} />}

      {item && (
        <>
          <div className="incident-strip">
            <div>
              <Badge tone="red">{item.severity}</Badge>
              <h2>{item.title}</h2>
            </div>
            <Badge tone={statusTone(item.status)}>{human(item.status)}</Badge>
          </div>

          {!sample && (
            <div className="action-bar" role="toolbar" aria-label="Incident actions">
              <button
                className="button" disabled={busy}
                onClick={() => run(async () => { await post(`/incidents/${item.incident_id}/analyze`); await load(item.incident_id); })}
              >
                <RefreshCw size={15} aria-hidden="true" />Re-analyze current evidence
              </button>
              <button className="button primary" disabled={busy} onClick={() => setShowOutcome(!showOutcome)}>
                <CheckCircle2 size={15} aria-hidden="true" />Record outcome
              </button>
              {/* Reopen button for terminal statuses */}
              {["resolved","mitigated","escalated","closed"].includes(item.status) && (
                <button
                  className="button" disabled={busy}
                  onClick={() => run(async () => {
                    const updated = await post(`/incidents/${item.incident_id}/updates`, {
                      note: "Reopened for further investigation.",
                      kind: "evidence",
                      reopen: true,
                    });
                    setItem(updated); onSaved(updated);
                    setMessage("Incident reopened.");
                  })}
                >
                  <RefreshCw size={15} aria-hidden="true" />Reopen incident
                </button>
              )}
              {(item.outcome || item.updates?.length > 0) && !item.memory_retained && (
                <button
                  className="button" disabled={busy}
                  onClick={() => run(async () => {
                    const r = await post(`/incidents/${item.incident_id}/retry-memory`);
                    setItem(r); onSaved(r);
                    setMessage(r.memory_retained ? "Memory delivered." : "Memory remains pending. Check Hindsight connectivity.");
                  })}
                >
                  Retry memory save
                </button>
              )}
            </div>
          )}

          {showOutcome && !sample && (
            <Outcome
              incidentId={item.incident_id}
              onSaved={async (msg) => { await load(item.incident_id); setMessage(msg); setShowOutcome(false); }}
              onClose={() => setShowOutcome(false)}
            />
          )}

          {a ? (
            <Analysis analysis={a} sample={sample} />
          ) : (
            <Notice>This incident is saved. Re-analyze once your providers are connected.</Notice>
          )}

          {!sample && (
            <div className="workspace-grid">
              <section className="panel">
                <div className="panel-heading">
                  <div><h3>Add what happened next</h3><p>Failed attempts are useful experience too.</p></div>
                  <Plus size={17} aria-hidden="true" />
                </div>
                <div className="panel-body">
                  <label htmlFor="update-kind">Type
                    <select id="update-kind" value={kind} onChange={(e) => setKind(e.target.value)}>
                      <option value="evidence">New evidence</option>
                      <option value="failed_attempt">Attempt that did not work</option>
                    </select>
                  </label>
                  <label htmlFor="update-note">Observation
                    <textarea
                      id="update-note" rows={3} value={note}
                      onChange={(e) => setNote(e.target.value)}
                      placeholder="What did you check or try, and what did you observe?"
                      maxLength={5000}
                    />
                  </label>
                  <button
                    className="button"
                    onClick={update}
                    disabled={busy || note.trim().length < 10}
                    aria-disabled={busy || note.trim().length < 10}
                  >
                    <Brain size={15} aria-hidden="true" />Save evidence to memory
                  </button>
                </div>
              </section>
              <section className="panel">
                <div className="panel-heading">
                  <h3>Investigation history</h3>
                  <Clock3 size={17} aria-hidden="true" />
                </div>
                <div className="panel-body">
                  {item.updates?.length ? (
                    item.updates.map((u, i) => (
                      <div className="timeline-entry" key={i}>
                        <span className="timeline-dot" aria-hidden="true" />
                        <div>
                          <small>{human(u.kind)} · {date(u.timestamp)}</small>
                          <p>{u.note}</p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="muted">No updates yet. Record the next observation so the next engineer can pick up here.</p>
                  )}
                  {item.outcome && (
                    <div className="timeline-entry">
                      <CheckCircle2 size={16} style={{ color: "var(--accent)", flexShrink: 0 }} aria-hidden="true" />
                      <div>
                        <small>{human(item.outcome)}</small>
                        <p>{item.resolution}</p>
                        <MemoryChip retained={item.memory_retained} />
                      </div>
                    </div>
                  )}
                </div>
              </section>
            </div>
          )}
          <details className="panel details">
            <summary>
              <Terminal size={16} aria-hidden="true" />Original incident evidence
            </summary>
            <p>{item.symptoms}</p>
            {item.error_logs && <pre>{item.error_logs}</pre>}
          </details>
        </>
      )}
    </>
  );
}

/* ─────────────────────────── Analysis ──────────────────────────── */
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
              <ShieldCheck size={16} aria-hidden="true" />
              <p>{a.evidence_assessment}</p>
            </div>
            {a.severity_reasoning && (
              <div className="evidence-assessment">
                <Activity size={16} aria-hidden="true" />
                <p>
                  <strong>Severity {a.severity_assessment}:</strong>{" "}
                  {a.severity_reasoning}
                </p>
              </div>
            )}
          </div>
        </section>

        {/* warnings from trim / recall / guardrails */}
        {a.warnings?.length > 0 && (
          <div role="region" aria-label="Analysis warnings">
            {a.warnings.map((w, i) => (
              <Notice key={i}>{w}</Notice>
            ))}
          </div>
        )}

        {/* flagged actions */}
        {a.flagged_actions?.length > 0 && (
          <section className="panel" aria-label="Flagged actions">
            <div className="panel-heading">
              <div className="section-label">
                <span className="number-box"><TriangleAlert size={14} aria-hidden="true" /></span>
                <h3>Flagged actions — verify before executing</h3>
              </div>
              <Badge tone="amber">{a.flagged_actions.length} flagged</Badge>
            </div>
            <div className="panel-body">
              {a.flagged_actions.map((text, i) => (
                <Notice key={i} tone="error">{text}</Notice>
              ))}
            </div>
          </section>
        )}

        <section className="panel">
          <div className="panel-heading">
            <div className="section-label">
              <span className="number-box">02</span>
              <h3>Check this first</h3>
            </div>
            <Search size={17} aria-hidden="true" />
          </div>
          <div className="panel-body">
            <List items={a.investigation_steps} />
          </div>
        </section>

        <section className="panel">
          <div className="panel-heading">
            <h3>What could change this diagnosis?</h3>
            <GitCompareArrows size={17} aria-hidden="true" />
          </div>
          <div className="panel-body">
            <List items={a.disconfirming_checks} />
          </div>
        </section>

        <details className="panel details" open={compact || undefined}>
          <summary>
            Conditional remediation &amp; recovery
            <ChevronRight size={16} aria-hidden="true" />
          </summary>
          <List items={a.recommended_actions} />
          <h4>Verify recovery</h4>
          <List items={a.verification_steps} />
          {a.risk_notes && <Notice>{a.risk_notes}</Notice>}
        </details>
      </div>

      <aside className="evidence-column">
        <section className="panel evidence-panel" aria-label="Memory behind the answer">
          <div className="panel-heading">
            <div className="section-label">
              <Brain size={18} aria-hidden="true" />
              <h3>Memory behind the answer</h3>
            </div>
          </div>
          <div className="panel-body">
            <Badge tone={a.used_memory ? "teal" : "amber"}>
              {sample ? "Illustrative memory" : human(a.memory_status)}
            </Badge>
            <p className="muted">
              {a.used_memory
                ? "Historical context influenced this hypothesis. Verify it against today's evidence."
                : "No historical source was cited in this recommendation."}
            </p>
            {a.memory_insights?.length > 0 && (
              <div className="memory-delta">
                <div className="eyebrow">WHAT MEMORY CHANGED</div>
                {a.memory_insights.map((x, i) => <p key={i}>{x}</p>)}
              </div>
            )}
            {a.historical_evidence?.map((x, i) => (
              <p className="evidence-claim" key={i}>
                <span aria-hidden="true">↳</span>{x}
              </p>
            ))}
            <div className="source-label" aria-label={`${a.historical_incidents?.length || 0} retrieved memory fragments`}>
              {a.historical_incidents?.length || 0} RETRIEVED MEMORY FRAGMENTS
            </div>
            {a.historical_incidents?.map((m, i) => (
              <details className="source-card" key={m.source_id || i}>
                <summary>
                  <FileText size={15} aria-hidden="true" />
                  <span>
                    Source {i + 1}
                    <small>
                      {a.cited_sources?.includes(m.source_id)
                        ? "Cited in analysis"
                        : "Retrieved context"}
                    </small>
                  </span>
                  <ChevronRight size={14} aria-hidden="true" />
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
        {!sample && a.timings_ms && Object.keys(a.timings_ms).length > 0 && (
          <div className="timings" aria-label="Timing breakdown">
            <Clock3 size={14} aria-hidden="true" />
            <span>Recall {(a.timings_ms.recall / 1000).toFixed(1)}s</span>
            <span>Model {(a.timings_ms.model / 1000).toFixed(1)}s</span>
            <strong>{(a.timings_ms.total / 1000).toFixed(1)}s total</strong>
          </div>
        )}
      </aside>
    </div>
  );
}

/* ─────────────────────────── Outcome form ──────────────────────── */
function Outcome({ incidentId, onSaved, onClose }) {
  const [form, setForm] = useState({
    outcome: "successfully_resolved",
    root_cause: "",
    resolution: "",
    actions_taken: "",
    lessons_learned: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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
    <section className="panel outcome-panel" aria-label="Record outcome">
      <div className="panel-heading">
        <div>
          <h3>Record the outcome</h3>
          <p>Save what actually happened, including partial or unsuccessful fixes.</p>
        </div>
        <button className="icon-button" onClick={onClose} aria-label="Close outcome form">
          <X size={17} aria-hidden="true" />
        </button>
      </div>
      <form className="incident-form" onSubmit={save} noValidate>
        {error && <div className="full"><Notice tone="error">{error}</Notice></div>}
        <label className="full" htmlFor="outcome-select">
          Outcome
          <select
            id="outcome-select"
            value={form.outcome}
            onChange={(e) => setForm({ ...form, outcome: e.target.value })}
          >
            <option value="successfully_resolved">Resolved — recovery verified</option>
            <option value="partially_resolved">Mitigated — issue remains</option>
            <option value="unresolved_escalated">Unresolved — escalated</option>
          </select>
        </label>
        {[
          ["root_cause", "Confirmed cause or remaining uncertainty", true],
          ["resolution", "Result observed", true],
          ["actions_taken", "Actions taken (one per line)", true],
          ["lessons_learned", "Lesson for the next incident (optional)", false],
        ].map(([key, labelText, required]) => (
          <label key={key} htmlFor={`outcome-${key}`}>
            {labelText}
            <textarea
              id={`outcome-${key}`}
              value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              minLength={required ? 10 : undefined}
              required={required}
              aria-required={required}
              rows={3}
            />
          </label>
        ))}
        <div className="form-footer full">
          <span>Outcome stays local if memory delivery fails.</span>
          <button className="button primary" disabled={busy} type="submit">
            {busy
              ? <Loader2 className="spin" size={16} aria-hidden="true" />
              : <Brain size={16} aria-hidden="true" />}
            Save outcome &amp; remember
          </button>
        </div>
      </form>
    </section>
  );
}

/* ─────────────────────────── Comparison page ───────────────────── */
function Comparison() {
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(form) {
    setBusy(true); setError(""); setResult(null);
    try {
      // Strip client_request_id — comparison is never idempotency-keyed
      const { client_request_id: _cri, ...incident } = form;
      setResult(await post("/incidents/compare", { incident }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const diffKeys = result ? Object.keys(result.differences || {}) : [];

  return (
    <>
      <Heading
        eyebrow="MEMORY / CONTROLLED COMPARISON"
        title="See the difference memory makes."
        description="Same incident. Both runs use temperature 0 for consistency. Results can still vary between runs — use this as directional evidence, not a reproducible benchmark."
      />
      <details className="panel details" open={!result}>
        <summary>
          Incident input — edit and run comparison
          <ChevronRight size={16} aria-hidden="true" />
        </summary>
        <IncidentForm compare onSubmit={run} busy={busy} />
      </details>
      {busy && <Busy text="Running both analyses concurrently…" />}
      {error && <Notice tone="error">{error}</Notice>}
      {result && (
        <>
          {diffKeys.length > 0 && (
            <section className="panel" aria-label="Where memory changed the answer">
              <div className="panel-heading">
                <div>
                  <h3>Where memory changed the answer</h3>
                  <p>Fields where the two analyses produced different output.</p>
                </div>
                <Badge tone="teal">
                  {diffKeys.length} difference{diffKeys.length !== 1 ? "s" : ""}
                </Badge>
              </div>
              <div className="panel-body">
                {diffKeys.map((field) => (
                  <div className="diff-row" key={field}>
                    <code>{field}</code>
                    <div className="diff-values">
                      <span className="muted">Without:</span>
                      <p>{JSON.stringify(result.differences[field].without_memory)}</p>
                      <span className="muted">With memory:</span>
                      <p>{JSON.stringify(result.differences[field].with_memory)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
          {diffKeys.length === 0 && (
            <Notice>
              Both analyses produced identical key fields. Memory did not change the diagnosis this time.
            </Notice>
          )}
          <div className="comparison-grid">
            {[
              ["without_memory", "Current evidence only", ""],
              ["with_memory", "With operational memory", "teal"],
            ].map(([key, title, tone]) => (
              <section key={key} aria-label={title}>
                <div className="comparison-title">
                  <h2>{title}</h2>
                  <Badge tone={tone}>
                    {key === "with_memory" ? "Hindsight enabled" : "Baseline"}
                  </Badge>
                </div>
                <Analysis compact analysis={result[key]} />
              </section>
            ))}
          </div>
        </>
      )}
    </>
  );
}

/* ─────────────────────────── Memory explorer ───────────────────── */
function Memory({ reflection }) {
  const [query, setQuery] = useState(
    reflection
      ? "Which incident resolutions failed, and what evidence should we check before reusing an old fix?"
      : "",
  );
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError(""); setData(null);
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
        title={reflection ? "Make experience useful." : "Find the context worth keeping."}
        description={
          reflection
            ? "Reflect across recorded incidents to identify patterns, failures and open questions."
            : "Search persistent operational memory. Results are evidence fragments, not incident counts."
        }
      />
      <section className="panel">
        <form className="search-form" onSubmit={submit}>
          <label htmlFor="memory-query">
            {reflection ? "What would you like to learn?" : "Search your operational history"}
            <textarea
              id="memory-query"
              rows={2}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              minLength={reflection ? 10 : 5}
              maxLength={3000}
              required
              aria-required="true"
              placeholder="e.g. Failed Redis fixes in the payment service"
            />
          </label>
          <button className="button primary" disabled={busy} type="submit">
            {reflection
              ? <><Sparkles size={16} aria-hidden="true" />Reflect on memory</>
              : <><Search size={16} aria-hidden="true" />Search memory</>}
          </button>
        </form>
      </section>

      {busy && (
        <Busy text={reflection ? "Reflecting across retained evidence…" : "Retrieving matching memories…"} />
      )}
      {error && <Notice tone="error">{error}</Notice>}
      {data && (
        reflection ? (
          <section className="panel">
            <div className="panel-heading">
              <h3>Reflection</h3>
              <Badge tone="amber">Review against source records</Badge>
            </div>
            <div className="panel-body reflection-text">{data.reflection}</div>
          </section>
        ) : (
          <>
            <div className="result-count" aria-live="polite">
              {data.count} memory fragments retrieved
            </div>
            {data.memories.length ? (
              data.memories.map((m, i) => (
                <section className="panel memory-result" key={m.source_id || i} aria-label={`Memory ${i + 1}`}>
                  <div className="panel-heading">
                    <div className="section-label">
                      <FileText size={16} aria-hidden="true" />
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
                <Search size={26} aria-hidden="true" />
                <h3>No matching memories.</h3>
                <p>Try a different query, or record an incident outcome first.</p>
              </div>
            )}
          </>
        )
      )}
    </>
  );
}
