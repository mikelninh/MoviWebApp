from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


class Follow(db.Model):
    follower_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    follower    = db.relationship("User", foreign_keys=[follower_id], backref="following")
    followed    = db.relationship("User", foreign_keys=[followed_id], backref="followers")


class ReviewLike(db.Model):
    user_id   = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey("review.id"), primary_key=True)


class UserList(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name       = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user       = db.relationship("User", backref="lists")
    items      = db.relationship("UserListItem", backref="user_list",
                                 cascade="all, delete-orphan", lazy=True)


class UserListItem(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    list_id     = db.Column(db.Integer, db.ForeignKey("user_list.id"), nullable=False)
    movie_title = db.Column(db.String(120), nullable=False)
    poster_url  = db.Column(db.String(300), nullable=True)
    added_at    = db.Column(db.DateTime, default=datetime.utcnow)


class MovieNight(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    creator_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name        = db.Column(db.String(120), nullable=False)
    date        = db.Column(db.String(20), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    creator     = db.relationship("User", backref="movie_nights")
    films       = db.relationship("MovieNightFilm", backref="night",
                                  cascade="all, delete-orphan", lazy=True)


class MovieNightFilm(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    night_id     = db.Column(db.Integer, db.ForeignKey("movie_night.id"), nullable=False)
    movie_title  = db.Column(db.String(120), nullable=False)
    poster_url   = db.Column(db.String(300), nullable=True)
    suggested_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    suggester    = db.relationship("User", backref="suggestions")
    votes        = db.relationship("MovieNightVote", backref="film",
                                   cascade="all, delete-orphan", lazy=True)


class MovieNightVote(db.Model):
    user_id  = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    film_id  = db.Column(db.Integer, db.ForeignKey("movie_night_film.id"), primary_key=True)


class Review(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    movie_title = db.Column(db.String(120), nullable=False)
    body        = db.Column(db.Text, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    user        = db.relationship("User", backref="reviews")
    likes       = db.relationship("ReviewLike", backref="review",
                                  cascade="all, delete-orphan", lazy=True)


class Movie(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(120), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rating     = db.Column(db.Integer, nullable=True)
    year       = db.Column(db.String(10), nullable=True)
    director   = db.Column(db.String(120), nullable=True)
    plot       = db.Column(db.Text, nullable=True)
    poster_url = db.Column(db.String(300), nullable=True)
    genre      = db.Column(db.String(200), nullable=True)
    status     = db.Column(db.String(20), default='watched')
    date_added = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    user       = db.relationship("User", backref="movies")
