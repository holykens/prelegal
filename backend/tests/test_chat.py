"""Tests for the /api/chat endpoint."""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app, build_system_prompt, NDAFormFields, PartyFields

client = TestClient(app)


# ── build_system_prompt ──────────────────────────────────────────────────────

def test_build_system_prompt_includes_current_fields():
    fields = NDAFormFields(purpose="Test purpose", governingLaw="Delaware")
    prompt = build_system_prompt(fields)
    assert "Test purpose" in prompt
    assert "Delaware" in prompt


def test_build_system_prompt_contains_field_names():
    prompt = build_system_prompt(NDAFormFields())
    for field in ["purpose", "effectiveDate", "mndaTermType", "governingLaw", "jurisdiction"]:
        assert field in prompt


# ── helper: build fake litellm response ─────────────────────────────────────

def _mock_llm(reply: str, **extra_fields):
    payload = {"reply": reply, **extra_fields}
    msg = MagicMock()
    msg.content = json.dumps(payload)
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


BASE_FIELDS = {
    "purpose": "",
    "effectiveDate": "2026-05-14",
    "mndaTermType": "expires",
    "mndaTermYears": 1,
    "confidentialityTermType": "years",
    "confidentialityTermYears": 1,
    "governingLaw": "",
    "jurisdiction": "",
    "mndaModifications": "",
    "party1": {"name": "", "title": "", "company": "", "noticeAddress": ""},
    "party2": {"name": "", "title": "", "company": "", "noticeAddress": ""},
}


# ── /api/chat ────────────────────────────────────────────────────────────────

@patch("main.completion")
def test_chat_returns_reply_and_empty_fields(mock_completion):
    mock_completion.return_value = _mock_llm("Hello! What is the purpose of this NDA?")
    res = client.post("/api/chat", json={"messages": [], "current_fields": BASE_FIELDS})
    assert res.status_code == 200
    data = res.json()
    assert data["reply"] == "Hello! What is the purpose of this NDA?"
    assert data["fields"] == {}


@patch("main.completion")
def test_chat_extracts_governing_law(mock_completion):
    mock_completion.return_value = _mock_llm(
        "Got it—Delaware law it is. What city for jurisdiction?",
        governingLaw="Delaware",
    )
    res = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "Use Delaware law"}],
            "current_fields": BASE_FIELDS,
        },
    )
    assert res.status_code == 200
    assert res.json()["fields"]["governingLaw"] == "Delaware"


@patch("main.completion")
def test_chat_extracts_party_companies(mock_completion):
    mock_completion.return_value = _mock_llm(
        "Party 1 is Acme Corp, Party 2 is Widget Ltd.",
        party1={"company": "Acme Corp"},
        party2={"company": "Widget Ltd"},
    )
    res = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "Acme Corp and Widget Ltd"}],
            "current_fields": BASE_FIELDS,
        },
    )
    data = res.json()
    assert data["fields"]["party1"]["company"] == "Acme Corp"
    assert data["fields"]["party2"]["company"] == "Widget Ltd"


@patch("main.completion")
def test_chat_null_fields_excluded_from_response(mock_completion):
    """Null LLM fields must not appear in returned fields dict."""
    mock_completion.return_value = _mock_llm(
        "Noted.",
        purpose=None,
        governingLaw="California",
    )
    res = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "California"}], "current_fields": BASE_FIELDS},
    )
    data = res.json()
    assert "purpose" not in data["fields"]
    assert data["fields"]["governingLaw"] == "California"


@patch("main.completion", side_effect=Exception("LLM unavailable"))
def test_chat_handles_llm_error_gracefully(mock_completion):
    res = client.post("/api/chat", json={"messages": [], "current_fields": BASE_FIELDS})
    assert res.status_code == 200
    data = res.json()
    assert data["fields"] == {}
    assert len(data["reply"]) > 0


# ── /api/health ──────────────────────────────────────────────────────────────

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
