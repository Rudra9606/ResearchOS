"""Build a project graph from persisted, traceable research records."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.crud.project import get_project_by_id
from app.db.session import get_db
from app.models.research_run import ResearchRun
from app.models.research_source import ResearchSource
from app.models.user import User
from app.models.verified_claim import VerifiedClaim

router = APIRouter()


@router.get("/", summary="Get a traceable source and claim graph for a project")
def get_project_graph(
    project_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return only stored claims and sources; edges require explicit evidence references."""
    project = get_project_by_id(db, project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found or access denied.")

    runs = db.scalars(
        select(ResearchRun).where(ResearchRun.project_id == project_id)
    ).all()
    run_ids = [run.id for run in runs]
    sources = db.scalars(
        select(ResearchSource).where(ResearchSource.research_run_id.in_(run_ids))
    ).all() if run_ids else []
    claims = db.scalars(
        select(VerifiedClaim).where(VerifiedClaim.research_run_id.in_(run_ids))
    ).all() if run_ids else []

    nodes = [
        {"id": f"source:{source.id}", "kind": "source", "label": source.title,
         "url": source.url, "source_type": source.source_type, "run_id": str(source.research_run_id)}
        for source in sources
    ]
    nodes.extend(
        {"id": f"claim:{claim.id}", "kind": "claim", "label": claim.claim_text,
         "status": claim.verification_status, "confidence": claim.confidence_score,
         "run_id": str(claim.research_run_id)}
        for claim in claims
    )

    # An edge is emitted only when the persisted claim evidence names the exact
    # source URL or title. We do not infer links from topic similarity.
    edges = []
    for claim in claims:
        evidence = (claim.evidence or "").casefold()
        if not evidence:
            continue
        for source in sources:
            if source.research_run_id != claim.research_run_id:
                continue
            references_url = bool(source.url and source.url.casefold() in evidence)
            references_title = len(source.title.strip()) >= 12 and source.title.casefold() in evidence
            if references_url or references_title:
                edges.append({
                    "id": f"evidence:{claim.id}:{source.id}",
                    "source": f"claim:{claim.id}",
                    "target": f"source:{source.id}",
                    "relation": claim.verification_status,
                })

    return {"project_id": str(project_id), "nodes": nodes, "edges": edges}
