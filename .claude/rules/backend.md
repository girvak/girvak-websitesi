---
paths:
  - "backend/**"
---

# Backend rules (Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 async)

## Layers: who may do what

| Layer | Folder | Does | Never |
|---|---|---|---|
| Router | `modules/*/router.py`, `http/router.py` | parse the request, call the service, return the response schema, declare `responses={…}` with error codes | business rules, SQL |
| Service | `modules/*/service.py`, page modules | product rules, commit/rollback, raise app errors | build HTTP responses |
| Repository | `infra/db/repositories/` | row access for one model | commit, product decisions |
| Infra | `infra/airtable`, `infra/cache`, `infra/storage`, `infra/db` | talk to one external thing | contain a product noun or sentence |
| Shared | `shared/errors`, `shared/logging` | cross-cutting plumbing | know any feature |
| HTTP | `http/` | request id, CORS, rate limit, security headers, error JSON, the mount list | feature logic |

- New feature: put it in `modules/<feature>/` (`router.py`, `schemas.py`, `service.py`) and mount it in `http/router.py`.
- Content page mapping (`modules/content/<page>.py`) is pure: values in, model out, no I/O. `service.py` alone does the fetching, caching and mirroring.

## Errors

- Raise only subclasses of the hierarchy in `shared/errors/base.py` (`NotFoundError`, `ConflictError`, `ValidationError`, `ServiceUnavailableError`, …).
- A feature error is a subclass that overrides `error_code` (SCREAMING_SNAKE, prefixed by feature, e.g. `NEWSLETTER_ALREADY_SUBSCRIBED`) and passes a Turkish user message.
- `details` may hold ids and field names only, never SQL, secrets, paths or another visitor's data.
- Let the database decide uniqueness: catch `IntegrityError`, roll back, and re-raise `from None`. Don't SELECT first; two concurrent requests would both pass.

## Logging

- `get_logger(LoggerName.X)` with `API`, `SYSTEM`, `ERROR` or `AUDIT`. Module-level `_logger` / `_audit`.
- Messages are snake_case event names (`"newsletter_subscribe_stored"`). Put data in `extra={…}`, not in f-strings. Never log email addresses or secrets.

## Style

- `from __future__ import annotations` at the top of every module.
- mypy is strict on `src/`, so type everything. Use `Annotated` dependencies from `http/deps.py` (`SessionDep`, …).
- Use Google-style docstrings (`Args:` / `Returns:` / `Raises:`) on public functions. Explain *why* in the docstring when the reason isn't obvious; the existing code does this a lot.
- Private module names start with `_`. Module-level constants are UPPER_SNAKE.
- Ruff rules: E, F, I, UP, B, ASYNC, S, RUF. Line length 100. RUF001–003 are off because the copy is Turkish.
- Schema changes go through Alembic: `uv run alembic revision -m "…"`. Migration files are named `YYYYMMDD_HHMM-NNNN_<slug>.py`.

## Tests

- Mirror the source tree: `tests/modules/content/test_home.py` tests `src/girvak/modules/content/home.py`.
- Test names are sentences about behaviour: `test_missing_fragments_keep_the_seed`.
- Build Airtable rows with `tests/modules/content/builders.py` (`record`, `fragments`, `attachment`) rather than hand-written dicts.
- Settings in tests come from explicit values in `conftest.py`, never from the developer's shell.
- Tests that need PostgreSQL are marked `@pytest.mark.db`.
- Before finishing: `uv run pytest -m "not db" && uv run ruff check src tests && uv run mypy`.
