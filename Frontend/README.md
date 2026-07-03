# Frontend — minimal query UI

A single, dependency-free `index.html` that streams answers from the Lodestone
query API and renders them as Markdown. No build step, no npm, no framework — it
runs anywhere a browser can open it.

```
Frontend/
├── index.html   the whole UI (HTML + CSS + vanilla JS in one file)
└── README.md    this guide
```

## What it does

- Sends your question to **`POST /query/stream`** and consumes the
  **Server-Sent Events (SSE)** stream, so the answer appears token-by-token.
- Lets you pick the pipeline: **Retriever** (fast, default), **Deep thought**,
  **KAG thinker** — these map to `QueryRequest.pipeline`.
- Renders the model's Markdown (headings, **bold**, lists, tables, code,
  links) with a small built-in renderer, so raw `**`/`#` markers never leak
  into the page.
- `Enter` sends, `Shift+Enter` inserts a newline, `Stop` aborts a run.

### The event contract it relies on

`src/lodestone/api/routes/query.py` emits these SSE events; the UI handles each:

| event    | data                    | UI behaviour                          |
|----------|-------------------------|---------------------------------------|
| `step`   | `{stage, label, status}`| shows progress in the status line     |
| `token`  | `{delta}`               | appends a chunk to the live answer    |
| `answer` | `{answer}`              | replaces with the authoritative answer|
| `done`   | `[DONE]`                | marks the run complete                |
| `error`  | `{error}`               | shows the failure in red              |

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

## Run it

From the repo root (`v2/`), with a `.env` that has Neo4j + Bedrock configured:

```bash
uv run uvicorn src.lodestone.main:app --host 0.0.0.0 --port 8080
```

Then open **http://localhost:8080/** (redirects to `/ui/`).

Required environment (see `../.env.example` / `config/settings.py`, `LODESTONE_` prefix):

| Variable                | Purpose                                        |
|-------------------------|------------------------------------------------|
| `LODESTONE_NEO4J_URI`     | e.g. `bolt://10.20.1.73:7687` (private) or a tunnel |
| `LODESTONE_NEO4J_PASSWORD`| Neo4j password                                 |
| `LODESTONE_BEDROCK_API_KEY` | bearer token for the LLM + embeddings        |

> The query path calls the LLM. If `LODESTONE_BEDROCK_API_KEY` is missing or lacks
> access to the configured models, questions return an `error` event — the UI is
> fine, the backend just can't answer.

## Reaching it on an EC2 deployment

Don't expose port 8080 to the world. Two options:

- **Recommended — SSM tunnel** (nothing public, survives IP changes):
  ```bash
  aws ssm start-session --profile sandbox --region eu-west-2 \
    --target <app-instance-id> --document-name AWS-StartPortForwardingSession \
    --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}'
  ```
  then browse `http://localhost:8080/`.

- **Or** open 8080 in the app instance's security group **to your IP only**
  (`x.x.x.x/32`), and browse `http://<app-public-ip>:8080/`. Re-whitelist when
  your IP rotates.

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
