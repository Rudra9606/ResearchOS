from uuid import uuid4

from app.models.research_source import ResearchSource
from app.models.verified_claim import VerifiedClaim


def test_project_graph_contains_only_persisted_records_and_explicit_evidence_links(
    client, auth_headers, db_session
):
    project = client.post(
        "/api/v1/projects/",
        json={"title": "Graph test", "research_topic": "Evidence graph testing"},
        headers=auth_headers,
    )
    assert project.status_code == 201
    project_id = project.json()["id"]
    run = client.post(
        "/api/v1/research-runs/",
        json={
            "project_id": project_id,
            "research_topic": "Evidence graph testing",
            "research_depth": "basic",
        },
        headers=auth_headers,
    )
    assert run.status_code == 201
    run_id = run.json()["id"]

    source = ResearchSource(
        research_run_id=run_id,
        title="Evidence report on model outcomes",
        url="https://example.org/evidence",
        source_type="web",
    )
    db_session.add(source)
    db_session.flush()
    claim = VerifiedClaim(
        research_run_id=run_id,
        claim_text="The report describes a measurable outcome.",
        verification_status="supported",
        evidence="See https://example.org/evidence for the result.",
    )
    db_session.add(claim)
    db_session.flush()

    response = client.get(
        "/api/v1/knowledge-graph/",
        params={"project_id": project_id},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    graph = response.json()
    assert {node["kind"] for node in graph["nodes"]} == {"claim", "source"}
    assert graph["edges"] == [
        {
            "id": f"evidence:{claim.id}:{source.id}",
            "source": f"claim:{claim.id}",
            "target": f"source:{source.id}",
            "relation": "supported",
        }
    ]

    inaccessible = client.get(
        "/api/v1/knowledge-graph/",
        params={"project_id": str(uuid4())},
        headers=auth_headers,
    )
    assert inaccessible.status_code == 404
