# MoviWebApp

A social movie tracking app built with Flask — think Letterboxd, but open-source and yours to run. Users build personal watchlists, write reviews, follow each other, and discover films through a community feed.

![Homepage](screenshots/home.jpg)

---

## Features

### Discovery
- **Global film pages** — every film has its own canonical page (`/film/<id>`) with community ratings, reviews, and similar films
- **Film-aware search** — searches the Film table directly; unknown titles are fetched live from OMDb and get their own page instantly
- **Search filters** — narrow by year and genre
- **Trending** — most-added films in the last 14 days
- **Genre browse** — all genres with member counts, colour-coded
- **Curated inspiration rows** — Doomed Romance, Ghibli Forever, Mind the Gap, and more on the homepage

### Social
- **Follow users** — following feed shows recent activity from people you follow
- **Reviews & likes** — write reviews, like others' reviews (HTMX — no page reload)
- **Follow / Unfollow** — instant HTMX toggle on profiles
- **Notifications** — in-app bell for follows and likes
- **Taste match** — Jaccard + rating correlation score shown on every profile you visit
- **Friends on film pages** — see which people you follow have watched a film and how they rated it
- **Movie Nights** — create group nights, suggest films, vote on what to watch
- **Custom Lists** — curated lists with poster strip previews, shareable

### Profiles
- **Pretty URLs** — `/u/<username>` (legacy `/users/<id>` redirects automatically)
- **Diary view** — films grouped by month watched
- **Year in Review** — `/u/<username>/year/<year>` with stats, bar charts, badges, and AI summary
- **Profile stats** — watched count, average rating, top genres
- **AI taste profile** — 2-sentence blurb describing your taste (requires Anthropic API key)
- **Pagination** — 24 films per page on profiles, 20 per page in search

### Film pages
- **AI review synthesis** — Claude summarises community reviews in 1–2 sentences
- **"You'll love this because"** — personalised one-liner based on your top-rated films
- **Quick-add watchlist** — add any film to your watchlist from search results

### Challenges
- Milestone badges for watching streaks, genre variety, prolific reviewing, and more

### UI
- Cinematic dark design — glass morphism header, gradient text, DiceBear avatars
- Skeleton shimmer on poster areas while images load
- Mobile hamburger nav (< 640 px)
- Custom 404 / 500 / 403 error pages with film quotes

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13 / Flask |
| Database | SQLite via SQLAlchemy |
| Auth | Flask-Login + Werkzeug password hashing |
| Frontend | HTML / CSS / HTMX (no JS framework) |
| Movie data | OMDb API |
| AI | Anthropic Claude Haiku (optional) |
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

# 3. Configure environment
# Create a .env file:
OMDB_API_KEY=your_omdb_key       # https://www.omdbapi.com/apikey.aspx (free)
ANTHROPIC_API_KEY=your_key_here  # optional — enables AI features
SECRET_KEY=change-me-in-production

# 4. Seed demo data
python seed.py          # 23 users with movie lists
python seed_social.py   # follows, reviews, movie nights, custom lists
python seed_rich.py     # more movies, reviews, and social graph density

# 5. Run
python app.py
```

Open `http://127.0.0.1:5000`

---

## Database stats (after full seed)

| Table | Count |
|-------|-------|
| Users | 23 |
| Films | ~360 |
| Movies (user entries) | ~420 |
| Reviews | ~87 |
| Follows | ~67 |
| Review likes | ~84 |

---

## Project structure

```
MoviWebApp/
├── app.py               # Flask routes, AI helpers, HTMX endpoints
├── data_manager.py      # DB operations and OMDb fetching
├── models.py            # SQLAlchemy models
├── seed.py              # Base users and movie lists
├── seed_social.py       # Follows, reviews, movie nights, custom lists
├── seed_rich.py         # Extended movies, reviews, social graph
├── requirements.txt
├── static/
│   └── style.css        # Full design system (2 000 + lines)
├── templates/
│   ├── base.html               # Header, nav, HTMX, flash messages
│   ├── index.html              # Homepage — hero spotlight + inspiration rows
│   ├── film_detail.html        # Global film page with AI, reviews, friends
│   ├── user_detail.html        # Profile — movies, stats, AI taste blurb
│   ├── year_in_review.html     # /u/<username>/year/<year>
│   ├── search.html             # Film-aware search with filters
│   ├── feed.html               # Following feed
│   ├── trending.html           # Most-added films (14-day window)
│   ├── browse.html             # Genre grid
│   ├── genre_page.html         # Single genre film list
│   ├── notifications.html      # In-app notification centre
│   ├── movie_nights.html       # Group movie night lobby
│   ├── movie_night_detail.html # Suggest + vote on films
│   ├── lists_directory.html    # Community lists with poster strips
│   ├── user_list.html          # Single custom list view
│   ├── diary.html              # Films grouped by month
│   ├── challenges.html         # Milestone badges
│   ├── _like_btn.html          # HTMX partial — like button
│   ├── _follow_btn.html        # HTMX partial — follow/unfollow button
│   └── error.html              # Custom 404/500/403
└── data/
    └── movies.db               # SQLite (created on first run, gitignored)
```

---

## Key URLs

| URL | Description |
|-----|-------------|
| `/` | Homepage |
| `/u/<username>` | User profile (canonical) |
| `/u/<username>/year/<year>` | Year in Review |
| `/film/<id>` | Global film page |
| `/search?q=...&year=...&genre=...` | Film search |
| `/trending` | Trending films |
| `/browse` | Genre browser |
| `/browse/<genre>` | Single genre |
| `/lists` | Community lists |
| `/feed` | Following feed |
| `/notifications` | Notification centre |
| `/nights` | Movie nights |
| `/challenges` | Challenges |
