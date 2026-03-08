import copy
import json
import os
import threading
from collections import Counter

from dotenv import load_dotenv
load_dotenv()

import anthropic as _anthropic_sdk

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)
from sqlalchemy import text

# ── AI HELPERS ────────────────────────────────────────────────────────────────
_ai_cache  = {}
_ai_client = None


def _get_ai_client():
    global _ai_client
    if _ai_client is None:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if key:
            _ai_client = _anthropic_sdk.Anthropic(api_key=key)
    return _ai_client


def ai_review_synthesis(film_title, reviews):
    """1-2 sentence community consensus, or None."""
    client = _get_ai_client()
    if not client or len(reviews) < 2:
        return None
    cache_key = ("synth", film_title, len(reviews))
    if cache_key in _ai_cache:
        return _ai_cache[cache_key]
    try:
        texts = "\n".join(f"- {r.body}" for r in reviews[:15])
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=100,
            messages=[{"role": "user", "content":
                f"Summarize what people think of '{film_title}' in 1-2 sentences based on:\n{texts}\nBe specific, no preamble."}])
        result = msg.content[0].text.strip()
        _ai_cache[cache_key] = result
        return result
    except Exception:
        return None


def ai_why_love(user_movies, film):
    """1-sentence personalised reason, or None."""
    client = _get_ai_client()
    if not client or not user_movies:
        return None
    cache_key = ("why", film.id, len(user_movies))
    if cache_key in _ai_cache:
        return _ai_cache[cache_key]
    try:
        top = sorted([m for m in user_movies if m.rating and m.rating >= 4],
                     key=lambda m: m.rating, reverse=True)[:8]
        if not top:
            return None
        favs = ", ".join(m.title for m in top)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=80,
            messages=[{"role": "user", "content":
                f"Someone loves: {favs}. One sentence starting with 'You'll love this because' explaining why they'd enjoy '{film.title}' ({film.genre or ''}). No preamble."}])
        result = msg.content[0].text.strip()
        _ai_cache[cache_key] = result
        return result
    except Exception:
        return None


def ai_taste_report(user_movies):
    """2-sentence taste profile, or None."""
    client = _get_ai_client()
    watched = [m for m in user_movies if m.status == "watched"]
    if not client or len(watched) < 5:
        return None
    cache_key = ("taste", len(watched), sum(m.id for m in watched[-20:]))
    if cache_key in _ai_cache:
        return _ai_cache[cache_key]
    try:
        top = sorted([m for m in watched if m.rating],
                     key=lambda m: m.rating, reverse=True)[:10]
        titles = ", ".join(m.title for m in (top or watched[:10]))
        gc = Counter(g for m in watched if m.genre for g in m.genre.split(", "))
        genres = ", ".join(g for g, _ in gc.most_common(3))
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=120,
            messages=[{"role": "user", "content":
                f"Write a 2-sentence film taste profile for someone who loves: {titles}. Top genres: {genres}. Make it feel personal and insightful. No preamble."}])
        result = msg.content[0].text.strip()
        _ai_cache[cache_key] = result
        return result
    except Exception:
        return None


def ai_year_summary(total, top_genres, top_directors, avg_rating, year):
    """2-sentence year-in-film summary, or None."""
    client = _get_ai_client()
    if not client or total < 3:
        return None
    cache_key = ("year", total, year, str(top_genres[:2]))
    if cache_key in _ai_cache:
        return _ai_cache[cache_key]
    try:
        genres = ", ".join(g for g, _ in top_genres[:3]) if top_genres else "various"
        dirs   = ", ".join(d for d, _ in top_directors[:2]) if top_directors else "various directors"
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=100,
            messages=[{"role": "user", "content":
                f"Write 2 sentences describing someone's {year} in film: {total} films watched, top genres: {genres}, favourite directors: {dirs}, avg rating: {avg_rating or 'N/A'}/5. Make it feel celebratory and personal. No preamble."}])
        result = msg.content[0].text.strip()
        _ai_cache[cache_key] = result
        return result
    except Exception:
        return None

from data_manager import DataManager
from models import (Film, Follow, Movie, MovieNight, MovieNightFilm, MovieNightVote,
                    Notification, Review, ReviewLike, User, UserList, UserListItem, db)

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

        existing_movie = {row[1] for row in conn.execute(text("PRAGMA table_info(movie)"))}
        if "film_id" not in existing_movie:
            conn.execute(text("ALTER TABLE movie ADD COLUMN film_id INTEGER REFERENCES film(id)"))

        conn.commit()


def populate_films():
    """Backfill Film records from existing Movie data and link movie.film_id."""
    from sqlalchemy import func
    rows = (db.session.query(Movie.title, Movie.year, Movie.director,
                              Movie.plot, Movie.poster_url, Movie.genre)
            .filter(Movie.status == 'watched')
            .group_by(Movie.title)
            .all())
    changed = 0
    for row in rows:
        film = Film.query.filter_by(title=row.title).first()
        if not film:
            film = Film(title=row.title, year=row.year, director=row.director,
                        plot=row.plot, poster_url=row.poster_url, genre=row.genre)
            db.session.add(film)
            db.session.flush()
            changed += 1
        # Link any unlinked Movie rows
        Movie.query.filter_by(title=row.title, film_id=None)\
                   .update({'film_id': film.id}, synchronize_session=False)
    if changed:
        db.session.commit()


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
        "name": "Ghibli Forever",
        "icon": "✦",
        "tagline": "Studio Ghibli — where every frame is a painting.",
        "movies": [
            {"title": "Spirited Away", "year": "2001"},
            {"title": "Princess Mononoke", "year": "1997"},
            {"title": "My Neighbor Totoro", "year": "1988"},
            {"title": "Howl's Moving Castle", "year": "2004"},
            {"title": "Grave of the Fireflies", "year": "1988"},
            {"title": "Nausicaa of the Valley of the Wind", "year": "1984"},
            {"title": "Kiki's Delivery Service", "year": "1989"},
            {"title": "The Tale of Princess Kaguya", "year": "2013"},
            {"title": "Castle in the Sky", "year": "1986"},
            {"title": "Porco Rosso", "year": "1992"},
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
        "name": "Anime That Breaks You",
        "icon": "◉",
        "tagline": "Mind-bending, heartbreaking, unforgettable.",
        "movies": [
            {"title": "Perfect Blue", "year": "1997"},
            {"title": "Akira", "year": "1988"},
            {"title": "Ghost in the Shell", "year": "1995"},
            {"title": "Paprika", "year": "2006"},
            {"title": "Your Name", "year": "2016"},
            {"title": "A Silent Voice", "year": "2016"},
            {"title": "The Girl Who Leapt Through Time", "year": "2006"},
            {"title": "Millennium Actress", "year": "2001"},
            {"title": "5 Centimeters per Second", "year": "2007"},
            {"title": "Wolf Children", "year": "2012"},
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


# ── TEMPLATE HELPERS & CONTEXT ────────────────────────────────────────────────

@app.context_processor
def inject_globals():
    unread = 0
    if current_user.is_authenticated:
        unread = Notification.query.filter_by(
            user_id=current_user.id, read=False).count()
    return {"unread_notifications": unread}


def get_or_create_film(title, meta=None):
    film = Film.query.filter_by(title=title).first()
    if not film:
        if meta is None:
            meta = data_manager.fetch_omdb_data(title)
        film = Film(title=title, year=meta.get("year"),
                    director=meta.get("director"), plot=meta.get("plot"),
                    poster_url=meta.get("poster_url"), genre=meta.get("genre"))
        db.session.add(film)
        db.session.flush()
    return film


def create_notification(user_id, from_user_id, ntype, message, link=None):
    if user_id == from_user_id:
        return
    db.session.add(Notification(user_id=user_id, from_user_id=from_user_id,
                                type=ntype, message=message, link=link))


@app.template_global()
def avatar_url(username):
    """DiceBear avataaars — unique cartoon portrait per username."""
    return (
        f"https://api.dicebear.com/9.x/avataaars/svg"
        f"?seed={username}"
        f"&backgroundColor=b6e3f4,c0aede,d1d4f9,ffd5dc,ffdfbf,d1fae5"
        f"&backgroundType=gradientLinear"
    )


# ── HELPERS ───────────────────────────────────────────────────────────────────

def compute_taste_match(movies_a, movies_b):
    if not movies_a or not movies_b:
        return 0
    a = {m.title.lower(): m.rating for m in movies_a}
    b = {m.title.lower(): m.rating for m in movies_b}
    common = set(a) & set(b)
    if not common:
        return 0
    jaccard = len(common) / len(set(a) | set(b))
    common_rated = [(a[t], b[t]) for t in common if a.get(t) and b.get(t)]
    if common_rated:
        avg_diff = sum(abs(ra - rb) for ra, rb in common_rated) / len(common_rated)
        score = (jaccard * 0.5 + (1 - avg_diff / 4) * 0.5) * 100
    else:
        score = jaccard * 100
    return round(min(score, 99))


def compute_profile_stats(movies):
    from collections import Counter
    watched = [m for m in movies if m.status == 'watched']
    rated   = [m for m in movies if m.rating]
    avg_rating = round(sum(m.rating for m in rated) / len(rated), 1) if rated else None
    gc = Counter()
    for m in movies:
        if m.genre:
            for g in m.genre.split(', '):
                gc[g] += 1
    dc = Counter(m.director for m in movies if m.director)
    return {
        "watched":      len(watched),
        "avg_rating":   avg_rating,
        "top_genres":   gc.most_common(3),
        "top_director": dc.most_common(1)[0][0] if dc else None,
    }


def compute_challenges(movies, review_count=0):
    from collections import Counter
    watched = [m for m in movies if m.status == 'watched']
    rated   = [m for m in movies if m.rating]
    gc = Counter()
    for m in movies:
        if m.genre:
            for g in m.genre.split(', '):
                gc[g] += 1
    decades = {m.year[:3] for m in rated if m.year and len(m.year) >= 3}
    return [
        {"name": "First Steps",    "icon": "◎", "desc": "Watch your first movie",        "progress": min(len(watched), 1),               "target": 1},
        {"name": "Getting Serious","icon": "◎", "desc": "Watch 10 movies",                "progress": min(len(watched), 10),              "target": 10},
        {"name": "Film Buff",      "icon": "◎", "desc": "Watch 25 movies",                "progress": min(len(watched), 25),              "target": 25},
        {"name": "Cinephile",      "icon": "◉", "desc": "Watch 50 movies",                "progress": min(len(watched), 50),              "target": 50},
        {"name": "Harsh Critic",   "icon": "★", "desc": "Rate 10 movies",                 "progress": min(len(rated), 10),                "target": 10},
        {"name": "Genre Hopper",   "icon": "◈", "desc": "Watch films in 5 different genres","progress": min(len(gc), 5),                  "target": 5},
        {"name": "Anime Pilgrim",  "icon": "✦", "desc": "Watch 5 animated films",          "progress": min(gc.get("Animation", 0), 5),    "target": 5},
        {"name": "Time Traveller", "icon": "⧗", "desc": "Rate films from 3 different decades","progress": min(len(decades), 3),           "target": 3},
        {"name": "Critic",         "icon": "✍", "desc": "Write your first review",         "progress": min(review_count, 1),              "target": 1},
        {"name": "Voice",          "icon": "✍", "desc": "Write 5 reviews",                 "progress": min(review_count, 5),              "target": 5},
    ]


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
        flash(f"Welcome to MoviWebApp, {user.username}! Follow some members to fill your feed.", "success")
        return redirect(url_for("feed"))
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
    # Pick a hero film: 5-star, has poster, watched — rotate by day
    import datetime
    hero_pool = (Movie.query
                 .filter(Movie.rating == 5, Movie.poster_url.isnot(None),
                         Movie.status == 'watched')
                 .all())
    hero = hero_pool[datetime.date.today().toordinal() % len(hero_pool)] if hero_pool else None
    return render_template("index.html", users=users,
                           total_movies=total_movies, activity=activity,
                           inspiration=inspiration, hero=hero)


_PROFILE_PER_PAGE = 24


@app.route("/u/<username>")
def user_profile(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("index"))
    user_id       = user.id
    sort          = request.args.get("sort", "title")
    status_filter = request.args.get("status", "")
    page          = request.args.get("page", 1, type=int)
    all_sorted    = data_manager.get_movies(user_id, sort=sort, status=status_filter)
    total         = len(all_sorted)
    total_pages   = max(1, (total + _PROFILE_PER_PAGE - 1) // _PROFILE_PER_PAGE)
    page          = max(1, min(page, total_pages))
    movies        = all_sorted[(page - 1) * _PROFILE_PER_PAGE : page * _PROFILE_PER_PAGE]
    all_count       = Movie.query.filter_by(user_id=user_id).count()
    watched_count   = Movie.query.filter(Movie.user_id == user_id,
                                         Movie.status == "watched").count()
    watchlist_count = Movie.query.filter(Movie.user_id == user_id,
                                         Movie.status == "watchlist").count()
    recommendations = []
    if current_user.is_authenticated and current_user.id == user_id:
        recommendations = data_manager.get_recommendations(user_id)
    all_movies    = Movie.query.filter_by(user_id=user_id).all()
    profile_stats = compute_profile_stats(all_movies)
    taste_match   = 0
    is_following  = False
    if current_user.is_authenticated and current_user.id != user_id:
        taste_match  = compute_taste_match(
            Movie.query.filter_by(user_id=current_user.id).all(), all_movies)
        is_following = Follow.query.filter_by(
            follower_id=current_user.id, followed_id=user_id).first() is not None
    user_lists  = UserList.query.filter_by(user_id=user_id).all()
    taste_blurb = ai_taste_report(all_movies)
    from datetime import date
    current_year = date.today().year
    return render_template(
        "user_detail.html",
        user=user, favorites=movies, sort=sort, status_filter=status_filter,
        all_count=all_count, watched_count=watched_count,
        watchlist_count=watchlist_count, recommendations=recommendations,
        profile_stats=profile_stats, taste_match=taste_match,
        is_following=is_following, user_lists=user_lists,
        followers_count=len(user.followers),
        following_count=len(user.following),
        page=page, total_pages=total_pages,
        taste_blurb=taste_blurb, current_year=current_year,
    )


@app.route("/users/<int:user_id>")
def get_movies(user_id):
    """Legacy numeric URL — redirect to canonical pretty URL."""
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("index"))
    args = request.args.to_dict()
    return redirect(url_for("user_profile", username=user.username, **args), 301)


@app.route("/movies/<int:movie_id>")
def movie_detail(movie_id):
    """Legacy route — redirect to global film page if possible."""
    movie = db.session.get(Movie, movie_id)
    if not movie:
        flash("Movie not found.", "error")
        return redirect(url_for("index"))
    film = Film.query.filter_by(title=movie.title).first()
    if film:
        return redirect(url_for("film_detail", film_id=film.id), 301)
    # Fallback: render inline if Film record doesn't exist yet
    all_instances    = Movie.query.filter_by(title=movie.title).all()
    users_with_movie = [(db.session.get(User, m.user_id), m) for m in all_instances]
    similar          = data_manager.get_similar_movies(movie_id)
    reviews          = Review.query.filter_by(movie_title=movie.title)\
                              .order_by(Review.created_at.desc()).all()
    user_review      = None
    if current_user.is_authenticated:
        user_review = Review.query.filter_by(
            movie_title=movie.title, user_id=current_user.id).first()
    return render_template("movie_detail.html", movie=movie,
                           users_with_movie=users_with_movie, similar=similar,
                           reviews=reviews, user_review=user_review)


@app.route("/film/<int:film_id>")
def film_detail(film_id):
    film = db.session.get(Film, film_id)
    if not film:
        flash("Film not found.", "error")
        return redirect(url_for("index"))
    all_instances    = Movie.query.filter_by(title=film.title).all()
    users_with_movie = [(db.session.get(User, m.user_id), m) for m in all_instances]
    # similar: films shared by users who also have this film
    shared_user_ids = [m.user_id for m in all_instances]
    similar_films = []
    if shared_user_ids:
        from sqlalchemy import func
        similar_titles = (
            db.session.query(Movie.title, func.count(Movie.id).label("c"))
            .filter(Movie.user_id.in_(shared_user_ids),
                    Movie.title != film.title,
                    Movie.status == "watched")
            .group_by(Movie.title)
            .order_by(func.count(Movie.id).desc())
            .limit(12).all()
        )
        for row in similar_titles:
            f = Film.query.filter_by(title=row.title).first()
            if f and f.poster_url:
                similar_films.append(f)
            if len(similar_films) >= 8:
                break
    reviews   = Review.query.filter_by(movie_title=film.title)\
                            .order_by(Review.created_at.desc()).all()
    user_review = None
    friends_with_movie = []
    ai_synthesis = None
    ai_why       = None
    if current_user.is_authenticated:
        user_review = Review.query.filter_by(
            movie_title=film.title, user_id=current_user.id).first()
        followed_ids = {f.followed_id for f in
                        Follow.query.filter_by(follower_id=current_user.id).all()}
        friends_with_movie = [(u, m) for u, m in users_with_movie
                              if u.id in followed_ids]
        user_movies = Movie.query.filter_by(user_id=current_user.id).all()
        ai_why = ai_why_love(user_movies, film)
    ai_synthesis = ai_review_synthesis(film.title, reviews)
    return render_template("film_detail.html", film=film,
                           users_with_movie=users_with_movie,
                           friends_with_movie=friends_with_movie,
                           similar=similar_films,
                           reviews=reviews, user_review=user_review,
                           ai_synthesis=ai_synthesis, ai_why=ai_why)


@app.route("/search")
def search():
    from sqlalchemy import func
    q            = request.args.get("q", "").strip()
    year_filter  = request.args.get("year", "").strip()
    genre_filter = request.args.get("genre", "").strip()
    page         = request.args.get("page", 1, type=int)
    results    = []
    omdb_film  = None
    pagination = None
    if q:
        fq = Film.query.filter(Film.title.ilike(f"%{q}%"))
        if year_filter:
            fq = fq.filter(Film.year.like(f"{year_filter}%"))
        if genre_filter:
            fq = fq.filter(Film.genre.ilike(f"%{genre_filter}%"))
        film_pag = fq.order_by(Film.title).paginate(page=page, per_page=20, error_out=False)
        if film_pag.items:
            pagination = film_pag
            film_ids = [f.id for f in film_pag.items]
            counts = dict(
                db.session.query(Movie.film_id, func.count(Movie.id))
                .filter(Movie.film_id.in_(film_ids), Movie.status == "watched")
                .group_by(Movie.film_id).all()
            )
            results = [(f, counts.get(f.id, 0)) for f in film_pag.items]
        else:
            meta = data_manager.fetch_omdb_data(q)
            if meta and meta.get("poster_url"):
                film = get_or_create_film(q, meta)
                db.session.commit()
                return redirect(url_for("film_detail", film_id=film.id))
            omdb_film = meta
    return render_template("search.html", q=q, results=results,
                           year_filter=year_filter, genre_filter=genre_filter,
                           omdb_film=omdb_film, pagination=pagination)


# ── YEAR IN REVIEW ─────────────────────────────────────────────────────────────

@app.route("/u/<username>/year/<int:year>")
def year_in_review(username, year):
    from datetime import date
    user = User.query.filter_by(username=username).first()
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("index"))
    movies = (Movie.query
              .filter_by(user_id=user.id, status="watched")
              .filter(db.func.strftime("%Y", Movie.date_added) == str(year))
              .order_by(Movie.date_added)
              .all())
    if not movies:
        flash(f"No watched movies logged in {year}.", "error")
        return redirect(url_for("user_profile", username=username))
    total = len(movies)
    hours = total * 2
    gc = Counter(g for m in movies if m.genre for g in m.genre.split(", "))
    dc = Counter(m.director for m in movies if m.director)
    top_genres    = gc.most_common(5)
    top_directors = dc.most_common(3)
    rated    = [m for m in movies if m.rating]
    avg_rating = round(sum(m.rating for m in rated) / len(rated), 1) if rated else None
    rating_dist = {i: sum(1 for m in rated if m.rating == i) for i in range(1, 6)}
    contrarian = None
    biggest_diff = 0
    for m in rated:
        others = [om.rating for om in Movie.query.filter(
            Movie.title == m.title, Movie.user_id != user.id,
            Movie.rating.isnot(None)).all()]
        if len(others) >= 2:
            comm_avg = sum(others) / len(others)
            diff = abs(m.rating - comm_avg)
            if diff > biggest_diff:
                biggest_diff, contrarian = diff, (m, round(comm_avg, 1))
    if total >= 100:
        badge = ("Film Addict", "🎬")
    elif total >= 50:
        badge = ("Cinema Devotee", "🍿")
    elif total >= 20:
        badge = ("Movie Buff", "⭐")
    else:
        badge = ("Film Explorer", "🔭")
    ai_summary = ai_year_summary(total, top_genres, top_directors, avg_rating, year)
    return render_template("year_in_review.html",
        user=user, year=year, total=total, hours=hours,
        top_genres=top_genres, top_directors=top_directors,
        avg_rating=avg_rating, rating_dist=rating_dist,
        contrarian=contrarian, first_film=movies[0], last_film=movies[-1],
        badge=badge, rated_count=len(rated), ai_summary=ai_summary,
        prev_year=year - 1, next_year=year + 1,
        current_year=date.today().year)


@app.route("/film/<int:film_id>/review", methods=["POST"])
@login_required
def add_film_review(film_id):
    film = db.session.get(Film, film_id)
    if not film:
        return redirect(url_for("index"))
    body = request.form.get("body", "").strip()
    if not body:
        flash("Review cannot be empty.", "error")
        return redirect(url_for("film_detail", film_id=film_id))
    if len(body) > 1000:
        flash("Review too long (max 1000 characters).", "error")
        return redirect(url_for("film_detail", film_id=film_id))
    existing = Review.query.filter_by(
        movie_title=film.title, user_id=current_user.id).first()
    if existing:
        existing.body = body
        flash("Review updated.", "success")
    else:
        db.session.add(Review(user_id=current_user.id,
                              movie_title=film.title, body=body))
        flash("Review posted.", "success")
    db.session.commit()
    return redirect(url_for("film_detail", film_id=film_id))


# ── NOTIFICATIONS ─────────────────────────────────────────────────────────────

@app.route("/notifications")
@login_required
def notifications():
    notifs = (Notification.query
              .filter_by(user_id=current_user.id)
              .order_by(Notification.created_at.desc())
              .limit(50).all())
    # Mark all read
    Notification.query.filter_by(user_id=current_user.id, read=False)\
                      .update({"read": True})
    db.session.commit()
    return render_template("notifications.html", notifs=notifs)


# ── DISCOVERY ─────────────────────────────────────────────────────────────────

@app.route("/trending")
def trending():
    from datetime import datetime as dt, timedelta
    from sqlalchemy import func
    cutoff = dt.utcnow() - timedelta(days=14)
    rows = (db.session.query(Movie.title, func.count(Movie.id).label("c"))
            .filter(Movie.date_added >= cutoff, Movie.status == "watched")
            .group_by(Movie.title)
            .order_by(func.count(Movie.id).desc())
            .limit(30).all())
    films = []
    for row in rows:
        f = Film.query.filter_by(title=row.title).first()
        if f:
            films.append((f, row.c))
    return render_template("trending.html", films=films)


@app.route("/browse")
def browse():
    from collections import Counter
    gc = Counter()
    for m in Movie.query.filter(Movie.genre.isnot(None)).all():
        for g in m.genre.split(", "):
            gc[g.strip()] += 1
    genres = [(g, c) for g, c in gc.most_common() if c >= 2]
    return render_template("browse.html", genres=genres)


@app.route("/browse/<genre>")
def genre_page(genre):
    from sqlalchemy import func
    _PER = 24
    page = request.args.get("page", 1, type=int)
    rows = (db.session.query(Movie.title, func.count(Movie.id).label("c"))
            .filter(Movie.genre.ilike(f"%{genre}%"), Movie.status == "watched")
            .group_by(Movie.title)
            .order_by(func.count(Movie.id).desc())
            .all())
    all_films = []
    for row in rows:
        f = Film.query.filter_by(title=row.title).first()
        if f:
            all_films.append((f, row.c))
    total_pages = max(1, (len(all_films) + _PER - 1) // _PER)
    page = max(1, min(page, total_pages))
    films = all_films[(page - 1) * _PER : page * _PER]
    return render_template("genre_page.html", genre=genre, films=films,
                           page=page, total_pages=total_pages, total=len(all_films))


# ── LISTS DIRECTORY ───────────────────────────────────────────────────────────

@app.route("/lists")
def lists_directory():
    lists = (UserList.query
             .order_by(UserList.created_at.desc())
             .all())
    lists_with_counts = sorted(
        [(lst, len(lst.items)) for lst in lists],
        key=lambda x: x[1], reverse=True
    )
    return render_template("lists_directory.html", lists=lists_with_counts)


@app.route("/movies/<int:movie_id>/review", methods=["POST"])
@login_required
def add_review(movie_id):
    movie = db.session.get(Movie, movie_id)
    if not movie:
        flash("Movie not found.", "error")
        return redirect(url_for("index"))
    body = request.form.get("body", "").strip()
    if not body:
        flash("Review cannot be empty.", "error")
        return redirect(url_for("movie_detail", movie_id=movie_id))
    if len(body) > 1000:
        flash("Review too long (max 1000 characters).", "error")
        return redirect(url_for("movie_detail", movie_id=movie_id))
    existing = Review.query.filter_by(
        movie_title=movie.title, user_id=current_user.id).first()
    if existing:
        existing.body = body
        flash("Review updated.", "success")
    else:
        db.session.add(Review(user_id=current_user.id,
                              movie_title=movie.title, body=body))
        flash("Review posted.", "success")
    db.session.commit()
    return redirect(url_for("movie_detail", movie_id=movie_id))


# ── SOCIAL: FOLLOW / LIKE ────────────────────────────────────────────────────

@app.route("/users/<int:user_id>/follow", methods=["POST"])
@login_required
def follow_user(user_id):
    if current_user.id == user_id:
        flash("You can't follow yourself.", "error")
        return redirect(url_for("user_profile", username=current_user.username))
    existing = Follow.query.filter_by(
        follower_id=current_user.id, followed_id=user_id).first()
    target = db.session.get(User, user_id)
    if existing:
        db.session.delete(existing)
        if not request.headers.get("HX-Request"):
            flash(f"Unfollowed {target.username}.", "success")
    else:
        db.session.add(Follow(follower_id=current_user.id, followed_id=user_id))
        create_notification(user_id, current_user.id, "follow",
                            f"{current_user.username} started following you.",
                            link=f"/u/{current_user.username}")
        if not request.headers.get("HX-Request"):
            flash(f"You're now following {target.username}! Their activity will appear in your feed.", "success")
    db.session.commit()
    if request.headers.get("HX-Request"):
        is_following = Follow.query.filter_by(
            follower_id=current_user.id, followed_id=user_id).first() is not None
        return render_template("_follow_btn.html", target_user_id=user_id,
                               target_username=target.username, is_following=is_following)
    return redirect(url_for("user_profile", username=target.username))


@app.route("/reviews/<int:review_id>/like", methods=["POST"])
@login_required
def like_review(review_id):
    review = db.session.get(Review, review_id)
    if not review:
        if request.headers.get("HX-Request"):
            return "", 204
        flash("Review not found.", "error")
        return redirect(request.referrer or url_for("index"))
    existing = ReviewLike.query.filter_by(
        user_id=current_user.id, review_id=review_id).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(ReviewLike(user_id=current_user.id, review_id=review_id))
        if review.user_id != current_user.id:
            film = Film.query.filter_by(title=review.movie_title).first()
            link = f"/film/{film.id}" if film else None
            create_notification(review.user_id, current_user.id, "like",
                                f"{current_user.username} liked your review of \"{review.movie_title}\".",
                                link=link)
    db.session.commit()
    if request.headers.get("HX-Request"):
        liked      = ReviewLike.query.filter_by(user_id=current_user.id, review_id=review_id).first() is not None
        like_count = ReviewLike.query.filter_by(review_id=review_id).count()
        return render_template("_like_btn.html", review=review, liked=liked, like_count=like_count)
    return redirect(request.referrer or url_for("index"))


@app.route("/feed")
@login_required
def feed():
    followed_ids = [f.followed_id for f in current_user.following]
    movies, reviews = [], []
    if followed_ids:
        movies = (Movie.query
                  .filter(Movie.user_id.in_(followed_ids))
                  .order_by(Movie.date_added.desc())
                  .limit(30).all())
        reviews = (Review.query
                   .filter(Review.user_id.in_(followed_ids))
                   .order_by(Review.created_at.desc())
                   .limit(20).all())
    # Suggest users to follow when feed is sparse or empty
    suggested = []
    if len(movies) < 5:
        exclude = set(followed_ids) | {current_user.id}
        candidates = User.query.filter(User.id.notin_(exclude)).all()
        # Sort by movie count descending, take top 8
        candidates.sort(key=lambda u: len(u.movies), reverse=True)
        suggested = candidates[:8]
    return render_template("feed.html", movies=movies, reviews=reviews,
                           following_count=len(followed_ids), suggested=suggested)


# ── MOVIE NIGHTS ─────────────────────────────────────────────────────────────

@app.route("/movie-nights")
def movie_nights():
    nights = MovieNight.query.order_by(MovieNight.created_at.desc()).all()
    return render_template("movie_nights.html", nights=nights)


@app.route("/movie-nights/create", methods=["POST"])
@login_required
def create_movie_night():
    name = request.form.get("name", "").strip()
    date = request.form.get("date", "").strip()
    desc = request.form.get("description", "").strip()
    if not name:
        flash("Movie night needs a name.", "error")
        return redirect(url_for("movie_nights"))
    night = MovieNight(creator_id=current_user.id, name=name,
                       date=date or None, description=desc or None)
    db.session.add(night)
    db.session.commit()
    flash(f"'{name}' created!", "success")
    return redirect(url_for("movie_night_detail", night_id=night.id))


@app.route("/movie-nights/<int:night_id>")
def movie_night_detail(night_id):
    night = db.session.get(MovieNight, night_id)
    if not night:
        flash("Movie night not found.", "error")
        return redirect(url_for("movie_nights"))
    user_vote = None
    if current_user.is_authenticated:
        user_vote = MovieNightVote.query.filter_by(
            user_id=current_user.id).first()
    sorted_films = sorted(night.films, key=lambda f: len(f.votes), reverse=True)
    return render_template("movie_night_detail.html", night=night,
                           sorted_films=sorted_films, user_vote=user_vote)


@app.route("/movie-nights/<int:night_id>/suggest", methods=["POST"])
@login_required
def suggest_film(night_id):
    night = db.session.get(MovieNight, night_id)
    if not night:
        flash("Movie night not found.", "error")
        return redirect(url_for("movie_nights"))
    title = request.form.get("title", "").strip()
    if not title:
        flash("Film title required.", "error")
        return redirect(url_for("movie_night_detail", night_id=night_id))
    meta = data_manager.fetch_omdb_data(title)
    film = MovieNightFilm(night_id=night_id, movie_title=title,
                          poster_url=meta.get("poster_url"),
                          suggested_by=current_user.id)
    db.session.add(film)
    db.session.commit()
    flash(f"'{title}' suggested!", "success")
    return redirect(url_for("movie_night_detail", night_id=night_id))


@app.route("/movie-nights/<int:night_id>/vote/<int:film_id>", methods=["POST"])
@login_required
def vote_film(night_id, film_id):
    film = db.session.get(MovieNightFilm, film_id)
    if not film or film.night_id != night_id:
        flash("Film not found.", "error")
        return redirect(url_for("movie_night_detail", night_id=night_id))
    existing = MovieNightVote.query.filter_by(
        user_id=current_user.id, film_id=film_id).first()
    if existing:
        db.session.delete(existing)
    else:
        # Remove old vote for this night first (one vote per night)
        old_votes = (MovieNightVote.query
                     .join(MovieNightFilm)
                     .filter(MovieNightFilm.night_id == night_id,
                             MovieNightVote.user_id == current_user.id)
                     .all())
        for v in old_votes:
            db.session.delete(v)
        db.session.add(MovieNightVote(user_id=current_user.id, film_id=film_id))
    db.session.commit()
    return redirect(url_for("movie_night_detail", night_id=night_id))


# ── CUSTOM LISTS ─────────────────────────────────────────────────────────────

@app.route("/users/<int:user_id>/lists/create", methods=["POST"])
@login_required
def create_list(user_id):
    if current_user.id != user_id:
        flash("Not allowed.", "error")
        return redirect(url_for("get_movies", user_id=user_id))
    name = request.form.get("name", "").strip()
    if not name:
        flash("List needs a name.", "error")
        return redirect(url_for("get_movies", user_id=user_id))
    lst = UserList(user_id=user_id, name=name)
    db.session.add(lst)
    db.session.commit()
    flash(f"List '{name}' created.", "success")
    return redirect(url_for("view_list", list_id=lst.id))


@app.route("/lists/<int:list_id>")
def view_list(list_id):
    lst = db.session.get(UserList, list_id)
    if not lst:
        flash("List not found.", "error")
        return redirect(url_for("index"))
    return render_template("user_list.html", lst=lst)


@app.route("/lists/<int:list_id>/add", methods=["POST"])
@login_required
def add_to_list(list_id):
    lst = db.session.get(UserList, list_id)
    if not lst or lst.user_id != current_user.id:
        flash("Not allowed.", "error")
        return redirect(url_for("index"))
    title = request.form.get("title", "").strip()
    if not title:
        flash("Title required.", "error")
        return redirect(url_for("view_list", list_id=list_id))
    meta = data_manager.fetch_omdb_data(title)
    db.session.add(UserListItem(list_id=list_id, movie_title=title,
                                poster_url=meta.get("poster_url")))
    db.session.commit()
    flash(f"'{title}' added to list.", "success")
    return redirect(url_for("view_list", list_id=list_id))


@app.route("/lists/<int:list_id>/remove/<int:item_id>", methods=["POST"])
@login_required
def remove_from_list(list_id, item_id):
    lst = db.session.get(UserList, list_id)
    if not lst or lst.user_id != current_user.id:
        flash("Not allowed.", "error")
        return redirect(url_for("index"))
    item = db.session.get(UserListItem, item_id)
    if item and item.list_id == list_id:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for("view_list", list_id=list_id))


# ── DIARY ─────────────────────────────────────────────────────────────────────

@app.route("/users/<int:user_id>/diary")
def diary(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("index"))
    movies = (Movie.query
              .filter_by(user_id=user_id, status="watched")
              .order_by(Movie.date_added.desc())
              .all())
    # Group by month
    from collections import defaultdict
    grouped = defaultdict(list)
    for m in movies:
        if m.date_added:
            key = m.date_added.strftime("%B %Y")
        else:
            key = "Earlier"
        grouped[key].append(m)
    return render_template("diary.html", user=user, grouped=dict(grouped))


# ── CHALLENGES ────────────────────────────────────────────────────────────────

@app.route("/challenges")
@login_required
def challenges():
    movies = Movie.query.filter_by(user_id=current_user.id).all()
    review_count = Review.query.filter_by(user_id=current_user.id).count()
    all_challenges = compute_challenges(movies, review_count)
    return render_template("challenges.html", challenges=all_challenges)


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
    film = get_or_create_film(title, meta)
    movie = Movie(
        title=title, user_id=user_id, film_id=film.id, rating=rating,
        status=status if status in ("watched", "watchlist") else "watched",
        year=meta.get("year"), director=meta.get("director"),
        plot=meta.get("plot"), poster_url=meta.get("poster_url"),
        genre=meta.get("genre"),
    )
    data_manager.add_movie(movie)
    flash(f"'{title}' added.", "success")
    return redirect(request.referrer or url_for("get_movies", user_id=user_id))


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


# ── ERROR HANDLERS ───────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404,
                           title="Scene Missing",
                           message="We looked everywhere. This page got cut from the final edit.",
                           quote="\"I don't know what you're talking about. There's no scene here.\"",
                           quote_attr="— Every director ever"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500,
                           title="The Projector Broke",
                           message="Something went wrong in the booth. We're rewinding the reel.",
                           quote="\"All right, Mr. DeMille, I'm ready for my close-up.\"",
                           quote_attr="— Norma Desmond, Sunset Blvd."), 500


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403,
                           title="Restricted Section",
                           message="You don't have a ticket for this screening.",
                           quote="\"You shall not pass.\"",
                           quote_attr="— Gandalf (wrong franchise, still applies)"), 403


# ── STARTUP ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(os.path.join(basedir, "data")):
        os.makedirs(os.path.join(basedir, "data"))
    with app.app_context():
        db.create_all()
        migrate_db()
        populate_films()
    app.run(debug=True)
