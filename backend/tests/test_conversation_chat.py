from uuid import uuid4

from app.rag.qa import RAGQuestionAnsweringService


def test_conversation_ask_saves_grounded_turn_and_citations(client, auth_headers, monkeypatch):
    project = client.post(
        "/api/v1/projects/",
        json={"title": "Chat project", "research_topic": "Evidence-based chat"},
        headers=auth_headers,
    ).json()
    conversation = client.post(
        "/api/v1/conversations/",
        json={"project_id": project["id"], "title": "Review"},
        headers=auth_headers,
    ).json()
    observed = {}

    async def fake_answer(self, question, **kwargs):
        observed.update(kwargs)
        observed["question"] = question
        return {
            "answer": "The document supports the finding [1].",
            "citations": [{
                "citation": "[1]", "chunk_id": "chunk-1",
                "document_id": str(uuid4()), "document_filename": "study.pdf",
                "chunk_index": 0, "source_url": None,
                "content": "Supporting evidence", "retrieval_score": 0.9,
                "rerank_score": None, "metadata": {},
            }],
            "evidence_sufficient": True,
        }

    monkeypatch.setattr(RAGQuestionAnsweringService, "answer", fake_answer)
    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/ask",
        json={"query": "What did the study find?"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["evidence_sufficient"] is True
    assert result["citations"][0]["document_filename"] == "study.pdf"
    assert "Sources:" in result["assistant_message"]["content"]
    assert str(observed["project_id"]) == project["id"]
    assert observed["question"] == "What did the study find?"

    history = client.get(
        f"/api/v1/messages/conversation/{conversation['id']}",
        headers=auth_headers,
    ).json()
    assert [message["role"] for message in history] == ["user", "assistant"]
    assert "study.pdf" in history[1]["content"]


def test_conversation_ask_passes_only_recent_owned_history(client, auth_headers, monkeypatch):
    project = client.post(
        "/api/v1/projects/",
        json={"title": "History project", "research_topic": "Conversation context"},
        headers=auth_headers,
    ).json()
    conversation = client.post(
        "/api/v1/conversations/",
        json={"project_id": project["id"]},
        headers=auth_headers,
    ).json()
    client.post(
        f"/api/v1/messages/?conversation_id={conversation['id']}",
        json={"content": "Earlier question about the sample size."},
        headers=auth_headers,
    )
    observed = {}

    async def fake_answer(self, question, **kwargs):
        observed.update(kwargs)
        return {"answer": "Insufficient evidence.", "citations": [], "evidence_sufficient": False}

    monkeypatch.setattr(RAGQuestionAnsweringService, "answer", fake_answer)
    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/ask",
        json={"query": "And how does that compare?"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert "Earlier question about the sample size." in observed["conversation_context"]
    assert response.json()["evidence_sufficient"] is False


def test_conversation_ask_rejects_another_users_conversation(client, auth_headers):
    response = client.post(
        f"/api/v1/conversations/{uuid4()}/ask",
        json={"query": "Private question"},
        headers=auth_headers,
    )
    assert response.status_code == 404
