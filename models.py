from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)

    # one-to-many: one user, many movies
    movies = db.relationship("Movie", backref="user", lazy=True)


class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    year = db.Column(db.Integer, nullable=True)

    # foreign key to User.id
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
