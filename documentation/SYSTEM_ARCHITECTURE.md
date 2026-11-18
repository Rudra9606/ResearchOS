# ResearchOS – System Architecture

## 1. Introduction

ResearchOS follows a modular, multi-layered architecture designed to support autonomous AI research, document intelligence, information retrieval, data analysis and automated report generation.

The platform integrates a Next.js frontend, FastAPI backend, LangGraph orchestration engine, specialised AI agents, Retrieval-Augmented Generation (RAG), Large Language Models (LLMs) and persistent data storage.

The architecture is designed to support modular development, scalability, maintainability and reliable AI workflow execution.

## 2. High-Level Architecture

ResearchOS consists of six major architectural layers:

1. Presentation Layer
2. API and Backend Layer
3. Agent Orchestration Layer
4. AI Intelligence Layer
5. Retrieval and Processing Layer
6. Data Storage Layer

### 2.1 Presentation Layer

Technology: Next.js, React, TypeScript and Tailwind CSS.

Responsibilities:

- Provide an interactive user interface.
- Display the research dashboard.
- Allow users to create research projects.
- Support document uploads.
- Provide AI-powered chat.
- Display agent execution progress.
- Present research findings and citations.
- Display data visualisations.
- Allow report downloads.

### 2.2 API and Backend Layer

Technology: Python and FastAPI.

Responsibilities:

- Handle frontend API requests.
- Manage authentication and authorisation.
- Create and manage research projects.
- Process document uploads.
- Communicate with LangGraph workflows.
- Manage conversation history.
- Retrieve research results.
- Generate reports.
- Handle API validation and errors.

### 2.3 Agent Orchestration Layer

Technology: LangGraph and LangChain.

LangGraph coordinates the specialised AI agents and manages research execution.

Responsibilities:

- Initialise research workflows.
- Manage shared workflow state.
- Distribute research tasks.
- Execute agents sequentially or in parallel.
- Handle conditional routing.
- Manage retries and failures.
- Maintain execution checkpoints.
- Support human approval.

### 2.4 AI Intelligence Layer

This layer contains the specialised AI components.

Planned components:

**Planner Agent**
- Understand user requests.
- Create research plans.
- Break research into smaller tasks.
- Assign tasks to appropriate agents.

**Web Research Agent**
- Search the internet.
- Collect relevant information.
- Extract website content.
- Organise source references.

**Academic Research Agent**
- Discover academic papers.
- Retrieve publication information.
- Analyse research methodologies.
- Extract findings and limitations.

**Document Analysis Agent**
- Process uploaded documents.
- Summarise research papers.
- Extract important information.
- Answer document-related questions.

**Data Analyst Agent**
- Analyse uploaded datasets.
- Perform statistical analysis.
- Identify patterns and outliers.
- Generate visualisations.

**Fact Checker Agent**
- Extract factual claims.
- Retrieve supporting evidence.
- Identify contradictory evidence.
- Apply Natural Language Inference.
- Generate verification explanations.

**Report Writer Agent**
- Consolidate research findings.
- Organise report sections.
- Include source references.
- Generate structured reports.

### 2.5 Retrieval and Processing Layer

This layer implements the document intelligence and RAG pipeline.

Technologies:

- PyMuPDF
- Docling
- Sentence Transformers
- ChromaDB
- pgvector
- BM25
- Cross-Encoder

Responsibilities:

- Validate uploaded documents.
- Extract text.
- Clean extracted content.
- Split documents into chunks.
- Generate embeddings.
- Store embeddings.
- Perform semantic retrieval.
- Perform keyword retrieval.
- Rerank relevant results.
- Supply contextual information to LLMs.

### 2.6 Data Storage Layer

Technologies:

- PostgreSQL
- pgvector
- File storage

PostgreSQL stores structured application information.

Planned data includes:

- User accounts.
- Research projects.
- Conversations.
- Messages.
- Uploaded document metadata.
- Research sources.
- Agent execution records.
- Research findings.
- Generated report metadata.

pgvector supports vector similarity search.

File storage maintains uploaded documents and generated reports.

## 3. Frontend Architecture

The frontend will use Next.js with TypeScript.

### Main application pages

1. Landing Page
2. Login and Registration
3. Dashboard
4. Research Workspace
5. AI Research Chat
6. Document Library
7. Fact Verification
8. Data Intelligence
9. Knowledge Graph
10. Research Reports
11. Research History
12. Settings

### Frontend communication

The frontend communicates with FastAPI through REST APIs.

Server-Sent Events (SSE) will be used where appropriate to stream research progress and agent execution updates.

## 4. Backend Architecture

FastAPI will provide modular API endpoints.

### Planned API modules

| Module | Responsibility |
|---|---|
| Authentication | Registration, login and user access |
| Research | Research project management |
| Documents | Document upload and processing |
| Chat | Research conversations |
| Agents | Agent workflow execution |
| Reports | Report generation and downloads |
| History | Persistent research history |

### Backend service modules

- Authentication Service
- Research Service
- Document Processing Service
- RAG Service
- LLM Service
- Agent Orchestration Service
- Data Analysis Service
- Fact Verification Service
- Report Generation Service

## 5. Multi-Agent Architecture

LangGraph will coordinate the research agents.

### Research execution flow

1. User submits a research request.
2. Planner Agent interprets the request.
3. Planner Agent generates a research plan.
4. Research tasks are distributed.
5. Web Research Agent performs web research.
6. Academic Research Agent retrieves academic information.
7. Document Analysis Agent processes relevant documents.
8. Agent outputs are consolidated.
9. Data Analyst executes when data analysis is required.
10. Fact Checker evaluates important claims.
11. Human Review provides approval or requests revisions.
12. Report Writer generates the final report.

### Agent communication

Agents will communicate through a shared LangGraph state.

The shared state will maintain:

- Research objective.
- Research plan.
- Task assignments.
- Agent outputs.
- Collected sources.
- Document references.
- Analysis results.
- Verification results.
- Execution status.

Agents will not independently maintain disconnected copies of the research workflow.

## 6. RAG Architecture

ResearchOS will implement a Retrieval-Augmented Generation pipeline.

### 6.1 Document Ingestion

1. User uploads a document.
2. File validation is performed.
3. Text is extracted.
4. Extracted content is cleaned.
5. Text is divided into chunks.
6. Metadata is attached to chunks.
7. Embeddings are generated.
8. Embeddings and document metadata are stored.

### 6.2 Query Processing

1. User submits a question.
2. The question is converted into an embedding.
3. Semantic retrieval searches relevant chunks.
4. BM25 performs keyword retrieval.
5. Retrieved results are combined.
6. A reranking model reorders relevant chunks.
7. Relevant context is supplied to the LLM.
8. The LLM generates an answer.
9. Source references are attached to the response.

### 6.3 Retrieval Components

| Component | Technology |
|---|---|
| Embedding Generation | Sentence Transformers |
| Vector Database | ChromaDB initially |
| Production Vector Storage | PostgreSQL with pgvector |
| Keyword Retrieval | BM25 |
| Reranking | Cross-Encoder |
| Answer Generation | Gemini / Ollama |

## 7. LLM Architecture

ResearchOS will support configurable LLM providers.

### Google Gemini API

Responsibilities:

- Research planning.
- Research summarisation.
- Report generation.
- Question answering.
- Structured output generation.

### Ollama

Responsibilities:

- Local LLM execution.
- Local experimentation.
- Alternative model inference.
- Reduced dependency on external API providers.

A common LLM service interface will allow model providers to be changed without rewriting the agent implementations.

## 8. Database Architecture

PostgreSQL will act as the primary relational database.

### Planned database entities

- Users
- Research Projects
- Conversations
- Messages
- Documents
- Sources
- Research Results
- Agent Runs
- Reports

### Vector storage

pgvector will support:

- Document embeddings.
- Chunk embeddings.
- Semantic similarity search.
- Retrieval of relevant research content.

ChromaDB will initially be used for local RAG development and experimentation.

The production storage approach will be finalised during database implementation.

## 9. Data Flow Architecture

The overall application workflow:

1. User interacts with the Next.js frontend.
2. Frontend sends a request to FastAPI.
3. FastAPI validates the request and user permissions.
4. FastAPI initiates the LangGraph workflow.
5. Planner Agent creates a research plan.
6. Specialised agents perform assigned tasks.
7. Agents retrieve information from external sources, documents and databases.
8. Research findings are consolidated.
9. Fact Checker evaluates claims against available evidence.
10. Human approval is requested when required.
11. Report Writer generates the final output.
12. Results are stored in PostgreSQL and file storage.
13. Frontend displays the research results.

## 10. Security Architecture

ResearchOS will implement the following security practices:

- Secure user authentication.
- Protected API endpoints.
- Role and ownership-based authorisation.
- Environment variables for API credentials.
- Password hashing.
- Input validation.
- File type and file size validation.
- Secure document access.
- Database access controls.
- Protection against prompt injection in retrieved documents.
- Restricted execution of data analysis operations.

Sensitive API keys and database credentials must never be committed to GitHub.

## 11. Deployment Architecture

Planned deployment technologies:

| Component | Technology |
|---|---|
| Frontend | Vercel |
| Backend | Render or another suitable hosting provider |
| Database | Supabase PostgreSQL |
| Vector Search | pgvector |
| File Storage | Supabase Storage or compatible storage |
| Source Code | GitHub |
| Containerisation | Docker |

Deployment configuration will be finalised after the application has been tested locally.

## 12. Reliability and Performance

ResearchOS will aim to provide:

- Asynchronous processing for long-running tasks.
- Workflow checkpoints.
- Retry mechanisms.
- API timeouts.
- Error handling.
- Persistent execution state.
- Efficient document retrieval.
- Agent execution monitoring.
- Logging and performance tracking.

LangSmith may be integrated for tracing and evaluating agent workflows.

## 13. Architecture Design Principles

The system will follow these principles:

**Modularity:** Each major component should have a clearly defined responsibility.

**Reusability:** Shared services should be reusable across different agents.

**Scalability:** Additional agents and capabilities should be integrable without redesigning the entire platform.

**Maintainability:** Clear module boundaries and consistent coding practices.

**Explainability:** Research findings should include supporting evidence and source references.

**Reliability:** Long-running workflows should support checkpoints, retries and error recovery.

---

## 14. Architecture Status

| Component | Status |
|---|---|
| Frontend Architecture | Designed |
| Backend Architecture | Designed |
| Multi-Agent Architecture | Designed |
| RAG Architecture | Designed |
| Database Architecture | Planned |
| LLM Integration Architecture | Planned |
| Security Architecture | Planned |
| Deployment Architecture | Planned |

**Document Status:** Initial Technical Architecture Specification

**Project:** ResearchOS  
**Author:** Rudra Joshi