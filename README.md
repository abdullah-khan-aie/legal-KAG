# legal-kag

A domain-agnostic GraphRAG engine: it ingests documents into a Neo4j knowledge
graph, then answers questions over that graph with multi-hop reasoning, full
token-cost tracing, and streaming responses.

The worked example in this repo is a corpus of UK legal matters (leases,
share-purchase agreements, litigation bundles, restructuring papers), but
nothing in the pipeline is legal-specific.

## Why KAG rather than plain GraphRAG

Vector-only RAG struggles when an answer depends on relationships spread across
documents. KAG adds a schema-constrained graph, mutual indexing between the
graph and the source chunks, and logical-form-guided reasoning, which is what
makes multi-hop questions answerable rather than merely retrievable.

## Architecture

**Ingestion** (`src/application/ingestion/`)

read → split → extract → align → embed → post-process → write

Documents are read by extension (pdf, docx, xlsx, md, txt, json), split, then
passed through schema-constrained extractors that build entities, relations and
events. Subgraphs are merged, embedded with Cohere, entity-linked, and written
to Neo4j.

**Query** (`src/application/query/`)

Several solver pipelines are available (`retriever`, `deep_thought`,
`kag_thinker`, `naive_rag`). Retrievers are derived from the same index list
that drives ingestion, so what is indexed and what is searched stay in lockstep.
Answers stream to the client over Server-Sent Events.

**Stack:** Python 3.13, FastAPI, Neo4j, Anthropic Claude, Cohere embeddings,
Langfuse, Docker, Terraform on AWS.

## What I built on top of KAG

- **Async Anthropic client** (`kag/common/llm/anthropic_client.py`) replacing the
  original Amazon Bedrock path. Native async on `AsyncAnthropic` for the hot
  paths, with schema-validated output via forced tool-use.
- **Bounded-concurrency ingestion pipeline**: a process-wide worker pool drains a
  bounded queue, so memory stays flat regardless of corpus size and extraction
  concurrency is capped globally rather than per document.
- **Langfuse cost tracing** (`src/observability/tracing.py`): one trace
  per document, a span per stage, and a generation per model call carrying real
  token usage and computed USD cost. A zero-overhead no-op when disabled.
- **Direct Cohere embeddings** replacing the Bedrock embedding path.
- **Evaluation harness** (`src/evaluation/`): goldset sweep across
  pipelines, scored with exact match, token F1, an LLM judge, and context recall.
- **Deployment**: Docker image, Terraform-managed AWS infrastructure, and GitHub
  Actions CI/CD using OIDC.

## Findings worth noting

Tracing surfaced an **~84x token amplification**: a 1,600-token document billed
roughly 134,000 input and 32,500 output tokens, because every chunk passes
through several extractors, each carrying a large system prompt. Cost is
therefore driven by *chunks x extractor passes*, not raw document size.

That measurement made cost predictable: about **$0.88 per document** on Claude
Sonnet 4.6, or roughly a third of that on Haiku 4.5, which turned model
selection into an evidence-based decision rather than a guess.

## Configuration

All configuration loads from a single AWS Secrets Manager secret. There is no
`.env` fallback, so a missing key fails startup loudly instead of running on a
stale value. See `.env.example` for the full key reference.

```bash
AWS_SECRETS_MANAGER_SECRET_ID=env
AWS_SECRETS_MANAGER_REGION=eu-west-2
```

## Dev setup

```bash
uv sync
uv run pre-commit install
uv run uvicorn src.main:app --reload
```

Dependencies are managed with [uv](https://docs.astral.sh/uv/): `pyproject.toml`
declares them and `uv.lock` pins exact versions. `uv sync` creates the `.venv`
and installs everything, including the `dev` group (ruff, pytest, pre-commit).

## Quality gates

- **pre-commit** (local, on `git commit`): ruff format + ruff lint auto-fix.
- **CI** (GitHub Actions, on push/PR): `ruff format --check`, `ruff check`, `pytest`.
