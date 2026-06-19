# lodestone-graphrag

OpenSPG-based variant of Lodestone.

## Quality gates

- **pre-commit** (local, on `git commit`): ruff format + ruff lint auto-fix.
- **CI** (GitHub Actions, on push/PR): `ruff format --check`, `ruff check`, `pytest`.

## Dev setup

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -r requirements.txt
pre-commit install
```
