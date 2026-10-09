import { useEffect, useMemo, useRef, useState } from "react";
import { BrowserRouter, useLocation, useNavigate } from "react-router-dom";
import { Activity, BookOpen, Check, ChevronRight, Clipboard, Download, FileText, FolderOpen, Home, Lightbulb, LoaderCircle, MessageSquare, Plus, Search, Settings, Sparkles, Trash2, Upload, X } from "lucide-react";
import { deleteReport, exportReport, generateReport, getAuthToken, getCurrentUser, listReports, logout, readReport, saveReport, submitFeedback, uploadPdf } from "./services/api";
import AuthScreen from "./pages/AuthScreen";

const agents = ["Planner", "Researcher", "Analyst", "Verifier", "Writer", "Reviewer"];
const reportTypes = ["Academic / Research Report", "Business / Professional Report", "General Information Report", "Project / Technical Report"];
const nav = [
  { id: "home", label: "Overview", icon: Home },
  { id: "setup", label: "New research", icon: Plus },
  { id: "reports", label: "My reports", icon: FolderOpen },
  { id: "sources", label: "Sources & evidence", icon: BookOpen },
  { id: "insights", label: "Research insights", icon: Lightbulb },
  { id: "feedback", label: "Feedback", icon: MessageSquare },
];

function App() {
  return <BrowserRouter><AuthenticationGate/></BrowserRouter>;
}

function AuthenticationGate() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(Boolean(getAuthToken()));

  useEffect(() => {
    let active = true;
    const onExpired = () => {
      setUser(null);
      setChecking(false);
    };
    window.addEventListener("auth-expired", onExpired);
    if (getAuthToken()) {
      getCurrentUser()
        .then((currentUser) => { if (active) setUser(currentUser); })
        .catch(() => { if (active) setUser(null); })
        .finally(() => { if (active) setChecking(false); });
    }
    return () => {
      active = false;
      window.removeEventListener("auth-expired", onExpired);
    };
  }, []);

  const onAuthenticated = (authenticatedUser) => {
    setUser(authenticatedUser);
    navigate("/");
  };
  const onLogout = async () => {
    try { await logout(); }
    finally { setUser(null); navigate("/"); }
  };

  if (checking && pathname !== "/reset-password") {
    return <main className="auth-page"><p className="auth-loading">Checking your session…</p></main>;
  }
  if (!user || pathname === "/reset-password") {
    return <AuthScreen onAuthenticated={onAuthenticated}/>;
  }
  return <Workspace user={user} onLogout={onLogout}/>;
}

function Workspace({ user, onLogout }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const page = pathname.slice(1) || "home";
  const setPage = (nextPage) => navigate(nextPage === "home" ? "/" : `/${nextPage}`);
  const [topic, setTopic] = useState("");
  const [reportType, setReportType] = useState(reportTypes[0]);
  const [result, setResult] = useState(null);
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [runProgress, setRunProgress] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [history, setHistory] = useState([]);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [rating, setRating] = useState(5);
  const [comments, setComments] = useState("");
  const [fontScale, setFontScale] = useState(() => {
    const savedScale = Number(localStorage.getItem("atlas_font_scale"));
    return Number.isFinite(savedScale) && savedScale >= 80 && savedScale <= 160 ? savedScale : 100;
  });
  const inputRef = useRef(null);

  useEffect(() => {
    document.documentElement.style.setProperty("--font-scale", String(fontScale / 100));
    localStorage.setItem("atlas_font_scale", String(fontScale));
  }, [fontScale]);

  useEffect(() => {
    const showError = (event) => setError(event.detail || "The request failed.");
    window.addEventListener("app-error", showError);
    return () => window.removeEventListener("app-error", showError);
  }, []);

  const refreshHistory = async () => {
    try { setHistory(await listReports()); } catch { /* Keep the workspace usable when history is unavailable. */ }
  };
  useEffect(() => {
    listReports().then(setHistory).catch(() => {});
  }, []);

  const completedAgents = useMemo(() => new Set((result?.agent_runs || []).filter((run) => run.status === "completed").map((run) => run.agent_name)), [result]);
  const handleGenerate = async (event) => {
    event?.preventDefault();
    if (!topic.trim()) { setError("Add a research topic to continue."); setPage("setup"); return; }
    setLoading(true); setRunProgress({ status: "running", agents: agents.map((agent_name) => ({ agent_name, status: "pending" })) }); setError(""); setNotice(""); setResult(null); setEditing(false);
    try {
      const report = await generateReport(topic.trim(), reportType, setRunProgress);
      setResult(report); setDraft(report.report || ""); setPage("workspace");
      setNotice("Research report generated and saved to My reports.");
      await refreshHistory();
    } catch (err) { setError(err.message || "Report generation failed."); }
    finally { setLoading(false); }
  };
  const chooseFile = (next) => {
    const selected = next?.[0];
    if (!selected) return;
    if (selected.type !== "application/pdf" && !selected.name.toLowerCase().endsWith(".pdf")) { setError("Choose a PDF file."); return; }
    setError(""); setUploadResult(null); setFile(selected);
  };
  const handleUpload = async () => {
    if (!file) return;
    setUploading(true); setError(""); setUploadResult(null);
    try { setUploadResult(await uploadPdf(file)); }
    catch (err) { setError(err.message || "PDF processing failed."); }
    finally { setUploading(false); }
  };
  const openReport = async (id) => {
    try { const report = await readReport(id); setResult(report); setDraft(report.report || ""); setTopic(report.topic); setReportType(report.report_type); setPage("workspace"); setError(""); }
    catch (err) { setError(err.message); }
  };
  const saveDraft = async () => {
    if (!result?.id) { setResult({ ...result, report: draft }); setEditing(false); return; }
    try { const saved = await saveReport(result.id, draft); setResult(saved); setEditing(false); setNotice("Changes saved."); await refreshHistory(); }
    catch (err) { setError(err.message); }
  };
  const removeReport = async (id) => {
    try { await deleteReport(id); if (result?.id === id) setResult(null); await refreshHistory(); }
    catch (err) { setError(err.message); }
  };
  const copyReport = async () => {
    try { await navigator.clipboard.writeText(draft || result?.report || ""); setNotice("Report copied to clipboard."); }
    catch { setError("Clipboard access was blocked by the browser."); }
  };

  const currentTitle = result?.topic || "Your research workspace";
  return <div className="shell">
    <aside className="sidebar">
      <button className="brand" onClick={() => setPage("home")}><span className="brand-mark"><Sparkles size={18}/></span><span>Atlas<span className="brand-muted"> Research</span></span></button>
      <div className="workspace-label">WORKSPACE</div>
      <nav>{nav.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${page === id || (id === "setup" && page === "workspace") ? "active" : ""}`} onClick={() => { setPage(id); setError(""); }}><Icon size={17}/><span>{label}</span>{id === "reports" && history.length > 0 && <small>{history.length}</small>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="quota-card"><span className="status-dot"/><div><strong>Research engine</strong><small>Mock AI mode enabled</small></div></div><button className="nav-item" onClick={() => setPage("settings")}><Settings size={17}/>Settings</button><div className="profile"><div className="avatar">{user.email.slice(0, 1).toUpperCase()}</div><div className="profile-details"><strong>{user.email}</strong><small>Signed in</small></div><button className="signout-button" onClick={onLogout} title="Sign out">Sign out</button></div></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div className="breadcrumb">Workspace <ChevronRight size={14}/><span>{page === "workspace" ? "Report workspace" : nav.find((item) => item.id === page)?.label || "Settings"}</span></div><div className="top-actions"><div className="font-size-controls" role="group" aria-label="Font size controls"><button type="button" aria-label="Decrease font size" title="Decrease font size" disabled={fontScale <= 80} onClick={() => setFontScale((size) => Math.max(80, size - 10))}>A−</button><span aria-live="polite">{fontScale}%</span><button type="button" aria-label="Increase font size" title="Increase font size" disabled={fontScale >= 160} onClick={() => setFontScale((size) => Math.min(160, size + 10))}>A+</button></div><span className="mode-pill"><span className="status-dot"/> Development mode</span><button className="icon-button" title="Settings" onClick={() => setPage("settings")}><Settings size={17}/></button></div></header>
      <div className="content">
        {(error || notice) && <div className={error ? "alert error-alert" : "alert success-alert"}>{error || notice}<button onClick={() => { setError(""); setNotice(""); }}><X size={15}/></button></div>}
        {page === "home" && <>
          <div className="welcome-row"><div><div className="eyebrow"><span className="eyebrow-line"/> AUTONOMOUS RESEARCH WORKSPACE</div><h1>Turn a question into <span className="gradient-text">clear insight.</span></h1><p>Coordinate research agents, ground findings in evidence, and create a report you can refine and share.</p></div><div className="welcome-icon"><Sparkles size={24}/></div></div>
          <section className="hero-card"><div className="hero-glow"/><div className="hero-copy"><div className="eyebrow light">START A RESEARCH RUN</div><h2>What would you like to understand?</h2><p>Choose a topic and report style. Add your own PDF as supporting evidence.</p><form onSubmit={(e) => { setPage("setup"); handleGenerate(e); }}><div className="hero-input-wrap"><Search size={18}/><input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. How AI is changing healthcare diagnostics"/><button className="primary-button" disabled={loading}>{loading ? <LoaderCircle className="spin" size={16}/> : <Sparkles size={16}/>} {loading ? "Working" : "Start research"}</button></div></form><div className="hero-foot"><span><Check size={14}/> Six-agent workflow</span><span><Check size={14}/> Source-aware reports</span><span><Check size={14}/> PDF evidence support</span></div></div></section>
          <div className="section-heading"><div><h2>Workspace snapshot</h2><p>Your recent research activity at a glance.</p></div><button className="text-button" onClick={() => setPage("reports")}>View reports <ChevronRight size={15}/></button></div>
          <div className="stat-grid"><Stat icon={FileText} label="Reports created" value={history.length}/><Stat icon={BookOpen} label="Evidence sources" value={result?.sources?.length ?? "—"}/><Stat icon={Activity} label="Agents per run" value="6"/><Stat icon={Check} label="Latest status" value={history[0]?.status || "Ready"}/></div>
          <div className="section-heading recent-heading"><div><h2>Recent reports</h2><p>Pick up where your research left off.</p></div></div><ReportList rows={history.slice(0, 3)} onOpen={openReport} onDelete={removeReport} onDownload={(id) => exportReport(id, "pdf")}/>
        </>}
        {page === "setup" && <>
          <PageTitle eyebrow="REPORT SETUP" title="Set up your research" description="Give the agent team a focused question and the context it needs."/>
          <div className="setup-grid"><section className="panel setup-form"><label className="field-label" htmlFor="topic">Research topic</label><textarea id="topic" rows="4" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Describe the question, problem, or subject you want to explore…"/><div className="field-hint">A specific question helps the agents produce a more focused report.</div><label className="field-label" htmlFor="report-type">Report format</label><select id="report-type" value={reportType} onChange={(e) => setReportType(e.target.value)}>{reportTypes.map((type) => <option key={type}>{type}</option>)}</select><div className="field-hint">The planner and writer adapt the outline to this format.</div><div className="form-divider"/><div className="section-mini-title">Knowledge sources</div><p className="muted-copy">Upload a PDF to add its pages to the evidence store for this and future runs.</p><div className="dropzone" onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); chooseFile(e.dataTransfer.files); }} onClick={() => inputRef.current?.click()}><input ref={inputRef} type="file" accept="application/pdf,.pdf" hidden onChange={(e) => chooseFile(e.target.files)}/><div className="drop-icon"><Upload size={19}/></div><strong>{file?.name || "Drop a PDF here or browse files"}</strong><span>PDF document · Up to 20 MB</span></div>{file && <div className="file-row"><FileText size={16}/><span>{file.name}</span><button onClick={() => { setFile(null); setUploadResult(null); }} aria-label="Remove file"><X size={15}/></button></div>}{uploadResult && <div className="upload-success"><Check size={15}/>{uploadResult.filename}: {uploadResult.chunks_created} chunks · {uploadResult.embedding_mode === "lexical_fallback" ? "offline keyword fallback" : "semantic index"}</div>}<div className="form-actions">{file && !uploadResult && <button className="secondary-button" onClick={handleUpload} disabled={uploading}>{uploading ? <><LoaderCircle size={15} className="spin"/> Processing PDF</> : <><Upload size={15}/> Upload & process</>}</button>}<button className="primary-button" onClick={handleGenerate} disabled={loading}>{loading ? <><LoaderCircle size={16} className="spin"/> Agents working</> : <><Sparkles size={16}/> Generate report</>}</button></div></section><aside className="panel workflow-panel"><div className="section-mini-title">Six agents. One research flow.</div><p className="muted-copy">Each stage contributes a distinct part of the final report.</p>{agents.map((agent, i) => <div className="workflow-step" key={agent}><div className="step-number">{i + 1}</div><div><strong>{agent}</strong><small>{["Builds a question-led outline", "Collects relevant evidence", "Finds patterns and limitations", "Checks claims against evidence", "Writes the structured report", "Reviews clarity and citations"][i]}</small></div><ChevronRight size={15}/></div>)}</aside></div>
          {(loading || runProgress?.status === "failed") && <div className="progress-panel"><div className="section-mini-title">{runProgress?.status === "failed" ? "Agent progress · run failed" : "Live agent progress"}</div><div className="progress-agent-grid">{agents.map((agent) => { const status = runProgress?.agents?.find((item) => item.agent_name === agent)?.status || "pending"; return <div className="progress-agent" key={agent}><span className={`progress-state ${status}`}>{status === "completed" ? <Check size={12}/> : status === "running" ? <LoaderCircle size={12} className="spin"/> : status === "failed" ? <X size={12}/> : "·"}</span><span>{agent}</span><small>{status[0].toUpperCase() + status.slice(1)}</small></div>; })}</div></div>}
        </>}
        {page === "workspace" && <>
          <div className="report-head"><div><div className="eyebrow"><span className="eyebrow-line"/> REPORT WORKSPACE</div><h1>{currentTitle}</h1><p>{result?.report_type || reportType}<span className="dot-sep">·</span>{result?.created_at ? new Date(result.created_at).toLocaleString() : "Just generated"}</p></div><span className="review-badge"><Check size={14}/> {result?.verification_status || "Reviewed"}</span></div>
          <div className="workspace-tabs"><button className={page === "workspace" ? "selected" : ""}><FileText size={15}/> Report</button><button onClick={() => setPage("sources")}><BookOpen size={15}/> Sources <span>{result?.sources?.length || 0}</span></button><button onClick={() => setPage("insights")}><Lightbulb size={15}/> Insights</button></div>
          <section className="report-paper"><div className="paper-topline"><span className="paper-type">{result?.report_type || reportType}</span><div className="paper-actions">{editing ? <><button className="secondary-button compact" onClick={() => { setDraft(result?.report || ""); setEditing(false); }}>Cancel</button><button className="primary-button compact" onClick={saveDraft}><Check size={14}/> Save changes</button></> : <><button className="secondary-button compact" onClick={() => setEditing(true)}>Edit</button><button className="secondary-button compact" onClick={handleGenerate}><Sparkles size={14}/> Regenerate</button><button className="icon-button" onClick={copyReport} title="Copy"><Clipboard size={16}/></button><div className="export-menu"><button className="secondary-button compact"><Download size={14}/> Export</button><div className="export-options">{[["PDF", "pdf"], ["Word", "docx"], ["Markdown", "md"]].map(([label, format]) => <button key={format} onClick={() => result?.id ? exportReport(result.id, format) : setError("Generate and save the report before exporting.")}>{label}</button>)}</div></div></>}</div></div>{editing ? <textarea className="report-editor" value={draft} onChange={(e) => setDraft(e.target.value)}/> : <article className="report-body">{draft || "The report content will appear here."}</article>}<div className="paper-footer"><span><Check size={14}/> Verification stage completed</span><span>{result?.sources?.length || 0} cited sources</span></div></section>
          <div className="section-heading"><div><h2>Agent run</h2><p>Stages reported by the backend for this completed run.</p></div><button className="text-button" onClick={() => setPage("insights")}>View insights <ChevronRight size={15}/></button></div><div className="agent-grid">{agents.map((agent) => <div className="agent-chip" key={agent}><span className={`agent-check ${completedAgents.has(agent) ? "done" : "pending"}`}>{completedAgents.has(agent) ? <Check size={12}/> : "·"}</span><span>{agent}</span><small>{completedAgents.has(agent) ? "Completed" : result ? "Not reported" : "Pending"}</small></div>)}</div>
        </>}
        {page === "reports" && <><PageTitle eyebrow="LIBRARY" title="My reports" description="Your research runs are saved locally and remain available after a restart."/><ReportList rows={history} onOpen={openReport} onDelete={removeReport} emptyAction={() => setPage("setup")}/></>}
        {page === "sources" && <><PageTitle eyebrow="EVIDENCE LIBRARY" title="Sources & evidence" description={result ? `Evidence attached to “${result.topic}”.` : "Open a report to inspect its sources and evidence."}/><SourceList sources={result?.sources || []}/></>}
        {page === "insights" && <><PageTitle eyebrow="RESEARCH ANALYTICS" title="Research insights" description={result ? `A summary of the research behind “${result.topic}”.` : "Generate or open a report to explore its research signals."}/><div className="insight-grid"><Stat icon={BookOpen} label="Sources found" value={result?.sources?.length ?? 0}/><Stat icon={FileText} label="Evidence chunks" value={result?.quality?.evidence_count ?? 0}/><Stat icon={Check} label="Verified claims" value={result?.quality?.verified_claims ?? 0}/><Stat icon={Activity} label="Reviewer score" value={result?.reviewer_score ?? "—"}/></div><div className="distribution-row"><strong>Evidence distribution</strong><span>{result?.sources?.filter((source) => source.source_type === "web").length || 0} web</span><span>{result?.sources?.filter((source) => source.source_type === "user_document").length || 0} uploaded PDF</span><span>Coverage {Math.round((result?.quality?.evidence_coverage || 0) * 100)}%</span></div><div className="insight-columns"><section className="panel"><div className="section-mini-title">Research questions & plan</div><pre className="insight-text">{result?.plan || "Your planner's research questions and outline will appear here when a report is open."}</pre></section><section className="panel"><div className="section-mini-title">Key findings & themes</div><pre className="insight-text">{result?.analysis || "The analyst's themes and findings will appear here."}</pre></section></div><section className="panel verification-panel"><div className="section-mini-title">Evidence verification</div><pre className="insight-text">{result?.verification || "Verification notes will appear here with the report."}</pre></section></>}
        {page === "settings" && <><PageTitle eyebrow="PREFERENCES" title="Settings" description="Local development configuration for this project."/><section className="panel settings-panel"><div><strong>AI generation mode</strong><p>Mock mode is active for development, so report generation does not consume Gemini quota.</p></div><span className="mode-pill"><span className="status-dot"/> Mock AI</span><div className="settings-divider"/><div><strong>Evidence index</strong><p>Uploaded PDF evidence is indexed for the lifetime of the running API process. Uploaded document metadata is saved locally.</p></div></section><section className="panel feedback-panel"><MessageSquare size={18}/><div><strong>Feedback notifications</strong><p>Feedback messages are emailed to the configured inbox when SMTP delivery is enabled.</p></div></section></>}
        {page === "feedback" && <><PageTitle eyebrow="FEEDBACK" title="Help improve the reports" description="Share how useful this report was. Feedback is emailed to the configured inbox and saved in the project database."/><section className="panel feedback-form"><label className="field-label">How would you rate this experience?</label><div className="rating-picker">{[1,2,3,4,5].map((score) => <button key={score} className={rating === score ? "picked" : ""} onClick={() => setRating(score)}>{score}</button>)}</div><label className="field-label" htmlFor="feedback-comments">Comments</label><textarea id="feedback-comments" rows="5" value={comments} onChange={(e) => setComments(e.target.value)} placeholder="What worked well, or what should be improved?"/><button className="primary-button" onClick={async () => { try { await submitFeedback({ report_id: result?.id || null, rating, comments }); setComments(""); setNotice("Thanks, your feedback was emailed and saved."); } catch (err) { setError(err.message); } }}><MessageSquare size={15}/> Send feedback</button></section></>}
        {loading && <div className="running-banner"><span className="pulse-dot"/><div><strong>Research run in progress</strong><small>The backend is executing the agent pipeline. Stage completion will be shown when returned.</small></div><LoaderCircle size={17} className="spin"/></div>}
        <footer className="footer"><span>Atlas Research <span className="footer-dot">·</span> Multi-agent report studio</span><span>Local workspace</span></footer>
      </div>
    </main>
  </div>;
}

function PageTitle({ eyebrow, title, description }) { return <div className="page-title"><div className="eyebrow"><span className="eyebrow-line"/> {eyebrow}</div><h1>{title}</h1><p>{description}</p></div>; }
function Stat({ icon: Icon, label, value }) { return <div className="stat-card"><div className="stat-icon"><Icon size={17}/></div><div><div className="stat-value">{value}</div><div className="stat-label">{label}</div></div></div>; }
function ReportList({ rows, onOpen, onDelete, onDownload, emptyAction }) { return rows.length ? <div className="report-list">{rows.map((row) => <div className="report-row" key={row.id}><div className="report-file-icon"><FileText size={18}/></div><div className="report-row-main"><strong>{row.topic}</strong><span>{row.report_type}</span></div><span className="report-date">{row.created_at ? new Date(row.created_at).toLocaleDateString() : "—"}</span><span className="table-status"><span className="status-dot"/>{row.status}</span><button className="secondary-button compact" onClick={() => onOpen(row.id)}>Open</button><button className="icon-button" title="Download PDF" onClick={() => onDownload?.(row.id)}><Download size={15}/></button><button className="icon-button danger-icon" title="Delete report" onClick={() => onDelete(row.id)}><Trash2 size={15}/></button></div>)}</div> : <div className="empty-state"><div className="empty-icon"><FileText size={22}/></div><strong>No reports yet</strong><p>Your completed research reports will be saved here.</p>{emptyAction && <button className="primary-button" onClick={emptyAction}><Plus size={15}/> Create a report</button>}</div>; }
function SourceList({ sources }) { return sources.length ? <div className="source-list">{sources.map((source) => <article className="source-card" key={source.id}><div className="source-top"><span className={`source-type ${source.source_type === "web" ? "web" : "pdf"}`}>{source.source_type === "web" ? "WEB" : "PDF"}</span><strong>{source.id}</strong>{source.score != null && <span className="source-score">Relevance {Number(source.score).toFixed(2)}</span>}</div><h3>{source.title || source.filename || "Evidence source"}</h3>{source.url && <a href={source.url} target="_blank" rel="noreferrer">{source.url}</a>}{source.page && <span className="page-label">Page {source.page}</span>}<p>{source.content}</p></article>)}</div> : <div className="empty-state"><div className="empty-icon"><BookOpen size={22}/></div><strong>No evidence sources for this report</strong><p>Web search may be unavailable, or no PDF has been uploaded. The report does not invent source citations.</p></div>; }

export default App;
