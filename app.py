import copy
import csv
import io
import json
import os
import re
import secrets
import threading
import urllib.request as _urllib_req
import xml.etree.ElementTree as ET
import zipfile
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
from models import (Cinema, CinemaFilm, Film, FilmStreaming, Follow, Movie,
                    MovieNight, MovieNightFilm, MovieNightVote,
                    Notification, Review, ReviewComment, ReviewLike,
                    User, UserList, UserListItem, db)

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(basedir, 'data/movies.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")

# ── FLASK-MAIL ─────────────────────────────────────────────────────────────────
app.config["MAIL_SERVER"]   = os.environ.get("MAIL_SERVER", "")
app.config["MAIL_PORT"]     = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"]  = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME", "noreply@moviwebapp.com")

from flask_mail import Mail, Message as MailMessage
mail = Mail(app)

def send_notification_email(to_email, subject, body):
    """Send an email asynchronously, silently skip if mail not configured."""
    if not app.config.get("MAIL_SERVER"):
        return
    def _send():
        with app.app_context():
            try:
                msg = MailMessage(subject, recipients=[to_email], body=body)
                mail.send(msg)
            except Exception:
                pass
    threading.Thread(target=_send, daemon=True).start()

# ── FLASK-LIMITER ──────────────────────────────────────────────────────────────
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
limiter = Limiter(get_remote_address, app=app, default_limits=[])

db.init_app(app)
data_manager = DataManager()

# ── TRANSLATIONS (i18n) ────────────────────────────────────────────────────────
TRANSLATIONS = {
    "de": {
        "Home": "Startseite",
        "Trending": "Trending",
        "Browse": "Entdecken",
        "Nights": "Filmabende",
        "My List": "Meine Liste",
        "Feed": "Feed",
        "Challenges": "Herausforderungen",
        "Login": "Anmelden",
        "Register": "Registrieren",
        "Logout": "Abmelden",
        "Import": "Importieren",
        "Settings": "Einstellungen",
        "Cinemas": "Kinos",
        "About": "Über uns",
        "Privacy": "Datenschutz",
        "Watched": "Gesehen",
        "Watchlist": "Merkliste",
        "Watching": "Schaue ich",
        "All": "Alle",
        "Add": "Hinzufügen",
        "Edit": "Bearbeiten",
        "Delete": "Löschen",
        "Post review": "Rezension posten",
        "Update review": "Rezension aktualisieren",
        "Your Feed": "Dein Feed",
        "Reviews": "Rezensionen",
        "Recently Added": "Zuletzt hinzugefügt",
        "Recent Reviews": "Aktuelle Rezensionen",
        "No recent movies.": "Keine aktuellen Filme.",
        "No recent reviews.": "Keine aktuellen Rezensionen.",
        "Filter…": "Filtern…",
        "Search movies…": "Filme suchen…",
        "Movie title": "Filmtitel",
        "Rating": "Bewertung",
        "Status": "Status",
        "People to follow — find your people": "Personen folgen — finde deine Community",
        "You might also enjoy": "Das könnte dir auch gefallen",
        "Diary": "Tagebuch",
        "Recap": "Rückblick",
    }
}

from flask import session as flask_session

def _t(key):
    lang = flask_session.get("lang", "en")
    if lang == "en":
        return key
    return TRANSLATIONS.get(lang, {}).get(key, key)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "error"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Register _t as Jinja2 global
app.jinja_env.globals["_"] = _t


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
        if "email" not in existing_user:
            conn.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(120)"))
        if "email_notifications" not in existing_user:
            conn.execute(text("ALTER TABLE user ADD COLUMN email_notifications BOOLEAN DEFAULT 0"))

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
    with app.app_context():
        for lst in lists:
            for movie in lst['movies']:
                try:
                    meta = data_manager.fetch_omdb_data(movie['title'])
                    movie['poster_url'] = meta.get('poster_url', '')
                except Exception:
                    movie['poster_url'] = ''
                film = Film.query.filter(
                    db.func.lower(Film.title) == movie['title'].lower()
                ).first()
                movie['film_id'] = film.id if film else None
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
                lists = json.load(f)
            # Enrich missing film_ids and poster_urls from the live DB
            with app.app_context():
                for lst in lists:
                    for movie in lst['movies']:
                        if not movie.get('film_id') or not movie.get('poster_url'):
                            film = Film.query.filter(
                                db.func.lower(Film.title) == movie['title'].lower()
                            ).first()
                            if film:
                                movie['film_id'] = film.id
                                if not movie.get('poster_url') and film.poster_url:
                                    movie['poster_url'] = film.poster_url
            return lists
        except Exception:
            pass
    # No cache yet — serve without posters instantly, fetch in background
    threading.Thread(target=_fetch_and_cache_posters, daemon=True).start()
    lists = copy.deepcopy(INSPIRATION_LISTS)
    for lst in lists:
        for movie in lst['movies']:
            movie['poster_url'] = ''
            film = Film.query.filter(
                db.func.lower(Film.title) == movie['title'].lower()
            ).first()
            movie['film_id'] = film.id if film else None
    return lists


# ── FILM NEWS (RSS) ───────────────────────────────────────────────────────────

_news_cache = {"data": [], "fetched_at": None}
_NEWS_SOURCES = [
    ("The Guardian",   "https://www.theguardian.com/film/rss"),
    ("Variety",        "https://variety.com/feed/"),
    ("The Film Stage", "https://thefilmstage.com/feed/"),
]


def fetch_film_news(limit=18):
    import datetime
    now = datetime.datetime.utcnow()
    cached    = _news_cache.get("data")
    fetched_at = _news_cache.get("fetched_at")
    # Cache for 30 minutes
    if cached and fetched_at and (now - fetched_at).seconds < 1800:
        return cached
    articles = []
    ns = {
        "dc":      "http://purl.org/dc/elements/1.1/",
        "media":   "http://search.yahoo.com/mrss/",
        "content": "http://purl.org/rss/1.0/modules/content/",
    }
    for source_name, url in _NEWS_SOURCES:
        try:
            req = _urllib_req.Request(
                url, headers={"User-Agent": "MoviWebApp/1.0 film-news-reader"}
            )
            with _urllib_req.urlopen(req, timeout=6) as resp:
                raw = resp.read()
            root = ET.fromstring(raw)
            for item in root.findall(".//item")[:6]:
                title    = (item.findtext("title")       or "").strip()
                link     = (item.findtext("link")        or "").strip()
                desc_raw = (item.findtext("description") or "").strip()
                desc     = re.sub(r"<[^>]+>", "", desc_raw)[:200].strip()
                pub      = (item.findtext("pubDate")     or "").strip()[:16]
                img = None
                MEDIA = "http://search.yahoo.com/mrss/"
                # 1. Pick largest media:content by width
                best_w, best_url = 0, None
                for mc in item.findall(f"{{{MEDIA}}}content"):
                    try:
                        w = int(mc.get("width") or 0)
                    except ValueError:
                        w = 0
                    url_mc = mc.get("url") or ""
                    if url_mc and w > best_w:
                        best_w, best_url = w, url_mc
                if best_url:
                    img = best_url
                # 2. media:thumbnail
                if not img:
                    mt = item.find(f"{{{MEDIA}}}thumbnail")
                    if mt is not None:
                        img = mt.get("url")
                # 3. enclosure
                if not img:
                    enc = item.find("enclosure")
                    if enc is not None and "image" in (enc.get("type") or ""):
                        img = enc.get("url")
                # 4. first <img src="..."> in content:encoded or description
                if not img:
                    CE_NS = "http://purl.org/rss/1.0/modules/content/"
                    for raw_html in (
                        item.findtext(f"{{{CE_NS}}}encoded") or "",
                        item.findtext("description") or "",
                    ):
                        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw_html)
                        if m:
                            img = m.group(1)
                            break
                if title and link:
                    articles.append({
                        "source": source_name,
                        "title":  title,
                        "link":   link,
                        "desc":   desc,
                        "pub":    pub,
                        "img":    img,
                    })
        except Exception:
            pass
    articles = articles[:limit]
    _news_cache["data"]       = articles
    _news_cache["fetched_at"] = now
    return articles


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


# ── ONBOARDING ────────────────────────────────────────────────────────────────

@app.route("/welcome")
@login_required
def welcome():
    return render_template("welcome.html")


@app.route("/welcome/search")
@login_required
def welcome_search():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return ""
    films = (Film.query
             .filter(Film.title.ilike(f"%{q}%"), Film.poster_url.isnot(None))
             .order_by(Film.year.desc())
             .limit(12).all())
    return render_template("_welcome_results.html", films=films)


@app.route("/welcome/pick", methods=["POST"])
@login_required
def welcome_pick():
    film_ids = request.form.getlist("film_ids")
    if not film_ids:
        flash("Pick at least one film to continue.", "info")
        return redirect(url_for("welcome"))
    added = 0
    for fid in film_ids[:8]:
        film = db.session.get(Film, int(fid))
        if not film:
            continue
        exists = Movie.query.filter_by(user_id=current_user.id, film_id=film.id).first()
        if not exists:
            db.session.add(Movie(
                title=film.title, user_id=current_user.id, film_id=film.id,
                rating=5, status="watched",
                year=film.year, director=film.director,
                plot=film.plot, poster_url=film.poster_url, genre=film.genre,
            ))
            added += 1
    db.session.commit()
    return redirect(url_for("welcome_follow"))


@app.route("/welcome/follow")
@login_required
def welcome_follow():
    my_movies = Movie.query.filter_by(user_id=current_user.id).all()
    already_following = {f.followed_id for f in Follow.query.filter_by(follower_id=current_user.id).all()}
    candidates = User.query.filter(User.id != current_user.id, User.id.notin_(already_following)).all()
    scored = []
    for u in candidates:
        their_movies = Movie.query.filter_by(user_id=u.id).all()
        score = compute_taste_match(my_movies, their_movies)
        if score > 0:
            scored.append((u, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    suggestions = scored[:8]
    return render_template("welcome_follow.html", suggestions=suggestions)


@app.route("/welcome/done", methods=["POST"])
@login_required
def welcome_done():
    follow_ids = request.form.getlist("follow_ids")
    for uid in follow_ids:
        uid = int(uid)
        exists = Follow.query.filter_by(follower_id=current_user.id, followed_id=uid).first()
        if not exists:
            db.session.add(Follow(follower_id=current_user.id, followed_id=uid))
            notif = Notification(
                user_id=uid, from_user_id=current_user.id,
                type="follow",
                message=f"{current_user.username} started following you.",
                link=url_for("user_profile", username=current_user.username),
            )
            db.session.add(notif)
    db.session.commit()
    flash(f"Welcome to MoviWebApp, {current_user.username}! 🎬", "success")
    return redirect(url_for("feed"))


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
        return redirect(url_for("welcome"))
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


# ── STATIC PAGES ──────────────────────────────────────────────────────────────

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/news")
def news():
    articles = fetch_film_news(limit=18)
    return render_template("news.html", articles=articles)


@app.route("/export")
@login_required
def export_data():
    from flask import make_response
    movies = Movie.query.filter_by(user_id=current_user.id).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Title", "Year", "Rating", "Status", "Director", "Genre", "Date Added"])
    for m in movies:
        writer.writerow([
            m.title,
            m.year or "",
            m.rating or "",
            m.status or "watched",
            m.director or "",
            m.genre or "",
            m.date_added.strftime("%Y-%m-%d") if m.date_added else "",
        ])
    resp = make_response(out.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = f"attachment; filename={current_user.username}-moviwebapp.csv"
    return resp


# ── MAIN ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    total_movies = Movie.query.count()
    activity = data_manager.get_recent_activity(limit=8)
    inspiration = get_inspiration_with_posters()
    # Hero carousel: top 6 films by community rating, with poster
    from sqlalchemy import func as sqlfunc
    hero_films = (
        db.session.query(Film, sqlfunc.avg(Movie.rating).label('avg_rating'),
                         sqlfunc.count(Movie.id).label('count'))
        .join(Movie, Movie.film_id == Film.id)
        .filter(Film.poster_url.isnot(None), Movie.rating.isnot(None))
        .group_by(Film.id)
        .having(sqlfunc.count(Movie.id) >= 2)
        .order_by(sqlfunc.avg(Movie.rating).desc())
        .limit(6)
        .all()
    )
    hero_slides = [{"film": f, "avg_rating": round(avg, 1)} for f, avg, _ in hero_films]
    # Recent reviews enriched with film data
    raw_reviews = (Review.query
                   .order_by(Review.created_at.desc())
                   .limit(12)
                   .all())
    recent_reviews = []
    for rev in raw_reviews:
        film = Film.query.filter_by(title=rev.movie_title).first()
        # Find rating from the reviewer's movie entry
        movie_entry = Movie.query.filter_by(user_id=rev.user_id, title=rev.movie_title).first()
        recent_reviews.append({
            'review': rev,
            'film': film,
            'rating': movie_entry.rating if movie_entry else None,
        })
    return render_template("index.html",
                           total_movies=total_movies, activity=activity,
                           inspiration=inspiration, hero_slides=hero_slides,
                           recent_reviews=recent_reviews)


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
    watching_count  = Movie.query.filter(Movie.user_id == user_id,
                                         Movie.status == "watching").count()
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
        watchlist_count=watchlist_count, watching_count=watching_count,
        recommendations=recommendations,
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
    streaming = get_streaming(film)
    return render_template("film_detail.html", film=film,
                           users_with_movie=users_with_movie,
                           friends_with_movie=friends_with_movie,
                           similar=similar_films,
                           reviews=reviews, user_review=user_review,
                           ai_synthesis=ai_synthesis, ai_why=ai_why,
                           streaming=streaming)


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
        if target.email and target.email_notifications:
            send_notification_email(
                target.email,
                f"{current_user.username} started following you on MoviWebApp",
                f"Hi {target.username},\n\n{current_user.username} started following you on MoviWebApp.\n\nVisit their profile: https://moviwebapp.com/u/{current_user.username}\n"
            )
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
            review_owner = db.session.get(User, review.user_id)
            if review_owner and review_owner.email and review_owner.email_notifications:
                send_notification_email(
                    review_owner.email,
                    f"{current_user.username} liked your review on MoviWebApp",
                    f"Hi {review_owner.username},\n\n{current_user.username} liked your review of \"{review.movie_title}\".\n"
                )
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
    review_titles = [r.movie_title for r in reviews]
    film_map = {}
    if review_titles:
        for f in Film.query.filter(Film.title.in_(review_titles)).all():
            film_map[f.title] = f.id
    return render_template("feed.html", movies=movies, reviews=reviews,
                           film_map=film_map,
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
                       date=date or None, description=desc or None,
                       invite_token=secrets.token_hex(16))
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


@app.route("/movie-nights/<int:night_id>/film/<int:film_id>/delete", methods=["POST"])
@login_required
def delete_suggestion(night_id, film_id):
    film = db.session.get(MovieNightFilm, film_id)
    if not film or film.night_id != night_id:
        flash("Film not found.", "error")
        return redirect(url_for("movie_night_detail", night_id=night_id))
    night = db.session.get(MovieNight, night_id)
    if film.suggested_by != current_user.id and night.creator_id != current_user.id:
        flash("You can only remove your own suggestions.", "error")
        return redirect(url_for("movie_night_detail", night_id=night_id))
    db.session.delete(film)
    db.session.commit()
    flash("Suggestion removed.", "info")
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
    if request.headers.get("HX-Request"):
        user_voted = MovieNightVote.query.filter_by(
            user_id=current_user.id, film_id=film_id).first() is not None
        vote_count = MovieNightVote.query.filter_by(film_id=film_id).count()
        return render_template("_vote_btn.html", film=film,
                               user_voted=user_voted, vote_count=vote_count,
                               night_id=night_id)
    return redirect(url_for("movie_night_detail", night_id=night_id))


@app.route("/nights/join/<token>")
def join_night(token):
    night = MovieNight.query.filter_by(invite_token=token).first()
    if not night:
        flash("Invalid invite link.", "error")
        return redirect(url_for("movie_nights"))
    flash(f"You've been invited to '{night.name}'! Suggest a film or vote below.", "info")
    return redirect(url_for("movie_night_detail", night_id=night.id))


@app.route("/movie-nights/<int:night_id>/declare-winner/<int:film_id>", methods=["POST"])
@login_required
def declare_winner(night_id, film_id):
    night = db.session.get(MovieNight, night_id)
    if not night or night.creator_id != current_user.id:
        flash("Only the creator can declare a winner.", "error")
        return redirect(url_for("movie_night_detail", night_id=night_id))
    film = db.session.get(MovieNightFilm, film_id)
    if not film or film.night_id != night_id:
        flash("Film not found.", "error")
        return redirect(url_for("movie_night_detail", night_id=night_id))
    night.winner_film_id = film_id
    db.session.commit()
    flash(f"🏆 '{film.movie_title}' declared the winner!", "success")
    return redirect(url_for("movie_night_detail", night_id=night_id))


@app.route("/movie-nights/<int:night_id>/clear-winner", methods=["POST"])
@login_required
def clear_winner(night_id):
    night = db.session.get(MovieNight, night_id)
    if not night or night.creator_id != current_user.id:
        flash("Only the creator can change the winner.", "error")
        return redirect(url_for("movie_night_detail", night_id=night_id))
    night.winner_film_id = None
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

@app.route("/diary/<int:user_id>")
def diary(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("index"))
    movies = (Movie.query
              .filter_by(user_id=user_id, status="watched")
              .order_by(Movie.date_added.desc())
              .all())
    from collections import defaultdict
    grouped = defaultdict(list)
    for m in movies:
        key = m.date_added.strftime("%B %Y") if m.date_added else "Earlier"
        grouped[key].append(m)

    # Stats
    total = len(movies)
    rated = [m for m in movies if m.rating]
    avg_rating = round(sum(m.rating for m in rated) / len(rated), 1) if rated else None
    # Top genre
    from collections import Counter
    genre_counts = Counter()
    for m in movies:
        if m.genre:
            for g in m.genre.split(', '):
                genre_counts[g] += 1
    top_genre = genre_counts.most_common(1)[0][0] if genre_counts else None
    # This year's count
    import datetime
    this_year = datetime.date.today().year
    this_year_count = sum(1 for m in movies if m.date_added and m.date_added.year == this_year)

    return render_template("diary.html", user=user, grouped=dict(grouped),
                           total=total, avg_rating=avg_rating, top_genre=top_genre,
                           this_year=this_year, this_year_count=this_year_count)


# ── CHALLENGES ────────────────────────────────────────────────────────────────

@app.route("/challenges")
@login_required
def challenges():
    movies = Movie.query.filter_by(user_id=current_user.id).all()
    review_count = Review.query.filter_by(user_id=current_user.id).count()
    all_challenges = compute_challenges(movies, review_count)
    return render_template("challenges.html", challenges=all_challenges)


@app.route("/import", methods=["GET", "POST"])
@login_required
def import_letterboxd():
    if request.method == "GET":
        return render_template("import.html")

    file = request.files.get("file")
    if not file or not file.filename:
        flash("Please select a file.", "error")
        return render_template("import.html")

    filename = file.filename.lower()
    watched_rows, watchlist_rows, ratings_map = [], [], {}

    def parse_rating(raw):
        try:
            return max(1, min(5, int(float(raw) + 0.5)))
        except (ValueError, TypeError):
            return None

    try:
        if filename.endswith(".zip"):
            with zipfile.ZipFile(file) as z:
                names = z.namelist()
                if "watched.csv" in names:
                    with z.open("watched.csv") as f:
                        watched_rows = list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8")))
                if "ratings.csv" in names:
                    with z.open("ratings.csv") as f:
                        for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8")):
                            key = (row["Name"].strip(), row.get("Year", "").strip())
                            r = parse_rating(row.get("Rating"))
                            if r:
                                ratings_map[key] = r
                if "watchlist.csv" in names:
                    with z.open("watchlist.csv") as f:
                        watchlist_rows = list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8")))
        elif filename.endswith(".csv"):
            content = file.read().decode("utf-8")
            rows = list(csv.DictReader(io.StringIO(content)))
            if rows and "Rating" in (rows[0] if rows else {}):
                for row in rows:
                    key = (row["Name"].strip(), row.get("Year", "").strip())
                    r = parse_rating(row.get("Rating"))
                    if r:
                        ratings_map[key] = r
            else:
                watched_rows = rows
        else:
            flash("Please upload the .zip file from Letterboxd.", "error")
            return render_template("import.html")
    except Exception as e:
        flash(f"Could not read file: {e}", "error")
        return render_template("import.html")

    # Build set of already-owned titles for deduplication
    existing = {
        (m.title.lower(), m.year or "")
        for m in Movie.query.filter_by(user_id=current_user.id).all()
    }

    # Build Film lookup cache
    film_cache = {f.title.lower(): f for f in Film.query.all()}

    def get_or_create_film_fast(title, year):
        key = title.lower()
        if key in film_cache:
            return film_cache[key]
        film = Film(title=title, year=year)
        db.session.add(film)
        db.session.flush()
        film_cache[key] = film
        return film

    watched_imported = skipped_watched = 0
    watchlist_imported = skipped_watchlist = 0

    for row in watched_rows:
        title = row.get("Name", "").strip()
        year  = row.get("Year", "").strip()
        if not title:
            continue
        if (title.lower(), year) in existing:
            skipped_watched += 1
            continue
        rating = ratings_map.get((title, year))
        film   = get_or_create_film_fast(title, year)
        db.session.add(Movie(
            title=title, user_id=current_user.id, film_id=film.id,
            rating=rating, status="watched", year=year,
        ))
        existing.add((title.lower(), year))
        watched_imported += 1

    for row in watchlist_rows:
        title = row.get("Name", "").strip()
        year  = row.get("Year", "").strip()
        if not title:
            continue
        if (title.lower(), year) in existing:
            skipped_watchlist += 1
            continue
        film = get_or_create_film_fast(title, year)
        db.session.add(Movie(
            title=title, user_id=current_user.id, film_id=film.id,
            rating=None, status="watchlist", year=year,
        ))
        existing.add((title.lower(), year))
        watchlist_imported += 1

    db.session.commit()

    # Sync metadata from Film records that already existed before import
    orphans = (db.session.query(Movie)
               .join(Film, Movie.film_id == Film.id)
               .filter(Movie.user_id == current_user.id,
                       Movie.poster_url.is_(None),
                       Film.poster_url.isnot(None))
               .all())
    for m in orphans:
        film = db.session.get(Film, m.film_id)
        m.poster_url = film.poster_url
        m.plot       = film.plot or m.plot
        m.director   = film.director or m.director
        m.genre      = film.genre or m.genre
        if not m.year:
            m.year   = film.year
    db.session.commit()

    parts = []
    if watched_imported:   parts.append(f"{watched_imported} watched")
    if watchlist_imported: parts.append(f"{watchlist_imported} watchlist")
    skipped = skipped_watched + skipped_watchlist
    if skipped:            parts.append(f"{skipped} already in your list")
    flash("Import complete! " + " · ".join(parts) + ".", "success")
    return redirect(url_for("user_profile", username=current_user.username))


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
        status=status if status in ("watched", "watchlist", "watching") else "watched",
        year=meta.get("year"), director=meta.get("director"),
        plot=meta.get("plot"), poster_url=meta.get("poster_url"),
        genre=meta.get("genre"),
    )
    data_manager.add_movie(movie)
    if meta:
        flash(f"'{title}' added.", "success")
    else:
        flash(f"'{title}' added — no metadata found. Double-check the title for a richer entry.", "info")
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


# ── STREAMING (JustWatch) ─────────────────────────────────────────────────────

import urllib.request as _urllib_req

_JUSTWATCH_GQL = """
query GetStreamingOffers($title: String!, $country: Country!) {
  titleSearch(input: {searchQuery: $title, country: $country, first: 1}) {
    edges {
      node {
        ... on Movie {
          offers(country: $country, platform: WEB) {
            monetizationType
            package { clearName shortName }
            standardWebURL
          }
        }
      }
    }
  }
}
"""


def get_streaming(film):
    """Return list of {service, url, type} dicts, using 7-day cache."""
    from datetime import timedelta
    try:
        cache = FilmStreaming.query.filter_by(film_id=film.id).first()
        now = datetime.utcnow()
        if cache and (now - cache.fetched_at) < timedelta(days=7):
            return json.loads(cache.data_json or "[]")
        # Query JustWatch GraphQL
        payload = json.dumps({
            "query": _JUSTWATCH_GQL,
            "variables": {"title": film.title, "country": "DE"},
        }).encode("utf-8")
        req = _urllib_req.Request(
            "https://apis.justwatch.com/graphql",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "MoviWebApp/1.0"},
        )
        with _urllib_req.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        offers = []
        edges = (data.get("data", {})
                     .get("titleSearch", {})
                     .get("edges", []))
        seen = set()
        for edge in edges:
            node = edge.get("node", {})
            for offer in node.get("offers", []):
                pkg  = offer.get("package", {})
                name = pkg.get("clearName", "")
                url  = offer.get("standardWebURL", "")
                mtype = offer.get("monetizationType", "")
                key = (name, mtype)
                if name and url and key not in seen:
                    seen.add(key)
                    offers.append({"service": name, "url": url, "type": mtype})
        data_str = json.dumps(offers)
        if cache:
            cache.data_json  = data_str
            cache.fetched_at = now
        else:
            db.session.add(FilmStreaming(film_id=film.id, data_json=data_str, fetched_at=now))
        db.session.commit()
        return offers
    except Exception:
        return []


# ── SETTINGS ──────────────────────────────────────────────────────────────────

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        email_notifs = bool(request.form.get("email_notifications"))
        current_user.email = email or None
        current_user.email_notifications = email_notifs
        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html")


@app.route("/settings/delete-account", methods=["POST"])
@login_required
def delete_account():
    password = request.form.get("confirm_password", "")
    if not current_user.check_password(password):
        flash("Incorrect password. Account not deleted.", "error")
        return redirect(url_for("settings"))

    user_id = current_user.id

    # Delete all user data before removing the account
    ReviewComment.query.filter_by(user_id=user_id).delete()
    ReviewLike.query.filter_by(user_id=user_id).delete()
    # Remove likes on the user's reviews (so cascade doesn't fail)
    for review in Review.query.filter_by(user_id=user_id).all():
        ReviewLike.query.filter_by(review_id=review.id).delete()
        ReviewComment.query.filter_by(review_id=review.id).delete()
    Review.query.filter_by(user_id=user_id).delete()
    Follow.query.filter_by(follower_id=user_id).delete()
    Follow.query.filter_by(followed_id=user_id).delete()
    Movie.query.filter_by(user_id=user_id).delete()
    Notification.query.filter_by(user_id=user_id).delete()
    Notification.query.filter_by(from_user_id=user_id).delete()

    logout_user()
    user = db.session.get(User, user_id)
    if user:
        db.session.delete(user)
    db.session.commit()

    flash("Your account has been deleted.", "success")
    return redirect(url_for("index"))


# ── LANGUAGE SWITCHER ─────────────────────────────────────────────────────────

@app.route("/lang/<code>")
def set_lang(code):
    from flask import session as flask_session
    if code in ("en", "de"):
        flask_session["lang"] = code
    return redirect(request.referrer or url_for("index"))


# ── CINEMAS ───────────────────────────────────────────────────────────────────

def _seed_cinemas():
    if Cinema.query.count() > 0:
        return
    intimes = Cinema(
        name="Intimes", slug="intimes", city="Berlin",
        neighbourhood="Friedrichshain",
        website="https://www.intimes-kino.de",
        description="Tiny 90-seat cinema on Boxhagener Platz. Known for anime nights and independent programming.",
    )
    bware = Cinema(
        name="B-ware! Ladenkino", slug="b-ware-ladenkino", city="Berlin",
        neighbourhood="Friedrichshain",
        website="https://b-ware-ladenkino.de",
        description="Neighbourhood arthouse cinema on Frankfurter Allee. Late-night screenings and politically engaged programming.",
    )
    db.session.add_all([intimes, bware])
    db.session.flush()
    # Seed CinemaFilms for Intimes
    for title in ["Nausicaa of the Valley of the Wind", "The Tale of Princess Kaguya", "Spirited Away"]:
        db.session.add(CinemaFilm(cinema_id=intimes.id, film_title=title, show_type="now_showing"))
    for title in ["Grave of the Fireflies", "Perfect Blue"]:
        db.session.add(CinemaFilm(cinema_id=intimes.id, film_title=title, show_type="staff_pick"))
    db.session.commit()


@app.route("/cinemas")
def cinemas():
    all_cinemas = Cinema.query.order_by(Cinema.name).all()
    return render_template("cinemas.html", cinemas=all_cinemas)


@app.route("/cinema/<slug>")
def cinema_detail(slug):
    cinema = Cinema.query.filter_by(slug=slug).first_or_404()
    now_showing   = [f for f in cinema.films if f.show_type == "now_showing"]
    staff_picks   = [f for f in cinema.films if f.show_type == "staff_pick"]
    requests_list = sorted([f for f in cinema.films if f.show_type == "screening_request"],
                           key=lambda f: f.votes, reverse=True)
    return render_template("cinema_detail.html", cinema=cinema,
                           now_showing=now_showing, staff_picks=staff_picks,
                           requests_list=requests_list)


@app.route("/cinema/<slug>/request", methods=["POST"])
@login_required
def cinema_request(slug):
    cinema = Cinema.query.filter_by(slug=slug).first_or_404()
    title = request.form.get("title", "").strip()
    if not title:
        flash("Film title required.", "error")
        return redirect(url_for("cinema_detail", slug=slug))
    db.session.add(CinemaFilm(cinema_id=cinema.id, film_title=title,
                               show_type="screening_request", votes=0))
    db.session.commit()
    flash(f"Screening request for '{title}' submitted!", "success")
    return redirect(url_for("cinema_detail", slug=slug))


@app.route("/cinema/<slug>/request/<int:film_id>/vote", methods=["POST"])
@login_required
def cinema_vote(slug, film_id):
    cf = db.session.get(CinemaFilm, film_id)
    if not cf:
        flash("Film not found.", "error")
        return redirect(url_for("cinema_detail", slug=slug))
    cf.votes = (cf.votes or 0) + 1
    db.session.commit()
    return redirect(url_for("cinema_detail", slug=slug))


# ── REST API v1 ───────────────────────────────────────────────────────────────

from flask import jsonify

_API_PER_PAGE = 20


def _api_404(msg="Not found"):
    return jsonify({"error": msg}), 404


@app.route("/api/v1/")
@limiter.limit("100 per hour")
def api_root():
    return jsonify({
        "name": "MoviWebApp API",
        "version": "1.0",
        "endpoints": [
            "/api/v1/films", "/api/v1/films/<id>",
            "/api/v1/users/<username>", "/api/v1/users/<username>/films",
            "/api/v1/trending",
        ],
    })


@app.route("/api/v1/films")
@limiter.limit("100 per hour")
def api_films():
    from sqlalchemy import func as sqlfunc
    q    = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    fq   = Film.query
    if q:
        fq = fq.filter(Film.title.ilike(f"%{q}%"))
    pag = fq.order_by(Film.title).paginate(page=page, per_page=_API_PER_PAGE, error_out=False)
    return jsonify({
        "page": page, "total": pag.total, "pages": pag.pages,
        "films": [{"id": f.id, "title": f.title, "year": f.year,
                   "director": f.director, "genre": f.genre,
                   "poster_url": f.poster_url} for f in pag.items],
    })


@app.route("/api/v1/films/<int:film_id>")
@limiter.limit("100 per hour")
def api_film_detail(film_id):
    film = db.session.get(Film, film_id)
    if not film:
        return _api_404("Film not found")
    ratings = [m.rating for m in Movie.query.filter_by(film_id=film_id) if m.rating]
    avg = round(sum(ratings) / len(ratings), 2) if ratings else None
    return jsonify({
        "id": film.id, "title": film.title, "year": film.year,
        "director": film.director, "genre": film.genre,
        "plot": film.plot, "poster_url": film.poster_url,
        "avg_rating": avg, "rating_count": len(ratings),
    })


@app.route("/api/v1/users/<username>")
@limiter.limit("100 per hour")
def api_user(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return _api_404("User not found")
    movies = Movie.query.filter_by(user_id=user.id).all()
    watched  = sum(1 for m in movies if m.status == "watched")
    ratings  = [m.rating for m in movies if m.rating]
    avg      = round(sum(ratings) / len(ratings), 2) if ratings else None
    return jsonify({
        "username": user.username,
        "watched_count": watched,
        "avg_rating": avg,
        "followers": len(user.followers),
        "following": len(user.following),
    })


@app.route("/api/v1/users/<username>/films")
@limiter.limit("100 per hour")
def api_user_films(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return _api_404("User not found")
    page = request.args.get("page", 1, type=int)
    pag  = (Movie.query.filter_by(user_id=user.id)
            .order_by(Movie.date_added.desc())
            .paginate(page=page, per_page=_API_PER_PAGE, error_out=False))
    return jsonify({
        "page": page, "total": pag.total, "pages": pag.pages,
        "films": [{"id": m.id, "title": m.title, "year": m.year,
                   "rating": m.rating, "status": m.status,
                   "poster_url": m.poster_url} for m in pag.items],
    })


@app.route("/api/v1/trending")
@limiter.limit("100 per hour")
def api_trending():
    from datetime import datetime as dt, timedelta
    from sqlalchemy import func as sqlfunc
    cutoff = dt.utcnow() - timedelta(days=14)
    rows   = (db.session.query(Movie.title, sqlfunc.count(Movie.id).label("c"))
              .filter(Movie.date_added >= cutoff, Movie.status == "watched")
              .group_by(Movie.title)
              .order_by(sqlfunc.count(Movie.id).desc())
              .limit(20).all())
    result = []
    for row in rows:
        f = Film.query.filter_by(title=row.title).first()
        if f:
            result.append({"id": f.id, "title": f.title, "year": f.year,
                           "poster_url": f.poster_url, "watches_14d": row.c})
    return jsonify({"trending": result})


# ── REVIEW COMMENTS ───────────────────────────────────────────────────────────

@app.route("/reviews/<int:review_id>/comment", methods=["POST"])
@login_required
def add_comment(review_id):
    review = db.session.get(Review, review_id)
    if not review:
        if request.headers.get("HX-Request"):
            return "", 204
        flash("Review not found.", "error")
        return redirect(request.referrer or url_for("index"))
    body = request.form.get("body", "").strip()
    if not body or len(body) > 500:
        if request.headers.get("HX-Request"):
            return "", 400
        flash("Comment must be 1–500 characters.", "error")
        return redirect(request.referrer or url_for("index"))
    comment = ReviewComment(review_id=review_id, user_id=current_user.id, body=body)
    db.session.add(comment)
    db.session.commit()
    if request.headers.get("HX-Request"):
        return render_template("_review_comments.html", review=review)
    return redirect(request.referrer or url_for("index"))


@app.route("/reviews/<int:review_id>/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(review_id, comment_id):
    comment = db.session.get(ReviewComment, comment_id)
    if not comment or comment.review_id != review_id:
        flash("Comment not found.", "error")
        return redirect(request.referrer or url_for("index"))
    if comment.user_id != current_user.id:
        flash("You can only delete your own comments.", "error")
        return redirect(request.referrer or url_for("index"))
    db.session.delete(comment)
    db.session.commit()
    if request.headers.get("HX-Request"):
        review = db.session.get(Review, review_id)
        return render_template("_review_comments.html", review=review)
    return redirect(request.referrer or url_for("index"))


# ── PICK TONIGHT ─────────────────────────────────────────────────────────────

@app.route("/pick-tonight")
@login_required
def pick_tonight():
    import random
    from datetime import datetime as dt, timedelta
    from sqlalchemy import func

    exclude_film_id = request.args.get("exclude", type=int)

    # 1. Watchlist films
    watchlist = Movie.query.filter_by(
        user_id=current_user.id, status="watchlist"
    ).all()

    # 2. Gems from followed users (rated 4+) that current user hasn't seen
    followed_ids = [f.followed_id for f in current_user.following]
    my_titles = {m.title for m in current_user.movies}
    their_gems = []
    if followed_ids:
        their_gems = Movie.query.filter(
            Movie.user_id.in_(followed_ids),
            Movie.rating >= 4,
            Movie.title.notin_(my_titles),
            Movie.status == "watched",
        ).all()

    # 3. Trending films (last 14 days)
    cutoff = dt.utcnow() - timedelta(days=14)
    trending_rows = (
        db.session.query(Movie.title, func.count(Movie.id).label("c"))
        .filter(Movie.date_added >= cutoff, Movie.status == "watched")
        .group_by(Movie.title)
        .order_by(func.count(Movie.id).desc())
        .limit(20)
        .all()
    )
    trending_films = []
    for row in trending_rows:
        if row.title not in my_titles:
            f = Film.query.filter_by(title=row.title).first()
            if f:
                trending_films.append(f)

    # Build weighted pool: (film_obj_or_movie, reason, weight)
    pool = []
    for m in watchlist:
        if m.film_id and (not exclude_film_id or m.film_id != exclude_film_id):
            f = db.session.get(Film, m.film_id)
            if f:
                pool.extend([(f, "On your watchlist", None)] * 3)
    for m in their_gems:
        if m.film_id and (not exclude_film_id or m.film_id != exclude_film_id):
            f = db.session.get(Film, m.film_id)
            if f:
                recommender = db.session.get(User, m.user_id)
                stars = "★" * m.rating if m.rating else ""
                reason = f"{recommender.username} gave it {stars}" if recommender else "Loved by your network"
                pool.extend([(f, reason, recommender)] * 2)
    for f in trending_films:
        if not exclude_film_id or f.id != exclude_film_id:
            pool.append((f, "Trending this week", None))

    if not pool:
        return render_template("pick_tonight.html", film=None, reason=None, recommender=None)

    picked_film, reason, recommender = random.choice(pool)
    return render_template(
        "pick_tonight.html",
        film=picked_film,
        reason=reason,
        recommender=recommender,
        exclude_film_id=picked_film.id,
    )


# ── DISCOVER ──────────────────────────────────────────────────────────────────

@app.route("/discover")
@login_required
def discover():
    from datetime import datetime as dt, timedelta
    from sqlalchemy import func

    followed_ids = [f.followed_id for f in current_user.following]
    my_titles = {m.title for m in current_user.movies}

    # Section 1: From your network — rated 4.5+ by follows, unseen
    network_films = []
    if followed_ids:
        network_movies = (
            Movie.query.filter(
                Movie.user_id.in_(followed_ids),
                Movie.rating >= 4,
                Movie.title.notin_(my_titles),
                Movie.status == "watched",
            )
            .order_by(Movie.rating.desc(), Movie.date_added.desc())
            .all()
        )
        seen_titles = set()
        for m in network_movies:
            if m.title not in seen_titles and m.film_id:
                f = db.session.get(Film, m.film_id)
                if f:
                    recommender = db.session.get(User, m.user_id)
                    network_films.append((f, recommender, m.rating))
                    seen_titles.add(m.title)
                if len(network_films) >= 12:
                    break

    # Section 2: Because you liked [Film] — collaborative filtering
    because_films = []
    because_title = None
    my_top = sorted(
        [m for m in current_user.movies if m.rating and m.rating >= 4 and m.status == "watched"],
        key=lambda m: m.rating, reverse=True,
    )
    if my_top:
        anchor = my_top[0]
        because_title = anchor.title
        # Find users who also love the anchor film
        sibling_users = (
            Movie.query.filter(
                Movie.title == anchor.title,
                Movie.user_id != current_user.id,
                Movie.rating >= 4,
            )
            .with_entities(Movie.user_id)
            .all()
        )
        sibling_ids = [r.user_id for r in sibling_users]
        if sibling_ids:
            loved_by_siblings = (
                Movie.query.filter(
                    Movie.user_id.in_(sibling_ids),
                    Movie.title.notin_(my_titles),
                    Movie.rating >= 4,
                    Movie.status == "watched",
                )
                .order_by(Movie.rating.desc())
                .all()
            )
            seen_titles = set()
            for m in loved_by_siblings:
                if m.title not in seen_titles and m.film_id:
                    f = db.session.get(Film, m.film_id)
                    if f:
                        because_films.append(f)
                        seen_titles.add(m.title)
                    if len(because_films) >= 8:
                        break

    # Section 3: Hidden gems — high avg rating but fewer than 5 users
    hidden_gems = []
    rows = (
        db.session.query(
            Movie.title,
            func.avg(Movie.rating).label("avg_r"),
            func.count(Movie.id).label("cnt"),
        )
        .filter(Movie.status == "watched", Movie.rating.isnot(None))
        .group_by(Movie.title)
        .having(func.avg(Movie.rating) >= 4.0)
        .having(func.count(Movie.id) < 5)
        .order_by(func.avg(Movie.rating).desc())
        .limit(30)
        .all()
    )
    for row in rows:
        if row.title not in my_titles:
            f = Film.query.filter_by(title=row.title).first()
            if f and f.poster_url:
                hidden_gems.append((f, round(row.avg_r, 1)))
            if len(hidden_gems) >= 8:
                break

    # Section 4: Your watchlist
    watchlist_movies = (
        Movie.query.filter_by(user_id=current_user.id, status="watchlist")
        .order_by(Movie.date_added.asc())
        .limit(6)
        .all()
    )
    watchlist_films = []
    for m in watchlist_movies:
        if m.film_id:
            f = db.session.get(Film, m.film_id)
            if f:
                watchlist_films.append(f)
        elif m.title:
            # Try to find by title
            f = Film.query.filter_by(title=m.title).first()
            if f:
                watchlist_films.append(f)

    # Section 5: New to the community — added in last 30 days
    cutoff = dt.utcnow() - timedelta(days=30)
    fresh_rows = (
        db.session.query(Movie.title, func.max(Movie.date_added).label("added"))
        .filter(Movie.date_added >= cutoff, Movie.status == "watched")
        .group_by(Movie.title)
        .order_by(func.max(Movie.date_added).desc())
        .limit(30)
        .all()
    )
    fresh_films = []
    seen_fresh = set()
    for row in fresh_rows:
        if row.title not in seen_fresh:
            f = Film.query.filter_by(title=row.title).first()
            if f and f.poster_url:
                fresh_films.append(f)
                seen_fresh.add(row.title)
            if len(fresh_films) >= 8:
                break

    return render_template(
        "discover.html",
        network_films=network_films,
        because_films=because_films,
        because_title=because_title,
        hidden_gems=hidden_gems,
        watchlist_films=watchlist_films,
        fresh_films=fresh_films,
        followed_count=len(followed_ids),
    )


# ── ERROR HANDLERS ───────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404,
                           badge="SCENE MISSING",
                           title="This Page Got Cut",
                           message="The editor removed it. The director's cut never existed. "
                                   "The intern deleted it. Nobody knows. It's gone.",
                           quote="\u201cI don\u2019t think we\u2019re in Kansas anymore.\u201d",
                           quote_attr="\u2014 Dorothy, The Wizard of Oz (1939)",
                           suggested_films=[
                               "Lost Highway (1997)",
                               "Gone with the Wind (1939)",
                               "The Missing (2003)",
                               "Somewhere (2010)",
                               "Into the Void (2009)",
                           ]), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500,
                           badge="TECHNICAL DIFFICULTIES",
                           title="The Projector Exploded",
                           message="Something caught fire in the booth. Our best grip is on it. "
                                   "Please stand by — intermission music playing.",
                           quote="\u201cAll right, Mr. DeMille, I\u2019m ready for my close-up.\u201d",
                           quote_attr="\u2014 Norma Desmond, Sunset Blvd. (1950)",
                           suggested_films=[
                               "Meltdown (1995)",
                               "The Core (2003)",
                               "Catastrophe (2015)",
                               "Chaos (2005)",
                               "Burn After Reading (2008)",
                           ]), 500


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403,
                           badge="PRIVATE SCREENING",
                           title="Members Only",
                           message="This screening is invitation-only. "
                                   "Your name isn\u2019t on the list. Neither is your plus-one.",
                           quote="\u201cYou\u2019re not supposed to be here.\u201d",
                           quote_attr="\u2014 Clerks (1994)",
                           suggested_films=[
                               "Forbidden Planet (1956)",
                               "The Uninvited (1944)",
                               "No Trespassing (1922)",
                               "Eyes Wide Shut (1999)",
                               "The Insider (1999)",
                           ]), 403


# ── STARTUP ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(os.path.join(basedir, "data")):
        os.makedirs(os.path.join(basedir, "data"))
    with app.app_context():
        db.create_all()
        migrate_db()
        populate_films()
        _seed_cinemas()
    app.run(debug=True)
