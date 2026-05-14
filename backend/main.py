import os
import json
import sqlite3
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI
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


# ── Chat request / response models ───────────────────────────────────────────

class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=4000)


class PartyFields(BaseModel):
    name: str = ""
    title: str = ""
    company: str = ""
    noticeAddress: str = ""


class NDAFormFields(BaseModel):
    purpose: str = ""
    effectiveDate: str = ""
    mndaTermType: Literal["expires", "continues"] = "expires"
    mndaTermYears: int = 1
    confidentialityTermType: Literal["years", "perpetuity"] = "years"
    confidentialityTermYears: int = 1
    governingLaw: str = ""
    jurisdiction: str = ""
    mndaModifications: str = ""
    party1: PartyFields = PartyFields()
    party2: PartyFields = PartyFields()


class ChatRequest(BaseModel):
    messages: list[ChatMessageIn] = Field(..., max_length=50)
    current_fields: NDAFormFields


# ── Structured output model (returned by LLM) ────────────────────────────────

class PartyExtraction(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    noticeAddress: Optional[str] = None


class NDAExtraction(BaseModel):
    reply: str
    purpose: Optional[str] = None
    effectiveDate: Optional[str] = None
    mndaTermType: Optional[Literal["expires", "continues"]] = None
    mndaTermYears: Optional[int] = None
    confidentialityTermType: Optional[Literal["years", "perpetuity"]] = None
    confidentialityTermYears: Optional[int] = None
    governingLaw: Optional[str] = None
    jurisdiction: Optional[str] = None
    mndaModifications: Optional[str] = None
    party1: Optional[PartyExtraction] = None
    party2: Optional[PartyExtraction] = None


def build_system_prompt(current_fields: NDAFormFields) -> str:
    return f"""You are a legal document assistant helping a user fill out a Mutual Non-Disclosure Agreement (MNDA).

Your job is to have a friendly, natural conversation to collect the required information. Ask clear, focused questions—one topic at a time.

The MNDA requires the following information:
- purpose: How confidential information will be used (e.g. "Evaluating a potential business partnership")
- effectiveDate: When the agreement starts (YYYY-MM-DD format)
- mndaTermType: "expires" (after N years) or "continues" (until terminated)
- mndaTermYears: Number of years if mndaTermType is "expires"
- confidentialityTermType: "years" (for N years) or "perpetuity" (forever)
- confidentialityTermYears: Number of years if confidentialityTermType is "years"
- governingLaw: Which US state's laws govern the agreement (e.g. "Delaware")
- jurisdiction: Specific court location (e.g. "courts located in New Castle, DE")
- mndaModifications: Any modifications to standard terms (often "None")
- party1.name, party1.title, party1.company, party1.noticeAddress
- party2.name, party2.title, party2.company, party2.noticeAddress

Current field values (JSON):
{current_fields.model_dump_json(indent=2)}

Rules:
- Only set a field to non-null if the user has clearly stated that value in this conversation turn
- Use null for any field you are not changing
- Keep replies concise—acknowledge what you extracted, then ask about the next missing field
- Dates must be in YYYY-MM-DD format
- For party noticeAddress, accept either email or postal address"""


@app.post("/api/chat")
async def chat(req: ChatRequest):
    system_prompt = build_system_prompt(req.current_fields)
    messages = [{"role": "system", "content": system_prompt}] + [
        {"role": m.role, "content": m.content} for m in req.messages[-20:]
    ]

    try:
        response = completion(
            model=MODEL,
            messages=messages,
            response_format=NDAExtraction,
            reasoning_effort="low",
            extra_body=EXTRA_BODY,
        )
        extraction = NDAExtraction.model_validate_json(response.choices[0].message.content)
    except Exception as exc:
        print(f"[chat] LLM error: {exc!r}")
        return {"reply": "I had trouble processing that. Please try again.", "fields": {}}

    fields: dict = {}
    for field in [
        "purpose", "effectiveDate", "mndaTermType", "mndaTermYears",
        "confidentialityTermType", "confidentialityTermYears",
        "governingLaw", "jurisdiction", "mndaModifications",
    ]:
        val = getattr(extraction, field)
        if val is not None:
            fields[field] = val

    if extraction.party1:
        p1 = extraction.party1.model_dump(exclude_none=True)
        if p1:
            fields["party1"] = p1

    if extraction.party2:
        p2 = extraction.party2.model_dump(exclude_none=True)
        if p2:
            fields["party2"] = p2

    return {"reply": extraction.reply, "fields": fields}


_frontend_dir = os.path.join(os.path.dirname(__file__), "frontend_out")
if os.path.exists(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
