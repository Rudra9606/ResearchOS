import { expect, test } from "@playwright/test";

const user = { id: "user-1", name: "Ada Lovelace", email: "ada@example.test" };
const project = { id: "project-1", user_id: user.id, title: "Clinical AI review", research_topic: "AI outcomes in clinical practice", status: "active", created_at: "2026-11-18T00:00:00Z" };

test.beforeEach(async ({ page }) => {
  let activeRun: Record<string, unknown> | null = null;
  let savedConversations: Record<string, unknown>[] = [];
  let currentProject: typeof project | null = { ...project };
  let uploadedDocument: Record<string, unknown> | null = null;
  let documentJob = { id: "document-job-1", job_type: "document", status: "queued" };
  let generatedReport: Record<string, unknown> | null = null;
  const backgroundJob = { id: "job-1", job_type: "research", status: "queued" };
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/^\/api\//, "");
    const method = request.method();
    if (path === "users/") return route.fulfill({ status: 401, json: { detail: "Not signed in" } });
    if (path === "auth/login" && method === "POST") return route.fulfill({ json: { message: "Login successful", user } });
    if (path === "projects/" && method === "GET") return route.fulfill({ json: { total: currentProject ? 1 : 0, projects: currentProject ? [currentProject] : [] } });
    if (path === "projects/project-1" && method === "PUT") {
      if (!currentProject) return route.fulfill({ status: 404, json: { detail: "Project not found" } });
      currentProject = { ...currentProject, ...request.postDataJSON() };
      return route.fulfill({ json: currentProject });
    }
    if (path === "projects/project-1" && method === "DELETE") { currentProject = null; return route.fulfill({ status: 204 }); }
    if (path === "research-runs/" && method === "POST") {
      activeRun = { id: "run-1", project_id: project.id, research_topic: "AI outcomes in clinical practice", research_depth: "standard", status: "pending", progress: 0 };
      return route.fulfill({ status: 201, json: activeRun });
    }
    if (path === "research-runs/" && method === "GET") return route.fulfill({ json: activeRun ? [activeRun] : [] });
    if (path === "research-runs/run-1/enqueue") return route.fulfill({ status: 202, json: backgroundJob });
    if (path === "research-runs/run-1/status") return route.fulfill({ json: { research_run_id: "run-1", status: "completed", progress: 100, current_step: "completed", error_message: null } });
    if (path === "agent-executions/") return route.fulfill({ json: { total: 1, executions: [{ id: "execution-1", agent_name: "Data Analyst", output_data: { analysis_results: [{ dataset_id: "dataset-1", status: "completed", summary: { filename: "sample.csv", rows: 4, columns: 1 }, findings: ["Four observations."], chart_specs: [{ type: "histogram", column: "visits", counts: [2, 2], bin_edges: [0, 2, 4] }] }] } }] } });
    if (path === "documents/upload" && method === "POST") {
      uploadedDocument = { id: "document-1", project_id: project.id, filename: "notes.txt", file_type: "txt", processing_status: "queued", created_at: "2026-11-18T00:00:00Z" };
      return route.fulfill({ status: 201, json: uploadedDocument });
    }
    if (path === "documents/" && method === "GET") return route.fulfill({ json: { total: uploadedDocument ? 1 : 0, documents: uploadedDocument ? [uploadedDocument] : [] } });
    if (path === "documents/document-1" && method === "GET") return route.fulfill({ json: uploadedDocument || { id: "document-1", processing_status: "cancelled" } });
    if (path === "jobs/" && method === "GET" && new URL(request.url()).searchParams.has("document_id")) return route.fulfill({ json: [documentJob] });
    if (path === "jobs/document-job-1/cancel" && method === "POST") { documentJob = { ...documentJob, status: "cancelled" }; if (uploadedDocument) uploadedDocument.processing_status = "cancelled"; return route.fulfill({ json: documentJob }); }
    if (path === "jobs/document-job-1/retry" && method === "POST") { documentJob = { ...documentJob, status: "queued" }; if (uploadedDocument) uploadedDocument.processing_status = "queued"; return route.fulfill({ status: 202, json: documentJob }); }
    if (path === "reports/generate" && method === "POST") {
      generatedReport = { id: "report-1", research_run_id: "run-1", title: "Research report", report_format: "docx", content: "Evidence-based report", generation_status: "completed" };
      return route.fulfill({ json: { report_id: "report-1", generation_status: "completed", report_format: "docx", file_path: null } });
    }
    if (path === "reports/" && method === "GET") return route.fulfill({ json: { total: generatedReport ? 1 : 0, reports: generatedReport ? [generatedReport] : [] } });
    if (path === "reports/report-1/download") return route.fulfill({ headers: { "content-type": "application/octet-stream" }, body: "test report bytes" });
    if (path === "conversations/" && method === "GET") return route.fulfill({ json: savedConversations });
    if (path === "conversations/" && method === "POST") {
      const body = request.postDataJSON();
      const conversation = { id: "conversation-1", project_id: project.id, title: body.title, created_at: "2026-11-18T00:00:00Z", updated_at: "2026-11-18T00:00:00Z" };
      savedConversations = [conversation];
      return route.fulfill({ status: 201, json: conversation });
    }
    if (path === "conversations/conversation-1/ask" && method === "POST") {
      const query = request.postDataJSON().query;
      return route.fulfill({ json: {
        user_message: { id: "message-2", conversation_id: "conversation-1", role: "user", content: query, created_at: "2026-11-18T00:00:00Z" },
        assistant_message: { id: "message-3", conversation_id: "conversation-1", role: "assistant", agent_name: "ResearchOS RAG", content: "The review found a measurable outcome [1].", created_at: "2026-11-18T00:00:01Z" },
        citations: [], evidence_sufficient: true,
      } });
    }
    if (path === "messages/conversation/conversation-1") return route.fulfill({ json: [{ id: "message-1", conversation_id: "conversation-1", role: "user", content: "What did the review conclude?", created_at: "2026-11-18T00:00:00Z" }] });
    if (path === "jobs/job-1") return route.fulfill({ json: { ...backgroundJob, status: "completed" } });
    if (path === "jobs/" && method === "GET") return route.fulfill({ json: [] });
    if (path.startsWith("documents/")) return route.fulfill({ json: { total: 0, documents: [] } });
    if (path.startsWith("knowledge-graph/")) return route.fulfill({ json: { project_id: project.id, nodes: [], edges: [] } });
    if (path.startsWith("logout")) return route.fulfill({ json: { ok: true } });
    return route.fulfill({ json: { total: 0, sources: [], claims: [], reports: [], executions: [] } });
  });
});

test("signs in and opens a project workspace", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email address").fill(user.email);
  await page.getByLabel("Password").fill("test-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Good to see you, Ada." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Clinical AI review", level: 2 })).toBeVisible();
});

test("shows that the project has no active research run yet", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email address").fill(user.email);
  await page.getByLabel("Password").fill("test-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: /Research runs/ }).click();
  await expect(page.getByText("No runs yet. Start with a focused question.")).toBeVisible();
  await expect(page.getByRole("button", { name: "New research run" })).toBeVisible();
});

test("queues research and displays its completed status", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email address").fill(user.email);
  await page.getByLabel("Password").fill("test-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: /Research runs/ }).click();
  await page.getByRole("button", { name: "New research run" }).click();
  await page.getByRole("button", { name: "Create research run" }).click();
  await expect(page.getByRole("heading", { name: "Research runs" })).toBeVisible();
  await page.getByRole("button", { name: "Run research →" }).click();
  await expect(page.getByText("Research complete. Evidence and report are ready.")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("completed", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("img", { name: "Histogram of visits with 2 bins" })).toBeVisible();
  await page.getByRole("button", { name: "DOCX" }).click();
  await expect(page.getByText("DOCX report generated.")).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download latest report" }).click();
  expect((await downloadPromise).suggestedFilename()).toBe("research-report.docx");
});

test("creates and reviews project conversation history", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email address").fill(user.email);
  await page.getByLabel("Password").fill("test-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "History" }).click();
  await page.getByRole("button", { name: "New conversation" }).click();
  await expect(page.getByText("Conversation created.")).toBeVisible();
  await page.locator(".conversation-open").click();
  await expect(page.getByText("What did the review conclude?")).toBeVisible();
  await page.getByLabel("Ask this project").fill("Summarize the review");
  await page.getByRole("button", { name: "Send question" }).click({ force: true });
  await expect(page.getByText("The review found a measurable outcome [1].")).toBeVisible();
  await page.getByRole("button", { name: /Delete Research notes/ }).click();
  await expect(page.getByText("No saved conversations in this project yet.")).toBeVisible();
});

test("edits the selected project using the project API", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email address").fill(user.email);
  await page.getByLabel("Password").fill("test-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Projects" }).click();
  await page.getByRole("button", { name: "Edit selected" }).click();
  await page.getByLabel("Project name").fill("Updated clinical review");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("button", { name: /Updated clinical review/ })).toBeVisible();
});

test("deletes a project only after explicit confirmation", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email address").fill(user.email);
  await page.getByLabel("Password").fill("test-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Projects" }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete selected" }).click();
  await expect(page.getByRole("heading", { name: "Start with a question worth answering." })).toBeVisible();
});

test("cancels and retries background document indexing", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email address").fill(user.email);
  await page.getByLabel("Password").fill("test-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Document library" }).click();
  await page.locator('input[type="file"]').setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("Research notes") });
  await page.getByRole("button", { name: "Upload document" }).click();
  await expect(page.getByText("notes.txt uploaded. Processing continues in the background.")).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByText("Document processing cancellation requested.")).toBeVisible();
  await page.getByRole("button", { name: "Retry indexing" }).click();
  await expect(page.getByText("Document indexing retry queued.")).toBeVisible();
});

test("preserves the signed-in workspace across a page refresh", async ({ page }) => {
  await page.route("**/api/users/", (route) => route.fulfill({
    status: 200,
    json: [user],
  }));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Good to see you, Ada." })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Good to see you, Ada." })).toBeVisible();
});

test("logout clears the client session and returns to sign-in", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email address").fill(user.email);
  await page.getByLabel("Password").fill("test-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.locator('.top-actions button[title="Sign out"]').click();
  await expect(page.getByRole("heading", { name: "Sign in to your workspace" })).toBeVisible();
});
