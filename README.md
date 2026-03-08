# MoviWebApp

[![Ko-fi](https://img.shields.io/badge/Support-Ko--fi-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/mikel777)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

A social film tracking app built with Flask — think Letterboxd, but open-source, self-hostable, and community-built. Track what you watch, write reviews, follow people with great taste, and plan group movie nights.

![Homepage](screenshots/home.JPG)

---

## Features

### Discovery
- **Global film pages** — canonical pages with community ratings, AI review synthesis, streaming availability (JustWatch/DE)
- **Film search** — live OMDb lookup for any title, year and genre filters
- **Trending** — most-added films in the last 14 days with genre filter
- **Genre browse** — colour-coded genre grid with member counts
- **Curated inspiration rows** — Doomed Romance, Ghibli Forever, Mind the Gap, and more

### Social
- **Follow** — feed shows activity from people you follow
- **Reviews & comments** — write reviews, like and comment (HTMX, no page reload)
- **Taste match** — Jaccard + rating correlation score on every profile
- **Movie Nights** — plan group watches, vote on films, declare a winner, share an invite link
- **Custom Lists** — curated lists with poster strips, shareable URLs
- **Notifications** — in-app bell + optional email notifications (opt-in)

### Profiles
- **Half-star ratings** — 0.5–5.0 stars with interactive star picker
- **Currently Watching** status alongside Watched / Watchlist
- **Letterboxd import** — ZIP upload, instant history migration
- **Data export** — download your full list as CSV
- **Diary view** — films grouped by month
- **Year in Review** — stats, bar charts, genre breakdown, AI summary
- **AI taste profile** — Claude describes your taste in 2 sentences

### Cinema Partners
- `/cinemas` — local partner cinema pages (Berlin/Friedrichshain)
- Community screening requests + upvoting
- Now Showing & Staff Picks per cinema

### Tech
- **REST API** — `/api/v1/` JSON endpoints for films, users, trending
- **PWA** — installable on Android/iOS (manifest + icons)
- **i18n** — DE/EN language switcher
- **Dark/light theme** — toggle with localStorage persistence
- **Open Graph** — rich link previews on profiles, film pages, movie nights

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13 / Flask |
| Database | SQLite via SQLAlchemy |
| Auth | Flask-Login + Werkzeug |
| Frontend | HTML / CSS / HTMX (no JS framework) |
| Movie data | OMDb API |
| Streaming | JustWatch (unofficial GraphQL, DE) |
| AI | Anthropic Claude Haiku (optional) |
| Email | Flask-Mail (optional) |
| Avatars | DiceBear Avataaars |

---

## Setup

```bash
# 1. Clone and create a virtual environment
git clone https://github.com/hallochupi-sketch/MoviWebApp.git
cd MoviWebApp
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment — create a .env file:
OMDB_API_KEY=your_key        # free at omdbapi.com
SECRET_KEY=change-me

# Optional:
ANTHROPIC_API_KEY=your_key   # enables AI features
MAIL_SERVER=smtp.example.com # enables email notifications
MAIL_PORT=587
MAIL_USERNAME=you@example.com
MAIL_PASSWORD=yourpassword
MAIL_DEFAULT_SENDER=you@example.com

# 4. Seed demo data (23 users, 500+ films, 200+ reviews)
python seed_all.py

# 5. Run
python app.py
```

Open `http://127.0.0.1:5000` — log in with `ninh` / `nolancore` / `voidpilot`, password `password123`.

---

## Database (after full seed)

| Table | Count |
|-------|-------|
| Users | 23 seeded |
| Films | ~503 |
| Movies (user entries) | ~1 100 |
| Reviews | ~215 |
| Follows | ~90 |
| Review likes | ~706 |
| Cinemas | 2 (Berlin) |

---

## Key URLs

| URL | Description |
|-----|-------------|
| `/` | Homepage |
| `/u/<username>` | User profile |
| `/u/<username>/year/<year>` | Year in Review |
| `/film/<id>` | Global film page with streaming |
| `/cinemas` | Partner cinema directory |
| `/cinema/<slug>` | Cinema page with programme |
| `/nights` | Movie nights |
| `/feed` | Following feed |
| `/import` | Letterboxd import |
| `/export` | Download your list (CSV) |
| `/settings` | Email & notification settings |
| `/about` | About page |
| `/privacy` | Privacy policy |
| `/api/v1/` | REST API root |

---

## Project structure

```
MoviWebApp/
├── app.py               # All routes, AI helpers, HTMX endpoints, REST API
├── data_manager.py      # DB queries and OMDb fetching
├── models.py            # SQLAlchemy models (16 tables)
├── seed_all.py          # Run all seed scripts in order
├── seed.py              # Base users and movie lists
├── seed_social.py       # Follows, reviews, movie nights, custom lists
├── seed_rich.py         # Extended movies, reviews, social graph
├── seed_community.py    # Rich persona-matched reviews + likes
├── enrich_films.py      # Batch OMDb enrichment for Film records
├── requirements.txt
├── static/
│   ├── style.css        # Full design system (~3 000 lines)
│   ├── manifest.json    # PWA manifest
│   ├── icon-192.svg     # PWA icon
│   └── icon-512.svg
└── templates/
    ├── base.html                # Header, nav, theme toggle, PWA meta
    ├── _macros.html             # stars(), rating_select() macros
    ├── _like_btn.html           # HTMX like button
    ├── _follow_btn.html         # HTMX follow/unfollow
    ├── _vote_btn.html           # HTMX movie night vote
    ├── _review_comments.html    # HTMX review comments partial
    ├── _welcome_results.html    # HTMX onboarding film search
    ├── index.html               # Homepage
    ├── film_detail.html         # Film page with streaming, AI, comments
    ├── user_detail.html         # Profile — movies, stats, taste blurb
    ├── feed.html                # Following feed
    ├── welcome.html             # Onboarding step 1 — film picker
    ├── welcome_follow.html      # Onboarding step 2 — follow suggestions
    ├── cinemas.html             # Cinema partner directory
    ├── cinema_detail.html       # Cinema programme + requests
    ├── settings.html            # Email & notification preferences
    ├── import.html              # Letterboxd import
    ├── about.html               # About page
    └── privacy.html             # Privacy policy
```

---

## Contributing

This is a real deployed app in Berlin — your PR will be used. See **[CONTRIBUTING.md](CONTRIBUTING.md)** for the quick start, good first issues, and code style guide.

## Support

Free and open source, forever. If it made you smile, [buy us a coffee ☕](https://ko-fi.com/mikel777).

## License

MIT
