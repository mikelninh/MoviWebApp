from models import Movie, User, db


class DataManager:
    # USERS
    def create_user(self, name):
        """Return (user, created) — created is False if the username already existed."""
        existing = User.query.filter_by(username=name).first()
        if existing:
            return existing, False
        user = User(username=name)
        db.session.add(user)
        db.session.commit()
        return user, True

    def get_users(self):
        return User.query.all()

    # MOVIES
    def get_movies(self, user_id):
        return Movie.query.filter_by(user_id=user_id).all()

    def add_movie(self, movie):
        db.session.add(movie)
        db.session.commit()
        return movie

    def update_movie(self, movie_id, new_title):
        movie = db.session.get(Movie, movie_id)
        if not movie:
            return None
        movie.title = new_title
        db.session.commit()
        return movie

    def delete_movie(self, movie_id):
        movie = db.session.get(Movie, movie_id)
        if not movie:
            return False
        db.session.delete(movie)
        db.session.commit()
        return True
