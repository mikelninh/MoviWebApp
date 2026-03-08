# Contributing to MoviWebApp

Thanks for your interest! MoviWebApp is a real deployed app with real users in Berlin — your contribution will be used, not just merged and forgotten.

No corporate process here. Just good taste in films and clean code.

---

## Quick start

```bash
git clone https://github.com/hallochupi-sketch/MoviWebApp.git
cd MoviWebApp
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt

# Create .env with your keys:
# OMDB_API_KEY=your_key   ← free at omdbapi.com
# SECRET_KEY=dev-secret

python seed.py
python seed_social.py
python seed_rich.py
python seed_community.py

python app.py
# → http://127.0.0.1:5000
```

Log in with `ninh` / `nolancore` / `voidpilot` — password `password123`.

---

## How to contribute

1. **Check open issues** — anything labelled `good first issue` is ready to pick up
2. **Comment on the issue** so we know you're working on it
3. **Fork → branch → PR** — keep branches focused (one feature per PR)
4. **Open an issue first** for anything large or architectural

No formal CLA. No contributor license agreement. MIT project, MIT contributions.

---

## What we're looking for

### Good first issues

| Issue | Complexity | Notes |
|-------|-----------|-------|
| Interactive half-star rating picker | Low | Replace `<select>` with clickable stars — JS, no framework |
| "Currently watching" status | Low | Add a third status alongside watched/watchlist |
| Dark / light theme toggle | Low | CSS custom properties, `localStorage` preference |
| German translation (i18n) | Medium | Flask-Babel, `de` locale — perfect for Berlin users |
| Email notifications | Medium | Flask-Mail, digest of follows and likes |
| Cinema partner pages | Medium | `/cinemas`, `Cinema` model, programme list |
| REST API (`/api/v1/`) | Medium | JSON endpoints for films, users, reviews |
| Mobile PWA manifest | Low | `manifest.json` + service worker for installability |

### Bigger ideas (open an issue to discuss first)

- **Comments on reviews** — threaded discussion under each review
- **Film clubs** — private groups with shared lists and chat
- **Streaming availability** — JustWatch API integration
- **Import from IMDb** — CSV export format support
- **Local cinema integration** — scheduling data, ticket deep-links

---

## Code style

- **Python**: follow existing patterns — Flask routes, SQLAlchemy models, no magic
- **Templates**: Jinja2 + HTMX — avoid adding JS frameworks; HTMX partial swaps preferred
- **CSS**: add to `static/style.css` in the relevant section; use existing CSS variables (`--accent`, `--surface`, `--text-muted`)
- **No linter config yet** — use common sense: 4-space indent, descriptive names, short functions

---

## Stack cheat sheet

| Thing | How |
|-------|-----|
| New route | Add to `app.py`, follow naming conventions |
| New model | Add to `models.py`, run `db.create_all()` or alter the SQLite table manually |
| HTMX partial | New template starting with `_`, return with `render_template()` |
| New page | Extend `base.html`, add to nav if top-level |
| Styles | Add to `style.css` in the right section with a comment header |

---

## What a good PR looks like

- Does one thing
- Has a description explaining *why*, not just *what*
- Doesn't break existing pages (quick smoke test: home, profile, film detail, feed)
- Keeps the cinematic dark aesthetic

---

## Questions?

Open an issue or reach out via [Ko-fi](https://ko-fi.com/mikel777). We're friendly.

---

*MoviWebApp is deployed and used by real humans in Berlin. Ship something good.*
