"""API tests for ResearchOS backend (Task 3.18)."""

import pytest


def test_request_id_is_returned_and_invalid_values_are_replaced(client):
    response = client.get("/health", headers={"X-Request-ID": "trace-test_01"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "trace-test_01"

    invalid = client.get("/health", headers={"X-Request-ID": "bad/value"})
    assert invalid.status_code == 200
    assert invalid.headers["x-request-id"] != "bad/value"


class TestUserAPI:
    """Test user management API endpoints."""

    def test_list_users_requires_auth(self, client):
        """Test that listing users requires authentication."""
        response = client.get("/api/v1/users/")
        assert response.status_code == 401

    def test_profile_routes_only_expose_current_user(self, client, auth_headers):
        first = client.get("/api/v1/users/", headers=auth_headers)
        assert first.status_code == 200
        assert len(first.json()) == 1
        current_user_id = first.json()[0]["id"]

        second = client.post(
            "/api/v1/auth/register",
            json={
                "name": "Another User",
                "email": "another@example.com",
                "password": "AnotherPassword123!",
            },
        )
        assert second.status_code == 201
        second_user_id = second.json()["user"]["id"]

        assert second_user_id != current_user_id
        assert client.get(
            f"/api/v1/users/{second_user_id}", headers=auth_headers
        ).status_code == 404
        assert [user["id"] for user in client.get(
            "/api/v1/users/", headers=auth_headers
        ).json()] == [current_user_id]
        assert client.post("/api/v1/users/", headers=auth_headers).status_code == 405


class TestProjectAPI:
    """Test project management API endpoints."""

    def test_create_project(self, client, auth_headers):
        """Test creating a research project."""
        project_data = {
            "title": "Test Project",
            "research_topic": "Artificial Intelligence Research",
            "description": "A test project",
        }
        response = client.post(
            "/api/v1/projects/",
            json=project_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Project"
        assert data["research_topic"] == "Artificial Intelligence Research"

    def test_list_projects(self, client, auth_headers):
        """Test listing projects."""
        response = client.get("/api/v1/projects/", headers=auth_headers)
        assert response.status_code == 200

    def test_project_pagination_returns_filtered_total_and_is_bounded(
        self, client, auth_headers
    ):
        for number in range(2):
            created = client.post(
                "/api/v1/projects/",
                json={
                    "title": f"Project {number}",
                    "research_topic": f"Research topic {number}",
                },
                headers=auth_headers,
            )
            assert created.status_code == 201

        page = client.get(
            "/api/v1/projects/?skip=1&limit=1", headers=auth_headers
        )
        assert page.status_code == 200
        assert page.json()["total"] == 2
        assert len(page.json()["projects"]) == 1
        assert client.get(
            "/api/v1/projects/?limit=101", headers=auth_headers
        ).status_code == 422

    def test_get_project_by_id(self, client, auth_headers):
        """Test getting a project by ID."""
        project_data = {
            "title": "Test Project",
            "research_topic": "AI Research Topic",
        }
        create_resp = client.post(
            "/api/v1/projects/",
            json=project_data,
            headers=auth_headers,
        )
        project_id = create_resp.json()["id"]
        response = client.get(
            f"/api/v1/projects/{project_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_update_project(self, client, auth_headers):
        """Test updating a project."""
        project_data = {
            "title": "Original Title",
            "research_topic": "Original Topic Research",
        }
        create_resp = client.post(
            "/api/v1/projects/",
            json=project_data,
            headers=auth_headers,
        )
        project_id = create_resp.json()["id"]
        update_data = {"title": "Updated Title"}
        response = client.put(
            f"/api/v1/projects/{project_id}",
            json=update_data,
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_delete_project(self, client, auth_headers):
        """Test deleting a project."""
        project_data = {
            "title": "To Delete",
            "research_topic": "Delete Me Research",
        }
        create_resp = client.post(
            "/api/v1/projects/",
            json=project_data,
            headers=auth_headers,
        )
        project_id = create_resp.json()["id"]
        response = client.delete(
            f"/api/v1/projects/{project_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204


class TestConversationAPI:
    """Test conversation management API endpoints."""

    def test_create_conversation(self, client, auth_headers):
        """Test creating a conversation."""
        project_data = {
            "title": "Test Project",
            "research_topic": "Artificial Intelligence Research",
        }
        project_resp = client.post(
            "/api/v1/projects/",
            json=project_data,
            headers=auth_headers,
        )
        project_id = project_resp.json()["id"]

        conv_data = {
            "project_id": str(project_id),
            "title": "Test Conversation",
        }
        response = client.post(
            "/api/v1/conversations/",
            json=conv_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["project_id"] == str(project_id)
        assert "thread_id" in data

    def test_list_conversations(self, client, auth_headers):
        """Test listing conversations."""
        response = client.get("/api/v1/conversations/", headers=auth_headers)
        assert response.status_code == 200


class TestMessageAPI:
    """Test message management API endpoints."""

    def test_send_message(self, client, auth_headers):
        """Test sending a message."""
        project_resp = client.post(
            "/api/v1/projects/",
            json={"title": "Test", "research_topic": "AI Research Topic"},
            headers=auth_headers,
        )
        project_id = project_resp.json()["id"]

        conv_resp = client.post(
            "/api/v1/conversations/",
            json={"project_id": str(project_id), "title": "Test Conv"},
            headers=auth_headers,
        )
        conv_id = conv_resp.json()["id"]

        msg_data = {"content": "Hello, this is a test message."}
        response = client.post(
            f"/api/v1/messages/?conversation_id={conv_id}",
            json=msg_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Hello, this is a test message."
        assert data["role"] == "user"

    def test_list_messages(self, client, auth_headers):
        """Test listing messages."""
        project_resp = client.post(
            "/api/v1/projects/",
            json={"title": "Test", "research_topic": "AI Research Topic"},
            headers=auth_headers,
        )
        project_id = project_resp.json()["id"]

        conv_resp = client.post(
            "/api/v1/conversations/",
            json={"project_id": str(project_id), "title": "Test Conv"},
            headers=auth_headers,
        )
        conv_id = conv_resp.json()["id"]

        client.post(
            f"/api/v1/messages/?conversation_id={conv_id}",
            json={"content": "Test message"},
            headers=auth_headers,
        )

        response = client.get(
            f"/api/v1/messages/conversation/{conv_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
