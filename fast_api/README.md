# fast_api: local setup

Postgres and Redis run via docker compose. Ollama is **disabled in compose by default**: the app uses
the locally installed Ollama through `LLM_BASE_URL=http://host.docker.internal:11434/v1` in `.env`.
To run Ollama in docker instead, see "Ollama in docker" below.

## First-time setup

```bash
cp .env.example .env              # then set SECRET_KEY etc.
docker compose up -d --build
```

## Ollama in docker

The `ollama` and `ollama-pull` services sit behind the `ollama` compose profile (no model downloads
or extra container unless you ask for it).

```bash
docker volume create ollama_data              # once; external volume, holds the downloaded models
docker compose --profile ollama up -d --build
docker compose logs -f ollama-pull            # first run downloads the models (several GB)
```

Then in `.env` switch `LLM_BASE_URL` to `http://ollama:11434/v1` (comment the `host.docker.internal`
line) and run `docker compose up -d api`. To go back to the local install, revert that line and run
`docker compose stop ollama`.

The sections below ("Ollama" port, models, logs, volume) only apply when the profile is enabled.

Ollama is reachable from the host at `http://localhost:11435` (11435, so it doesn't clash with a
host-installed Ollama on 11434). The api container reaches it at `http://ollama:11434/v1`
(`LLM_BASE_URL` in `.env`). To run the app outside docker, use `http://localhost:11435/v1` and
`REDIS_URL=redis://localhost:6380/0` instead (and `...@localhost:5433/fastapi_db` for `DATABASE_URL`).

Host ports: postgres `5433`, redis `6380`, ollama `11435`, api `8000`, mcp `8100`. They are shifted
so they don't clash with locally installed services. Containers still talk to each other on the
standard ports (`postgres:5432`, `redis:6379`).

It runs on CPU. For an NVIDIA GPU, add a `deploy.resources.reservations.devices` block
(`driver: nvidia, count: all, capabilities: [gpu]`) to the `ollama` service.

Requires Docker Compose v2.20+ (`docker compose version`).

## Models

Edit `ollama-models.txt` (one per line, `#` starts a comment; it must include the models `LLM_MODEL` and
`LLM_EMBEDDING_MODEL` point to), then `docker compose up ollama-pull`.
Already-pulled models are skipped. To switch the app to a new model, set `LLM_MODEL` (or
`LLM_EMBEDDING_MODEL`) in `.env` and run `docker compose up -d api`.
Changing the embedding model means re-indexing stored vectors (dimensions and spaces differ).

## Logs

`postgres`, `redis`, `ollama` and `ollama-pull` have `attach: false`, so `docker compose up` doesn't
stream their output. Logs are still stored; view them separately:

```bash
docker compose logs -f postgres
docker compose logs -f redis
docker compose logs -f ollama
docker compose logs -f ollama-pull   # model download progress
```

Only `api` and `mcp-server` stream by default. To stream one of the hidden services for a single run,
use `docker compose up --attach ollama`. To hide the others too, run `docker compose up -d`.

## Ollama volume (`ollama_data`)

It is declared `external` (its name has no project prefix), so `docker compose down -v` does NOT delete it and models are not re-downloaded.
`docker compose up` fails with "external volume not found" until you create it once (above).

Drop and recreate it (e.g. to reclaim disk or force a clean re-pull):

```bash
docker compose down                # the volume must not be in use
docker volume rm ollama_data
docker volume create ollama_data
docker compose up -d               # ollama-pull re-downloads everything in ollama-models.txt
```

Inspect: `docker volume ls`, `docker volume inspect ollama_data`.
