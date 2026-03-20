"""Add cinema content for Intimes and B-ware! Ladenkino."""
from app import app, db
from models import Cinema, CinemaFilm, Film


INTIMES_NOW = [
    ("Perfect Blue", None),
    ("Akira", None),
    ("Ghost in the Shell", None),
    ("Your Name", None),
]

INTIMES_STAFF = [
    ("Millennium Actress", None),
    ("Paprika", None),
    ("The Night Is Short Walk on Girl", None),
]

INTIMES_REQUESTS = [
    ("Evangelion 3.0+1.0 Thrice Upon a Time", None),
    ("Belle", None),
    ("Inu-Oh", None),
]

BWARE_NOW = [
    ("I, Daniel Blake", None),
    ("Portrait of a Lady on Fire", None),
    ("Capernaum", None),
]

BWARE_STAFF = [
    ("La Haine", None),
    ("The Square", None),
    ("Sorry to Bother You", None),
]

BWARE_REQUESTS = [
    ("Parasite", None),
    ("Never Rarely Sometimes Always", None),
    ("Atlantics", None),
]

# Known poster URLs from OMDb / standard sources
POSTERS = {
    "Perfect Blue":              "https://m.media-amazon.com/images/M/MV5BZWM0NjcxNjQtMGU0OS00NDIwLTlhNzMtNTQ4ZGRlNTFmZTZhXkEyXkFqcGdeQXVyMTA0MTM5NjI2._V1_SX300.jpg",
    "Akira":                     "https://m.media-amazon.com/images/M/MV5BM2ZiZTk1ODgtMTZkNS00NTYxLWb3ZjQtZGM5N2JhNjJlN2I2XkEyXkFqcGdeQXVyMTE2MzA3MDM._V1_SX300.jpg",
    "Ghost in the Shell":        "https://m.media-amazon.com/images/M/MV5BNGMwNzViZTAtZGQ4Ni00ZWM1LWFhZGYtNTM2ZTVlNGViZmRiXkEyXkFqcGdeQXVyMTEyMjM2NDc2._V1_SX300.jpg",
    "Your Name":                 "https://m.media-amazon.com/images/M/MV5BODRmZDVmNzUtZjU5OC00YmI1LTk1OTMtZTM5ZjkwMzZjZTJiXkEyXkFqcGdeQXVyNTk0MzMzODA._V1_SX300.jpg",
    "Millennium Actress":        "https://m.media-amazon.com/images/M/MV5BNGU0ZWUwMWEtMzYzNS00NzZiLTljNTMtMTVmZGFkZmM4MGRjXkEyXkFqcGdeQXVyNTk0MzMzODA._V1_SX300.jpg",
    "Paprika":                   "https://m.media-amazon.com/images/M/MV5BNjcwODcyNTM5OF5BMl5BanBnXkFtZTcwODEyNjU2MQ@@._V1_SX300.jpg",
    "The Night Is Short Walk on Girl": "https://m.media-amazon.com/images/M/MV5BMjM5MzQ3NDItNGViMS00MmNlLWI2YTAtYTVkNjg3ZTZmZDdjXkEyXkFqcGdeQXVyMzgxODM4NjM._V1_SX300.jpg",
    "Evangelion 3.0+1.0 Thrice Upon a Time": "https://m.media-amazon.com/images/M/MV5BOWY4NDhhNDUtZjZlNC00MTZiLThhMjQtNzI4NzFmZDZiMWNhXkEyXkFqcGdeQXVyNjU0OTQ0OTY._V1_SX300.jpg",
    "Belle":                     "https://m.media-amazon.com/images/M/MV5BNWM0ZTNjOGItNWYwNi00YmY4LWJkZTItMzRlZjNlNWFiZDE4XkEyXkFqcGdeQXVyMTI3MDk3MzQ._V1_SX300.jpg",
    "Inu-Oh":                    "https://m.media-amazon.com/images/M/MV5BNjkxNDA0ZjktMmYzZS00ZWZlLWEzZDMtYmIzN2NjNjQ4ZWMwXkEyXkFqcGdeQXVyMTI3MDk3MzQ._V1_SX300.jpg",
    "I, Daniel Blake":           "https://m.media-amazon.com/images/M/MV5BMjIyNjk1OTgzNV5BMl5BanBnXkFtZTgwNjU3NDMwMDI._V1_SX300.jpg",
    "Portrait of a Lady on Fire":"https://m.media-amazon.com/images/M/MV5BOGUzODYyZGQtNWYwMi00M2ZhLWFkZTQtMzA4OGY3NDY3MWVjXkEyXkFqcGdeQXVyMTkxNjUyNQ@@._V1_SX300.jpg",
    "Capernaum":                 "https://m.media-amazon.com/images/M/MV5BYWI4OTZiZjYtZDQwMS00YzViLWI0ZDUtMWNhZmU3MGNhMWZkXkEyXkFqcGdeQXVyMTkxNjUyNQ@@._V1_SX300.jpg",
    "La Haine":                  "https://m.media-amazon.com/images/M/MV5BNzkzOWNlMTYtMzliZS00ODYxLWEyNTctYzAzODgxZTM5YzliXkEyXkFqcGdeQXVyMTEyNzgwMDUw._V1_SX300.jpg",
    "The Square":                "https://m.media-amazon.com/images/M/MV5BMjAwODYyMTAyMF5BMl5BanBnXkFtZTgwNzU4NTY0MjI._V1_SX300.jpg",
    "Sorry to Bother You":       "https://m.media-amazon.com/images/M/MV5BZjEzNWMwYTQtZDZiZS00NGY3LWI3MDQtMDNlMzE5OGZkYmJiXkEyXkFqcGdeQXVyMjM4NTM5NDY._V1_SX300.jpg",
    "Parasite":                  "https://m.media-amazon.com/images/M/MV5BYWZjMjk3ZTItODQ2ZC00NTY0LWE2ZTgtOTY3ZGY3ZmI1ZDQ3XkEyXkFqcGdeQXVyODk4OTc3MTY._V1_SX300.jpg",
    "Never Rarely Sometimes Always": "https://m.media-amazon.com/images/M/MV5BODg5NTc0MjEtOGZlMC00YTZiLWFjNTMtYmE5OGMzYzllNzIzXkEyXkFqcGdeQXVyMTkxNjUyNQ@@._V1_SX300.jpg",
    "Atlantics":                 "https://m.media-amazon.com/images/M/MV5BOTVlN2Q0NDQtNTJiNS00MmVhLWJmZmQtNDgxMGViM2VlZjQ0XkEyXkFqcGdeQXVyMTkxNjUyNQ@@._V1_SX300.jpg",
}


def get_poster(title):
    """Try Film table first, then our hardcoded list, else None."""
    film = Film.query.filter(Film.title.ilike(title)).first()
    if film and film.poster_url:
        return film.poster_url
    return POSTERS.get(title)


def add_films(cinema, entries, show_type):
    existing = {cf.film_title.lower() for cf in cinema.films if cf.show_type == show_type}
    added = 0
    for title, _ in entries:
        if title.lower() in existing:
            print(f"  skip (exists): {title}")
            continue
        poster = get_poster(title)
        db.session.add(CinemaFilm(
            cinema_id=cinema.id,
            film_title=title,
            poster_url=poster,
            show_type=show_type,
            votes=0,
        ))
        added += 1
        print(f"  + [{show_type}] {title}")
    return added


def run():
    with app.app_context():
        # Ensure base cinema records exist (idempotent)
        from app import _seed_cinemas
        _seed_cinemas()

        intimes = Cinema.query.filter_by(slug="intimes").first()
        bware   = Cinema.query.filter_by(slug="b-ware-ladenkino").first()

        if not intimes:
            print("ERROR: Intimes cinema not found.")
            return
        if not bware:
            print("ERROR: B-ware! Ladenkino not found.")
            return

        print(f"\n=== Intimes (id={intimes.id}) ===")
        n = 0
        n += add_films(intimes, INTIMES_NOW,      "now_showing")
        n += add_films(intimes, INTIMES_STAFF,    "staff_pick")
        n += add_films(intimes, INTIMES_REQUESTS, "screening_request")

        print(f"\n=== B-ware! Ladenkino (id={bware.id}) ===")
        n += add_films(bware, BWARE_NOW,      "now_showing")
        n += add_films(bware, BWARE_STAFF,    "staff_pick")
        n += add_films(bware, BWARE_REQUESTS, "screening_request")

        db.session.commit()
        print(f"\nDone. Added {n} new CinemaFilm entries.")


if __name__ == "__main__":
    run()
