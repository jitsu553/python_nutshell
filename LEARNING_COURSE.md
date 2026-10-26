# python_nutshell: AI-side learning course

You have already built the backend (FastAPI, auth, Postgres, Redis, documents pipeline) and the agent (RAG, tools, LangGraph, MCP, human approval, memory). This course covers **only what we discussed and the repo does not have yet**: measuring, observing and improving the AI.

## How to use this file

1. Chapters are numbered in **study order**. Go top to bottom. Each chapter lists what it **Needs**.
2. Pick the next chapter. Ask: *"Tailor a lesson for Chapter N."* A lesson is then written against your actual code.
3. Do the **Build** items in the repo. Tick **Done when**.

Each chapter has: **Needs**, **Why**, **Where it plugs into your repo**, **Learn**, **Build**, **Done when**.

## The one-picture map

Four pillars. Every term you heard belongs to one of them.

| Pillar | Question it answers | Terms | Chapters |
|---|---|---|---|
| **See** | What did the system actually do? | observability, trace, span, logs, metrics, OpenTelemetry, Langfuse, Grafana | 4, 12, 17 |
| **Trust** | Should I believe this answer? | confidence score, abstention, groundedness, faithfulness, hallucination, ambiguity, semantic search scores | 3, 5, 7 |
| **Measure** | Is it getting better or worse? | golden set, recall@k, LLM-as-judge, model comparison, regression evals, MLflow | 6, 7, 9, 10, 11, 13, 19 |
| **Improve** | What should I change? | prompts, reranking, hybrid search, query rewriting, citations, guardrails, cost control, multi-agent | 8, 14, 15, 16, 18 |

## What the repo has and lacks (AI side)

| Has | Lacks |
|---|---|
| RAG with pgvector, `/ask`, `search_documents` tool | Tracing (only a `log.info("llm_call ms=...")` line in `graph.py`) |
| LangGraph agent, 16 tools, Postgres checkpointer | Abstention: `/ask` answers even when retrieval is weak |
| Risk tiers, role gating, prechecks, `interrupt()` approval | Groundedness or hallucination checks |
| Keyword `not_asked` injection guard | Golden dataset, retrieval metrics, regression evals |
| History summarisation, token trimming, memory | Citations, reranking, hybrid search, query rewriting |
| `evals/run_evals.py` live-API harness | Prompt versioning, cost tracking, CI evals |
| Single agent | Router or specialist agents (and no evidence yet that you need them) |
| 4 tests in `tests/test_security.py` | Tests for the graph and routers, fake-LLM tests, Alembic migrations |

## Chapter tracker

| # | Chapter | Pillar | Status |
|---|---|---|---|
| 1 | Safety net: tests with a fake LLM, migrations, cleanup | Foundation | [ ] |
| 2 | The AI quality lifecycle and vocabulary | Map | [ ] |
| 3 | Semantic search fundamentals | Trust | [ ] |
| 4 | Tracing with Langfuse | See | [ ] |
| 5 | Confidence, abstention and ambiguity | Trust | [ ] |
| 6 | Golden set and retrieval metrics | Measure | [ ] |
| 7 | Groundedness, faithfulness and LLM-as-judge | Trust and Measure | [ ] |
| 8 | Prompt engineering and structured output | Improve | [ ] |
| 9 | Model and embedding selection | Measure | [ ] |
| 10 | Agent evals: tools, approvals, injection | Measure | [ ] |
| 11 | Multi-turn, memory and ingestion evals | Measure | [ ] |
| 12 | OpenTelemetry and Grafana | See | [ ] |
| 13 | MLflow for experiment comparison | Measure | [ ] |
| 14 | RAG quality upgrades | Improve | [ ] |
| 15 | Guardrails and prompt injection | Improve | [ ] |
| 16 | Cost, caching and abuse control | Improve | [ ] |
| 17 | Feedback loop, privacy and drift | See and Trust | [ ] |
| 18 | Multi-agent and orchestration | Improve | [ ] |
| 19 | Regression in CI, prompt versions | Measure | [ ] |

Short path if time is limited: **3 → 4 → 5 → 6 → 7**. That is the 3-step plan we agreed on (tracing, "I don't know", golden set with groundedness), plus the semantic search fundamentals that the threshold depends on.

One deliberate loop: Chapter 5 builds the abstention mechanism with a placeholder threshold, and Chapter 6 gives you the data to set the real value. Come back to Chapter 5's setting after Chapter 6.

---

## Chapter 1: Safety net: tests with a fake LLM, migrations, cleanup

**Needs:** nothing.

**Why.** Regression evals (Chapter 19) and every refactor need tests you can trust. Today 4 tests cover about 5,000 lines.

**Where it plugs in.** `tests/conftest.py`, `tests/test_security.py`, `main.py`, `app/infra/database.py`, `graph.py`.

**Learn.**
- Unit vs integration vs eval: tests are fast and deterministic, evals are slow, noisy and cost money
- A stub chat model with canned replies, so the graph can be tested without Ollama
- Testing the approval flow: tool call → `interrupt()` → resume
- FastAPI `TestClient` / `httpx.AsyncClient`, dependency overrides, a test database
- Alembic: the dependency is installed but the schema comes from `create_all`
- `lifespan` instead of 8 deprecated `on_event` hooks

**Build.**
1. Fix `require_role` so the `xfail(strict=True)` test flips, then remove the marker.
2. A graph test with a fake model that calls a tool, hits approval and resumes.
3. A baseline Alembic migration. Replace `create_all`.
4. Remove `print()` calls and the `utils/scratch_*.py` leftovers.

**Done when.** [ ] Tests run without Ollama. [ ] Role tests pass without `xfail`.

---

## Chapter 2: The AI quality lifecycle and vocabulary

**Needs:** nothing.

**Why.** You heard many terms with gaps between them. This chapter fills the gaps so later chapters have a frame.

**Where it plugs in.** Nowhere in code. It is the map.

**Learn.**
- The lifecycle: build → trace → evaluate → find failure → fix → re-evaluate. Each term sits in one stage.
- Retrieval quality vs generation quality: a wrong answer is either "the right chunk was not retrieved" or "the right chunk was ignored or distorted". These need different fixes.
- Offline evals (before release, on a fixed set) vs online evals (on live traffic, via traces).
- Definitions, each in one sentence: groundedness, faithfulness, hallucination, abstention, confidence score (a proxy, not a probability), ambiguity and clarification, answer relevance, recall@k, MRR, LLM-as-judge.
- Tool landscape and what each is for: Langfuse, LangSmith, OpenTelemetry, Grafana (Prometheus, Tempo, Loki), MLflow, Arize Phoenix, Helicone, Ragas, DeepEval, promptfoo.

**Build.**
1. Take 5 real failures from your own use of `/ask` or the agent. Label each as retrieval failure, generation failure, or tool failure.
2. Write the label table in a scratch file. It becomes your first eval cases.

**Done when.** [ ] You can classify any bad answer into retrieval, generation or tool failure. [ ] You can define each glossary term without looking.

---

## Chapter 3: Semantic search fundamentals

**Needs:** nothing. Chapters 5, 6 and 14 assume it.

**Why.** Thresholds and metrics make no sense without understanding how semantic search works and fails.

**Where it plugs in.** `service.py` (`find_similar`), `models/llm_chat.py` (`TextEmbedding`), `utils/similarity.py`, `/search`, `/similarity`, `/embeddings`, `search_documents`.

**Learn.**
- What an embedding captures and what it misses: weak on exact terms, ids, numbers and negation
- Distance metrics: cosine vs inner product vs L2, and why normalized vectors make the first two equivalent
- Exact vs approximate search: sequential scan vs HNSW or IVFFlat (`m`, `ef_construction`, `ef_search`) and the recall you give up
- Query vs document prefixes: nomic models expect `search_query:` and `search_document:`
- Scores are not comparable across embedding models, so thresholds must be tuned on your data
- Chunk size changes what a vector represents. Per-user filtering belongs in the query
- Failure cases: short queries, jargon, acronyms, multi-part questions

**Build.**
1. Check which operator your query uses and whether an index exists. Run `EXPLAIN ANALYZE`.
2. Add the nomic prefixes and compare results on 10 queries by eye.
3. Add an HNSW index and compare latency and recall against exact search.
4. Find 5 queries where semantic search fails and note why.

**Done when.** [ ] You can explain why a cosine of 0.6 is not portable between models. [ ] You know whether your index is used.

---

## Chapter 4: Tracing with Langfuse

**Needs:** nothing. Chapters 5, 7, 12, 16 and 17 build on it.

**Why.** You cannot fix what you cannot see. A trace shows the prompt, retrieved chunks, each tool call, tokens and latency for one request.

**Where it plugs in.** `app/services/llm/graph.py` (`call_model`, the existing `llm_call` log line), `client.py` (`ChatOpenAI`), `docker-compose.yml` (add Langfuse), `config.py` (keys).

**Learn.**
- Trace vs span vs generation; sessions and users on traces
- Langfuse is open source, self-hosted or cloud (LangSmith is the one with enterprise-only self-hosting)
- The LangChain/LangGraph callback handler, and passing it through `config={"callbacks": [...]}`
- Tagging traces with `user_id`, `session_id`, `thread_id`
- Scores on traces (the hook Chapters 5 and 7 reuse)
- Privacy: what prompt content you are putting in a trace store
- Self-hosting cost: Langfuse needs its own Postgres, ClickHouse and Redis. Alongside Ollama this is heavy, so start with the cloud free tier if memory is tight

**Build.**
1. Run Langfuse (cloud or compose) and add keys to settings.
2. Attach the callback to the graph invocation and to `/ask`.
3. Send one request that uses a tool and one that triggers an approval. Read both traces end to end.
4. Add `user_id` and `session_id` to every trace.

**Done when.** [ ] You can open a trace and see the retrieved chunks for an `/ask` call. [ ] You can answer "why did the agent call that tool?" from the trace.

---

## Chapter 5: Confidence, abstention and ambiguity

**Needs:** Chapter 3 (what similarity scores mean). Chapter 4 helps (log scores on traces). **Loop:** the threshold value is tuned after Chapter 6.

**Why.** The cheapest big win: stop answering when evidence is weak, and ask when the question is unclear.

**Where it plugs in.** `service.py` (`find_similar`, `build_rag_context`, `answer_with_context`), `routers/llm_chat.py` (`/ask`), `search_documents` tool, `schemas/llm_chat.py`.

**Learn.**
- Confidence is a **proxy**. Options: top retrieval similarity, gap between top-1 and top-2, token logprobs, model self-rating. Know the weakness of each.
- Abstention: a threshold below which the answer is "I could not find this in your documents." Choosing the threshold needs data (Chapter 6), not a guess.
- Ambiguity: the question has several readings, or is missing a slot. Respond with a clarifying question instead of guessing.
- Calibration: does "0.8 confident" actually mean right 80% of the time?
- The abstention trade-off: too strict loses useful answers, too loose lets hallucinations through.

**Build.**
1. Return `top_score` and the chunk sources in the `/ask` response.
2. Add a similarity threshold setting. Below it, return a fixed "not found" answer and skip the LLM call.
3. Add a prompt rule and a small check for ambiguity: if the question is under-specified, ask one clarifying question.
4. Log the score as a Langfuse score on the trace.

**Done when.** [ ] An off-topic question gets "not found" with no LLM call. [ ] The threshold lives in settings. [ ] You can say how you would pick it from data.

---

## Chapter 6: Golden set and retrieval metrics

**Needs:** Chapter 3 (how retrieval behaves). Chapter 5 supplies the threshold this chapter tunes.

**Why.** Measurement turns "feels better" into a number. Retrieval is the first thing to measure because it caps everything downstream. **Most later chapters depend on this one.**

**Where it plugs in.** `evals/run_evals.py` (extend it), your uploaded documents, `find_similar`.

**Learn.**
- A golden set: questions, the expected source chunk or document, and the expected answer
- Include **unanswerable** questions (the correct result is abstention) and **ambiguous** ones
- recall@k, hit rate, MRR: what each says and when it misleads
- Dataset hygiene: write questions the way users ask, not by copying chunk text
- Small and good beats big and sloppy: 30 cases is enough to start
- Using the set to choose the abstention threshold and `top_k`

**Build.**
1. A `golden.jsonl` with 30 cases: ~20 answerable, ~5 unanswerable, ~5 ambiguous.
2. Add a retrieval-only mode to the harness that prints recall@k and MRR.
3. Sweep chunk size (200 vs 400 words) and `top_k`, and tabulate.
4. Use the unanswerable cases to set the threshold from Chapter 5.

**Done when.** [ ] One command prints a retrieval scorecard. [ ] You changed a setting because of the numbers.

---

## Chapter 7: Groundedness, faithfulness and LLM-as-judge

**Needs:** Chapter 6 (golden set to score). Chapter 4 helps for online scoring.

**Why.** Retrieval can be perfect and the model can still invent. This measures the generation half.

**Where it plugs in.** `evals/run_evals.py`, `answer_with_context`, Langfuse scores (online scoring of live traces).

**Learn.**
- Groundedness: is every claim in the answer supported by the retrieved context?
- Faithfulness (same family), answer relevance, correctness against a reference
- LLM-as-judge: prompt design, one criterion per judge, structured verdict, and its biases (prefers long answers, prefers its own style, position bias)
- A small local model as judge is weak. Know what that does to your numbers
- Validating the judge: compare its verdicts to your own on 10 to 20 cases
- Libraries: Ragas and DeepEval implement these metrics. Write one by hand first so you understand it
- Offline (golden set) vs online (sample live traces) scoring

**Build.**
1. A judge prompt that splits an answer into claims and marks each supported or not.
2. Run it over the golden set and report a groundedness percentage.
3. Hand-check 10 verdicts and record the judge's accuracy.
4. Optional: swap in Ragas faithfulness and compare with your own judge.

**Done when.** [ ] The scorecard shows retrieval and groundedness side by side. [ ] You know how far to trust the judge.

---

## Chapter 8: Prompt engineering and structured output

**Needs:** Chapters 6 and 7 (to judge whether a prompt change helped).

**Why.** With a 7B local model, prompt quality changes results more than most infrastructure work.

**Where it plugs in.** The system prompt and RAG prompt in `service.py`, tool descriptions in `tools.py`, `schemas/llm_chat.py`.

**Learn.**
- Message roles, instruction placement, few-shot examples, delimiting untrusted text
- Tool descriptions are prompts too: the model reads them to pick tools
- Structured output: a Pydantic schema, validation and retry on invalid JSON
- Temperature and max tokens, determinism for evals
- Changing one thing at a time and judging with the golden set, not by feel

**Build.**
1. Print the exact messages array for one turn.
2. A structured-output endpoint (schema → validated JSON, with one retry).
3. Rewrite 3 weak tool descriptions and measure tool-choice accuracy (Chapter 10).

**Done when.** [ ] A prompt change comes with a before/after number.

---

## Chapter 9: Model and embedding selection

**Needs:** Chapters 6 and 7 (a scorecard to compare on).

**Why.** `qwen2.5:7b` and `nomic-embed-text` are choices. Measure them against alternatives instead of assuming.

**Where it plugs in.** `config.py` (`llm_model`, `llm_embedding_model`), `client.py`, `ollama-models.txt`, the golden set from Chapter 6.

**Learn.**
- Local vs hosted: quality, latency, cost, data residency
- Model size and quantization, context length, tool-calling reliability in small models
- Embedding model dimension, language and domain fit. Changing it means re-indexing everything
- Fine-tuning: when it is worth it (rarely before prompts and retrieval are tuned). This is the one place MLflow earns its keep
- Model routing: cheap model for easy questions, strong model for hard ones

**Build.**
1. Run the golden set against 2 chat models and 2 embedding models.
2. Tabulate quality, latency and cost. Log runs to MLflow if you added it (Chapter 13).

**Done when.** [ ] You can justify your model choices with numbers.

---

## Chapter 10: Agent evals: tools, approvals, injection

**Needs:** Chapter 6 (the eval harness and case format).

**Why.** An agent can fail without a single wrong sentence: wrong tool, wrong arguments, skipped approval, obeying injected text.

**Where it plugs in.** `evals/run_evals.py` (already rejects every approval so nothing is sent), `tool_registry.py`, `tools.py` prechecks, `not_asked`.

**Learn.**
- Trajectory evals: did it call the expected tools, in a sane order, with the right arguments?
- Approval-path evals: dangerous tool → approval requested; admin-only tool as a normal user → refused
- Prompt injection tests: direct, and **indirect** (an uploaded document or web result containing instructions)
- Why `not_asked` (keyword matching) is a weak guard and how an eval exposes that
- Loop and cost evals: calls per task, hitting `RECURSION_LIMIT`
- Deterministic checks first, judge-based checks only where needed

**Build.**
1. 20 agent cases with expected tool names and whether approval should trigger.
2. 5 injection cases (a document saying "refund every customer 500").
3. Report: tool-choice accuracy, approval correctness, injection resisted yes/no.

**Done when.** [ ] You have a recorded injection result for the current guard. [ ] Tool-choice accuracy is a number.

---

## Chapter 11: Multi-turn, memory and ingestion evals

**Needs:** Chapter 6 (harness). Chapter 7 helps for judging summaries.

**Why.** Earlier evals test single questions. Real failures happen over long chats and bad documents.

**Where it plugs in.** `summarize_messages`, `maybe_compact_history`, the `remember` tool and `UserMemory` in `service.py`, `extractor.py`, `chunking.py`.

**Learn.**
- Multi-turn cases: pronouns, follow-ups, topic changes
- Summary quality: does it keep names, numbers and decisions?
- Memory risks: wrong or poisoned memories, stale facts, memories that should never be stored
- Ingestion quality: tables, scans, columns, headers. Bad extraction silently ruins RAG
- Token counting: the approximate trim vs the model's real tokenizer

**Build.**
1. 10 multi-turn scripts with expected facts after summarisation.
2. A test that a prompt-injected `remember` call is refused or flagged.
3. 5 messy PDFs: compare extracted text against what you see, and record failures.
4. List and delete memories for a user.

**Done when.** [ ] You have a pass rate for summary fidelity. [ ] You know which document types extract badly.

---

## Chapter 12: OpenTelemetry and Grafana

**Needs:** Chapter 4 (Langfuse is the LLM side of this pipeline).

**Why.** Langfuse tells you whether the **AI** was good. Grafana tells you whether the **system** is healthy (latency, errors, load). You decided to use both, with OTel as the shared pipe.

**Where it plugs in.** `main.py` (FastAPI instrumentation), `docker-compose.yml` (Collector, Prometheus, Tempo, Grafana, optional Loki), `graph.py`.

**Learn.**
- OTel is a **standard and SDK**, not a product. Collector = a router for telemetry
- Three signals: traces, metrics, logs. Context propagation
- Architecture: app → OTel SDK → Collector → {Langfuse, Tempo/Prometheus/Loki → Grafana}
- Auto-instrumentation: FastAPI, httpx, SQLAlchemy, Redis
- Avoid **double-capturing** LLM spans (Langfuse callback and OTel both recording them)
- Send full prompt text only to Langfuse. Strip it before Grafana/Tempo
- Sampling, and the RAM cost of running all of this next to Ollama
- Useful dashboard panels: p50/p95 latency, error rate, tokens per minute, approval rate, queue depth for the indexer
- One alert that matters (e.g. error rate or p95 latency)

**Build (staged).**
1. Add the OTel SDK and auto-instrumentation. Export to the Collector.
2. Route LLM spans to Langfuse through the Collector.
3. Add Prometheus, Tempo and Grafana. Build one dashboard and one alert.

**Done when.** [ ] One request shows up as a trace in Grafana and in Langfuse. [ ] The dashboard answers "is the API slow right now?"

---

## Chapter 13: MLflow for experiment comparison

**Needs:** Chapters 6 and 7 (there must be eval runs to log).

**Why.** MLflow overlaps heavily with Langfuse for you, since you call models and do not train them. It earns a place only for **comparing offline experiment runs**.

**Where it plugs in.** `evals/run_evals.py` (log each run).

**Learn.**
- MLflow's strength: runs with parameters and metrics, side-by-side comparison, model registry
- Its LLM tracing and eval features exist but overlap with Langfuse. Do not run two trace UIs
- Where it fits: "chunk 200 vs 400, with and without reranker, qwen vs llama, which scored best?"
- Cost: another service, DB and artifact store

**Build.**
1. Run `mlflow server` in compose.
2. Log parameters (chunk size, top_k, threshold, model) and metrics (recall@k, groundedness, abstention accuracy) per eval run.
3. Compare 4 or more runs in the MLflow table.

**Done when.** [ ] You picked a configuration from the MLflow comparison. [ ] You can explain why MLflow is not your trace store.

---

## Chapter 14: RAG quality upgrades

**Needs:** Chapters 3, 6 and 7 (each upgrade needs a before/after number).

**Why.** Basic vector search plateaus. These are the standard next steps. Do each only when Chapters 6 and 7 show the failure it fixes.

**Where it plugs in.** `find_similar`, `build_rag_context`, `chunking.py`, `indexer.py`, `models/llm_chat.py`.

**Learn and build, one at a time, with a before/after number.**
- **Hybrid search**: Postgres full-text (BM25-style) plus vector, merged with reciprocal rank fusion. Fixes exact terms, ids, names
- **Reranking**: a cross-encoder reorders the top 20 into the best 5. Fixes "right chunk found but ranked low"
- **Query rewriting / multi-query**: fixes vague or conversational questions
- **Citations**: return `[document, page]` per claim. Needs page metadata from extraction. Makes groundedness checkable by a human
- **Better chunking**: by heading or sentence, parent-child chunks. Current chunking is word-based (200 words, 20 overlap)
- **Metadata filters**: tags, owner, date in the retrieval query

**Done when.** [ ] Each upgrade has a recorded before/after on your golden set. [ ] Answers carry citations.

---

## Chapter 15: Guardrails and prompt injection

**Needs:** Chapter 10 (its injection cases are the metric).

**Why.** Chapter 10 shows how the current defences fare. This chapter hardens them.

**Where it plugs in.** `tool_registry.py` (`not_asked`, `TOOL_RISK`, `TOOL_ROLE`), `tools.py` prechecks, the approval gate in `graph.py`.

**Learn.**
- Layers: input checks, tool permissions, output checks, human approval. No single layer is enough
- Direct vs indirect injection, and treating retrieved text and web results as **untrusted data**
- Replacing keyword guards with something stronger: structured intent checks, allow-lists, a separate classifier call
- Output guardrails: PII leakage, system prompt leakage
- Least privilege: the agent should not hold tools a task does not need (links to Chapter 18)
- Audit trail of approvals and rejections
- Tools: Guardrails, NeMo Guardrails, Llama Guard (learn the layers first)

**Build.**
1. Re-run the Chapter 10 injection cases after each change. The pass rate is your metric.
2. Wrap retrieved and web content in clearly marked untrusted delimiters, and measure whether it helps.
3. Add an audit table of tool calls with the approver and the decision.

**Done when.** [ ] Injection pass rate improved on the same cases. [ ] Every dangerous action has an audit row.

---

## Chapter 16: Cost, caching and abuse control

**Needs:** Chapter 4 (cost shown on traces). Chapter 12 helps for dashboards.

**Why.** LLM endpoints can run up a bill or tie up the model. This is both a cost and a security issue.

**Where it plugs in.** `rate_limit.py`, `cache.py`, `routers/llm_chat.py`, `config.py`, token counts from `graph.py`.

**Learn.**
- Per-user token and request budgets, max-token caps, `RECURSION_LIMIT` as a cost guard
- Rate limits for chat and `/ask` (today only uploads are limited)
- Exact cache and semantic cache for repeated questions, and the risk of serving a stale or wrong-user answer
- Cost per request from token counts, shown in Langfuse or Grafana
- Abuse patterns: huge prompts, loops, parallel floods

**Build.**
1. A per-user rate limit and daily token budget on chat endpoints.
2. A Redis cache for repeated `/ask` questions, keyed by user and document scope, with a TTL.
3. A cost-per-request figure on each trace.

**Done when.** [ ] One user cannot exhaust the model. [ ] Cache hits are visible in traces.

---

## Chapter 17: Feedback loop, privacy and drift

**Needs:** Chapters 4 and 6 (traces to score, a golden set to grow).

**Why.** Quality work never ends. Production tells you what the golden set missed.

**Where it plugs in.** Langfuse scores, `evals/golden.jsonl`, the memory and trace stores.

**Learn.**
- User feedback (thumbs, comments) stored as scores on traces
- Turning failed production traces into new golden-set cases
- Annotation queues and human review for the judge's blind spots
- PII: redact before traces, memory or hosted-model calls. Retention and deletion of user data
- Drift: quality changes after a model update, a new document set or a prompt edit, not only latency spikes
- Alerts on quality scores, not just errors

**Build.**
1. Add thumbs up or down to the chat API and record it on the trace.
2. A script that exports low-scored traces into new golden cases.
3. A PII redaction step before data reaches traces. Test it on fake emails and phone numbers.
4. A scheduled eval run that alerts if scores drop.

**Done when.** [ ] A real failure became a permanent test case. [ ] No raw PII reaches the trace store.

---

## Chapter 18: Multi-agent and orchestration

**Needs:** Chapter 10 (the agent evals decide whether to split).

**Why.** Mostly about knowing **when not to**. You have a single agent with 16 tools, which is a reasonable place to be.

**Where it plugs in.** `graph.py` (a router node and subgraphs), `tool_registry.py` (per-agent tool sets).

**Learn.**
- Patterns: workflow/chain, router, supervisor with workers, handoff/swarm, planner-executor, parallel fan-out, evaluator-optimizer
- Real reasons to split: too many tools confuse a small model, tasks need different prompts or models, work can run in parallel, different permissions per domain
- Reasons not to: more latency, tokens and failure points, harder tracing and evals
- LangGraph subgraphs, shared vs private state, checkpointing across agents
- MCP vs A2A: tools vs agent-to-agent calls

**Build.**
1. A router node that classifies a request into billing, tickets or documents and hands it to a specialist with **only that domain's tools**.
2. Run the Chapter 10 agent evals on both designs.
3. Keep the router only if tool-choice accuracy or cost clearly improves.

**Done when.** [ ] The decision to split, or not, rests on your eval numbers.

---

## Chapter 19: Regression in CI, prompt versions

**Needs:** Chapter 1 (tests and CI base), Chapters 6 and 7 (the scorecard to protect).

**Why.** Quality drifts when someone edits a prompt or swaps a model. This makes the evals a safety net.

**Where it plugs in.** `evals/`, a CI workflow, Langfuse prompt management, `config.py`.

**Learn.**
- Running a small eval subset on every change, with thresholds that fail the build
- Fake or stubbed LLM for unit tests vs the real model for evals (and why evals are slower, noisier and cost money)
- Prompt versioning: keep prompts out of code, version them (Langfuse prompt management or files), link a version to its eval score
- Non-determinism: temperature 0 and repeated runs for stable numbers
- Cost and latency regressions, not only quality (see Chapter 16)

**Build.**
1. A CI job that runs the retrieval eval and fails if recall@k drops by more than a set margin.
2. Move the system prompt into a versioned prompt and record its version on each trace.
3. Show cost per request next to quality in the CI report.

**Done when.** [ ] Changing a prompt shows its effect on the scorecard. [ ] A regression fails CI.

---

## Glossary

| Term | One line |
|---|---|
| Observability | Being able to explain system behavior from the data it emits |
| Trace / span | One request's journey / one step within it |
| Groundedness / faithfulness | Does the answer only say what the context supports? |
| Hallucination | A confident claim not supported by context or fact |
| Abstention | Declining to answer because evidence is weak |
| Confidence score | A proxy for certainty (similarity, logprobs, self-rating). Not a true probability |
| Calibration | Whether stated confidence matches actual accuracy |
| Ambiguity | The question has several valid readings, so ask before answering |
| Golden set | A fixed set of questions with known good answers or sources |
| recall@k / MRR | Whether, and how high, the right chunk appears in the top k |
| LLM-as-judge | Using a model to grade another model's output |
| Reranker | A slower, sharper model that reorders retrieved chunks |
| Hybrid search | Keyword plus vector retrieval, merged |
| Prompt injection | Untrusted text that tries to give the model new instructions |
| Excessive agency | The agent has more power than the task needs |
| Trajectory eval | Grading the sequence of tool calls, not just the final text |
| Online vs offline eval | Scoring live traffic vs scoring a fixed set before release |
| OTel Collector | A service that receives, processes and forwards telemetry |
| HNSW / IVFFlat | Approximate nearest-neighbour indexes that trade a little recall for speed |
| Cosine / inner product / L2 | Ways to measure how close two vectors are |
| Semantic cache | Reusing an answer for a new question that means the same as an earlier one |
| Drift | Quality changing over time because a model, data or prompt changed |
| Structured output | Model output forced into a validated schema such as JSON |
