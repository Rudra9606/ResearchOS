# AI agent architecture

Phase 5 extends the existing LangGraph workflow without replacing its provider,
retrieval, or persistence layers.

## Agents

- **Research Coordinator** validates topic and depth and initializes shared
  state.
- **Planner** uses the configured Gemini/Ollama provider with a Pydantic
  structured response to create objectives, subquestions, source requirements,
  and workflow steps.
- **Web Research** and **Academic Research** use the Phase 3 provider services.
- **Document Analysis** retrieves user-owned RAG chunks and produces
  citation-preserving summaries, concepts, entities, and visible
  contradictions.
- **Data Analyst** reads only CSV/XLSX files with pandas. It reports schema,
  types, descriptive statistics, missing values, duplicates, IQR outliers, and
  chart specifications. It never executes uploaded code.
- **Fact Checker** extracts claims and evaluates them only against attributed
  evidence.
- **Report Writer** aggregates findings and avoids unsupported conclusions when
  evidence is absent.

## Workflow

The graph runs:

`Coordinator -> Planner -> Web -> Academic -> optional Document/Data -> Fact Checker -> Report Writer`

Routing uses supplied, ownership-validated document and dataset IDs. Agent
failures are recorded in shared state and do not become fabricated findings.
Configured retries update the same execution record and expose retry counts.
SQLite checkpointers remain supported through the existing `checkpointer`
constructor argument.

Research execution accepts optional `document_ids` and `dataset_ids` query
query parameters on `POST /api/v1/research-runs/{run_id}/execute`; each is
validated against the authenticated user's project.

## Persistence

When a database session, user ID, and research-run ID are supplied, every graph
node creates an `AgentExecution` record, marks it running, and stores bounded
input/output summaries, timestamps, status, and safe error text. Run progress is
updated after each persisted node. No raw document or dataset contents are
stored in execution metadata.

## Testing

Agent tests inject fake structured providers and retrieval services. Dataset
tests use temporary CSV/XLSX files. External LLM, Tavily, academic, and
database-provider calls are not required for the automated unit suite.
