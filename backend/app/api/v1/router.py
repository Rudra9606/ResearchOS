from fastapi import APIRouter
from app.api.v1.endpoints import research
from app.api.v1.endpoints import auth
from app.api.v1.endpoints import users
from app.api.v1.endpoints import projects
from app.api.v1.endpoints import conversations
from app.api.v1.endpoints import messages
from app.api.v1.endpoints import documents
from app.api.v1.endpoints import research_runs
from app.api.v1.endpoints import research_sources
from app.api.v1.endpoints import reports
from app.api.v1.endpoints import agent_executions
from app.api.v1.endpoints import verified_claims
from app.api.v1.endpoints import rag
from app.api.v1.endpoints import knowledge_graph
from app.api.v1.endpoints import jobs

api_router = APIRouter()

api_router.include_router(
    research.router,
    prefix="/research",
    tags=["Research"]
)

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["Users"]
)

api_router.include_router(
    projects.router,
    prefix="/projects",
    tags=["Projects"]
)

api_router.include_router(
    conversations.router,
    prefix="/conversations",
    tags=["Conversations"]
)

api_router.include_router(
    messages.router,
    prefix="/messages",
    tags=["Messages"]
)

api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["Documents"]
)

api_router.include_router(
    research_runs.router,
    prefix="/research-runs",
    tags=["Research Runs"]
)

api_router.include_router(
    research_sources.router,
    prefix="/research-sources",
    tags=["Research Sources"]
)

api_router.include_router(
    reports.router,
    prefix="/reports",
    tags=["Reports"]
)

api_router.include_router(
    agent_executions.router,
    prefix="/agent-executions",
    tags=["Agent Executions"],
)

api_router.include_router(
    verified_claims.router,
    prefix="/verified-claims",
    tags=["Verified Claims"],
)

api_router.include_router(
    rag.router,
    prefix="/rag",
    tags=["RAG"],
)

api_router.include_router(
    knowledge_graph.router,
    prefix="/knowledge-graph",
    tags=["Knowledge Graph"],
)

api_router.include_router(
    jobs.router,
    prefix="/jobs",
    tags=["Background Jobs"],
)
