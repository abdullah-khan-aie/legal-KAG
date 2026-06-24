# lodestone-graphrag

OpenSPG-based variant of Lodestone.

## Quality gates

- **pre-commit** (local, on `git commit`): ruff format + ruff lint auto-fix.
- **CI** (GitHub Actions, on push/PR): `ruff format --check`, `ruff check`, `pytest`.

## Dev setup

```bash
uv sync
uv run pre-commit install
```

Dependencies are managed with [uv](https://docs.astral.sh/uv/): `pyproject.toml`
declares them and `uv.lock` pins exact versions. `uv sync` creates the `.venv` and
installs everything, including the `dev` dependency group (ruff, pytest, pre-commit).
