import os

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)
from sqlalchemy import text

from data_manager import DataManager
from models import Movie, User, db

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'data/movies.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")

db.init_app(app)
data_manager = DataManager()

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "error"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def migrate_db():
    """Add new columns to existing tables without destroying data."""
    with db.engine.connect() as conn:
        existing_movie = {row[1] for row in conn.execute(text("PRAGMA table_info(movie)"))}
        for col, sql in {
            "rating":     "ALTER TABLE movie ADD COLUMN rating INTEGER",
            "year":       "ALTER TABLE movie ADD COLUMN year VARCHAR(10)",
            "director":   "ALTER TABLE movie ADD COLUMN director VARCHAR(120)",
            "plot":       "ALTER TABLE movie ADD COLUMN plot TEXT",
            "poster_url": "ALTER TABLE movie ADD COLUMN poster_url VARCHAR(300)",
            "genre":      "ALTER TABLE movie ADD COLUMN genre VARCHAR(200)",
            "status":     "ALTER TABLE movie ADD COLUMN status VARCHAR(20) DEFAULT 'watched'",
            "date_added": "ALTER TABLE movie ADD COLUMN date_added DATETIME",
        }.items():
            if col not in existing_movie:
                conn.execute(text(sql))

        existing_user = {row[1] for row in conn.execute(text("PRAGMA table_info(user)"))}
        if "password_hash" not in existing_user:
            conn.execute(text("ALTER TABLE user ADD COLUMN password_hash VARCHAR(256)"))

        conn.commit()


# ── AUTH ──────────────────────────────────────────────────────────────────────

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        if not name or not password:
            flash("Username and password are required.", "error")
            return render_template("register.html")
        if len(name) > 80:
            flash("Username too long (max 80 characters).", "error")
            return render_template("register.html")
        user, created = data_manager.create_user(name, password)
        if not created:
            flash("Username already taken.", "error")
            return render_template("register.html")
        login_user(user)
        flash(f"Welcome, {user.username}!", "success")
        return redirect(url_for("get_movies", user_id=user.id))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        user = data_manager.get_user_by_username(name)
        if not user or not user.check_password(password):
            flash("Invalid username or password.", "error")
            return render_template("login.html")
        login_user(user)
        flash(f"Welcome back, {user.username}!", "success")
        next_page = request.args.get("next")
        return redirect(next_page or url_for("get_movies", user_id=user.id))
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "success")
    return redirect(url_for("index"))


# ── MAIN ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    users = data_manager.get_users()
    total_movies = Movie.query.count()
    activity = data_manager.get_recent_activity(limit=8)
    return render_template("index.html", users=users,
                           total_movies=total_movies, activity=activity)


@app.route("/users/<int:user_id>")
def get_movies(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("index"))
    sort          = request.args.get("sort", "title")
    status_filter = request.args.get("status", "")
    movies        = data_manager.get_movies(user_id, sort=sort, status=status_filter)
    all_count       = Movie.query.filter_by(user_id=user_id).count()
    watched_count   = Movie.query.filter(Movie.user_id == user_id,
                                         Movie.status == "watched").count()
    watchlist_count = Movie.query.filter(Movie.user_id == user_id,
                                         Movie.status == "watchlist").count()
    recommendations = []
    if current_user.is_authenticated and current_user.id == user_id:
        recommendations = data_manager.get_recommendations(user_id)
    return render_template(
        "user_detail.html",
        user=user, favorites=movies, sort=sort, status_filter=status_filter,
        all_count=all_count, watched_count=watched_count,
        watchlist_count=watchlist_count, recommendations=recommendations,
    )


@app.route("/movies/<int:movie_id>")
def movie_detail(movie_id):
    movie = db.session.get(Movie, movie_id)
    if not movie:
        flash("Movie not found.", "error")
        return redirect(url_for("index"))
    all_instances    = Movie.query.filter_by(title=movie.title).all()
    users_with_movie = [(db.session.get(User, m.user_id), m) for m in all_instances]
    similar          = data_manager.get_similar_movies(movie_id)
    return render_template("movie_detail.html", movie=movie,
                           users_with_movie=users_with_movie, similar=similar)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        results = (Movie.query
                   .filter(Movie.title.ilike(f"%{q}%"))
                   .order_by(Movie.title)
                   .all())
    return render_template("search.html", q=q, results=results)


@app.route("/users/<int:user_id>/add_movie", methods=["POST"])
@login_required
def add_movie(user_id):
    if current_user.id != user_id:
        flash("You can only add movies to your own list.", "error")
        return redirect(url_for("get_movies", user_id=user_id))
    title  = request.form.get("title", "").strip()
    rating = request.form.get("rating", type=int)
    status = request.form.get("status", "watched")
    if not title:
        flash("Movie title cannot be empty.", "error")
        return redirect(url_for("get_movies", user_id=user_id))
    if len(title) > 120:
        flash("Title too long (max 120 characters).", "error")
        return redirect(url_for("get_movies", user_id=user_id))
    meta = data_manager.fetch_omdb_data(title)
    movie = Movie(
        title=title, user_id=user_id, rating=rating,
        status=status if status in ("watched", "watchlist") else "watched",
        year=meta.get("year"), director=meta.get("director"),
        plot=meta.get("plot"), poster_url=meta.get("poster_url"),
        genre=meta.get("genre"),
    )
    data_manager.add_movie(movie)
    flash(f"'{title}' added.", "success")
    return redirect(url_for("get_movies", user_id=user_id))


@app.route("/users/<int:user_id>/movies/<int:movie_id>/toggle", methods=["POST"])
@login_required
def toggle_status(user_id, movie_id):
    if current_user.id != user_id:
        flash("Not allowed.", "error")
        return redirect(url_for("get_movies", user_id=user_id))
    data_manager.toggle_status(movie_id)
    return redirect(request.referrer or url_for("get_movies", user_id=user_id))


@app.route("/users/<int:user_id>/movies/<int:movie_id>/edit", methods=["GET", "POST"])
@login_required
def edit_movie(user_id, movie_id):
    if current_user.id != user_id:
        flash("You can only edit your own movies.", "error")
        return redirect(url_for("get_movies", user_id=user_id))
    movie = db.session.get(Movie, movie_id)
    if not movie or movie.user_id != user_id:
        flash("Movie not found.", "error")
        return redirect(url_for("get_movies", user_id=user_id))
    if request.method == "POST":
        title  = request.form.get("title", "").strip()
        rating = request.form.get("rating", type=int)
        status = request.form.get("status", "watched")
        if not title:
            flash("Title cannot be empty.", "error")
            return render_template("edit_movie.html", movie=movie, user_id=user_id)
        data_manager.update_movie(movie.id, title, rating, status)
        flash(f"'{title}' updated.", "success")
        return redirect(url_for("get_movies", user_id=user_id))
    return render_template("edit_movie.html", movie=movie, user_id=user_id)


@app.route("/users/<int:user_id>/movies/<int:movie_id>/delete", methods=["POST"])
@login_required
def delete_movie(user_id, movie_id):
    if current_user.id != user_id:
        flash("You can only delete your own movies.", "error")
        return redirect(url_for("get_movies", user_id=user_id))
    data_manager.delete_movie(movie_id)
    flash("Movie removed.", "success")
    return redirect(url_for("get_movies", user_id=user_id))


@app.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
def delete_user(user_id):
    if current_user.id != user_id:
        flash("You can only delete your own account.", "error")
        return redirect(url_for("index"))
    logout_user()
    data_manager.delete_user(user_id)
    flash("Your account has been deleted.", "success")
    return redirect(url_for("index"))


# ── STARTUP ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(os.path.join(basedir, "data")):
        os.makedirs(os.path.join(basedir, "data"))
    with app.app_context():
        db.create_all()
        migrate_db()
    app.run(debug=True)
