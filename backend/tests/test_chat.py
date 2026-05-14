"""Tests for the Prelegal backend API."""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app, extract_fields, _selection_prompt, _filling_prompt

client = TestClient(app)


# ── extract_fields ────────────────────────────────────────────────────────────

def test_extract_fields_coverpage_link():
    content = '<span class="coverpage_link">Purpose</span> and <span class="coverpage_link">Effective Date</span>'
    assert extract_fields(content) == ["Purpose", "Effective Date"]


def test_extract_fields_keyterms_link():
    content = '<span class="keyterms_link">Partner</span> and <span class="keyterms_link">Provider</span>'
    assert extract_fields(content) == ["Partner", "Provider"]


def test_extract_fields_orderform_link():
    content = '<span class="orderform_link">Pilot Period</span>'
    assert extract_fields(content) == ["Pilot Period"]


def test_extract_fields_deduplicates():
    content = (
        '<span class="coverpage_link">Purpose</span> '
        '<span class="coverpage_link">Purpose</span>'
    )
    assert extract_fields(content) == ["Purpose"]


def test_extract_fields_ignores_header_spans():
    content = '<span class="header_2">Section Title</span> <span class="coverpage_link">Field</span>'
    assert extract_fields(content) == ["Field"]


# ── system prompts ────────────────────────────────────────────────────────────

def test_selection_prompt_lists_documents():
    prompt = _selection_prompt()
    assert "Mutual Non-Disclosure Agreement" in prompt
    assert "Cloud Service Agreement" in prompt


def test_filling_prompt_includes_unfilled():
    fields = {"Provider": "Acme"}
    prompt = _filling_prompt("Pilot Agreement", ["Provider", "Customer", "Pilot Period"], fields)
    assert "Customer" in prompt
    assert "Pilot Period" in prompt
    assert "Acme" in prompt


# ── helper: build fake litellm response ──────────────────────────────────────

def _mock_llm(reply: str, document_name=None, slots=None):
    payload = {
        "reply": reply,
        "document_name": document_name,
        "slots": slots or [],
    }
    msg = MagicMock()
    msg.content = json.dumps(payload)
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


# ── /api/chat — document selection phase ─────────────────────────────────────

@patch("main.completion")
def test_chat_selection_phase_returns_reply(mock_completion):
    mock_completion.return_value = _mock_llm("What document do you need?")
    res = client.post("/api/chat", json={"messages": [], "document_name": None, "fields": {}})
    assert res.status_code == 200
    data = res.json()
    assert data["reply"] == "What document do you need?"
    assert data["document_name"] is None
    assert data["fields"] == {}


@patch("main.completion")
def test_chat_selects_document(mock_completion):
    mock_completion.return_value = _mock_llm(
        "Great! Let's fill out the Mutual NDA.",
        document_name="Mutual Non-Disclosure Agreement",
    )
    res = client.post("/api/chat", json={
        "messages": [{"role": "user", "content": "I need an NDA"}],
        "document_name": None,
        "fields": {},
    })
    assert res.status_code == 200
    assert res.json()["document_name"] == "Mutual Non-Disclosure Agreement"


# ── /api/chat — field filling phase ──────────────────────────────────────────

@patch("main.completion")
def test_chat_extracts_fields(mock_completion):
    mock_completion.return_value = _mock_llm(
        "Got it! What state governs this agreement?",
        slots=[
            {"key": "Provider", "value": "Acme Corp"},
            {"key": "Customer", "value": "Widget Ltd"},
        ],
    )
    res = client.post("/api/chat", json={
        "messages": [{"role": "user", "content": "Provider is Acme Corp, customer is Widget Ltd"}],
        "document_name": "Pilot Agreement",
        "fields": {},
    })
    assert res.status_code == 200
    data = res.json()
    assert data["fields"]["Provider"] == "Acme Corp"
    assert data["fields"]["Customer"] == "Widget Ltd"


@patch("main.completion")
def test_chat_safety_net4_extracts_ack_from_reply(mock_completion):
    """S4: if model acknowledges a field in reply but omits it from slots, extract from reply."""
    mock_completion.return_value = _mock_llm(
        "Payment Process has been set to: Ken Masters will pay $200k monthly.",
        slots=[],  # model forgot to include the field
    )
    res = client.post("/api/chat", json={
        "messages": [{"role": "user", "content": "Ken Masters will pay $200k monthly"}],
        "document_name": "Cloud Service Agreement",
        "fields": {},
    })
    assert res.status_code == 200
    data = res.json()
    assert "Payment Process" in data["fields"], (
        f"S4 should have extracted Payment Process from reply, got fields: {data['fields']}"
    )


@patch("main.completion")
def test_chat_appends_followup_when_reply_has_no_question(mock_completion):
    """Backend must append a follow-up question even when the model forgets to."""
    mock_completion.return_value = _mock_llm(
        "Got it, the Customer is Ken Masters.",  # no '?' — model forgot to ask next question
        slots=[{"key": "Customer", "value": "Ken Masters"}],
    )
    res = client.post("/api/chat", json={
        "messages": [{"role": "user", "content": "Customer is Ken Masters"}],
        "document_name": "Pilot Agreement",
        "fields": {},
    })
    assert res.status_code == 200
    reply = res.json()["reply"]
    assert reply.endswith("?"), f"Expected reply to end with '?', got: {reply!r}"


@patch("main.completion")
def test_chat_does_not_re_ask_field_set_to_none(mock_completion):
    """A field set to 'None' (user said leave empty) must not be appended as a follow-up question."""
    mock_completion.return_value = _mock_llm(
        "Noted, moving on.",  # reply already ends without '?'
        slots=[{"key": "Use Limitations", "value": "None"}],
    )
    res = client.post("/api/chat", json={
        "messages": [{"role": "user", "content": "Leave Use Limitations empty"}],
        "document_name": "Cloud Service Agreement",
        # Use Limitations is already in fields — the backend should NOT re-ask it
        "fields": {"Customer": "Ken", "Provider": "Ryu", "Use Limitations": "None"},
    })
    assert res.status_code == 200
    reply = res.json()["reply"]
    # The backend appends a follow-up, but it must NOT be about Use Limitations
    assert "What is the Use Limitations" not in reply, f"Re-asked handled field: {reply!r}"
    # The follow-up must still end with '?' (other fields remain)
    assert reply.endswith("?"), f"Expected a follow-up question, got: {reply!r}"


@patch("main.completion")
def test_chat_does_not_append_followup_when_reply_already_has_question(mock_completion):
    """Backend must NOT double-append a question if the model already asked one."""
    mock_completion.return_value = _mock_llm(
        "Got it! Who is the Provider for this agreement?",
        slots=[{"key": "Customer", "value": "Ken Masters"}],
    )
    res = client.post("/api/chat", json={
        "messages": [{"role": "user", "content": "Customer is Ken Masters"}],
        "document_name": "Pilot Agreement",
        "fields": {},
    })
    assert res.status_code == 200
    reply = res.json()["reply"]
    # Should end with exactly one '?'
    assert reply.count("?") >= 1
    assert reply == "Got it! Who is the Provider for this agreement?"


@patch("main.completion", side_effect=Exception("LLM unavailable"))
def test_chat_handles_llm_error(mock_completion):
    res = client.post("/api/chat", json={"messages": [], "document_name": None, "fields": {}})
    assert res.status_code == 200
    data = res.json()
    assert data["fields"] == {}
    assert len(data["reply"]) > 0


# ── /api/catalog ──────────────────────────────────────────────────────────────

def test_catalog_returns_list():
    res = client.get("/api/catalog")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "name" in data[0]
    assert "filename" in data[0]


# ── /api/template ─────────────────────────────────────────────────────────────

def test_template_returns_content_and_fields():
    res = client.get("/api/template", params={"document_name": "Mutual Non-Disclosure Agreement"})
    assert res.status_code == 200
    data = res.json()
    assert "content" in data
    assert "fields" in data
    assert isinstance(data["fields"], list)
    assert len(data["fields"]) > 0


def test_template_returns_404_for_unknown():
    res = client.get("/api/template", params={"document_name": "Nonexistent Document"})
    assert res.status_code == 404


# ── /api/health ───────────────────────────────────────────────────────────────

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
