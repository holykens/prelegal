"""Tests for document persistence endpoints."""
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

_EMAIL = "doctest@example.com"
_PASSWORD = "password123"


def _auth_header():
    client.post("/api/auth/register", json={"email": _EMAIL, "password": _PASSWORD})
    res = client.post("/api/auth/login", json={"email": _EMAIL, "password": _PASSWORD})
    token = res.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _sample_doc():
    return {
        "document_name": "Mutual Non-Disclosure Agreement",
        "fields": {"Provider": "Acme Corp", "Customer": "Widget Ltd"},
        "messages": [
            {"role": "user", "content": "I need an NDA"},
            {"role": "assistant", "content": "Great! Let's fill out the NDA."},
        ],
    }


# ── create document ───────────────────────────────────────────────────────────

def test_create_document_returns_201():
    headers = _auth_header()
    res = client.post("/api/documents", json=_sample_doc(), headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert "id" in data
    assert data["document_name"] == "Mutual Non-Disclosure Agreement"


def test_create_document_requires_auth():
    res = client.post("/api/documents", json=_sample_doc())
    assert res.status_code == 401


# ── list documents ────────────────────────────────────────────────────────────

def test_list_documents_empty_for_new_user():
    # Register a brand-new user with unique email
    client.post("/api/auth/register", json={"email": "fresh@example.com", "password": "password123"})
    token = client.post("/api/auth/login", json={"email": "fresh@example.com", "password": "password123"}).json()["token"]
    res = client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == []


def test_list_documents_returns_created_docs():
    headers = _auth_header()
    client.post("/api/documents", json=_sample_doc(), headers=headers)
    res = client.get("/api/documents", headers=headers)
    assert res.status_code == 200
    docs = res.json()
    assert any(d["document_name"] == "Mutual Non-Disclosure Agreement" for d in docs)


def test_list_documents_includes_fields():
    headers = _auth_header()
    client.post("/api/documents", json=_sample_doc(), headers=headers)
    res = client.get("/api/documents", headers=headers)
    doc = res.json()[0]
    assert "fields" in doc
    assert doc["fields"]["Provider"] == "Acme Corp"


def test_list_documents_includes_messages():
    """Regression: GET /api/documents must return messages so the history page
    can display message count without crashing on undefined.length."""
    headers = _auth_header()
    client.post("/api/documents", json=_sample_doc(), headers=headers)
    res = client.get("/api/documents", headers=headers)
    assert res.status_code == 200
    doc = res.json()[0]
    assert "messages" in doc, "messages key must be present in list response"
    assert isinstance(doc["messages"], list)
    assert len(doc["messages"]) == 2


# ── get document ──────────────────────────────────────────────────────────────

def test_get_document_returns_full_record():
    headers = _auth_header()
    create_res = client.post("/api/documents", json=_sample_doc(), headers=headers)
    doc_id = create_res.json()["id"]
    res = client.get(f"/api/documents/{doc_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == doc_id
    assert data["document_name"] == "Mutual Non-Disclosure Agreement"
    assert len(data["messages"]) == 2


def test_get_document_404_for_unknown():
    headers = _auth_header()
    res = client.get("/api/documents/999999", headers=headers)
    assert res.status_code == 404


def test_get_document_isolated_between_users():
    # User A creates a doc
    client.post("/api/auth/register", json={"email": "usera@example.com", "password": "password123"})
    token_a = client.post("/api/auth/login", json={"email": "usera@example.com", "password": "password123"}).json()["token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    create_res = client.post("/api/documents", json=_sample_doc(), headers=headers_a)
    doc_id = create_res.json()["id"]

    # User B cannot access it
    client.post("/api/auth/register", json={"email": "userb@example.com", "password": "password123"})
    token_b = client.post("/api/auth/login", json={"email": "userb@example.com", "password": "password123"}).json()["token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    res = client.get(f"/api/documents/{doc_id}", headers=headers_b)
    assert res.status_code == 404


# ── update document ───────────────────────────────────────────────────────────

def test_update_document_persists_new_fields():
    headers = _auth_header()
    doc_id = client.post("/api/documents", json=_sample_doc(), headers=headers).json()["id"]
    updated = {**_sample_doc(), "fields": {"Provider": "Acme Corp", "Customer": "New Customer Inc"}}
    res = client.put(f"/api/documents/{doc_id}", json=updated, headers=headers)
    assert res.status_code == 200

    fetched = client.get(f"/api/documents/{doc_id}", headers=headers).json()
    assert fetched["fields"]["Customer"] == "New Customer Inc"


def test_document_restore_preserves_all_data():
    """Regression: the data a user fills in must survive a create→update→fetch cycle
    so that clicking a history item fully restores the document.

    Previously GET /api/documents/{id} returned the correct record but
    GET /api/documents (list) omitted messages, causing the history page to crash
    before the user could even click restore."""
    headers = _auth_header()

    # Simulate: user starts a document (create)
    initial = {
        "document_name": "Pilot Agreement",
        "fields": {"Provider": "Acme Corp"},
        "messages": [
            {"role": "user", "content": "I need a pilot agreement"},
            {"role": "assistant", "content": "Sure! Who is the Provider?"},
            {"role": "user", "content": "Acme Corp"},
        ],
    }
    doc_id = client.post("/api/documents", json=initial, headers=headers).json()["id"]

    # Simulate: user fills more fields (update)
    updated = {
        "document_name": "Pilot Agreement",
        "fields": {"Provider": "Acme Corp", "Customer": "Widget Ltd", "Pilot Period": "30 days"},
        "messages": initial["messages"] + [
            {"role": "assistant", "content": "Got it! What is the Customer name?"},
            {"role": "user", "content": "Widget Ltd"},
            {"role": "assistant", "content": "And the Pilot Period?"},
            {"role": "user", "content": "30 days"},
        ],
    }
    client.put(f"/api/documents/{doc_id}", json=updated, headers=headers)

    # Restore: fetch the document by ID (what the frontend does when clicking history)
    res = client.get(f"/api/documents/{doc_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()

    # All fields must be present
    assert data["fields"]["Provider"] == "Acme Corp"
    assert data["fields"]["Customer"] == "Widget Ltd"
    assert data["fields"]["Pilot Period"] == "30 days"

    # Full message history must be preserved
    assert len(data["messages"]) == 7
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][-1]["content"] == "30 days"

    # The document must also appear correctly in the list view
    list_res = client.get("/api/documents", headers=headers)
    assert list_res.status_code == 200
    list_doc = next(d for d in list_res.json() if d["id"] == doc_id)
    assert "messages" in list_doc, "messages must be present in list response for history page"
    assert len(list_doc["messages"]) == 7
    assert list_doc["fields"]["Customer"] == "Widget Ltd"


def test_update_document_404_for_wrong_user():
    client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    token_owner = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "password123"}).json()["token"]
    doc_id = client.post("/api/documents", json=_sample_doc(), headers={"Authorization": f"Bearer {token_owner}"}).json()["id"]

    client.post("/api/auth/register", json={"email": "other@example.com", "password": "password123"})
    token_other = client.post("/api/auth/login", json={"email": "other@example.com", "password": "password123"}).json()["token"]
    res = client.put(f"/api/documents/{doc_id}", json=_sample_doc(), headers={"Authorization": f"Bearer {token_other}"})
    assert res.status_code == 404
