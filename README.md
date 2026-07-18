# Equipment Troubleshooting Agent

Equipment Troubleshooting Agent is a full-stack demo application for asking questions over uploaded equipment manuals. It lets users upload PDF manuals, extract text and figures, search across one or more manuals, and receive citation-backed troubleshooting answers with source pages, inline figures, PDF source links, and an inspectable agent trace.

The app is built around industrial equipment manuals, with the included Kemppi sample manuals used as local demo material.

## Current Implementation Boundary

The project plan is the target architecture, not a claim that every planned capability is already implemented. The current
application has a multi-step, traceable troubleshooting workflow, but its diagnosis and final-answer stages are primarily
deterministic/template-based. Groq is currently used as an optional document-classification fallback rather than as a fully
grounded final synthesis model.

The default `hashing` embedding provider is lexical and lightweight. Sentence Transformers can be enabled for dense text
embeddings, but hybrid retrieval, reranking, visual image embeddings, autonomous reflection/revision, and a production
multi-agent system are not currently implemented. Extracted figures are retrieved through nearby text and metadata, not
through image-pixel understanding. Direct Python execution defaults to inline ingestion for compatibility; both Compose
profiles use durable background ingestion with a separate worker.

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

## LLM Integration

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

The current Groq integration is used by optional document-type classification. Troubleshooting answer composition currently
uses the deterministic workflow described above, so configuring Groq does not by itself enable the target LLM synthesis,
reflection, or cross-check pipeline.

## Embeddings And Retrieval

The application uses hybrid retrieval by default: ChromaDB vector candidates and BM25 lexical candidates are merged with
reciprocal-rank fusion. Tenant and selected-document filters are applied before lexical ranking and revalidated after fusion.

```text
RETRIEVAL_MODE=hybrid
RETRIEVAL_CANDIDATE_MULTIPLIER=4
LEXICAL_CANDIDATE_LIMIT=1000
RECIPROCAL_RANK_FUSION_K=60
```

Set `RETRIEVAL_MODE=vector` to roll back to vector-only text retrieval without reindexing documents.

### Text Embeddings

Default provider:

```text
EMBEDDING_PROVIDER=hashing
```

That means the vector side of the default local setup uses a hashed bag-of-words embedding. It is lightweight and convenient
for local demos, while BM25 supplies exact lexical matching for terms such as equipment identifiers and error codes.

Optional semantic provider:

```text
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

When enabled, the backend attempts to use Sentence Transformers for dense semantic embeddings.

The default backend image intentionally excludes the large Sentence Transformers/PyTorch dependency stack. Install the
optional profile or build a derived image before setting this provider:

```bash
pip install -r backend/requirements-semantic.txt
```

### Image Embeddings

The application does not currently embed image pixels visually.

Instead, extracted images are indexed as image references using nearby page text, caption metadata when available, equipment name, file name, and page number. Retrieval finds relevant image references through this text metadata, then the UI displays the extracted image file.

In short:

- Text search: hybrid BM25 and Chroma vector retrieval with reciprocal-rank fusion.
- Image search: Chroma vector search over text descriptions/nearby text for extracted images.
- Vector-only text rollback: available through `RETRIEVAL_MODE=vector`.
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

View ingestion worker logs:

```bash
docker compose logs -f worker
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

## Deployment Profiles

`docker-compose.yml` is the supported local/demo profile. It uses development credentials, exposes Postgres on the host,
automatically creates tables, runs the Next.js development server, bind-mounts backend runtime data, and exposes the Docker
socket for the local admin log viewer. Do not use this profile as a production deployment.

`docker-compose.production.yml` is a production-oriented reference profile. It uses a production frontend build, required
secrets, JSON backend logs, named data volumes, health checks, no host Postgres port, and no Docker socket. It is not a full
enterprise deployment: TLS termination, ingress, managed secrets, backups, external object/vector storage, monitoring, and
orchestration are still later-phase work.

The production profile sets `AUTO_CREATE_TABLES=false`. A one-shot `migrate` service applies Alembic migrations before the
backend starts, and backend startup then performs only data bootstrap such as optional admin seeding. If migration fails,
the API does not start.

Validate the production configuration without starting services:

```bash
docker compose --env-file .env.production.example -f docker-compose.production.yml config
```

Apply production migrations without starting the full stack:

```bash
docker compose --env-file .env.production.example -f docker-compose.production.yml run --rm migrate
```

For an existing database originally created with `AUTO_CREATE_TABLES=true`, back it up and verify that it matches the current
model schema before adopting the baseline revision:

```bash
docker compose exec backend alembic -c alembic.ini stamp 20260711_0001
```

New schema changes must be delivered as reviewed revisions under `backend/migrations/versions`; application startup no longer
executes ad hoc `ALTER TABLE` statements.

## Background Ingestion

In Compose deployments, uploading a valid PDF creates a `processing` document and a durable `ingestion_jobs` row, then returns
without waiting for extraction, chunking, image processing, or indexing. The worker claims jobs with database row locking,
retries failures up to `INGESTION_MAX_ATTEMPTS`, and recovers jobs left `running` beyond
`INGESTION_JOB_TIMEOUT_MINUTES`. The frontend polls only while processing documents exist and exposes manuals to chat after
they reach `indexed`.

The direct non-Compose default remains `INGESTION_MODE=inline` for tests and simple development. Production validation
requires `INGESTION_MODE=background`.

## Metrics And Errors

When `METRICS_ENABLED=true`, Prometheus metrics are available at `GET /metrics`. HTTP metrics use route templates rather than
resource IDs, include full streaming duration, and expose durable ingestion-job counts by status. Domain errors retain the
existing JSON `{ "detail": "..." }` body and add an `X-Error-Code` response header for stable client handling.

## Runtime Data Lifecycle

Runtime uploads, extracted images, traces, and Chroma files live under `backend/data` locally and are excluded from Git.
The root-level Kemppi PDFs are immutable demo inputs and are not managed as runtime uploads. Deleting an indexed document
removes its database rows, vector evidence, uploaded PDF directory, and extracted-image directory. Failed ingestion rolls
back partial relational records and attempts to remove generated file/vector artifacts while retaining a failed status record.

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
