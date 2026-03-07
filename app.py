import os

from flask import Flask, flash, redirect, render_template, request, url_for

from data_manager import DataManager
from models import Movie, User, db

app = Flask(__name__)

# --- SQLAlchemy configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'data/movies.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")

db.init_app(app)
data_manager = DataManager()


# --- routes ---

@app.route("/")
def index():
    """Home page showing list of users."""
    users = data_manager.get_users()
    return render_template("index.html", users=users)


@app.route("/users", methods=["POST"])
def create_user():
    """Handle form submission to add a new user."""
    name = request.form.get("name", "").strip()
    if not name:
        flash("Name cannot be empty.", "error")
        return redirect(url_for("index"))
    if len(name) > 80:
        flash("Name is too long (max 80 characters).", "error")
        return redirect(url_for("index"))
    user, created = data_manager.create_user(name)
    if created:
        flash(f"User '{user.username}' created.", "success")
    else:
        flash(f"User '{user.username}' already exists.", "error")
    return redirect(url_for("index"))


@app.route("/users/<int:user_id>")
def get_movies(user_id):
    """Show a single user's favorite movies."""
    user = db.session.get(User, user_id)
    if user is None:
        return render_template("404.html"), 404
    movies = data_manager.get_movies(user_id)
    return render_template("user_detail.html", user=user, favorites=movies)


@app.route("/users/<int:user_id>/add_movie", methods=["POST"])
def add_movie(user_id):
    """Add a movie for the given user."""
    title = request.form.get("title", "").strip()
    if not title:
        flash("Movie title cannot be empty.", "error")
        return redirect(url_for("get_movies", user_id=user_id))
    if len(title) > 120:
        flash("Title is too long (max 120 characters).", "error")
        return redirect(url_for("get_movies", user_id=user_id))
    movie = Movie(title=title, user_id=user_id)
    data_manager.add_movie(movie)
    flash(f"'{title}' added to your list.", "success")
    return redirect(url_for("get_movies", user_id=user_id))


# --- create DB and run app ---

if __name__ == "__main__":
    if not os.path.exists(os.path.join(basedir, "data")):
        os.makedirs(os.path.join(basedir, "data"))
    with app.app_context():
        db.create_all()
    app.run(debug=True)
