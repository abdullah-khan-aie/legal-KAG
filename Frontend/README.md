# Frontend — Lodestone AI Search

A single, dependency-free `index.html` that streams answers from the Lodestone
query API. No build step, no npm, no framework — it runs anywhere a browser can
open it, and FastAPI serves it unchanged at `/ui`.

```
Frontend/
├── index.html          the whole UI (HTML + CSS + vanilla JS in one file)
├── legacy/index.html   the previous minimal UI, kept for reference
└── README.md           this guide
```

## What it does

- Enterprise app shell: dark-mode-first (zinc/slate + blue accent), sidebar
  navigation (only **AI Search** is live in this POC; other sections are
  visible but disabled), light theme toggle persisted in `localStorage`.
- Sends your question to **`POST /query/stream`** and consumes the
  **Server-Sent Events (SSE)** stream, so the answer appears token-by-token.
- Pipeline selector: **Retriever** (fast, default), **Deep thought**,
  **KAG thinker** — these map to `QueryRequest.pipeline`.
- **Reasoning trace**: `step` events render as a live timeline — each stage
  shows a spinner/check/error marker, per-step duration, and (for `thinker`
  stages) the streaming thinking text in an expandable body. Repeated events
  for the same `stage`+`label` update one entry in place (the solver re-sends
  content as it grows). The trace auto-collapses when the run completes.
- **Session run feed**: every question becomes a run block headed by the
  question itself (newest on top, expanded; older runs collapse to one line
  and can be re-opened) — so you can compare pipelines on the same question
  without losing answers. Each run has a "run again" action; failed runs get
  a **Retry** button.
- Answer card with copy-as-Markdown, plus run metadata: total time,
  first-token latency, chunk count, step count.
- An inline warning appears above the composer when the API health check
  fails, before you waste a query.
- Recent queries (last 5, `localStorage`) shown as one-click chips.
- Markdown rendered with a small built-in renderer (HTML-escaped first).
- Keyboard: `Enter` sends, `Shift+Enter` newline, `⌘/Ctrl+K` or `/` focuses
  the box, `Esc` stops a run.

### The event contract it relies on

`src/lodestone/api/routes/query.py` emits these SSE events; the UI handles each:

| event    | data                              | UI behaviour                                    |
|----------|-----------------------------------|-------------------------------------------------|
| `step`   | `{stage, label, status, content?}`| upserts a reasoning-trace entry; streams content |
| `token`  | `{delta}`                         | appends a chunk to the live answer               |
| `answer` | `{answer}`                        | replaces with the authoritative answer           |
| `done`   | `[DONE]`                          | marks the run complete                           |
| `error`  | `{error}`                         | error card + settles running steps as failed     |

Step `status` values are normalised: `FINISH`/`FINISHED`/`DONE` → done,
anything containing `ERROR`/`FAIL` → error, everything else → running.

## How it's wired (already done)

`src/lodestone/main.py` serves this folder as static files, so the page and the
API share an origin (no CORS needed):

```python
_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "Frontend"
...
@app.get("/", include_in_schema=False)
async def _root() -> RedirectResponse:
    return RedirectResponse(url="/ui/")

app.mount("/ui", StaticFiles(directory=_FRONTEND_DIR, html=True), name="ui")
```

- `GET /`     → redirects to `/ui/`
- `GET /ui/`  → serves `index.html`
- `POST /query/stream`, `POST /ingest` → the API (unchanged)

## Deploy the backend (which serves this UI)

There is **no separate frontend build or server** — the FastAPI backend serves
this folder at `/ui`. Deploy the backend and the UI is live on the same port.

On the app EC2 instance, from the repo root (`v2/`):

```bash
# 1. Install uv + dependencies (once)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --frozen

# 2. Write .env (LODESTONE_ prefix; see ../.env.example)
cat > .env <<'EOF'
LODESTONE_NEO4J_URI=bolt://10.20.1.73:7687       # Neo4j box private IP (same VPC)
LODESTONE_NEO4J_PASSWORD=<neo4j password>
LODESTONE_BEDROCK_API_KEY=sigv4                  # "sigv4" = use the instance role (no key)
LODESTONE_LLM_MODEL=anthropic.claude-sonnet-4-6
LODESTONE_EMBED_MODEL=cohere.embed-english-v3
LODESTONE_BEDROCK_REGION=eu-west-2
LODESTONE_EMBED_REGION=eu-west-2
LODESTONE_SCAN_DIR=ingest_docs
EOF

# 3. Run it (serves API + UI). Use a process manager so it survives logout:
nohup uv run uvicorn src.lodestone.main:app --host 0.0.0.0 --port 8080 \
  > app.log 2>&1 &
```

Required environment:

| Variable                  | Purpose                                              |
|---------------------------|------------------------------------------------------|
| `LODESTONE_NEO4J_URI`       | `bolt://<neo4j-private-ip>:7687` (same VPC)          |
| `LODESTONE_NEO4J_PASSWORD`  | Neo4j password                                       |
| `LODESTONE_BEDROCK_API_KEY` | `sigv4` to use the EC2 instance role (no key needed) |
| `LODESTONE_LLM_MODEL`       | `anthropic.claude-sonnet-4-6` (bare on-demand id)    |
| `LODESTONE_EMBED_MODEL`     | `cohere.embed-english-v3`                            |

Two things that must be true for it to actually answer:

1. **On EC2, leave `AWS_PROFILE` unset** — boto3 uses the instance role for
   Bedrock automatically (that's what `LODESTONE_BEDROCK_API_KEY=sigv4` selects).
   No `aws sso login` on the box. The instance role needs Bedrock + Neo4j access.
2. **The graph must have data** — run ingestion first (put docs in
   `LODESTONE_SCAN_DIR`, then `curl -X POST http://localhost:8080/ingest`), or the
   UI returns empty answers.

## Give it to test users (public URL)

The UI is served at `http://<app-ec2-public-ip>:8080/`. To hand that URL to
testers, open port 8080 to the internet on the app instance's security group:

```bash
aws ec2 authorize-security-group-ingress --region eu-west-2 \
  --group-id <app-sg-id> \
  --ip-permissions 'IpProtocol=tcp,FromPort=8080,ToPort=8080,IpRanges=[{CidrIp=0.0.0.0/0,Description="test-users"}]'
```

Then send testers: **`http://<app-ec2-public-ip>:8080/`** (bookmark it; nothing
to install). A stable Elastic IP or a domain is nicer than the raw public IP.

**Open the frontend port only.** Make *only* `8080` (the app that serves the UI
and its query API) public. **Do not** open the Neo4j ports (`7474`/`7687`) or SSH
(`22`) to the internet — those stay private/VPC-only. The public should be able
to reach the frontend and nothing else on the box.

> ⚠️ **No authentication.** With 8080 public, anyone with the URL can query the
> graph and can trigger `POST /ingest`. Only do this with **non-sensitive test
> data**, and close 8080 again (`revoke-security-group-ingress`) when the test
> window ends. To add a login later, see the CORS/auth note below — HTTP Basic
> auth middleware on FastAPI is the smallest change.

## Hosting the page apart from the API (optional)

If you serve `index.html` from somewhere else (a CDN, `file://`, a different
port), point it at the API and enable CORS.

1. Set the API base before the page's script runs:
   ```html
   <script>window.LODESTONE_API_BASE = "http://your-api-host:8080";</script>
   ```
   (When opened as `file://`, it already defaults to `http://localhost:8080`.)

2. Allow that origin on the API — add to `src/lodestone/main.py`:
   ```python
   from fastapi.middleware.cors import CORSMiddleware
   app.add_middleware(
       CORSMiddleware, allow_origins=["*"], allow_methods=["POST"], allow_headers=["*"],
   )
   ```

## Getting data in first

The UI only reads the graph — populate Neo4j before asking:

- Put documents in `LODESTONE_SCAN_DIR` and call **`POST /ingest`**, or
- run an ingestion script (see `../scratchpad/`).

## Customising

- **Pipelines** — edit the `.seg` buttons in `index.html` to match
  `PipelineName` in `src/lodestone/api/schemas.py`.
- **Examples** — edit the `.examples` chips.
- **Look** — all styling is CSS variables at the top of `index.html`; dark mode
  follows the OS via `prefers-color-scheme`.
