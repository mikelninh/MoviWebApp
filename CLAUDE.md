# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app
python app.py

# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_auth.py -v

# Run a single test
python -m pytest tests/test_auth.py::test_login -v

# Seed demo data (23 users, 500+ films, 200+ reviews)
python seed_all.py

# Or seed step by step
python seed.py && python seed_social.py && python seed_rich.py && python seed_community.py

# Apply DB migrations
flask db upgrade

# Create a new migration after model changes
flask db migrate -m "description"
```

Required env vars (copy `.env.example` to `.env`):
- `SECRET_KEY` — Flask secret key
- `OMDB_API_KEY` — free at omdbapi.com

Optional:
- `ANTHROPIC_API_KEY` — enables AI features (taste profile, review synthesis, "why you'll love this")
- `MAIL_SERVER` / `MAIL_USERNAME` / `MAIL_PASSWORD` — enables email notifications
- `JUSTWATCH_COUNTRY` — defaults to `DE`

## Architecture

### Key separation: `Film` vs `Movie`

The most important data model distinction:

- **`Film`** (`models.py`) — global canonical record for a title. One per film, shared across all users. Has `id`, `title`, `year`, `director`, `poster_url`, `genre`, `imdb_id`. Lives at `/film/<id>`.
- **`Movie`** (`models.py`) — a user's personal entry. Many per film (one per user who added it). Has `user_id`, `film_id` (FK to Film), `rating`, `status` (`watched`/`watchlist`/`currently_watching`), `date_added`.

When a user adds a film, a `Movie` row is created and linked to the canonical `Film` via `film_id`. Reviews are stored by `movie_title` string (not FK) for historical reasons.

### Blueprint structure

All routes live in `blueprints/`. Each blueprint is a logical domain:

| Blueprint | Prefix | Responsibility |
|-----------|--------|---------------|
| `auth` | — | Login, register, password reset, email verify |
| `profiles` | `/u/<username>` | User profile, diary, year-in-review, settings |
| `films` | `/film/`, `/movies/` | Film detail, add/edit/delete movies, reviews |
| `social` | — | Follow/unfollow, likes, comments, feed, notifications |
| `discovery` | `/discover`, `/browse`, `/genre/` | Trending, genre browse, inspiration |
| `lists` | `/lists/` | Custom user lists |
| `nights` | `/nights/` | Movie nights with voting |
| `cinemas` | `/cinemas/`, `/cinema/` | Partner cinema pages (Berlin) |
| `api` | `/api/v1/` | REST API (CSRF-exempt, rate-limited) |
| `pages` | — | Static pages (index, about, privacy, import, export) |

`app.py` creates the Flask app, registers all blueprints and extensions, runs startup migrations (`migrate_db()`, `populate_films()`, `_seed_cinemas()`), and registers template globals.

### Extensions (`extensions.py`)

All Flask extensions are instantiated in `extensions.py` and initialized with the app in `app.py`:
- `db` (SQLAlchemy) — in `models.py`
- `csrf` (Flask-WTF), `limiter` (Flask-Limiter), `login_manager`, `mail`, `migrate`

### `DataManager` (`data_manager.py`)

Class wrapping low-level DB queries and OMDb API calls. Instantiated once per blueprint that needs it. Handles user CRUD, movie CRUD, and `fetch_omdb_data()` for enriching titles from the OMDb API.

### AI helpers (`helpers.py`)

All AI/Claude calls go through `helpers.py`. The Anthropic client is lazy-initialized (only if `ANTHROPIC_API_KEY` is set) and results are in-process cached in `_ai_cache`. Main functions: `ai_review_synthesis()`, `ai_taste_profile()`, `ai_why_love()`. Uses `claude-haiku-4-5-20251001`.

### HTMX pattern

Interactive UI (likes, follows, vote buttons, review comments) uses HTMX partial swaps. Partial templates are prefixed with `_` (e.g., `_like_btn.html`, `_follow_btn.html`, `_review_comments.html`). Blueprints return these partials for HTMX requests and full pages for normal requests.

### Database

SQLite at `data/movies.db`. Schema managed by Flask-Migrate (Alembic). Legacy columns added by `migrate_db()` in `app.py` via raw `ALTER TABLE` for backwards compatibility on existing installs. New columns should use proper Alembic migrations instead.

### i18n

`helpers._t()` is a minimal translation helper injected as `_()` into all Jinja templates. Language is stored in the Flask session. German (`de`) and English (`en`) are supported.

## Code style

- Python: 4-space indent, type hints on new functions, descriptive names
- Templates: Jinja2 + HTMX — no JS frameworks; use HTMX partial swaps for interactivity
- CSS: add to `static/style.css` in the relevant section using existing CSS variables (`--accent`, `--surface`, `--text-muted`)
- New routes go in the appropriate blueprint, not in `app.py`

## Tests

Tests use a temporary SQLite database (not the dev DB). CSRF is disabled in tests. The `conftest.py` provides `app`, `client`, `runner`, and `test_user` fixtures. Tests live in `tests/test_auth.py`, `test_routes.py`, and `test_api.py`.
