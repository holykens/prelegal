# Prelegal Project

## Overview

This is a SaaS product to allow users to draft legal agreements based on templates in the templates directory.
The user can carry out AI chat in order to establish what document they want and how to fill in the fields.
The available documents are covered in the catalog.json file in the project root, included here:

@catalog.json

The current implementation supports Mutual NDA drafting via AI chat. Multi-document support, real authentication, and document persistence are not yet implemented.

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
The database should use SQLLite and be created from scratch each time the Docker container is brought up, allowing for a users table with sign up and sign in.  
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
- Two-phase chat: document selection phase (AI helps user pick from catalog), then field-filling phase
- Generic template rendering: extracts `coverpage_link`, `keyterms_link`, `orderform_link` span values as fillable fields; highlights collected values in the live preview
- `GET /api/catalog` — returns full document catalog
- `GET /api/template?document_name=...` — returns template content + extracted field names
- `DocumentState` frontend model (replaces NDA-specific `NDAFormData`)
- `DocumentPreview` and `FieldsForm` replace the NDA-specific preview and form
- `catalog.json` and `templates/` now copied into Docker image
- Focus returned to chat input after each AI response
- AI system prompt always requires a follow-up question
- 15 unit tests in `backend/tests/test_chat.py`

### Current API Endpoints
- `GET /api/health` — health check
- `GET /api/catalog` — full document catalog
- `GET /api/template?document_name=...` — template markdown + field names
- `POST /api/chat` — AI chat turn; accepts `{messages, document_name, fields}`, returns `{reply, document_name, fields}`

### Not yet implemented
- Real authentication and document persistence (PL-7)

