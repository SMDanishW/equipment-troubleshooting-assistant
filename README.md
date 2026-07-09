# Equipment Troubleshooting Agent

Equipment Troubleshooting Agent is a full-stack demo application for asking questions over uploaded equipment manuals. It lets users upload PDF manuals, extract text and figures, search across one or more manuals, and receive citation-backed troubleshooting answers with source pages, inline figures, PDF source links, and an inspectable agent trace.

The app is built around industrial equipment manuals, with the included Kemppi sample manuals used as local demo material.

## What The Application Does

- User accounts with username/email and password login.
- Admin account for inspecting traces, users, uploaded documents, and backend service logs.
- PDF upload from the Documents page or directly inside the Chat screen.
- Optional document type detection during upload.
- Text extraction from PDF manuals.
- Image extraction from PDF pages, including filtering of PDF mask/alpha images that should not be shown as real figures.
- Chroma-backed retrieval over manual text and image references.
- Chat over all uploaded manuals or a selected subset of manuals.
- Follow-up question support using recent chat context.
- Streaming answers with a thinking placeholder before the first tokens appear.
- Inline citations labelled as user-friendly sources, not raw embedding IDs.
- Clickable source citations that open the cited PDF page, with highlighted text where available.
- Inline figures that can be opened in a modal.
- Agent trace inspection for debugging retrieval and answer generation.
- Light/dark mode toggle.
- Docker Compose local stack for frontend, backend, and Postgres.

## Tech Stack

### Frontend

- Next.js 16
- React 19
- TypeScript
- React Markdown with GFM support
- Server-sent events via `@microsoft/fetch-event-source`
- Custom CSS with light/dark theme variables

### Backend

- FastAPI
- SQLAlchemy
- Pydantic settings
- JWT authentication
- LangGraph-style multi-step agent workflow
- PDF extraction with `pdfplumber` and `pypdf`
- Image handling with Pillow
- ChromaDB vector storage
- Docker SDK for admin log inspection
- Pytest test suite

### Infrastructure

- Docker Compose
- PostgreSQL 16
- Persistent local volumes for Postgres and backend data
- Local service ports:
  - Frontend: `http://localhost:3100`
  - Backend: `http://localhost:8100`
  - API docs: `http://localhost:8100/docs`
  - Postgres: `localhost:55432`

## LLM Used

The app is configured for Groq by default.

Default model:

```text
qwen/qwen3-32b
```

This is configured through:

```text
GROQ_MODEL=qwen/qwen3-32b
GROQ_API_KEY=<your Groq API key>
```

If no Groq key is supplied, local/demo behavior depends on the current backend code path and available fallback behavior. For best results, provide a valid `GROQ_API_KEY`.

## Embeddings And Retrieval

The application currently uses ChromaDB for vector retrieval.

### Text Embeddings

Default provider:

```text
EMBEDDING_PROVIDER=hashing
```

That means the default local Docker setup uses a hashed bag-of-words style vector embedding. It is lightweight and convenient for local demos, but it is not true dense semantic embedding and it is not hybrid search.

Optional semantic provider:

```text
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

When enabled, the backend attempts to use Sentence Transformers for dense semantic embeddings.

### Image Embeddings

The application does not currently embed image pixels visually.

Instead, extracted images are indexed as image references using nearby page text, caption metadata when available, equipment name, file name, and page number. Retrieval finds relevant image references through this text metadata, then the UI displays the extracted image file.

In short:

- Text search: Chroma vector search over extracted manual text.
- Image search: Chroma vector search over text descriptions/nearby text for extracted images.
- Hybrid BM25 + vector retrieval: not currently implemented.
- Visual CLIP-style image embeddings: not currently implemented.

## Project Structure

```text
.
|-- backend/          FastAPI backend, RAG, ingestion, auth, agent workflow
|-- frontend/         Next.js frontend
|-- docker-compose.yml
|-- backend/.env.example
|-- frontend/.env.local.example
`-- *.pdf             Sample equipment manuals for local testing
```

## Download And Setup

### 1. Clone The Repository

```bash
git clone <your-repository-url>
cd equipment-agent
```

If you already have the project folder, open a terminal in:

```text
C:\Users\smdan\Documents\claude_workspace\equipment-agent
```

### 2. Create Environment Files

Copy the backend and frontend examples:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

On Windows PowerShell:

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.local.example frontend/.env.local
```

Then edit `backend/.env` and set:

```text
GROQ_API_KEY=<your Groq API key>
SECRET_KEY=<a long random local secret>
```

For a local demo, the included admin credentials are:

```text
Username: admin
Email: admin@example.com
Password: admin-password
```

Change these before any non-local use.

### 3. Start With Docker Compose

```bash
docker compose up -d --build
```

Open the app:

```text
http://localhost:3100
```

Open the backend API docs:

```text
http://localhost:8100/docs
```

### 4. Upload Manuals

You can upload PDFs in either place:

- Documents page
- Chat page side panel

The included Kemppi PDFs can be used for testing:

```text
ax-mig-welder-om-en.pdf
flexlite-gxe-om-en.pdf
mastertig-acdc-om-en.pdf
```

After upload, ask a question in the Chat screen. You can search all uploaded manuals or select specific PDFs under Manual Scope.

## Common Commands

Start or rebuild the full stack:

```bash
docker compose up -d --build
```

View running services:

```bash
docker compose ps
```

View backend logs:

```bash
docker compose logs -f backend
```

View frontend logs:

```bash
docker compose logs -f frontend
```

Stop services but keep data:

```bash
docker compose down
```

Teardown local services and remove Docker volumes:

```bash
docker compose down -v
```

The `-v` flag removes Docker-managed volumes, including the local Postgres data volume.

## Running Tests

Backend tests:

```bash
python -m pytest backend/tests
```

Frontend typecheck:

```bash
cd frontend
npm run typecheck
```

## Notes About Accuracy

This app is intended as a technical demo and portfolio-grade local build. It should not replace official equipment documentation, trained technicians, or workplace safety procedures.

The assistant is designed to cite the manual evidence it used. Always verify the linked PDF page before acting on installation, maintenance, electrical, mechanical, or service instructions.

## License Ownership

No open-source license file is currently included in this repository. Unless a separate license is added, all rights remain with the project/repository owner.

The included or referenced Kemppi manuals and Kemppi documentation remain owned by their respective rights holder, Kemppi, and are used here only as sample/demo source documents.
