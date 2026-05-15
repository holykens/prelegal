import os
import re
import json
import sqlite3
import datetime
from typing import Literal, Optional

_ISO_DATE_RE = re.compile(r'\b(\d{4}-\d{2}-\d{2})\b')

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from litellm import completion
from pydantic import BaseModel, Field
import jwt
import bcrypt

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
JWT_SECRET = os.getenv("JWT_SECRET", "prelegal-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30

_BASE_DIR = os.path.dirname(__file__)
_catalog_path = os.getenv("CATALOG_PATH", os.path.join(_BASE_DIR, "catalog.json"))
TEMPLATES_DIR = os.getenv("TEMPLATES_DIR", os.path.join(_BASE_DIR, "templates"))
_catalog: list[dict] = []
_catalog_by_name: dict[str, dict] = {}

if os.path.exists(_catalog_path):
    with open(_catalog_path, encoding="utf-8") as _f:
        _catalog = json.load(_f)
    _catalog_by_name = {doc["name"]: doc for doc in _catalog}

_FIELD_SPAN_RE = re.compile(
    r'<span class="(?:coverpage_link|keyterms_link|orderform_link)">([^<]+)</span>'
)


def load_template(doc_name: str) -> str | None:
    doc = _catalog_by_name.get(doc_name)
    if not doc:
        return None
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


def _related_names(field: str) -> list[str]:
    variants = []
    variants.append(field + "s")
    if field.endswith("s") and len(field) > 2:
        variants.append(field[:-1])
    variants.append(field + "’s")  # curly apostrophe
    variants.append(field + "'s")       # straight apostrophe
    for suffix in ("’s", "'s"):
        if field.endswith(suffix):
            variants.append(field[: -len(suffix)])
    return variants


def _propagate_variants(new_fields: dict[str, str], template_fields: list[str],
                        existing_fields: dict[str, str]) -> dict[str, str]:
    result = dict(new_fields)
    for key, value in list(new_fields.items()):
        for variant in _related_names(key):
            if variant in template_fields and variant not in result and variant not in existing_fields:
                result[variant] = value
    return result


# ── DB helpers ────────────────────────────────────────────────────────────────

def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        DROP TABLE IF EXISTS documents;
        DROP TABLE IF EXISTS users;
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            document_name TEXT NOT NULL,
            fields_json TEXT NOT NULL DEFAULT '{}',
            messages_json TEXT NOT NULL DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


@app.on_event("startup")
async def startup():
    init_db()


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[len("Bearer "):]
    try:
        payload = _decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"user_id": int(payload["sub"]), "email": payload["email"]}


# ── Auth models ───────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=128)


class AuthResponse(BaseModel):
    token: str
    email: str


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=AuthResponse, status_code=201)
async def register(req: RegisterRequest):
    pw_hash = _hash_password(req.password)
    try:
        with _db() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?) RETURNING id",
                (req.email.lower().strip(), pw_hash),
            )
            user_id = cur.fetchone()[0]
            conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email already registered")
    token = _create_token(user_id, req.email.lower().strip())
    return AuthResponse(token=token, email=req.email.lower().strip())


@app.post("/api/auth/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    with _db() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?",
            (req.email.lower().strip(),),
        ).fetchone()
    if not row or not _verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = _create_token(row["id"], row["email"])
    return AuthResponse(token=token, email=row["email"])


# ── Document models ───────────────────────────────────────────────────────────

class SaveDocumentRequest(BaseModel):
    document_name: str = Field(..., max_length=200)
    fields: dict[str, str] = {}
    messages: list[dict] = []


class DocumentRecord(BaseModel):
    id: int
    document_name: str
    fields: dict[str, str]
    messages: list[dict]
    created_at: str
    updated_at: str


# ── Document endpoints ────────────────────────────────────────────────────────

@app.get("/api/documents")
async def list_documents(user: dict = Depends(get_current_user)):
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, document_name, fields_json, created_at, updated_at "
            "FROM documents WHERE user_id = ? ORDER BY updated_at DESC",
            (user["user_id"],),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "document_name": r["document_name"],
            "fields": json.loads(r["fields_json"]),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


@app.post("/api/documents", status_code=201)
async def create_document(req: SaveDocumentRequest, user: dict = Depends(get_current_user)):
    now = datetime.datetime.now(datetime.UTC).isoformat()
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO documents (user_id, document_name, fields_json, messages_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
            (user["user_id"], req.document_name, json.dumps(req.fields),
             json.dumps(req.messages), now, now),
        )
        doc_id = cur.fetchone()[0]
        conn.commit()
    return {"id": doc_id, "document_name": req.document_name, "created_at": now, "updated_at": now}


@app.put("/api/documents/{doc_id}")
async def update_document(doc_id: int, req: SaveDocumentRequest, user: dict = Depends(get_current_user)):
    now = datetime.datetime.now(datetime.UTC).isoformat()
    with _db() as conn:
        result = conn.execute(
            "UPDATE documents SET fields_json = ?, messages_json = ?, updated_at = ? "
            "WHERE id = ? AND user_id = ?",
            (json.dumps(req.fields), json.dumps(req.messages), now, doc_id, user["user_id"]),
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Document not found")
    return {"id": doc_id, "updated_at": now}


@app.get("/api/documents/{doc_id}", response_model=DocumentRecord)
async def get_document(doc_id: int, user: dict = Depends(get_current_user)):
    with _db() as conn:
        row = conn.execute(
            "SELECT id, document_name, fields_json, messages_json, created_at, updated_at "
            "FROM documents WHERE id = ? AND user_id = ?",
            (doc_id, user["user_id"]),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentRecord(
        id=row["id"],
        document_name=row["document_name"],
        fields=json.loads(row["fields_json"]),
        messages=json.loads(row["messages_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ── Basic endpoints ───────────────────────────────────────────────────────────

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
    handled = set(current_fields.keys())
    filled_display = {k: v for k, v in current_fields.items()}
    unfilled = [f for f in template_fields if f not in handled]

    return f"""You are a legal document assistant helping a user complete a {document_name}.

Required fields:
{fields_list}

Already handled:
{json.dumps(filled_display, indent=2) if filled_display else "None yet"}

Still needed:
{chr(10).join(f"- {f}" for f in unfilled) if unfilled else "All fields collected — ready to review!"}

Rules:
- When the user provides a value for a required field, capture it with the exact field name from the list.
- If the user says to leave a field blank, empty, skip, or "none", set it to the string "None" so it is marked as handled and we can move on.
- If the user asks to UPDATE, CHANGE, or REFORMAT a field that is already in "Already handled", you MUST include the corrected value in slots — overriding the previous value. Do NOT assume an already-handled field is frozen.
- When converting a relative date (e.g. "tomorrow", "today") to YYYY-MM-DD, include the converted date in slots with the exact field name.
- Once a field is in the "Already handled" list, never ask about it again — it is done (unless the user requests a change).
- Keep document_name null (document is already selected).
- Focus on one or two still-needed fields per turn — do not overwhelm the user.
- Your reply must be natural conversational English — never output a field name, JSON key, or code word as your reply.
- If all fields are handled, congratulate the user and invite them to review or download the document.
- MANDATORY: If there are any still-needed fields, the very last sentence of your reply MUST be a question asking for the next one. Your reply cannot end without a question mark (?) when fields remain."""


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest):
    template_fields: list[str] = []
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

    _bad_reply_tokens = {"slots", "field_updates", "document_name", "reply", "key", "value",
                         "null", "true", "false", "none", "extracted", "values"}
    reply = extraction.reply.strip()
    _field_names_lower = {f.lower() for f in (template_fields or [])}
    if (not reply
            or reply.lower() in _bad_reply_tokens
            or reply.lower() in _field_names_lower
            or len(reply) < 8):
        print(f"[chat] bad reply detected: {reply!r}")
        reply = ""

    new_fields = {u.key: u.value for u in extraction.slots}

    if req.messages and req.document_name and template_fields:
        last_msg = req.messages[-1].content.lower()
        _skip_signals = {"empty", "blank", "none", "skip", "n/a", "leave it", "leave empty", "leave blank"}
        if any(s in last_msg for s in _skip_signals):
            for field in template_fields:
                if field not in new_fields and field not in req.fields:
                    if field.lower() in last_msg:
                        new_fields[field] = "None"

    if req.document_name and template_fields:
        reply_lower_for_dates = reply.lower()
        for field in template_fields:
            existing_val = req.fields.get(field, "").strip()
            if existing_val and not _ISO_DATE_RE.match(existing_val) and field not in new_fields:
                field_lower = field.lower()
                if field_lower in reply_lower_for_dates:
                    idx = reply_lower_for_dates.find(field_lower)
                    nearby = reply[max(0, idx - 20): idx + len(field) + 80]
                    date_match = _ISO_DATE_RE.search(nearby)
                    if date_match:
                        new_fields[field] = date_match.group()
                        print(f"[chat] S3 date: {field} → {date_match.group()}")

    _S4_VERBS = (r"has been set|have been set|is set|are set|set|recorded|"
                 r"captured|noted|added|updated|is now")
    _S4_VERB_RE = re.compile(rf"\b(?:{_S4_VERBS})\b", re.I)
    _S4_VALUE_RE = re.compile(r"(?:to|as)[:\s]+(.+)", re.I)
    if req.document_name and template_fields and reply:
        reply_lower_s4 = reply.lower()
        for field in template_fields:
            if field in new_fields or field in req.fields:
                continue
            field_lower = field.lower()
            idx = reply_lower_s4.find(field_lower)
            if not (0 <= idx <= 100):
                continue
            window = reply[max(0, idx - 40): idx + len(field) + 40]
            if not _S4_VERB_RE.search(window):
                continue
            after_field = reply[idx + len(field):]
            m = _S4_VALUE_RE.search(after_field)
            if not m:
                continue
            raw = m.group(1).strip()
            sentence_end = re.search(r"[.?!]", raw)
            val = (raw[: sentence_end.start()].strip() if sentence_end else raw).rstrip(".,!?")
            val = val.strip("'\"" + "‘’“”")
            if 3 <= len(val) <= 500:
                new_fields[field] = val
                print(f"[chat] S4 ack: {field!r} → {val[:60]!r}")
                break

    if req.document_name and template_fields:
        new_fields = _propagate_variants(new_fields, template_fields, req.fields)

    if req.document_name and template_fields:
        already_filled = {**req.fields, **new_fields}
        still_unfilled = [f for f in template_fields if f not in already_filled]

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
