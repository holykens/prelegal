# Prelegal Project

## Overview

This is a SaaS product to allow users to draft legal agreements based on templates in the templates directory.
The user can carry out AI chat in order to establish what document they want and how to fill in the fields.
The available documents are covered in the catalog.json file in the project root, included here:

@catalog.json

The current implementation supports all 12 legal document types via AI chat. Real authentication, document persistence, and history restore are implemented (PL-7).

## Development process

When instructed to build a feature:
1. Use your Atlassian tools to read the feature instructions from Jira
2. Develop the feature - do not skip any step from the feature-dev 7 step process
3. Thoroughly test the feature with unit tests and integration tests and fix any issues
4. Submit a PR using your github tools

## AI design

When writing code to make calls to LLMs, use your Cerebras skill to use LiteLLM via OpenRouter to the `openrouter/openai/gpt-oss-120b` model with Cerebras as the inference provider. You should use Structured Outputs so that you can interpret the results and populate fields in the legal document.

There is an OPENROUTER_API_KEY in the .env file in the project root.

## Technical design

The entire project should be packaged into a Docker container.  
The backend should be in backend/ and be a uv project, using FastAPI.  
The frontend should be in frontend/  
The database uses SQLite stored at `./data/prelegal.db` on the host (mounted into the container via Docker volume). The schema is created with `CREATE TABLE IF NOT EXISTS` on startup so data persists across container restarts.  
Consider statically building the frontend and serving it via FastAPI, if that will work.  
There should be scripts in scripts/ for:  
```bash
# Mac
scripts/start-mac.sh    # Start
scripts/stop-mac.sh     # Stop

# Linux
scripts/start-linux.sh
scripts/stop-linux.sh

# Windows
scripts/start-windows.ps1
scripts/stop-windows.ps1
```
Backend available at http://localhost:8000

## Color Scheme
- Accent Yellow: `#ecad0a`
- Blue Primary: `#209dd7`
- Purple Secondary: `#753991` (submit buttons)
- Dark Navy: `#032147` (headings)
- Gray Text: `#888888`

## Implementation Status

### Completed (PL-4) — merged to main
- Docker multi-stage build: Node 20 builds Next.js static export; Python 3.11 runs FastAPI
- FastAPI backend (`backend/` uv project) at `http://localhost:8000`
- SQLite database initialised fresh on each container start (users table scaffolded)
- Next.js static export (`output: "export"`, `trailingSlash: true`) served by FastAPI
- Fake login screen — any credentials accepted; session stored in `localStorage`; main page redirects to `/login` when not signed in; sign-out button in header
- Start/stop scripts for Mac, Linux, and Windows in `scripts/`

### Completed (PL-5) — merged to main
- AI chat interface replacing the manual form sidebar
- Tab-based sidebar: **AI Chat** (default) and **Edit Fields** (manual form for review/tweaks)
- `POST /api/chat` uses LiteLLM → OpenRouter → Cerebras (`openrouter/openai/gpt-oss-120b`) with Pydantic structured outputs

### Completed (PL-6) — merged to main
- All 12 legal document types supported via the same AI chat flow
- Two-phase chat: document selection (AI matches user request to catalog, handles unsupported doc types gracefully), then field-filling
- Generic template rendering: extracts `coverpage_link`, `keyterms_link`, `orderform_link` span values as fillable fields; highlights collected values in the live preview
- `GET /api/catalog` — returns full document catalog
- `GET /api/template?document_name=...` — returns template content + extracted field names
- `DocumentState` frontend model (replaces NDA-specific `NDAFormData`)
- `DocumentPreview` and `FieldsForm` replace the NDA-specific preview and form
- `catalog.json` and `templates/` now copied into Docker image
- Chat auto-initialises on load — AI greets the user without requiring a first message
- After document selection the AI immediately asks the first field question (no blank-message gap)
- Focus returns to chat input after each AI response; textarea auto-grows as user types
- Backend enforces follow-up questions in code (not just via prompt) — model cannot skip asking
- Four layered safety nets handle cases where the model acknowledges a field in reply text but omits it from structured output: skip detection, date correction, acknowledgment extraction, variant propagation
- Plural/singular/possessive field variants are auto-propagated (e.g. setting "Subscription Period" also sets "Subscription Periods"; "Customer" → "Customer's")
- Fields the user marks empty ("leave blank") are set to `"None"` and never re-asked
- 24 unit tests in `backend/tests/test_chat.py`

### Completed (PL-7) — merged to main
- **Real authentication**: `POST /api/auth/register` and `POST /api/auth/login` with bcrypt password hashing; HS256 JWT returned and stored in `localStorage` as `pl_session`
- **Sign In / Sign Up toggle** on the login page with inline error display and loading state; separate Pydantic models (`RegisterRequest` with `min_length=8`, `LoginRequest` without) prevent 422 crashes on short login passwords
- **Document persistence**: `documents` table (`id, user_id, document_name, fields_json, messages_json, created_at, updated_at`); auto-saved after every chat turn that changes fields
- **Document history page** (`/history`): lists all user documents with field count, message count, and last-updated timestamp; each user's documents are isolated from other users
- **History restore**: clicking a document in `/history` sets `pl_restore_doc_id` in `sessionStorage`; on main page mount the document is fetched by ID, the template is re-fetched for content/field list, and `docState` + `messages` + `documentId` are fully restored
- **New Document button** in the main page header: resets all state and restarts the AI greeting flow
- **Legal disclaimer banner**: amber warning strip above the document preview — "Draft only — subject to legal review"
- **Persistent SQLite storage**: DB stored in `./data/prelegal.db` on the host via Docker volume mount; `init_db()` uses `CREATE TABLE IF NOT EXISTS` so data survives restarts
- **UI polish**: user email shown in header, History navigation link, updated page title
- **49 backend tests**: 24 chat tests (unchanged), 13 auth tests (`backend/tests/test_auth.py`), 12 document tests (`backend/tests/test_documents.py`); `conftest.py` `fresh_db` fixture drops/recreates tables before each test

### Current API Endpoints
- `GET /api/health` — health check
- `GET /api/catalog` — full document catalog
- `GET /api/template?document_name=...` — template markdown + field names
- `POST /api/chat` — AI chat turn; accepts `{messages, document_name, fields}`, returns `{reply, document_name, fields}`
- `POST /api/auth/register` — create account; returns `{token, email}`
- `POST /api/auth/login` — sign in; returns `{token, email}`
- `GET /api/documents` — list user's saved documents (auth required)
- `POST /api/documents` — create a document session (auth required); returns `{id, ...}`
- `PUT /api/documents/{id}` — update fields + messages for a session (auth required)
- `GET /api/documents/{id}` — fetch a full document session (auth required)

### Not yet implemented
- Nothing currently planned

