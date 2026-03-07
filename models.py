from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=True)
    year = db.Column(db.String(10), nullable=True)
    director = db.Column(db.String(120), nullable=True)
    plot = db.Column(db.Text, nullable=True)
    poster_url = db.Column(db.String(300), nullable=True)
    genre = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), default='watched')   # 'watched' | 'watchlist'
    date_added = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    user = db.relationship("User", backref="movies")
