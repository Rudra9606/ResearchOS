"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

// The API has several polymorphic response records; individual views narrow fields as they render.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Item = Record<string, any>;
type Project = Item & { id: string; title: string; research_topic: string; status?: string };
type Tab = "overview" | "projects" | "research" | "library" | "evidence" | "reports" | "history";
type GraphData = { nodes: Item[]; edges: Item[] };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/${path.replace(/^\//, "")}`, { ...init, cache: "no-store" });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { const data = await response.clone().json(); message = data.detail || data.message || message; } catch { /* file or empty response */ }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  const type = response.headers.get("content-type") || "";
  return (type.includes("json") ? response.json() : response.blob()) as Promise<T>;
}

function idOf(value: Item) { return value.id || value.research_run_id || ""; }
function dateOf(value?: string) { return value ? new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "—"; }
function initials(value = "Researcher") { return value.trim().split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase(); }

function EvidenceGraph({ graph }: { graph: GraphData }) {
  const claims = graph.nodes.filter((node) => node.kind === "claim");
  const sources = graph.nodes.filter((node) => node.kind === "source");
  const height = Math.max(210, Math.max(claims.length, sources.length) * 68 + 30);
  const points = new Map<string, { x: number; y: number }>();
  claims.forEach((node, index) => points.set(node.id, { x: 180, y: 35 + index * ((height - 60) / Math.max(1, claims.length - 1)) }));
  sources.forEach((node, index) => points.set(node.id, { x: 620, y: 35 + index * ((height - 60) / Math.max(1, sources.length - 1)) }));
  return <div className="graph-wrap"><div className="graph-legend"><span><i className="legend-claim"/> Verified claim</span><span><i className="legend-source"/> Research source</span><span><i className="legend-edge"/> Explicit evidence reference</span></div>{!claims.length && !sources.length ? <p className="list-empty">Graph nodes are created from persisted sources and claims after research runs.</p> : <svg className="evidence-graph" viewBox={`0 0 800 ${height}`} role="img" aria-label={`Evidence graph with ${claims.length} claims, ${sources.length} sources, and ${graph.edges.length} evidence links`}><defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#93aa97"/></marker></defs>{graph.edges.map((edge) => { const from = points.get(edge.source); const to = points.get(edge.target); return from && to ? <path key={edge.id} d={`M ${from.x + 8} ${from.y} C 330 ${from.y}, 470 ${to.y}, ${to.x - 8} ${to.y}`} fill="none" stroke={edge.relation === "contradicted" ? "#c47b69" : "#93aa97"} strokeWidth="1.5" markerEnd="url(#arrow)"/> : null; })}{graph.nodes.map((node) => { const point = points.get(node.id); if (!point) return null; const isClaim = node.kind === "claim"; const label = String(node.label || ""); return <g key={node.id}><circle cx={point.x} cy={point.y} r="7" fill={isClaim ? (node.status === "contradicted" ? "#c47b69" : "#4d8261") : "#6888a4"}/><text x={point.x + (isClaim ? -17 : 17)} y={point.y - 8} textAnchor={isClaim ? "end" : "start"} className="graph-node-kind">{isClaim ? String(node.status || "claim").replaceAll("_", " ") : String(node.source_type || "source")}</text><text x={point.x + (isClaim ? -17 : 17)} y={point.y + 9} textAnchor={isClaim ? "end" : "start"} className="graph-node-label">{label.length > 55 ? `${label.slice(0, 52)}…` : label}</text></g>; })}</svg>}{claims.length + sources.length > 0 && !graph.edges.length && <p className="graph-note">Nodes are based on stored records. No explicit claim to source references were found in the saved evidence text.</p>}</div>;
}

function DatasetVisualizations({ executions }: { executions: Item[] }) {
  const datasets = executions.flatMap((execution) => execution.agent_name === "Data Analyst" ? (execution.output_data?.analysis_results || []) as Item[] : []);
  const completed = datasets.filter((dataset) => dataset.status === "completed");
  if (!completed.length) return null;
  return <section className="dataset-visualizations"><div className="panel-head"><div><span className="eyebrow">DATASET ANALYSIS</span><h3>Numeric distributions</h3></div></div><div className="dataset-grid">{completed.map((dataset) => <article className="dataset-card" key={String(dataset.dataset_id)}><div className="dataset-title"><strong>{dataset.summary?.filename || `Dataset ${String(dataset.dataset_id).slice(0, 8)}`}</strong><small>{dataset.summary?.rows ?? "—"} rows · {dataset.summary?.columns ?? "—"} columns</small></div>{(dataset.findings || []).map((finding: string, index: number) => <p className="dataset-finding" key={`${index}-${finding}`}>{finding}</p>)}<div className="chart-grid">{(dataset.chart_specs || []).filter((chart: Item) => chart.type === "histogram" && Array.isArray(chart.counts) && chart.counts.length).map((chart: Item) => { const counts = chart.counts as number[]; const edges = chart.bin_edges as number[]; const peak = Math.max(1, ...counts); const barWidth = 350 / counts.length; return <div className="histogram-card" key={String(chart.column)}><strong>{String(chart.column)} distribution</strong><svg viewBox="0 0 390 180" role="img" aria-label={`Histogram of ${String(chart.column)} with ${counts.length} bins`}><line x1="35" y1="145" x2="380" y2="145" stroke="#dfe5dd"/>{counts.map((count, index) => { const height = count / peak * 112; return <rect key={index} x={38 + index * barWidth} y={140 - height} width={Math.max(2, barWidth - 3)} height={height} rx="2" fill="#5b9271"><title>{count} rows</title></rect>; })}<text x="38" y="163">{Number(edges?.[0] ?? 0).toPrecision(4)}</text><text x="380" y="163" textAnchor="end">{Number(edges?.[edges.length - 1] ?? 0).toPrecision(4)}</text><text x="10" y="22">{peak}</text></svg></div>; })}</div></article>)}</div></section>;
}

export default function Home() {
  const [user, setUser] = useState<Item | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [modal, setModal] = useState<"project" | "run" | "question" | "" > ("");
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [projectEditingOpen, setProjectEditingOpen] = useState(false);
  const [runs, setRuns] = useState<Item[]>([]);
  const [documents, setDocuments] = useState<Item[]>([]);
  const [sources, setSources] = useState<Item[]>([]);
  const [claims, setClaims] = useState<Item[]>([]);
  const [reports, setReports] = useState<Item[]>([]);
  const [conversations, setConversations] = useState<Item[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<Item | null>(null);
  const [conversationMessages, setConversationMessages] = useState<Item[]>([]);
  const [conversationQuestion, setConversationQuestion] = useState("");
  const [executions, setExecutions] = useState<Item[]>([]);
  const [activeJobId, setActiveJobId] = useState("");
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [] });
  const [evidenceView, setEvidenceView] = useState<"list" | "graph">("list");
  const [selectedRun, setSelectedRun] = useState<Item | null>(null);
  const [answer, setAnswer] = useState<Item | null>(null);
  const [previewReport, setPreviewReport] = useState<Item | null>(null);
  const [question, setQuestion] = useState("");
  const [search, setSearch] = useState("");
  const watchingJobs = useRef(new Set<string>());
  const watchJobRef = useRef<(jobId: string, runId: string) => void>(() => {});

  const loadProjects = useCallback(async (pickId?: string) => {
    const data = await api<{ projects: Project[] }>("projects/?skip=0&limit=100");
    const list = data.projects || [];
    setProjects(list);
    const found = list.find((project) => project.id === pickId) || list.find((project) => project.id === activeProject?.id) || list[0] || null;
    setActiveProject(found);
    return found;
  }, [activeProject?.id]);

  const loadWorkspace = useCallback(async (project: Project | null, run?: Item | null) => {
    if (!project) { setRuns([]); setDocuments([]); setSources([]); setClaims([]); setReports([]); setExecutions([]); setGraph({ nodes: [], edges: [] }); return; }
    const projectRuns = await api<Item[]>(`research-runs/?project_id=${project.id}&skip=0&limit=100`);
    setRuns(projectRuns || []);
    setDocuments(((await api<{ documents: Item[] }>(`documents/?project_id=${project.id}&skip=0&limit=100`)).documents || []).map((document) => ({ ...document, status: document.processing_status })));
    setGraph(await api<GraphData>(`knowledge-graph/?project_id=${project.id}`));
    const target = run || selectedRun || projectRuns?.[0] || null;
    setSelectedRun(target);
    if (!target) { setSources([]); setClaims([]); setReports([]); setExecutions([]); return; }
    const rid = idOf(target);
    const [sourceList, claimList, reportList, agentList] = await Promise.all([
      api<{ sources: Item[] }>(`research-sources/?research_run_id=${rid}&skip=0&limit=100`),
      api<{ claims: Item[] }>(`verified-claims/?research_run_id=${rid}&skip=0&limit=100`),
      api<{ reports: Item[] }>(`reports/?research_run_id=${rid}&skip=0&limit=100`),
      api<{ executions: Item[] }>(`agent-executions/?research_run_id=${rid}&skip=0&limit=100`),
    ]);
    setSources(sourceList.sources || []); setClaims(claimList.claims || []); setReports(reportList.reports || []); setExecutions(agentList.executions || []);
  }, [selectedRun]);

  useEffect(() => {
    let alive = true;
    api<Item[]>("users/").then((users) => {
      if (!alive) return;
      setUser(users?.[0] || null);
      return loadProjects();
    }).then((project) => project && alive ? loadWorkspace(project) : undefined)
      .catch(() => { if (alive) setUser(null); }).finally(() => alive && setLoading(false));
    return () => { alive = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // initial session check

  useEffect(() => {
    if (!activeProject?.id) return;
    const pendingDocuments = documents.filter((document) => ["pending", "queued", "processing"].includes(String(document.processing_status || document.status)));
    if (!pendingDocuments.length) return;
    const timer = window.setTimeout(async () => {
      try {
        const refreshed = (await Promise.all(pendingDocuments.map((document) => api<Item>(`documents/${idOf(document)}`)))).map((document) => ({ ...document, status: document.processing_status }));
        const byId = new Map(refreshed.map((document) => [idOf(document), document]));
        setDocuments((current) => current.map((document) => byId.get(idOf(document)) || document));
      } catch (issue) { setError((issue as Error).message); }
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [activeProject?.id, documents]);

  const resumableRunId = runs.find((item) => ["queued", "running"].includes(String(item.status)))?.id;
  useEffect(() => {
    if (!user) return;
    if (!resumableRunId) return;
    let cancelled = false;
    api<Item[]>(`jobs/?research_run_id=${resumableRunId}`).then((jobs) => {
      const job = jobs.find((item) => ["queued", "running", "cancel_requested"].includes(String(item.status)));
      if (!cancelled && job) { setActiveJobId(idOf(job)); watchJobRef.current(idOf(job), String(resumableRunId)); }
    }).catch((issue) => setError((issue as Error).message));
    return () => { cancelled = true; };
  }, [resumableRunId, user]);

  useEffect(() => {
    if (!user || tab !== "history") return;
    let cancelled = false;
    api<Item[]>("conversations/?skip=0&limit=100").then((items) => {
      if (cancelled) return;
      const scoped = (items || []).filter((item) => item.project_id === activeProject?.id);
      setConversations(scoped);
      setSelectedConversation((current) => scoped.find((item) => idOf(item) === idOf(current || {})) || null);
      if (!scoped.length) setConversationMessages([]);
    }).catch((issue) => { if (!cancelled) setError((issue as Error).message); });
    return () => { cancelled = true; };
  }, [activeProject?.id, tab, user]);

  async function handleAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setWorking(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      if (authMode === "register") {
        const result = await api<Item>("auth/register", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ name: form.get("name"), email: form.get("email"), password: form.get("password") }) });
        setUser(result.user); setNotice("Account created. Your workspace is ready.");
        const project = await loadProjects(); if (project) await loadWorkspace(project);
      } else {
        const body = new URLSearchParams({ username: String(form.get("email")), password: String(form.get("password")) });
        const result = await api<Item>("auth/login", { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" }, body });
        const profile = result.user;
        setUser(profile); setNotice(`Welcome back, ${profile.name.split(" ")[0]}.`);
        const project = await loadProjects(); if (project) await loadWorkspace(project);
      }
    } catch (e) { setError((e as Error).message); }
    finally { setWorking(false); }
  }

  async function logout() { await fetch("/api/logout", { method: "POST" }); setUser(null); setProjects([]); setActiveProject(null); setNotice(""); setTab("overview"); }

  async function createProject(event: FormEvent<HTMLFormElement>) {
    if (editingProject) return updateProject(event);
    event.preventDefault(); setWorking(true); setError("");
    const data = new FormData(event.currentTarget);
    try { const project = await api<Project>("projects/", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ title: data.get("title"), research_topic: data.get("topic"), description: data.get("description") || null }) }); const updated = await loadProjects(project.id); await loadWorkspace(updated); setModal(""); setTab("overview"); setNotice("Project created."); }
    catch (e) { setError((e as Error).message); } finally { setWorking(false); }
  }

  async function updateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!editingProject) return; setWorking(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      const updated = await api<Project>(`projects/${editingProject.id}`, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify({ title: form.get("title"), research_topic: form.get("topic"), description: form.get("description") || null }) });
      setProjects((items) => items.map((item) => item.id === updated.id ? updated : item));
      if (activeProject?.id === updated.id) { setActiveProject(updated); await loadWorkspace(updated); }
      setModal(""); setProjectEditingOpen(false); setEditingProject(null); setNotice("Project updated.");
    } catch (issue) { setError((issue as Error).message); } finally { setWorking(false); }
  }

  async function deleteProject(project: Project) {
    const confirmed = window.confirm(`Delete “${project.title}” and all of its research runs, conversations, documents, and reports? This cannot be undone.`);
    if (!confirmed) return;
    setWorking(true); setError("");
    try {
      await api(`projects/${project.id}`, { method: "DELETE" });
      const next = await loadProjects();
      setSelectedRun(null); setTab("overview"); await loadWorkspace(next);
      setNotice("Project and its stored research artifacts were deleted.");
    } catch (issue) { setError((issue as Error).message); } finally { setWorking(false); }
  }

  async function createConversation() {
    if (!activeProject) return;
    setWorking(true); setError("");
    try {
      const conversation = await api<Item>("conversations/", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ project_id: activeProject.id, title: `Research notes · ${new Date().toLocaleDateString()}` }) });
      setConversations((current) => [conversation, ...current]); setSelectedConversation(conversation); setConversationMessages([]); setNotice("Conversation created.");
    } catch (issue) { setError((issue as Error).message); } finally { setWorking(false); }
  }

  async function openConversation(conversation: Item) {
    setSelectedConversation(conversation); setError("");
    try { setConversationMessages(await api<Item[]>(`messages/conversation/${idOf(conversation)}?skip=0&limit=100`)); }
    catch (issue) { setError((issue as Error).message); }
  }

  async function deleteConversation(conversation: Item) {
    setError("");
    try {
      await api(`conversations/${idOf(conversation)}`, { method: "DELETE" });
      setConversations((current) => current.filter((item) => idOf(item) !== idOf(conversation)));
      if (idOf(selectedConversation || {}) === idOf(conversation)) { setSelectedConversation(null); setConversationMessages([]); }
      setNotice("Conversation deleted.");
    } catch (issue) { setError((issue as Error).message); }
  }

  async function sendConversationMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selectedConversation || !conversationQuestion.trim()) return;
    setWorking(true); setError("");
    try {
      const turn = await api<Item>(`conversations/${idOf(selectedConversation)}/ask`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query: conversationQuestion.trim() }) });
      setConversationMessages((current) => [...current, turn.user_message, turn.assistant_message]);
      setConversationQuestion("");
    } catch (issue) { setError((issue as Error).message); } finally { setWorking(false); }
  }

  async function createRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!activeProject) return; setWorking(true); setError("");
    const data = new FormData(event.currentTarget);
    try { const run = await api<Item>("research-runs/", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ project_id: activeProject.id, research_topic: data.get("topic"), research_depth: data.get("depth") }) }); setSelectedRun(run); setModal(""); await loadWorkspace(activeProject, run); setTab("research"); setNotice("Research run created."); }
    catch (e) { setError((e as Error).message); } finally { setWorking(false); }
  }

  async function executeRun(run: Item) {
    setWorking(true); setError(""); setNotice("Queueing research for background processing…");
    try { const query = new URLSearchParams(); documents.forEach((document) => query.append("document_ids", idOf(document))); documents.filter((document) => ["csv", "xlsx"].includes(String(document.file_type || "").toLowerCase())).forEach((document) => query.append("dataset_ids", idOf(document))); const suffix = query.size ? `?${query}` : ""; const job = await api<Item>(`research-runs/${idOf(run)}/enqueue${suffix}`, { method: "POST" }); setActiveJobId(idOf(job)); const queuedRun = { ...run, status: "queued" }; setSelectedRun(queuedRun); setRuns((current) => current.map((item) => idOf(item) === idOf(run) ? queuedRun : item)); setNotice("Research is queued. You can leave this page; progress is saved."); void watchJob(idOf(job), idOf(run)); }
    catch (e) { setError((e as Error).message); } finally { setWorking(false); }
  }

  async function watchJob(jobId: string, runId: string) {
    if (watchingJobs.current.has(jobId)) return;
    watchingJobs.current.add(jobId);
    try { while (true) {
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
      try {
        const [job, progress] = await Promise.all([
          api<Item>(`jobs/${jobId}`),
          api<Item>(`research-runs/${runId}/status`),
        ]);
        const merged = { ...progress, id: runId, status: progress.status, research_topic: selectedRun?.research_topic };
        setSelectedRun((current) => current && idOf(current) === runId ? { ...current, ...merged } : current);
        setRuns((current) => current.map((item) => idOf(item) === runId ? { ...item, ...merged } : item));
        if (["completed", "failed", "cancelled"].includes(job.status)) {
          if (job.status === "completed") setActiveJobId("");
          if (activeProject) await loadWorkspace(activeProject, { ...(runs.find((item) => idOf(item) === runId) || {}), ...merged });
          setNotice(job.status === "completed" ? "Research complete. Evidence and report are ready." : `Research ${job.status}. ${job.error_message || "Review the run status and retry if appropriate."}`);
          return;
        }
        if (job.status === "cancel_requested") setNotice("Cancellation requested. The current agent step will stop at its next checkpoint.");
      } catch (issue) { setError((issue as Error).message); return; }
    } } finally { watchingJobs.current.delete(jobId); }
  }

  watchJobRef.current = (jobId, runId) => { void watchJob(jobId, runId); };

  async function cancelActiveJob() {
    if (!activeJobId) return;
    try { await api(`jobs/${activeJobId}/cancel`, { method: "POST" }); setNotice("Cancellation requested."); }
    catch (issue) { setError((issue as Error).message); }
  }

  async function retryActiveJob() {
    if (!activeJobId) return;
    setWorking(true); setError("");
    try { const job = await api<Item>(`jobs/${activeJobId}/retry`, { method: "POST" }); setActiveJobId(idOf(job)); setNotice("Research retry queued."); if (selectedRun) void watchJob(idOf(job), idOf(selectedRun)); }
    catch (issue) { setError((issue as Error).message); } finally { setWorking(false); }
  }

  async function manageDocumentJob(document: Item, action: "cancel" | "retry") {
    setError("");
    try {
      const jobs = await api<Item[]>(`jobs/?document_id=${idOf(document)}`);
      const job = jobs[0];
      if (!job) throw new Error("Background document job not found.");
      const updated = await api<Item>(`jobs/${idOf(job)}/${action}`, { method: "POST" });
      const documentStatus = action === "retry" ? "queued" : updated.status === "cancelled" ? "cancelled" : String(document.status);
      setDocuments((items) => items.map((item) => idOf(item) === idOf(document) ? { ...item, status: documentStatus, processing_status: documentStatus } : item));
      setNotice(action === "cancel" ? "Document processing cancellation requested." : "Document indexing retry queued.");
    } catch (issue) { setError((issue as Error).message); }
  }

  async function uploadFiles(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!activeProject) return; setWorking(true); setError("");
    const uploadForm = event.currentTarget;
    const form = new FormData(uploadForm); const file = form.get("file") as File;
    if (!file?.size) { setError("Choose a file to upload."); setWorking(false); return; }
    const body = new FormData(); body.append("file", file);
    try { await api(`documents/upload?project_id=${activeProject.id}&background=true`, { method: "POST", body }); await loadWorkspace(activeProject); setNotice(`${file.name} uploaded. Processing continues in the background.`); uploadForm.reset(); }
    catch (e) { setError((e as Error).message); } finally { setWorking(false); }
  }

  async function askQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!activeProject) return; setWorking(true); setError(""); setAnswer(null);
    try { const result = await api<Item>("rag/ask", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ question, project_id: activeProject.id, max_tokens: 800 }) }); setAnswer(result); setQuestion(""); }
    catch (e) { setError((e as Error).message); } finally { setWorking(false); }
  }

  async function downloadReport(report: Item) {
    try { const blob = await api<Blob>(`reports/${idOf(report)}/download?format=${report.report_format || "pdf"}`); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = `research-report.${report.report_format || "pdf"}`; link.click(); URL.revokeObjectURL(url); }
    catch (e) { setError((e as Error).message); }
  }

  async function generateReport(format: "pdf" | "docx" | "html") {
    if (!selectedRun || !activeProject) return;
    setWorking(true); setError("");
    try { await api("reports/generate", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ research_run_id: idOf(selectedRun), report_format: format }) }); await loadWorkspace(activeProject, selectedRun); setNotice(`${format.toUpperCase()} report generated.`); }
    catch (issue) { setError((issue as Error).message); } finally { setWorking(false); }
  }

  if (loading) return <main className="boot"><div className="brand-mark">R</div><p>Preparing your research desk…</p></main>;
  if (!user) return <main className="auth-screen"><section className="auth-story"><a className="brand" href="#"><span className="brand-mark">R</span><span>ResearchOS</span></a><div className="story-copy"><span className="eyebrow">THE RESEARCH WORKSPACE</span><h1>Move from question<br/>to <em>evidence.</em></h1><p>Bring your sources together, investigate with AI, and keep every finding connected to its evidence.</p><div className="story-note"><span className="note-dot"/> Your research, organized and traceable.</div></div><div className="story-footer">A focused place for rigorous work <span>•</span> Evidence first</div></section><section className="auth-panel"><div className="auth-box"><span className="eyebrow">{authMode === "login" ? "WELCOME BACK" : "GET STARTED"}</span><h2>{authMode === "login" ? "Sign in to your workspace" : "Create your account"}</h2><p className="muted">{authMode === "login" ? "Pick up where your research left off." : "Your next research project starts here."}</p>{notice && <div className="alert success">{notice}</div>}{error && <div className="alert error">{error}</div>}<form className="stack-form" onSubmit={handleAuth}>{authMode === "register" && <label>Your name<input name="name" autoComplete="name" required placeholder="Ada Lovelace"/></label>}<label>Email address<input type="email" name="email" autoComplete="email" required placeholder="you@university.edu"/></label><label>Password<input type="password" name="password" autoComplete={authMode === "login" ? "current-password" : "new-password"} minLength={8} required placeholder="At least 8 characters"/></label><button className="button primary wide" disabled={working}>{working ? "Please wait…" : authMode === "login" ? "Sign in" : "Create account"}<span>→</span></button></form><p className="auth-switch">{authMode === "login" ? "New to ResearchOS?" : "Already have an account?"} <button onClick={() => { setAuthMode(authMode === "login" ? "register" : "login"); setError(""); }}>{authMode === "login" ? "Create an account" : "Sign in"}</button></p><div className="auth-foot">Private workspace · Bearer tokens held in an HttpOnly cookie</div></div></section></main>;

  const nav: { key: Tab; label: string; icon: string }[] = [{ key: "overview", label: "Overview", icon: "⌂" }, { key: "projects", label: "Projects", icon: "▦" }, { key: "research", label: "Research runs", icon: "⌕" }, { key: "library", label: "Document library", icon: "▤" }, { key: "evidence", label: "Evidence & claims", icon: "◇" }, { key: "reports", label: "Reports", icon: "▧" }, { key: "history", label: "History", icon: "☷" }];
  const title = nav.find((item) => item.key === tab)?.label || "Overview";
  const filteredProjects = projects.filter((project) => `${project.title} ${project.research_topic}`.toLowerCase().includes(search.toLowerCase()));

  return <main className="app-shell"><aside className="sidebar"><a className="brand" href="#" onClick={(e) => { e.preventDefault(); setTab("overview"); }}><span className="brand-mark">R</span><span>ResearchOS</span></a><div className="workspace-label">WORKSPACE</div><nav className="side-nav">{nav.map((item) => <button key={item.key} className={`nav-item ${tab === item.key ? "active" : ""}`} onClick={() => setTab(item.key)}><span className="nav-icon">{item.icon}</span>{item.label}{item.key === "projects" && <span className="nav-count">{projects.length}</span>}</button>)}</nav><div className="sidebar-bottom"><div className="help-card"><span className="help-symbol">✳</span><strong>Research, with clarity.</strong><p>Every claim connected to its source.</p></div><button className="profile" onClick={logout}><span className="avatar">{initials(user.name)}</span><span className="profile-text"><strong>{user.name}</strong><small>{user.email}</small></span><span className="logout-mark" title="Sign out">↗</span></button></div></aside>
    <section className="main-area"><header className="topbar"><div className="breadcrumb"><span>Workspace</span><b>/</b><strong>{title}</strong></div><div className="top-actions"><span className="connection"><i/> API connected</span><button className="avatar small" onClick={logout} title="Sign out">{initials(user.name)}</button></div></header><div className="content"><div className="page-heading"><div><span className="eyebrow">{tab === "overview" ? "YOUR RESEARCH DESK" : "WORKSPACE"}</span><h1>{tab === "overview" ? `Good to see you, ${user.name.split(" ")[0]}.` : title}</h1><p>{tab === "overview" ? "A clear view of the work in progress." : activeProject ? <>Working in <strong>{activeProject.title}</strong></> : "Choose a project to get started."}</p></div><div className="heading-actions">{activeProject && <button className="button secondary" onClick={() => setModal("question")}>Ask your documents</button>}{tab === "history" ? <button className="button primary" disabled={!activeProject || working} onClick={createConversation}>New conversation</button> : <button className="button primary" onClick={() => setModal(tab === "research" ? "run" : "project")}>{tab === "research" ? "New research run" : "New project"}</button>}</div></div>
      {(error || notice) && <div className={`alert ${error ? "error" : "success"}`} role="status">{error || notice}<button onClick={() => { setError(""); setNotice(""); }}>×</button></div>}
      {!projects.length && <section className="empty-hero"><div className="empty-art"><div className="art-ring ring-a"/><div className="art-ring ring-b"/><span>✳</span></div><span className="eyebrow">A GOOD PLACE TO BEGIN</span><h2>Start with a question worth answering.</h2><p>Create a project, collect your documents, then launch a research run to gather sources and verified claims.</p><button className="button primary" onClick={() => setModal("project")}>Create your first project <span>→</span></button></section>}
      {projects.length > 0 && <>
        <div className="metrics-grid"><article className="metric-card"><span className="metric-icon violet">▦</span><span className="metric-label">PROJECTS</span><strong>{projects.length.toString().padStart(2,"0")}</strong><small>Research spaces</small></article><article className="metric-card"><span className="metric-icon blue">⌕</span><span className="metric-label">RESEARCH RUNS</span><strong>{runs.length.toString().padStart(2,"0")}</strong><small>{runs.filter((run) => run.status === "completed").length} completed</small></article><article className="metric-card"><span className="metric-icon green">◇</span><span className="metric-label">SOURCES & CLAIMS</span><strong>{(sources.length + claims.length).toString().padStart(2,"0")}</strong><small>{sources.length} sources · {claims.length} claims</small></article><article className="metric-card"><span className="metric-icon amber">▤</span><span className="metric-label">DOCUMENTS</span><strong>{documents.length.toString().padStart(2,"0")}</strong><small>In selected project</small></article></div>
        <div className="project-toolbar"><div><h2>{tab === "projects" ? "All projects" : activeProject?.title || "Your projects"}</h2><p>{tab === "projects" ? "Every research question has its own workspace." : activeProject?.research_topic || "Choose a project workspace to see its activity."}</p></div><div className="toolbar-right"><label className="project-picker"><span>PROJECT</span><select value={activeProject?.id || ""} onChange={(e) => { const project = projects.find((item) => item.id === e.target.value) || null; setActiveProject(project); setSelectedRun(null); loadWorkspace(project).catch((issue) => setError(issue.message)); }}>{projects.map((project) => <option key={project.id} value={project.id}>{project.title}</option>)}</select></label>{tab === "projects" && activeProject && <><button className="button light" onClick={() => { setEditingProject(activeProject); setProjectEditingOpen(true); }}>Edit selected</button><button className="button light" disabled={working} onClick={() => deleteProject(activeProject)}>Delete selected</button></>}<button className="button light" onClick={() => { setEditingProject(null); setModal("project"); }}>New project</button></div></div>
        <div className="workspace-grid"><section className="panel main-panel"><div className="panel-head"><div><span className="eyebrow">{tab === "projects" ? "PROJECT SPACES" : tab === "library" ? "PROJECT DOCUMENTS" : tab === "evidence" ? "RESEARCH EVIDENCE" : tab === "reports" ? "GENERATED OUTPUTS" : tab === "history" ? "PROJECT CONVERSATIONS" : "RECENT RESEARCH"}</span><h3>{tab === "projects" ? "Projects" : tab === "library" ? "Document library" : tab === "evidence" ? "Sources & verified claims" : tab === "reports" ? "Reports" : tab === "history" ? "Conversation history" : "Research activity"}</h3></div>{tab === "projects" && <input className="search-input" placeholder="Search projects…" value={search} onChange={(e) => setSearch(e.target.value)}/>}</div>
          {tab === "history" ? <div className="conversation-layout"><div className="conversation-list">{conversations.map((conversation) => <article className={`conversation-row ${idOf(selectedConversation || {}) === idOf(conversation) ? "selected" : ""}`} key={idOf(conversation)}><button className="conversation-open" onClick={() => openConversation(conversation)}><strong>{conversation.title || "Untitled conversation"}</strong><small>Updated {dateOf(conversation.updated_at || conversation.created_at)}</small></button><button className="text-button" aria-label={`Delete ${conversation.title || "conversation"}`} onClick={() => deleteConversation(conversation)}>Delete</button></article>)}{!conversations.length && <div className="list-empty">No saved conversations in this project yet.</div>}</div><section className="conversation-detail">{selectedConversation ? <><div className="conversation-heading"><span className="eyebrow">SAVED HISTORY</span><h4>{selectedConversation.title || "Untitled conversation"}</h4></div><div className="message-list">{conversationMessages.map((message) => <article className={`saved-message ${message.role === "assistant" ? "assistant" : "user"}`} key={idOf(message)}><div><strong>{message.agent_name || (message.role === "assistant" ? "ResearchOS" : "You")}</strong><small>{dateOf(message.created_at)}</small></div><p>{message.content}</p></article>)}{!conversationMessages.length && <p className="list-empty">This conversation has no saved messages yet.</p>}</div><p className="history-note">Ask questions grounded in this project’s indexed documents; each answer and its citations are saved in this conversation.</p></> : <div className="list-empty">Choose a conversation to review its saved messages.</div>}</section></div>
          : tab === "projects" ? <div className="project-list">{filteredProjects.map((project) => <button className={`project-row ${activeProject?.id === project.id ? "selected" : ""}`} key={project.id} onClick={() => { setActiveProject(project); setTab("overview"); setSelectedRun(null); loadWorkspace(project).catch((issue) => setError(issue.message)); }}><span className="project-monogram">{initials(project.title)}</span><span className="project-info"><strong>{project.title}</strong><small>{project.research_topic}</small></span><span className="status-pill">{project.status || "active"}</span><span className="row-date">{dateOf(project.updated_at || project.created_at)}</span><span className="chevron">›</span></button>)}</div>
          : tab === "library" ? <><form className="upload-zone" onSubmit={uploadFiles}><div className="upload-icon">↑</div><strong>Drop a document into your library</strong><p>PDF, DOCX, TXT, CSV, XLSX · up to 50 MB</p><label className="button secondary file-button">Choose file<input name="file" type="file" accept=".pdf,.docx,.txt,.csv,.xlsx"/></label><button className="button primary" disabled={working}>Upload document</button></form><div className="data-list">{documents.map((doc) => <div className="data-row" key={idOf(doc)}><span className="file-icon">▤</span><span className="data-copy"><strong>{doc.filename || doc.file_name || "Research document"}</strong><small>{doc.file_type || doc.content_type || "Document"} · {dateOf(doc.created_at)}</small></span><span className={`status-pill ${doc.status === "processed" ? "done" : ""}`}>{doc.status || "uploaded"}</span></div>)}{!documents.length && <div className="list-empty">No documents in this project yet. Upload a file to begin.</div>}</div></>
          : tab === "evidence" ? <><div className="evidence-view-toggle"><button className={evidenceView === "list" ? "selected" : ""} onClick={() => setEvidenceView("list")}>Evidence list</button><button className={evidenceView === "graph" ? "selected" : ""} onClick={() => setEvidenceView("graph")}>Knowledge graph</button></div>{evidenceView === "graph" ? <EvidenceGraph graph={graph}/> : <div className="evidence-columns"><div><div className="subhead"><strong>Sources</strong><span>{sources.length}</span></div>{sources.slice(0,8).map((source) => <article className="evidence-card" key={idOf(source)}><strong>{source.title || source.source_title || source.url || "Research source"}</strong><p>{source.summary || source.snippet || source.authors || "Source collected during this research run."}</p>{source.url && <a href={source.url} target="_blank" rel="noreferrer">Open source ↗</a>}</article>)}{!sources.length && <p className="list-empty">Run research to collect sources.</p>}</div><div><div className="subhead"><strong>Verified claims</strong><span>{claims.length}</span></div>{claims.slice(0,8).map((claim) => <article className="evidence-card claim-card" key={idOf(claim)}><span className="claim-label">VERIFIED CLAIM</span><p>{claim.claim_text || claim.claim || claim.content || "Claim"}</p><small>{claim.confidence != null ? `Confidence ${Math.round(Number(claim.confidence) * 100)}%` : "Evidence-backed finding"}</small></article>)}{!claims.length && <p className="list-empty">Verified claims will appear after a research run.</p>}</div></div>}</>
          : tab === "reports" ? <div className="data-list">{reports.map((report) => <div className="data-row" key={idOf(report)}><span className="report-icon">▧</span><span className="data-copy"><strong>{report.title || `Research report · ${String(report.report_format || "pdf").toUpperCase()}`}</strong><small>{String(report.report_format || "pdf").toUpperCase()} · {dateOf(report.created_at)}</small></span>{report.content && <button className="button light compact" onClick={() => setPreviewReport(report)}>Preview</button>}<button className="button secondary compact" onClick={() => downloadReport(report)}>Download ↓</button></div>)}{!reports.length && <div className="list-empty">Completed research runs generate a PDF report. Other formats can be generated from the run.</div>}</div>
          : tab === "research" ? <div className="run-list">{runs.map((run) => <article className={`run-card ${selectedRun && idOf(selectedRun) === idOf(run) ? "chosen" : ""}`} key={idOf(run)}><button className="run-main" onClick={() => { setSelectedRun(run); loadWorkspace(activeProject, run).catch((e) => setError(e.message)); }}><span className="run-symbol">⌕</span><span className="run-copy"><strong>{run.research_topic}</strong><small>{String(run.research_depth || "standard")} depth · {dateOf(run.created_at)}</small></span><span className={`status-pill ${run.status === "completed" ? "done" : ""}`}>{run.status || "created"}</span></button>{["pending","created","failed"].includes(run.status) && <button className="button primary compact" disabled={working} onClick={() => executeRun(run)}>{working ? "Running…" : "Run research →"}</button>}</article>)}{!runs.length && <div className="list-empty">No runs yet. Start with a focused question.</div>}</div>
          : <div className="run-list">{runs.slice(0,4).map((run) => <article className="activity-row" key={idOf(run)}><span className={`activity-dot ${run.status === "completed" ? "complete" : ""}`}/><div><strong>{run.research_topic}</strong><small>{String(run.research_depth || "standard")} depth · {dateOf(run.created_at)}</small></div><span className={`status-pill ${run.status === "completed" ? "done" : ""}`}>{run.status || "created"}</span><button className="chevron-button" onClick={() => { setSelectedRun(run); setTab("research"); }}>›</button></article>)}{!runs.length && <div className="list-empty">Your project is ready for its first research run.</div>}</div>}
        </section><aside className="panel side-panel"><div className="panel-head"><div><span className="eyebrow">PROJECT SNAPSHOT</span><h3>{activeProject?.title || "Workspace"}</h3></div><span className="live-dot"/></div><p className="snapshot-topic">{activeProject?.research_topic || "Select a project to see its research snapshot."}</p><div className="snapshot-stats"><div><strong>{runs.length}</strong><small>Runs</small></div><div><strong>{documents.length}</strong><small>Documents</small></div><div><strong>{sources.length}</strong><small>Sources</small></div></div><div className="snapshot-divider"/><div className="snapshot-section"><span className="eyebrow">LATEST RUN</span>{selectedRun ? <><strong className="latest-topic">{selectedRun.research_topic}</strong><div className="latest-meta"><span className={`status-pill ${selectedRun.status === "completed" ? "done" : ""}`}>{selectedRun.status || "created"}</span><span>{String(selectedRun.research_depth || "standard")} depth</span></div><button className="text-button" onClick={() => setTab("research")}>View run details <span>→</span></button></> : <p className="muted small-text">No research activity yet.</p>}</div><div className="snapshot-section quick-actions"><span className="eyebrow">QUICK ACTIONS</span><button onClick={() => setModal("run")}><span>＋</span> Start a research run <b>→</b></button><button onClick={() => setTab("library")}><span>↑</span> Add documents <b>→</b></button><button onClick={() => setModal("question")}><span>✳</span> Ask your documents <b>→</b></button></div></aside></div></>}
      {tab === "history" && selectedConversation && <form className="conversation-ask" onSubmit={sendConversationMessage}><label htmlFor="conversation-question">Ask this project</label><textarea id="conversation-question" value={conversationQuestion} onChange={(event) => setConversationQuestion(event.target.value)} required maxLength={4000} placeholder="Ask a question grounded in this project's indexed documents…"/><div><span>Answers use project documents and are saved with citations.</span><button className="button primary compact" disabled={working || !conversationQuestion.trim()}>{working ? "Searching…" : "Send question"}</button></div></form>}
      </div></section>
    {modal && <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setModal(""); }}><section className="modal"><button className="modal-close" onClick={() => setModal("")}>×</button><span className="eyebrow">{modal === "project" ? "NEW WORKSPACE" : modal === "run" ? "RESEARCH WORKFLOW" : "GROUNDED DOCUMENT Q&A"}</span><h2>{modal === "project" ? "Create a project" : modal === "run" ? "Start a research run" : "Ask your documents"}</h2><p className="muted">{modal === "project" ? "Give your research question a dedicated home." : modal === "run" ? "The workflow will collect sources, evaluate evidence and produce findings." : "Answers are grounded in indexed documents from this project."}</p>{error && <div className="alert error">{error}</div>}{modal === "project" ? <form className="stack-form" onSubmit={createProject}><label>Project name<input name="title" required maxLength={200} placeholder="e.g. Climate adaptation policy"/></label><label>Research question<textarea name="topic" required minLength={5} maxLength={500} placeholder="What would you like to investigate?"/></label><label>Description <span className="optional">Optional</span><textarea name="description" placeholder="Scope, context, or notes"/></label><button className="button primary wide" disabled={working}>{working ? "Creating…" : "Create project"}<span>→</span></button></form> : modal === "run" ? <form className="stack-form" onSubmit={createRun}><label>Research question<input name="topic" required minLength={5} maxLength={500} defaultValue={activeProject?.research_topic || ""}/></label><label>Research depth<select name="depth" defaultValue="standard"><option value="basic">Basic · focused scan</option><option value="standard">Standard · balanced evidence</option><option value="comprehensive">Comprehensive · deeper analysis</option></select></label><div className="inline-note">Research runs may take a few minutes and keep this page connected while the workflow runs.</div><button className="button primary wide" disabled={working}>{working ? "Creating…" : "Create research run"}<span>→</span></button></form> : <><form className="stack-form" onSubmit={askQuestion}><label>Your question<textarea value={question} onChange={(e) => setQuestion(e.target.value)} required minLength={1} maxLength={4000} placeholder="What do the uploaded sources say about…?"/></label><button className="button primary wide" disabled={working}>{working ? "Searching evidence…" : "Ask with evidence"}<span>→</span></button></form>{answer && <div className="answer-box"><span className="claim-label">{answer.evidence_sufficient ? "EVIDENCE FOUND" : "LIMITED EVIDENCE"}</span><p>{answer.answer}</p>{answer.citations?.length > 0 && <small>{answer.citations.length} citation(s) included</small>}</div>}</>}</section></div>}
    {previewReport && <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setPreviewReport(null); }}><section className="modal report-modal"><button className="modal-close" onClick={() => setPreviewReport(null)}>×</button><span className="eyebrow">REPORT PREVIEW</span><h2>{previewReport.title || "Research report"}</h2><pre className="report-preview">{String(previewReport.content)}</pre><button className="button secondary" onClick={() => downloadReport(previewReport)}>Download report ↓</button></section></div>}
    {tab === "research" && selectedRun && <div className="run-detail"><span className="eyebrow">SELECTED RUN</span><div className="run-detail-head"><div><h2>{selectedRun.research_topic}</h2><p>{selectedRun.current_step || `Status: ${selectedRun.status || "created"}`}</p></div><span className={`status-pill ${selectedRun.status === "completed" ? "done" : ""}`}>{selectedRun.status || "created"}</span></div><div className="progress-track"><span style={{ width: `${Math.max(0, Math.min(100, Number(selectedRun.progress || 0)))}%` }}/></div><div className="progress-caption">{Math.round(Number(selectedRun.progress || 0))}% complete <span>{executions.length} agent activities · {sources.length} sources · {claims.length} claims</span></div>{selectedRun.status === "completed" && reports.length > 0 && <button className="button secondary compact" onClick={() => downloadReport(reports[0])}>Download latest report ↓</button>}{selectedRun.error_message && <div className="alert error">{selectedRun.error_message}</div>}</div>}
     {tab === "research" && selectedRun && <DatasetVisualizations executions={executions}/>}
     {activeJobId && ["queued", "running", "cancel_requested"].includes(String(selectedRun?.status)) && <div className="job-actions"><span className="eyebrow">BACKGROUND JOB</span><button className="button light compact" onClick={cancelActiveJob}>Cancel run</button></div>}
    {activeJobId && ["failed", "cancelled"].includes(String(selectedRun?.status)) && <div className="job-actions"><span className="eyebrow">BACKGROUND JOB {selectedRun?.status?.toUpperCase()}</span><button className="button primary compact" disabled={working} onClick={retryActiveJob}>Retry run</button></div>}
    {tab === "library" && documents.some((document) => ["queued", "pending", "processing", "failed", "cancelled"].includes(String(document.status))) && <div className="document-job-actions"><span className="eyebrow">DOCUMENT PROCESSING</span>{documents.filter((document) => ["queued", "pending", "processing", "failed", "cancelled"].includes(String(document.status))).map((document) => <div key={idOf(document)}><span>{document.filename}: {document.status}</span>{["queued", "pending", "processing"].includes(String(document.status)) ? <button className="text-button" onClick={() => manageDocumentJob(document, "cancel")}>Cancel</button> : <button className="text-button" onClick={() => manageDocumentJob(document, "retry")}>Retry indexing</button>}</div>)}</div>}
    {selectedRun?.status === "completed" && ["reports", "research"].includes(tab) && <div className="export-actions"><span className="eyebrow">GENERATE AN EXPORT</span>{(["pdf", "docx", "html"] as const).map((format) => <button className="button light compact" key={format} disabled={working} onClick={() => generateReport(format)}>{working ? "Generating…" : format.toUpperCase()}</button>)}</div>}
    {projectEditingOpen && editingProject && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) { setProjectEditingOpen(false); setEditingProject(null); } }}><section className="modal"><button className="modal-close" onClick={() => { setProjectEditingOpen(false); setEditingProject(null); }}>×</button><span className="eyebrow">PROJECT SETTINGS</span><h2>Edit project</h2><p className="muted">Update this project’s name, research question, or description.</p>{error && <div className="alert error">{error}</div>}<form className="stack-form" onSubmit={updateProject}><label>Project name<input name="title" required minLength={3} maxLength={255} defaultValue={editingProject.title}/></label><label>Research question<textarea name="topic" required minLength={5} defaultValue={editingProject.research_topic}/></label><label>Description <span className="optional">Optional</span><textarea name="description" defaultValue={editingProject.description || ""}/></label><div className="heading-actions"><button type="button" className="button light" onClick={() => { setProjectEditingOpen(false); setEditingProject(null); }}>Cancel</button><button className="button primary" disabled={working}>{working ? "Saving…" : "Save changes"}</button></div></form></section></div>}
    </main>;
}
