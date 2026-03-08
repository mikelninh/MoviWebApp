import copy
import json
import os
import threading

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


INSPIRATION_LISTS = [
    {
        "name": "Doomed Romance",
        "icon": "♥",
        "tagline": "Love that burns bright and ends in ashes.",
        "movies": [
            {"title": "In the Mood for Love", "year": "2000"},
            {"title": "Eternal Sunshine of the Spotless Mind", "year": "2004"},
            {"title": "Blue Valentine", "year": "2010"},
            {"title": "Atonement", "year": "2007"},
            {"title": "Brief Encounter", "year": "1945"},
            {"title": "Brokeback Mountain", "year": "2005"},
            {"title": "Portrait of a Lady on Fire", "year": "2019"},
            {"title": "Lost in Translation", "year": "2003"},
            {"title": "Normal People", "year": "2020"},
            {"title": "The Remains of the Day", "year": "1993"},
        ],
    },
    {
        "name": "Mind the Gap",
        "icon": "⧗",
        "tagline": "Time travel, fractured memory, and nonlinear minds.",
        "movies": [
            {"title": "Memento", "year": "2000"},
            {"title": "Arrival", "year": "2016"},
            {"title": "The Butterfly Effect", "year": "2004"},
            {"title": "Primer", "year": "2004"},
            {"title": "Coherence", "year": "2013"},
            {"title": "Predestination", "year": "2014"},
            {"title": "Looper", "year": "2012"},
            {"title": "12 Monkeys", "year": "1995"},
            {"title": "Source Code", "year": "2011"},
            {"title": "Timecrimes", "year": "2007"},
        ],
    },
    {
        "name": "Last Night on Earth",
        "icon": "◎",
        "tagline": "Apocalypse, survival, and the end of everything.",
        "movies": [
            {"title": "Melancholia", "year": "2011"},
            {"title": "Take Shelter", "year": "2011"},
            {"title": "Beasts of the Southern Wild", "year": "2012"},
            {"title": "Children of Men", "year": "2006"},
            {"title": "The Road", "year": "2009"},
            {"title": "Annihilation", "year": "2018"},
            {"title": "I Am Legend", "year": "2007"},
            {"title": "28 Days Later", "year": "2002"},
            {"title": "Seeking a Friend for the End of the World", "year": "2012"},
            {"title": "4:44 Last Day on Earth", "year": "2011"},
        ],
    },
    {
        "name": "Ugly Beautiful",
        "icon": "◈",
        "tagline": "Gritty realism, raw humanity, stories that hurt and heal.",
        "movies": [
            {"title": "Requiem for a Dream", "year": "2000"},
            {"title": "Moonlight", "year": "2016"},
            {"title": "City of God", "year": "2002"},
            {"title": "Shoplifters", "year": "2018"},
            {"title": "Parasite", "year": "2019"},
            {"title": "The Florida Project", "year": "2017"},
            {"title": "Beasts of No Nation", "year": "2015"},
            {"title": "The Wrestler", "year": "2008"},
            {"title": "Roma", "year": "2018"},
            {"title": "Tangerines", "year": "2013"},
        ],
    },
    {
        "name": "Men on the Edge",
        "icon": "△",
        "tagline": "Lone male protagonists slowly, magnificently unraveling.",
        "movies": [
            {"title": "Taxi Driver", "year": "1976"},
            {"title": "There Will Be Blood", "year": "2007"},
            {"title": "Whiplash", "year": "2014"},
            {"title": "The Lighthouse", "year": "2019"},
            {"title": "Uncut Gems", "year": "2019"},
            {"title": "Nightcrawler", "year": "2014"},
            {"title": "Falling Down", "year": "1993"},
            {"title": "Black Swan", "year": "2010"},
            {"title": "Pi", "year": "1998"},
            {"title": "A Beautiful Mind", "year": "2001"},
        ],
    },
    {
        "name": "Girls Who Run",
        "icon": "→",
        "tagline": "Female escape, reinvention, and hitting the open road.",
        "movies": [
            {"title": "Thelma & Louise", "year": "1991"},
            {"title": "Wild", "year": "2014"},
            {"title": "Promising Young Woman", "year": "2020"},
            {"title": "Lady Bird", "year": "2017"},
            {"title": "Mustang", "year": "2015"},
            {"title": "Fish Tank", "year": "2009"},
            {"title": "The Favourite", "year": "2018"},
            {"title": "Whale Rider", "year": "2002"},
            {"title": "Persepolis", "year": "2007"},
            {"title": "Mona Lisa Smile", "year": "2003"},
        ],
    },
    {
        "name": "Invisible Wars",
        "icon": "◇",
        "tagline": "Cold war, double agents, and the paranoia of loyalty.",
        "movies": [
            {"title": "Tinker Tailor Soldier Spy", "year": "2011"},
            {"title": "Bridge of Spies", "year": "2015"},
            {"title": "The Lives of Others", "year": "2006"},
            {"title": "Munich", "year": "2005"},
            {"title": "A Most Wanted Man", "year": "2014"},
            {"title": "The Spy Who Came in from the Cold", "year": "1965"},
            {"title": "Three Days of the Condor", "year": "1975"},
            {"title": "Syriana", "year": "2005"},
            {"title": "Zero Dark Thirty", "year": "2012"},
            {"title": "The Conversation", "year": "1974"},
        ],
    },
]


def _fetch_and_cache_posters():
    cache_path = os.path.join(basedir, 'data', 'inspiration_posters.json')
    lists = copy.deepcopy(INSPIRATION_LISTS)
    for lst in lists:
        for movie in lst['movies']:
            try:
                meta = data_manager.fetch_omdb_data(movie['title'])
                movie['poster_url'] = meta.get('poster_url', '')
            except Exception:
                movie['poster_url'] = ''
    try:
        with open(cache_path, 'w') as f:
            json.dump(lists, f)
    except Exception:
        pass


def get_inspiration_with_posters():
    cache_path = os.path.join(basedir, 'data', 'inspiration_posters.json')
    if os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                return json.load(f)
        except Exception:
            pass
    # No cache yet — serve without posters instantly, fetch in background
    threading.Thread(target=_fetch_and_cache_posters, daemon=True).start()
    lists = copy.deepcopy(INSPIRATION_LISTS)
    for lst in lists:
        for movie in lst['movies']:
            movie['poster_url'] = ''
    return lists


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
    inspiration = get_inspiration_with_posters()
    return render_template("index.html", users=users,
                           total_movies=total_movies, activity=activity,
                           inspiration=inspiration)


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
    omdb_fallback = None
    if q:
        raw = (Movie.query
               .filter(Movie.title.ilike(f"%{q}%"))
               .order_by(Movie.title)
               .all())
        # Deduplicate by title — keep best (prefer entry with poster/plot)
        seen, counts = {}, {}
        for m in raw:
            key = m.title.lower()
            counts[key] = counts.get(key, 0) + 1
            if key not in seen or (not seen[key].poster_url and m.poster_url):
                seen[key] = m
        results = sorted(
            [(m, counts[m.title.lower()]) for m in seen.values()],
            key=lambda x: x[0].title.lower()
        )
        if not raw:
            omdb_fallback = data_manager.fetch_omdb_data(q)
    return render_template("search.html", q=q, results=results, omdb_fallback=omdb_fallback)


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
