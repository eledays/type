# Repository Guidelines

## Project Structure & Module Organization

Application code lives in `app/`. Group HTTP handlers by domain under `app/routes/`; page handlers belong in `pages.py`, JSON endpoints in `api.py`, and business logic in `app/services/`. Database entities are in `app/models/`, with access helpers in `app/security/`. Templates and browser assets are under `app/templates/` and `app/static/`. Tests live in `tests/`, migration revisions in `migrations/versions/`, and seed data in `fixtures/`. See `docs/routing.md` before changing URLs or blueprints.

## Build, Test, and Development Commands

Create an environment and install dependencies with:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, set a secret of at least 16 characters, then use:

- `flask --app app db upgrade` — apply Alembic migrations.
- `flask --app app csv_to_db fixtures/test_words.csv` — load development data.
- `python run_dev.py` — start the local server.
- `pytest` — run the complete test suite with repository warning settings.
- `pytest tests/test_practice.py -q` — run one focused test module.

## Coding Style & Naming Conventions

Use four-space indentation, type hints, and concise docstrings for public Python functions. Follow PEP 8-style formatting and group imports as standard library, third party, then local modules. Use `snake_case` for modules, functions, variables, and API fields; use `PascalCase` for models and test classes. Keep route handlers thin: validation and responses stay in routes, while multi-model operations and external calls go into services. Obtain frontend routes through `url_for`/`window.routeConfig`, never hard-coded absolute paths.

## Testing Guidelines

Tests use pytest and Flask's test client with an isolated in-memory SQLite database (`tests/base.py`). Name files `test_<area>.py`, classes `TestFeature`, and methods `test_<behavior>`. Add regression coverage for fixes. Route changes should test the URL map, allowed methods, validation, permissions, and primary error statuses. Run `pytest` before submitting changes.

## Commit & Pull Request Guidelines

History uses short, imperative, scoped prefixes such as `feat:`, `fix:`, `refactor:`, `tests:`, and `db:`. Keep each commit focused; include migrations with schema changes. Pull requests should explain the user-visible effect, note configuration or migration steps, link related issues, and report test results. Include screenshots for template, CSS, or JavaScript UI changes.

## Security & Configuration

Never commit `.env`, credentials, OAuth secrets, or production databases. Add new settings through `AppSettings` in `config.py`, document them in `.env.example`, and validate unsafe or inconsistent values at startup.
