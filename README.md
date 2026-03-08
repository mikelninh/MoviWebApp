# MoviWebApp

A social movie tracking app where users build personal watchlists, discover films through curated lists, and see what others are watching.

## Features

- **Personal movie lists** — track what you've watched and what's on your watchlist
- **OMDb integration** — auto-fetches poster, year, director, plot, and genre for any title
- **Movie Night Inspiration** — curated themed lists (Doomed Romance, Ghibli Forever, Mind the Gap, etc.) with Netflix-style poster rows on the homepage
- **Smart search** — deduplicates results by title, shows OMDb fallback for movies not yet in any user's list
- **Recommendations** — suggests films based on taste overlap with other users
- **Similar movies** — shows what else users who have the same film tend to watch
- **Star ratings** — 1–5 stars per movie
- **Genre tags** — colour-coded, pulled from OMDb

## Stack

- **Backend** — Python / Flask
- **Database** — SQLite via SQLAlchemy
- **Auth** — Flask-Login with hashed passwords
- **Frontend** — Vanilla HTML/CSS, no JS framework
- **Movie data** — OMDb API

## Setup

```bash
# 1. Clone and create a virtual environment
git clone <repo-url>
cd MoviWebApp
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your OMDb API key
echo OMDB_API_KEY=your_key_here > .env
# Get a free key at https://www.omdbapi.com/apikey.aspx

# 4. Run the app
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

## Seed data

To populate the database with 23 example users and their movie lists:

```bash
python seed.py
```

This is safe to re-run — it skips any users or movies that already exist.

## Project structure

```
MoviWebApp/
├── app.py            # Flask routes and app factory
├── data_manager.py   # DB operations and OMDb fetching
├── models.py         # SQLAlchemy models (User, Movie)
├── seed.py           # Demo users and their movie lists
├── requirements.txt
├── static/
│   └── style.css
├── templates/
│   ├── base.html
│   ├── index.html        # Homepage with inspiration rows
│   ├── user_detail.html  # User's movie list
│   ├── movie_detail.html
│   ├── search.html
│   ├── edit_movie.html
│   ├── login.html
│   └── register.html
└── data/
    └── (movies.db created on first run)
```
