"""Run once to populate the DB with sample users and movies."""
from dotenv import load_dotenv
load_dotenv()

from app import app, db, data_manager
from models import Movie

SEED_DATA = {
    "alice": [
        ("The Dark Knight",     5),
        ("Inception",           5),
        ("Interstellar",        4),
        ("The Prestige",        4),
    ],
    "bob": [
        ("Pulp Fiction",        5),
        ("Fight Club",          4),
        ("The Godfather",       5),
        ("Goodfellas",          4),
    ],
    "carol": [
        ("Parasite",            5),
        ("Everything Everywhere All at Once", 5),
        ("Spirited Away",       4),
    ],
}

with app.app_context():
    db.create_all()
    for username, movies in SEED_DATA.items():
        user, created = data_manager.create_user(username, "password123")
        if created:
            print(f"Created user: {username}")
        else:
            print(f"User already exists: {username}")
        for title, rating in movies:
            existing = Movie.query.filter_by(user_id=user.id, title=title).first()
            if existing:
                print(f"  - skipping '{title}' (already exists)")
                continue
            meta = data_manager.fetch_omdb_data(title)
            movie = Movie(
                title=title,
                user_id=user.id,
                rating=rating,
                year=meta.get("year"),
                director=meta.get("director"),
                plot=meta.get("plot"),
                poster_url=meta.get("poster_url"),
            )
            db.session.add(movie)
            db.session.commit()
            print(f"  + added '{title}' (year={meta.get('year')}, poster={'yes' if meta.get('poster_url') else 'no'})")

print("\nDone.")
