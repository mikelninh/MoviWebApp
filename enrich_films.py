"""
One-time script: fetch OMDb metadata for Film records missing posters/plots.
Also syncs metadata to Movie records pointing to the same film.
Run: python enrich_films.py
"""
from dotenv import load_dotenv
load_dotenv()

import time
from app import app, db, data_manager
from models import Film, Movie

BATCH_DELAY = 0.25  # seconds between OMDb calls (stay within free tier)

with app.app_context():
    films = Film.query.filter(Film.poster_url.is_(None)).all()
    total = len(films)
    print(f"Films missing metadata: {total}")

    enriched = skipped = failed = 0

    for i, film in enumerate(films, 1):
        safe_title = film.title.encode('ascii', 'replace').decode('ascii')
        print(f"[{i}/{total}] {safe_title} ({film.year or '?'})", end=" ... ", flush=True)

        meta = data_manager.fetch_omdb_data(film.title)
        if not meta:
            print("not found")
            failed += 1
            time.sleep(BATCH_DELAY)
            continue

        film.poster_url = meta.get("poster_url")
        film.plot       = meta.get("plot")
        film.director   = meta.get("director")
        film.genre      = meta.get("genre")
        if not film.year:
            film.year   = meta.get("year")

        # Sync to all Movie records for this film
        Movie.query.filter_by(film_id=film.id).update({
            "poster_url": meta.get("poster_url"),
            "plot":       meta.get("plot"),
            "director":   meta.get("director"),
            "genre":      meta.get("genre"),
        }, synchronize_session=False)

        db.session.commit()
        enriched += 1
        print(f"OK {meta.get('director', '')} | {meta.get('genre', '')[:30]}")
        time.sleep(BATCH_DELAY)

    print(f"\nDone. Enriched: {enriched} | Not found: {failed}")
