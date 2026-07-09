# Equipment Troubleshooting Agent

Portfolio-grade full-stack application for authenticated equipment manual upload, multimodal RAG, LangGraph agent workflows, citation-backed troubleshooting answers, and agent trace inspection.

## Current Phase

Phase 1 foundation is scaffolded:

- FastAPI backend
- health endpoint at `GET /health`
- username/email/password auth
- JWT bearer tokens
- SQLAlchemy user model
- Postgres-ready configuration
- Next.js route skeleton
- local Docker Compose for Postgres, backend, and frontend

Later phases will add PDF ingestion, image extraction, ChromaDB indexing, Groq Qwen, LangGraph, SSE streaming, citations, trace dashboards, QA, and AWS ECS deployment.

## Local Development

Copy environment templates if you want local overrides:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

Start the local stack:

```bash
docker compose up --build
```

Services:

- Frontend: `http://localhost:3100`
- Backend: `http://localhost:8100`
- API docs: `http://localhost:8100/docs`
- Postgres: `localhost:55432`

## Auth Endpoints

Register:

```http
POST /auth/register
```

Login:

```http
POST /auth/login
```

Current user:

```http
GET /auth/me
Authorization: Bearer <token>
```

## Local Admin

The local Docker stack seeds an admin account from `backend/.env`:

- Username: `admin`
- Email: `admin@example.com`
- Password: `admin-password`

Admin users can list traces with `GET /traces` and inspect any conversation trace by ID.

## Backend Tests

From the repo root:

```bash
python -m pytest backend/tests
```

The tests use SQLite overrides so they do not require Docker.
