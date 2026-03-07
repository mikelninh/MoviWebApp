import os
from collections import Counter
from datetime import datetime

import requests

from models import Movie, User, db


class DataManager:
    OMDB_API_KEY = os.environ.get("OMDB_API_KEY", "")

    # ── USERS ────────────────────────────────────────────────────────────────

    def create_user(self, name, password):
        existing = User.query.filter_by(username=name).first()
        if existing:
            return existing, False
        user = User(username=name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user, True

    def get_user_by_username(self, username):
        return User.query.filter_by(username=username).first()

    def get_users(self):
        return User.query.all()

    def delete_user(self, user_id):
        user = db.session.get(User, user_id)
        if not user:
            return False
        Movie.query.filter_by(user_id=user_id).delete()
        db.session.delete(user)
        db.session.commit()
        return True

    # ── MOVIES ───────────────────────────────────────────────────────────────

    def get_movies(self, user_id, sort="title", status=""):
        query = Movie.query.filter_by(user_id=user_id)
        if status in ("watched", "watchlist"):
            query = query.filter(Movie.status == status)
        movies = query.all()
        if sort == "rating":
            movies.sort(key=lambda m: m.rating or 0, reverse=True)
        elif sort == "year":
            movies.sort(key=lambda m: m.year or "", reverse=True)
        else:
            movies.sort(key=lambda m: m.title.lower())
        return movies

    def get_recent_activity(self, limit=10):
        return Movie.query.order_by(Movie.id.desc()).limit(limit).all()

    def fetch_omdb_data(self, title):
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
            pass
        return {}

    def add_movie(self, movie):
        if not movie.date_added:
            movie.date_added = datetime.utcnow()
        db.session.add(movie)
        db.session.commit()
        return movie

    def update_movie(self, movie_id, new_title, new_rating=None, new_status=None):
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

    def toggle_status(self, movie_id):
        movie = db.session.get(Movie, movie_id)
        if not movie:
            return None
        movie.status = "watchlist" if movie.status == "watched" else "watched"
        db.session.commit()
        return movie

    def delete_movie(self, movie_id):
        movie = db.session.get(Movie, movie_id)
        if not movie:
            return False
        db.session.delete(movie)
        db.session.commit()
        return True

    # ── RECOMMENDATIONS ──────────────────────────────────────────────────────

    def get_recommendations(self, user_id, limit=6):
        """Movies liked by users with overlapping taste that this user hasn't added."""
        my_titles  = {m.title.lower() for m in Movie.query.filter_by(user_id=user_id).all()}
        my_liked   = {m.title for m in Movie.query.filter_by(user_id=user_id)
                      .filter(Movie.rating >= 4).all()}
        if not my_liked:
            return []

        similar_uids = set()
        for title in my_liked:
            for m in Movie.query.filter(
                Movie.title == title, Movie.user_id != user_id, Movie.rating >= 4
            ).all():
                similar_uids.add(m.user_id)

        if not similar_uids:
            return []

        candidates = Counter()
        best = {}
        for uid in similar_uids:
            for m in Movie.query.filter(Movie.user_id == uid, Movie.rating >= 4).all():
                if m.title.lower() not in my_titles:
                    candidates[m.title] += 1
                    if m.title not in best:
                        best[m.title] = m

        return [best[t] for t, _ in candidates.most_common(limit)]

    def get_similar_movies(self, movie_id, limit=6):
        """Movies that frequently co-appear with this one in users' lists."""
        movie = db.session.get(Movie, movie_id)
        if not movie:
            return []
        user_ids = [m.user_id for m in Movie.query.filter_by(title=movie.title).all()]

        candidates = Counter()
        best = {}
        for uid in user_ids:
            for m in Movie.query.filter(
                Movie.user_id == uid, Movie.title != movie.title
            ).all():
                candidates[m.title] += 1
                if m.title not in best:
                    best[m.title] = m

        return [best[t] for t, _ in candidates.most_common(limit)]
