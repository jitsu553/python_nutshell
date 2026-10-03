# python_nutshell: what's inside and why

Snapshot at commit `af93b9f` (+ one uncommitted line in `auth/dependencies.py`). Purpose: a map of what each module teaches, what is already connected, and where the seams are, so we can plan merging it into **one application**.

## 1. Big picture

One FastAPI app (`fast_api/main.py`) mounts 9 routers and runs on Docker Compose with 4 services:

| Service | Role |
|---|---|
| `postgres` (pgvector/pg16) | App DB, vector store, LangGraph checkpoints |
| `redis` | Rate limiting plus Redis demos |
| `mcp-server` (port 8100) | MCP tool server (`app/mcp_server/server.py`) |
| `api` (port 8000) | The FastAPI app |

External: an OpenAI-compatible LLM (Ollama locally: `qwen2.5:7b`, `nomic-embed-text` embeddings).

Outside `fast_api/`, `basic_prog/` and `python_basics/` are plain Python exercises. They are not part of the app.

## 2. Module-by-module

| Module | What it is | Concept learned | Status |
|---|---|---|---|


| `routers/system.py` | `/` and `/health` | Health checks | Fine as is |
| `auth/` | Register, login, refresh, JWT access plus refresh tokens, `Session` table, `Role`, `get_current_user`, `require_role` | Auth, password hashing, dependency injection, RBAC | **Core.** Used by documents, tickets, parts of chat |
| `document_service/` | Upload PDF/DOCX/TXT, validate (size, signature, type), local or S3 storage backend, text extraction, tags, soft delete plus purge, audit log, download and presigned URL, retry/dead-letter index queue | File handling, strategy pattern (`storage_backend`), background-style job queue with backoff, soft delete | **Core.** Per-user, rate-limited upload |
| `external_api_aggregator/` | Calls weather, crypto, news APIs concurrently. Retries (tenacity), timeouts, circuit breaker, health tracker, error classification | Resilience patterns, `asyncio.gather` vs sequential | Standalone. Nothing else calls it |
| `redis_lab/` | Raw Redis commands, cache-aside, fixed-window `rate_limit` dependency, queue, sessions with TTL, pub/sub worker | Redis data structures, caching, rate limiting | Only `rate_limit` is used elsewhere (document upload). The rest is a lab |
| `llm_chat/` | Largest module. Chat sessions and messages, SSE streaming, embeddings and cosine similarity, pgvector store and search, RAG (`/ask`, `use_rag`), history summarisation and token budgeting, LangGraph tool-calling agent, per-user memory, MCP client, human-in-the-loop approval | Whole LLM stack: prompts, RAG, agents, tools, memory, HITL, MCP | **Core**, but only loosely tied to the rest |
| `tickets/` | `Ticket` model, service and router (create, list, get, patch status), scoped per user | Simple domain CRUD with ownership checks | Wired into the agent via `create_ticket` |
| `mcp_server/` | FastMCP server exposing `get_employee_details`. Reads `users` and `roles` | MCP server and client over streamable-http | Wired into the agent for users with a role |
| `llm_chat/utils/scratch_*.py` | Hand-rolled embeddings, similarity, and agent loop | Learning scaffolding from before LangChain/LangGraph | Candidate to delete or archive |

## 3. How the agent already ties modules together

`ChatService.build_tools` (`llm_chat/service.py`) is the one real integration point. With `use_tools=True` it builds a LangGraph agent (`graph.py`, Postgres checkpointer) with these tools:

| Tool | Reaches into |
|---|---|
| `calculate` | Nothing (safe AST evaluator) |
| `search_documents` | pgvector `text_embeddings` (RAG) |
| `web_search` | DuckDuckGo scraper (`utils/web_search.py`) |
| `create_ticket` | `tickets` module. **Pauses via `interrupt()`** for approval (`PendingApproval` table, `/approvals/{id}/decision`) |
| `remember` | `UserMemory` table, injected into the system prompt next turn |
| `get_employee_details` | MCP server, which queries `users` and `roles` |

Dependency graph today:

```
auth ──► documents ──(rate_limit)── redis_lab
  │         ▲
  │         └─ document_id FKs ── llm_chat (TextEmbedding, ChatSession.rag_document_id)
  ├──► tickets ◄── llm_chat tools
  └──► mcp_server ◄── llm_chat tools
external_api_aggregator   (isolated)
```

## 4. Seams and problems that block "one application"

1. **Chat is not user-owned.** `ChatSession` has no `user_id`. `POST /sessions`, `GET /sessions/{id}/messages`, `/embeddings`, `/similarity`, `/store`, `/search`, and `/ask` need no login. Anyone can read any session by id.
2. **RAG is not user-scoped.** `find_similar` and `TextEmbedding` have no owner filter, so `search_documents` can return another user's document text. Documents are per-user, but their vectors are global.
3. **Two parallel indexing paths.** `document_service` has its own extract, index-queue, and retry/dead-letter flow (`DocumentText`). `llm_chat` has a separate `POST /documents/{id}/index` that chunks and embeds into `TextEmbedding`. They should be one pipeline: upload, extract, chunk, embed, searchable.
4. **`require_role` is currently a no-op.** The uncommitted line `return current_user` sits before the role check, so every "admin" route is open to any logged-in user. Revert it before anything else.
5. **Two MCP worlds.** `tools.py` has an in-process `get_employee_details`, and `server.py` has a copy that goes over MCP. The agent only uses the MCP one. One of them is dead weight.
6. **Redis and the aggregator are islands.** Their patterns (caching, circuit breaker, health) could serve the LLM tools, but nothing connects them.
7. **Startup wiring is repetitive.** `main.py` has 4 startup and 4 shutdown hooks (deprecated `on_event`; `lifespan` is the modern form). Each module also builds its own `get_db` or settings access.
8. **Housekeeping.** `print()` debugging in `graph.py` and `rate_limit.py`, `Base.metadata.create_all` instead of Alembic migrations (alembic is installed and configured but not driving schema), no tests.

## 5. Proposed direction: an "IT helpdesk assistant" as the single product

The data model already points here (tickets, employees, documents, a chat agent). Each learned concept gets a job:

| Concept | Role in the unified app |
|---|---|
| Auth and roles | Single identity. Every chat session, document, ticket, and memory belongs to a user. `admin` and `agent` roles gate approvals and admin routes |
| Documents | Company knowledge base (policies, runbooks). Upload → extract → chunk → embed in one pipeline |
| RAG | `search_documents` over the user's accessible documents (owner or tag filter) |
| Tickets plus HITL | Agent proposes a ticket, a human approves it. Ticket status is updatable by role |
| MCP server | The "company systems" boundary (employee directory, later ticket lookup or asset inventory) |
| Memory | Per-user preferences carried between sessions |
| Redis | Rate-limit chat and uploads per user, cache aggregator and web-search results, optionally hold queue state for the indexing worker |
| External aggregator | Becomes agent tools (`get_weather`, `get_crypto_price`, `get_news`) with the circuit breaker and health already built |

## 6. Suggested order of work (each step is small and testable)

1. Revert the `require_role` no-op and add tests for it.
2. Add `user_id` to `ChatSession` and require auth on every chat route. Scope session reads to the owner.
3. Merge indexing: one pipeline from `document_service`, with `TextEmbedding` carrying `user_id` (or reaching it through `document_id`) and `find_similar` filtering on it.
4. Pick one `get_employee_details` (MCP) and delete the other.
5. Expose the aggregator as agent tools and cache results in Redis.
6. Add per-user chat rate limit via `rate_limit`.
7. Move startup and shutdown to a single `lifespan`. Move schema to Alembic. Remove prints and the scratch scripts.

Steps 1 to 4 fix correctness and security. 5 to 7 make it feel like one product.
