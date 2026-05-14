import os
import re
import json
import sqlite3
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from litellm import completion
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title="Prelegal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "prelegal.db"))
MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

_BASE_DIR = os.path.dirname(__file__)
_catalog_path = os.getenv("CATALOG_PATH", os.path.join(_BASE_DIR, "catalog.json"))
TEMPLATES_DIR = os.getenv("TEMPLATES_DIR", os.path.join(_BASE_DIR, "templates"))
_catalog: list[dict] = []
_catalog_by_name: dict[str, dict] = {}

if os.path.exists(_catalog_path):
    with open(_catalog_path, encoding="utf-8") as _f:
        _catalog = json.load(_f)
    _catalog_by_name = {doc["name"]: doc for doc in _catalog}

# Matches all three span types used as fillable placeholders across templates
_FIELD_SPAN_RE = re.compile(
    r'<span class="(?:coverpage_link|keyterms_link|orderform_link)">([^<]+)</span>'
)


def load_template(doc_name: str) -> str | None:
    doc = _catalog_by_name.get(doc_name)
    if not doc:
        return None
    # doc["filename"] is like "templates/Mutual-NDA.md"; strip the leading "templates/" prefix
    # since we resolve relative to TEMPLATES_DIR
    filename = os.path.basename(doc["filename"])
    path = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def extract_fields(content: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for field_name in _FIELD_SPAN_RE.findall(content):
        if field_name not in seen:
            seen.add(field_name)
            result.append(field_name)
    return result


def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/catalog")
async def get_catalog():
    return _catalog


@app.get("/api/template")
async def get_template(document_name: str = Query(..., max_length=200)):
    content = load_template(document_name)
    if content is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"content": content, "fields": extract_fields(content)}


# ── Chat models ───────────────────────────────────────────────────────────────

class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessageIn] = Field(..., max_length=50)
    document_name: Optional[str] = Field(None, max_length=200)
    fields: dict[str, str] = {}


# ── LLM structured output model ───────────────────────────────────────────────

class FieldUpdate(BaseModel):
    key: str = Field(..., description="Field name exactly as it appears in the template")
    value: str = Field(..., description="Value for this field")


class DocumentExtraction(BaseModel):
    reply: str = Field(
        ...,
        description=(
            "Your natural language message to the user. "
            "Write 1-3 complete sentences in plain conversational English. "
            "This must NOT be a JSON key name, a field name, or a code identifier — "
            "it must be actual human-readable text."
        ),
    )
    document_name: Optional[str] = Field(
        None,
        description="Exact document name from catalog if the user selected one this turn, null otherwise",
    )
    slots: list[FieldUpdate] = Field(
        default_factory=list,
        description="Field name/value pairs extracted from what the user said this turn",
    )


# ── System prompts ────────────────────────────────────────────────────────────

def _selection_prompt() -> str:
    doc_list = "\n".join(f"- {d['name']}: {d['description']}" for d in _catalog)
    return f"""You are a legal document assistant for Prelegal.

Available documents:
{doc_list}

Your job:
1. Ask the user what document they need.
2. Match their request to the closest document in the list above.
3. If they request something not in the list, explain it is not supported and suggest the closest available option.
4. Once the user confirms a document, set document_name to the EXACT name from the list.

Rules:
- Set document_name to the exact catalog name when the user selects or clearly indicates a document.
- Set document_name to null if no document has been confirmed yet.
- Do not extract any field values during the selection phase; slots must stay empty.
- Your reply must be natural conversational English — a complete sentence, never a field name or code keyword.
- Always end your reply with a question to advance the conversation."""


def _filling_prompt(document_name: str, template_fields: list[str], current_fields: dict) -> str:
    fields_list = "\n".join(f"- {f}" for f in template_fields)
    filled = {k: v for k, v in current_fields.items() if v.strip()}
    unfilled = [f for f in template_fields if not current_fields.get(f, "").strip()]

    return f"""You are a legal document assistant helping a user complete a {document_name}.

Required fields:
{fields_list}

Already filled:
{json.dumps(filled, indent=2) if filled else "None yet"}

Still needed:
{chr(10).join(f"- {f}" for f in unfilled) if unfilled else "All fields collected — ready to review!"}

Rules:
- When the user provides a value that matches one of the required fields above, capture it using the exact field name from the list.
- Keep document_name null (document is already selected).
- Focus on one or two missing fields per turn — do not overwhelm the user.
- Your reply must be natural conversational English — never output a field name, JSON key, or code word as your reply.
- If all fields are complete, congratulate the user and invite them to review or download the document.
- MANDATORY: If there are any unfilled fields, the very last sentence of your reply MUST be a question asking for the next missing piece of information. Your reply cannot end without a question mark (?) when fields remain unfilled."""


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    if req.document_name:
        content = load_template(req.document_name)
        if content is None:
            return {"reply": "I couldn't load that template. Please try again.", "document_name": None, "fields": {}}
        template_fields = extract_fields(content)
        system_prompt = _filling_prompt(req.document_name, template_fields, req.fields)
    else:
        system_prompt = _selection_prompt()

    messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m.role, "content": m.content} for m in req.messages[-20:]
    ]

    try:
        response = completion(
            model=MODEL,
            messages=messages,
            response_format=DocumentExtraction,
            reasoning_effort="low",
            extra_body=EXTRA_BODY,
        )
        extraction = DocumentExtraction.model_validate_json(response.choices[0].message.content)
    except Exception as exc:
        print(f"[chat] LLM error: {exc!r}")
        return {"reply": "I had trouble processing that. Please try again.", "document_name": None, "fields": {}}

    # Guard against the model echoing a schema key as the reply.
    _bad_reply_tokens = {"slots", "field_updates", "document_name", "reply", "key", "value",
                         "null", "true", "false", "none", "extracted", "values"}
    reply = extraction.reply.strip()
    if not reply or reply.lower() in _bad_reply_tokens or len(reply) < 8:
        print(f"[chat] bad reply detected: {reply!r}")
        reply = ""  # will be rebuilt below

    new_fields = {u.key: u.value for u in extraction.slots}

    # Enforce follow-up question in code — never rely solely on the model obeying the prompt.
    # If there are still unfilled fields and the reply doesn't end with '?', append the next question.
    if req.document_name and template_fields:
        already_filled = {**req.fields, **new_fields}
        still_unfilled = [f for f in template_fields if not already_filled.get(f, "").strip()]

        if still_unfilled:
            if not reply:
                reply = f"Got it! Could you tell me the {still_unfilled[0]} for this agreement?"
            elif not reply.endswith("?"):
                reply = reply.rstrip(".!") + f" What is the {still_unfilled[0]}?"
        elif not reply:
            reply = "All fields are complete! You can review and download the document."

    elif not reply:
        reply = "What type of legal document do you need help with today?"

    return {
        "reply": reply,
        "document_name": extraction.document_name,
        "fields": new_fields,
    }


_frontend_dir = os.path.join(_BASE_DIR, "frontend_out")
if os.path.exists(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
