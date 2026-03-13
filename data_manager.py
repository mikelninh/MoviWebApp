import logging
import os
from collections import Counter
from datetime import datetime

import requests

from models import Movie, User, db

logger = logging.getLogger("moviwebapp")


class DataManager:
    OMDB_API_KEY = os.environ.get("OMDB_API_KEY", "")

    # ── USERS ────────────────────────────────────────────────────────────────

    def create_user(self, name: str, password: str) -> tuple[User, bool]:
        existing = User.query.filter_by(username=name).first()
        if existing:
            return existing, False
        user = User(username=name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user, True

    def get_user_by_username(self, username: str) -> User | None:
        return User.query.filter_by(username=username).first()

    def get_users(self) -> list[User]:
        return User.query.all()

    def delete_user(self, user_id: int) -> bool:
        user = db.session.get(User, user_id)
        if not user:
            return False
        Movie.query.filter_by(user_id=user_id).delete()
        db.session.delete(user)
        db.session.commit()
        return True

    # ── MOVIES ───────────────────────────────────────────────────────────────

    def get_movies(self, user_id: int, sort: str = "title", status: str = "") -> list[Movie]:
        query = Movie.query.filter_by(user_id=user_id)
        if status in ("watched", "watchlist"):
            query = query.filter(Movie.status == status)
        if sort == "rating":
            query = query.order_by(db.func.coalesce(Movie.rating, 0).desc())
        elif sort == "year":
            query = query.order_by(db.func.coalesce(Movie.year, "").desc())
        else:
            query = query.order_by(db.func.lower(Movie.title))
        return query.all()

    def get_recent_activity(self, limit: int = 10) -> list[Movie]:
        return Movie.query.order_by(Movie.id.desc()).limit(limit).all()

    def fetch_omdb_data(self, title: str) -> dict:
        """Return metadata dict from OMDb, or {} if unavailable."""
        if not self.OMDB_API_KEY:
            return {}
        try:
            resp = requests.get(
                "https://www.omdbapi.com/",
                params={"t": title, "apikey": self.OMDB_API_KEY},
                timeout=5,
            )
            data = resp.json()
            if data.get("Response") == "True":
                poster = data.get("Poster", "")
                return {
                    "year":       data.get("Year", "")[:10],
                    "director":   data.get("Director", "")[:120],
                    "plot":       data.get("Plot", ""),
                    "poster_url": poster if poster != "N/A" else "",
                    "genre":      data.get("Genre", "")[:200],
                }
        except Exception:
            logger.exception("OMDb fetch failed for '%s'", title)
        return {}

    def add_movie(self, movie: Movie) -> Movie:
        if not movie.date_added:
            movie.date_added = datetime.utcnow()
        db.session.add(movie)
        db.session.commit()
        return movie

    def update_movie(self, movie_id: int, new_title: str, new_rating: float | None = None, new_status: str | None = None) -> Movie | None:
        movie = db.session.get(Movie, movie_id)
        if not movie:
            return None
        movie.title = new_title
        movie.rating = new_rating
        if new_status in ("watched", "watchlist"):
            movie.status = new_status
        meta = self.fetch_omdb_data(new_title)
        if meta:
            movie.year       = meta.get("year")
            movie.director   = meta.get("director")
            movie.plot       = meta.get("plot")
            movie.poster_url = meta.get("poster_url")
            movie.genre      = meta.get("genre")
        db.session.commit()
        return movie

    def toggle_status(self, movie_id: int) -> Movie | None:
        movie = db.session.get(Movie, movie_id)
        if not movie:
            return None
        movie.status = "watchlist" if movie.status == "watched" else "watched"
        db.session.commit()
        return movie

    def delete_movie(self, movie_id: int) -> bool:
        movie = db.session.get(Movie, movie_id)
        if not movie:
            return False
        db.session.delete(movie)
        db.session.commit()
        return True

    # ── RECOMMENDATIONS ──────────────────────────────────────────────────────

    def get_recommendations(self, user_id: int, limit: int = 6) -> list[Movie]:
        """Movies liked by users with overlapping taste that this user hasn't added."""
        my_titles = {m.title.lower() for m in Movie.query.filter_by(user_id=user_id).all()}
        my_liked = {m.title for m in Movie.query.filter_by(user_id=user_id)
                    .filter(Movie.rating >= 4).all()}
        if not my_liked:
            return []

        # Single bulk query: find all user_ids who also rated >= 4 on any of my liked titles
        similar_uids = {
            m.user_id for m in Movie.query.filter(
                Movie.title.in_(my_liked),
                Movie.user_id != user_id,
                Movie.rating >= 4,
            ).all()
        }

        if not similar_uids:
            return []

        # Single bulk query: get all highly-rated movies from similar users
        candidates = Counter()
        best = {}
        for m in Movie.query.filter(
            Movie.user_id.in_(similar_uids),
            Movie.rating >= 4,
        ).all():
            if m.title.lower() not in my_titles:
                candidates[m.title] += 1
                if m.title not in best:
                    best[m.title] = m

        return [best[t] for t, _ in candidates.most_common(limit)]

    def get_similar_movies(self, movie_id: int, limit: int = 6) -> list[Movie]:
        """Movies that frequently co-appear with this one in users' lists."""
        movie = db.session.get(Movie, movie_id)
        if not movie:
            return []
        user_ids = [m.user_id for m in Movie.query.filter_by(title=movie.title).all()]

        if not user_ids:
            return []

        # Single bulk query: get all movies from those users except the source title
        candidates = Counter()
        best = {}
        for m in Movie.query.filter(
            Movie.user_id.in_(user_ids),
            Movie.title != movie.title,
        ).all():
            candidates[m.title] += 1
            if m.title not in best:
                best[m.title] = m

        return [best[t] for t, _ in candidates.most_common(limit)]
