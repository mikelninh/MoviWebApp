"""Seed the DB with 20 users and their movie lists. Safe to re-run (skips existing)."""
from dotenv import load_dotenv
load_dotenv()

import random
from datetime import datetime, timedelta

from app import app, db, data_manager
from models import Movie

random.seed(42)

SEED_DATA = {
    "alice": {                         # Christopher Nolan obsessive
        "movies": [
            ("The Dark Knight",         5, "watched"),
            ("Inception",               5, "watched"),
            ("Interstellar",            4, "watched"),
            ("The Prestige",            4, "watched"),
            ("Memento",                 5, "watched"),
            ("Dunkirk",                 3, "watched"),
        ]
    },
    "bob": {                           # Crime & neo-noir
        "movies": [
            ("Pulp Fiction",            5, "watched"),
            ("Fight Club",              4, "watched"),
            ("The Godfather",           5, "watched"),
            ("Goodfellas",              4, "watched"),
            ("Heat",                    5, "watched"),
            ("No Country for Old Men",  5, "watched"),
            ("Se7en",                   4, "watched"),
        ]
    },
    "carol": {                         # International & arthouse
        "movies": [
            ("Parasite",                5, "watched"),
            ("Everything Everywhere All at Once", 5, "watched"),
            ("Spirited Away",           4, "watched"),
            ("Amelie",                  5, "watched"),
            ("Pan's Labyrinth",         4, "watched"),
            ("City of God",             5, "watched"),
        ]
    },
    "dave": {                          # Sci-fi geek
        "movies": [
            ("Blade Runner 2049",       5, "watched"),
            ("2001: A Space Odyssey",   5, "watched"),
            ("Arrival",                 5, "watched"),
            ("The Matrix",              4, "watched"),
            ("Dune",                    4, "watched"),
            ("Ex Machina",              4, "watched"),
            ("Moon",                    4, "watched"),
            ("Annihilation",            4, "watchlist"),
        ]
    },
    "emma": {                          # Horror & thriller
        "movies": [
            ("Hereditary",              5, "watched"),
            ("Get Out",                 5, "watched"),
            ("The Shining",             5, "watched"),
            ("A Quiet Place",           4, "watched"),
            ("Midsommar",               4, "watched"),
            ("Alien",                   5, "watched"),
            ("The Silence of the Lambs", 5, "watched"),
            ("Nope",                    4, "watchlist"),
        ]
    },
    "frank": {                         # Action & blockbusters
        "movies": [
            ("Mad Max: Fury Road",      5, "watched"),
            ("John Wick",               5, "watched"),
            ("Die Hard",                4, "watched"),
            ("Mission: Impossible - Fallout", 4, "watched"),
            ("Top Gun: Maverick",       5, "watched"),
            ("The Raid",                4, "watched"),
            ("Atomic Blonde",           3, "watchlist"),
        ]
    },
    "grace": {                         # Animation & family
        "movies": [
            ("Spirited Away",           5, "watched"),
            ("The Lion King",           4, "watched"),
            ("WALL-E",                  5, "watched"),
            ("Up",                      5, "watched"),
            ("Princess Mononoke",       5, "watched"),
            ("Spider-Man: Into the Spider-Verse", 5, "watched"),
            ("Coco",                    4, "watched"),
            ("Howl's Moving Castle",    4, "watchlist"),
        ]
    },
    "henry": {                         # Classic Hollywood golden age
        "movies": [
            ("Casablanca",              5, "watched"),
            ("Singin' in the Rain",     5, "watched"),
            ("Rear Window",             5, "watched"),
            ("Some Like It Hot",        4, "watched"),
            ("12 Angry Men",            5, "watched"),
            ("To Kill a Mockingbird",   4, "watched"),
            ("Sunset Blvd.",            4, "watched"),
        ]
    },
    "iris": {                          # Romance & coming-of-age drama
        "movies": [
            ("Before Sunrise",          5, "watched"),
            ("Lost in Translation",     5, "watched"),
            ("Her",                     5, "watched"),
            ("Eternal Sunshine of the Spotless Mind", 5, "watched"),
            ("The Notebook",            3, "watched"),
            ("Normal People",           4, "watched"),
            ("Call Me by Your Name",    4, "watchlist"),
        ]
    },
    "jake": {                          # Comedy first
        "movies": [
            ("The Grand Budapest Hotel", 5, "watched"),
            ("Superbad",                4, "watched"),
            ("Monty Python and the Holy Grail", 5, "watched"),
            ("This Is Spinal Tap",      4, "watched"),
            ("Knives Out",              5, "watched"),
            ("The Nice Guys",           5, "watched"),
            ("Game Night",              3, "watched"),
            ("Game Night",              3, "watchlist"),
        ]
    },
    "kate": {                          # Biopics & true stories
        "movies": [
            ("Bohemian Rhapsody",       3, "watched"),
            ("Whiplash",                5, "watched"),
            ("I, Tonya",                4, "watched"),
            ("The Social Network",      5, "watched"),
            ("Oppenheimer",             5, "watched"),
            ("Steve Jobs",              4, "watched"),
            ("Sully",                   3, "watched"),
        ]
    },
    "lena": {                          # Indie & coming-of-age
        "movies": [
            ("Boyhood",                 5, "watched"),
            ("Lady Bird",               5, "watched"),
            ("The Perks of Being a Wallflower", 4, "watched"),
            ("Moonlight",               5, "watched"),
            ("Short Term 12",           4, "watched"),
            ("Eighth Grade",            4, "watched"),
            ("Mid90s",                  3, "watchlist"),
        ]
    },
    "marcus": {                        # Westerns & epics
        "movies": [
            ("Once Upon a Time in the West", 5, "watched"),
            ("The Good the Bad and the Ugly", 5, "watched"),
            ("Unforgiven",              5, "watched"),
            ("True Grit",               4, "watched"),
            ("Django Unchained",        4, "watched"),
            ("Dances with Wolves",      3, "watched"),
            ("Tombstone",               4, "watchlist"),
        ]
    },
    "nina": {                          # Musicals & feel-good
        "movies": [
            ("La La Land",              5, "watched"),
            ("Whiplash",                5, "watched"),
            ("Sing Street",             5, "watched"),
            ("Once",                    4, "watched"),
            ("The Greatest Showman",    4, "watched"),
            ("Grease",                  3, "watched"),
            ("Mamma Mia",               3, "watched"),
        ]
    },
    "oscar": {                         # War films
        "movies": [
            ("Saving Private Ryan",     5, "watched"),
            ("Apocalypse Now",          5, "watched"),
            ("Full Metal Jacket",       4, "watched"),
            ("Hacksaw Ridge",           4, "watched"),
            ("1917",                    5, "watched"),
            ("Dunkirk",                 4, "watched"),
            ("Letters from Iwo Jima",   4, "watched"),
        ]
    },
    "petra": {                         # Mystery & neo-noir
        "movies": [
            ("Chinatown",               5, "watched"),
            ("The Big Lebowski",        4, "watched"),
            ("L.A. Confidential",       5, "watched"),
            ("Knives Out",              5, "watched"),
            ("Vertigo",                 5, "watched"),
            ("Mulholland Drive",        4, "watched"),
            ("Blue Velvet",             3, "watchlist"),
        ]
    },
    "quinn": {                         # Superhero & comic book
        "movies": [
            ("The Dark Knight",         5, "watched"),
            ("Avengers: Infinity War",  5, "watched"),
            ("Spider-Man: Into the Spider-Verse", 5, "watched"),
            ("Logan",                   4, "watched"),
            ("Guardians of the Galaxy", 4, "watched"),
            ("Batman v Superman: Dawn of Justice", 2, "watched"),
            ("Doctor Strange in the Multiverse of Madness", 3, "watchlist"),
        ]
    },
    "ryan": {                          # Sports dramas
        "movies": [
            ("Rocky",                   5, "watched"),
            ("Moneyball",               4, "watched"),
            ("Rush",                    5, "watched"),
            ("The Fighter",             4, "watched"),
            ("Ford v Ferrari",          5, "watched"),
            ("Miracle",                 4, "watched"),
            ("Cool Runnings",           3, "watched"),
        ]
    },
    "sofia": {                         # Period & literary adaptations
        "movies": [
            ("Pride and Prejudice",     5, "watched"),
            ("Little Women",            4, "watched"),
            ("Atonement",               4, "watched"),
            ("Sense and Sensibility",   5, "watched"),
            ("The English Patient",     4, "watched"),
            ("Jane Eyre",               3, "watched"),
            ("The Great Gatsby",        3, "watchlist"),
        ]
    },
    "tom": {                           # Mind-benders & time travel
        "movies": [
            ("Primer",                  4, "watched"),
            ("Predestination",          5, "watched"),
            ("Looper",                  4, "watched"),
            ("Donnie Darko",            5, "watched"),
            ("Coherence",               5, "watched"),
            ("Triangle",                4, "watched"),
            ("The Butterfly Effect",    3, "watched"),
        ]
    },
    "uma": {                           # Korean & Asian cinema
        "movies": [
            ("Parasite",                5, "watched"),
            ("Oldboy",                  5, "watched"),
            ("Train to Busan",          4, "watched"),
            ("The Handmaiden",          5, "watched"),
            ("A Tale of Two Sisters",   4, "watched"),
            ("Burning",                 4, "watched"),
            ("Decision to Leave",       4, "watchlist"),
        ]
    },
}

# Spread dates over the last 60 days
now = datetime.utcnow()

with app.app_context():
    db.create_all()

    all_titles = []
    for udata in SEED_DATA.values():
        all_titles += [t for t, _, _ in udata["movies"]]
    # Assign a random date for each DB slot
    total = sum(len(v["movies"]) for v in SEED_DATA.values())
    dates = sorted(
        [now - timedelta(days=random.uniform(0, 60)) for _ in range(total)],
        reverse=True
    )
    date_idx = 0

    for username, udata in SEED_DATA.items():
        user, created = data_manager.create_user(username, "password123")
        print(f"{'Created' if created else 'Exists '}: {username}")

        for title, rating, status in udata["movies"]:
            existing = Movie.query.filter_by(user_id=user.id, title=title).first()
            if existing:
                # Backfill missing metadata
                if not existing.genre:
                    meta = data_manager.fetch_omdb_data(title)
                    if meta:
                        existing.year       = existing.year       or meta.get("year")
                        existing.director   = existing.director   or meta.get("director")
                        existing.plot       = existing.plot       or meta.get("plot")
                        existing.poster_url = existing.poster_url or meta.get("poster_url")
                        existing.genre      = meta.get("genre")
                        existing.status     = existing.status     or status
                        existing.date_added = existing.date_added or dates[date_idx]
                        db.session.commit()
                        print(f"  ~ backfilled '{title}'")
                date_idx += 1
                continue

            meta = data_manager.fetch_omdb_data(title)
            movie = Movie(
                title=title, user_id=user.id, rating=rating, status=status,
                year=meta.get("year"), director=meta.get("director"),
                plot=meta.get("plot"), poster_url=meta.get("poster_url"),
                genre=meta.get("genre"),
                date_added=dates[date_idx],
            )
            db.session.add(movie)
            db.session.commit()
            label = "yes" if meta.get("poster_url") else "no"
            print(f"  + '{title}' ({meta.get('year', '?')}) genre={meta.get('genre','?')[:30]} poster={label}")
            date_idx += 1

    # Also backfill any remaining movies without genre
    remaining = Movie.query.filter(Movie.genre.is_(None)).all()
    if remaining:
        print(f"\nBackfilling {len(remaining)} movies without genre…")
        for movie in remaining:
            meta = data_manager.fetch_omdb_data(movie.title)
            if meta:
                movie.genre      = meta.get("genre")
                movie.poster_url = movie.poster_url or meta.get("poster_url")
                movie.year       = movie.year       or meta.get("year")
                movie.director   = movie.director   or meta.get("director")
                movie.plot       = movie.plot       or meta.get("plot")
                db.session.commit()
                print(f"  ~ {movie.title}: {meta.get('genre','')[:40]}")

print("\nDone.")
