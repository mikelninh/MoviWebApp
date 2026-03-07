from flask import Flask, request, redirect, url_for, render_template
from data_manager import DataManager
from models import db, Movie, User
import os

app = Flask(__name__)

# --- SQLAlchemy configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'data/movies.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

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
    name = request.form.get("name")
    if name:
        data_manager.create_user(name)
    return redirect(url_for("index"))


@app.route("/users/<int:user_id>")
def get_movies(user_id):
    """Show a single user's favorite movies."""
    user = User.query.get_or_404(user_id)
    movies = data_manager.get_movies(user_id)
    return render_template("user_detail.html", user=user, favorites=movies)


@app.route("/add", methods=["POST"])
def add_movie():
    """Add a movie for a given user (for now, user_id=1)."""
    title = request.form.get("title")
    # In a more complete version you would take user_id from the form or URL.
    user_id = 1

    movie = Movie(
        title=title,
        user_id=user_id,
    )

    data_manager.add_movie(movie)
    return redirect(url_for("index"))


# --- create DB and run app ---

if __name__ == "__main__":
    # IMPORTANT: if you changed models, delete data/movies.db once, then recreate
    if not os.path.exists(os.path.join(basedir, "data")):
        os.makedirs(os.path.join(basedir, "data"))
    with app.app_context():
        db.create_all()
    app.run(debug=True)
