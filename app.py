"""MoviWebApp — main application module.

Creates the Flask app, registers blueprints and extensions, and
handles startup tasks (DB migration, seeding).
"""

import logging
import os
import secrets

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, jsonify, request
from flask_login import current_user
from sqlalchemy import text

from data_manager import DataManager
from extensions import csrf, limiter, login_manager, mail, migrate
from helpers import _t, get_inspiration_with_posters
from models import (Cinema, CinemaFilm, Film, Movie, Notification, User, db)

# ── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("moviwebapp")

# ── APP ──────────────────────────────────────────────────────────────────────

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = \
    f"sqlite:///{os.path.join(basedir, 'data/movies.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# Mail
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get(
    "MAIL_USERNAME", "noreply@moviwebapp.com")

# ── INIT EXTENSIONS ──────────────────────────────────────────────────────────

db.init_app(app)
csrf.init_app(app)
login_manager.init_app(app)
mail.init_app(app)
migrate.init_app(app, db)
limiter.init_app(app)

data_manager = DataManager()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ── REGISTER BLUEPRINTS ─────────────────────────────────────────────────────

from blueprints.auth import auth_bp
from blueprints.profiles import profiles_bp
from blueprints.films import films_bp
from blueprints.social import social_bp
from blueprints.discovery import discovery_bp
from blueprints.lists import lists_bp
from blueprints.nights import nights_bp
from blueprints.cinemas import cinemas_bp
from blueprints.api import api_bp
from blueprints.pages import pages_bp

app.register_blueprint(auth_bp)
app.register_blueprint(profiles_bp)
app.register_blueprint(films_bp)
app.register_blueprint(social_bp)
app.register_blueprint(discovery_bp)
app.register_blueprint(lists_bp)
app.register_blueprint(nights_bp)
app.register_blueprint(cinemas_bp)
app.register_blueprint(api_bp)
app.register_blueprint(pages_bp)

# ── STATIC FILE CACHE HEADERS ────────────────────────────────────────────────

@app.after_request
def add_cache_headers(response):
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    return response


# ── TEMPLATE GLOBALS ─────────────────────────────────────────────────────────

app.jinja_env.globals["_"] = _t


@app.template_global()
def avatar_url(username):
    """DiceBear avataaars — unique cartoon portrait per username."""
    return (
        f"https://api.dicebear.com/9.x/avataaars/svg"
        f"?seed={username}"
        f"&backgroundColor=b6e3f4,c0aede,d1d4f9,ffd5dc,ffdfbf,d1fae5"
        f"&backgroundType=gradientLinear"
    )


@app.context_processor
def inject_globals():
    unread = 0
    if current_user.is_authenticated:
        unread = Notification.query.filter_by(
            user_id=current_user.id, read=False).count()
    return {"unread_notifications": unread}


# ── ERROR HANDLERS ───────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404,
                           badge="SCENE MISSING",
                           title="This Page Got Cut",
                           message="The editor removed it. The director\u2019s "
                                   "cut never existed. It\u2019s gone.",
                           quote="\u201cI don\u2019t think we\u2019re in Kansas "
                                 "anymore.\u201d",
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
                           message="Something caught fire in the booth. "
                                   "Please stand by.",
                           quote="\u201cAll right, Mr. DeMille, I\u2019m ready "
                                 "for my close-up.\u201d",
                           quote_attr="\u2014 Norma Desmond, Sunset Blvd. (1950)",
                           suggested_films=[
                               "Meltdown (1995)", "The Core (2003)",
                               "Catastrophe (2015)", "Chaos (2005)",
                               "Burn After Reading (2008)",
                           ]), 500


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403,
                           badge="PRIVATE SCREENING",
                           title="Members Only",
                           message="This screening is invitation-only. "
                                   "Your name isn\u2019t on the list.",
                           quote="\u201cYou\u2019re not supposed to be "
                                 "here.\u201d",
                           quote_attr="\u2014 Clerks (1994)",
                           suggested_films=[
                               "Forbidden Planet (1956)",
                               "The Uninvited (1944)",
                               "No Trespassing (1922)",
                               "Eyes Wide Shut (1999)",
                               "The Insider (1999)",
                           ]), 403


# ── DB MIGRATIONS ────────────────────────────────────────────────────────────

def migrate_db():
    """Add new columns to existing tables without destroying data."""
    with db.engine.connect() as conn:
        existing_movie = {row[1] for row in
                          conn.execute(text("PRAGMA table_info(movie)"))}
        for col, sql in {
            "rating":     "ALTER TABLE movie ADD COLUMN rating INTEGER",
            "year":       "ALTER TABLE movie ADD COLUMN year VARCHAR(10)",
            "director":   "ALTER TABLE movie ADD COLUMN director VARCHAR(120)",
            "plot":       "ALTER TABLE movie ADD COLUMN plot TEXT",
            "poster_url": "ALTER TABLE movie ADD COLUMN poster_url VARCHAR(300)",
            "genre":      "ALTER TABLE movie ADD COLUMN genre VARCHAR(200)",
            "status":     "ALTER TABLE movie ADD COLUMN status VARCHAR(20) "
                          "DEFAULT 'watched'",
            "date_added": "ALTER TABLE movie ADD COLUMN date_added DATETIME",
        }.items():
            if col not in existing_movie:
                conn.execute(text(sql))

        existing_user = {row[1] for row in
                         conn.execute(text("PRAGMA table_info(user)"))}
        if "password_hash" not in existing_user:
            conn.execute(text(
                "ALTER TABLE user ADD COLUMN password_hash VARCHAR(256)"))
        if "email" not in existing_user:
            conn.execute(text(
                "ALTER TABLE user ADD COLUMN email VARCHAR(120)"))
        if "email_notifications" not in existing_user:
            conn.execute(text(
                "ALTER TABLE user ADD COLUMN email_notifications "
                "BOOLEAN DEFAULT 0"))
        if "reset_token" not in existing_user:
            conn.execute(text(
                "ALTER TABLE user ADD COLUMN reset_token VARCHAR(64)"))
        if "reset_token_expires" not in existing_user:
            conn.execute(text(
                "ALTER TABLE user ADD COLUMN reset_token_expires DATETIME"))
        if "email_verified" not in existing_user:
            conn.execute(text(
                "ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0"))

        existing_movie = {row[1] for row in
                          conn.execute(text("PRAGMA table_info(movie)"))}
        if "film_id" not in existing_movie:
            conn.execute(text(
                "ALTER TABLE movie ADD COLUMN film_id INTEGER "
                "REFERENCES film(id)"))
        conn.commit()


def populate_films():
    """Backfill Film records from existing Movie data and link movie.film_id."""
    rows = (db.session.query(Movie.title, Movie.year, Movie.director,
                             Movie.plot, Movie.poster_url, Movie.genre)
            .filter(Movie.status == "watched")
            .group_by(Movie.title).all())
    changed = 0
    for row in rows:
        film = Film.query.filter_by(title=row.title).first()
        if not film:
            film = Film(title=row.title, year=row.year, director=row.director,
                        plot=row.plot, poster_url=row.poster_url,
                        genre=row.genre)
            db.session.add(film)
            db.session.flush()
            changed += 1
        Movie.query.filter_by(title=row.title, film_id=None)\
                   .update({"film_id": film.id}, synchronize_session=False)
    if changed:
        db.session.commit()


def _seed_cinemas():
    if Cinema.query.count() > 0:
        return
    intimes = Cinema(
        name="Intimes", slug="intimes", city="Berlin",
        neighbourhood="Friedrichshain",
        website="https://kino-intimes.de/",
        description="Tiny 90-seat cinema on Boxhagener Platz.")
    bware = Cinema(
        name="B-ware! Ladenkino", slug="b-ware-ladenkino", city="Berlin",
        neighbourhood="Friedrichshain",
        website="https://ladenkino.de/",
        description="Neighbourhood arthouse cinema on Frankfurter Allee.")
    kino_intl = Cinema(
        name="Kino International", slug="kino-international", city="Berlin",
        neighbourhood="Mitte",
        website="https://www.kino-international.com/",
        description="Iconic 1960s GDR cinema on Karl-Marx-Allee.")
    delphi_lux = Cinema(
        name="Delphi LUX", slug="delphi-lux", city="Berlin",
        neighbourhood="Charlottenburg",
        website="https://www.yorck.de/kinos/delphi-lux",
        description="Modern arthouse cinema at Kantstrasse by Yorck Kinos.")
    arsenal = Cinema(
        name="Arsenal \u2013 Institut f\u00fcr Film und Videokunst", slug="arsenal", city="Berlin",
        neighbourhood="Kreuzberg",
        website="https://www.arsenal-berlin.de/",
        description="Film institute and cinema at Potsdamer Platz, specialising in rare and experimental film.")
    il_kino = Cinema(
        name="Il Kino", slug="il-kino", city="Berlin",
        neighbourhood="Neuk\u00f6lln",
        website="https://ilkino.de/",
        description="Micro-cinema in Neuk\u00f6lln showing independent and international film.")
    db.session.add_all([intimes, bware, kino_intl, delphi_lux, arsenal, il_kino])
    db.session.flush()
    for title in ["Nausicaa of the Valley of the Wind",
                  "The Tale of Princess Kaguya", "Spirited Away"]:
        db.session.add(CinemaFilm(cinema_id=intimes.id, film_title=title,
                                   show_type="now_showing"))
    for title in ["Grave of the Fireflies", "Perfect Blue"]:
        db.session.add(CinemaFilm(cinema_id=intimes.id, film_title=title,
                                   show_type="staff_pick"))
    for title in ["The Lives of Others", "Wings of Desire",
                  "Good Bye, Lenin!"]:
        db.session.add(CinemaFilm(cinema_id=kino_intl.id, film_title=title,
                                   show_type="now_showing"))
    for title in ["Das Cabinet des Dr. Caligari", "Metropolis"]:
        db.session.add(CinemaFilm(cinema_id=kino_intl.id, film_title=title,
                                   show_type="staff_pick"))
    for title in ["Close-Up", "Stalker", "Sans Soleil"]:
        db.session.add(CinemaFilm(cinema_id=arsenal.id, film_title=title,
                                   show_type="now_showing"))
    for title in ["Paris, Texas", "In the Mood for Love"]:
        db.session.add(CinemaFilm(cinema_id=delphi_lux.id, film_title=title,
                                   show_type="now_showing"))
    for title in ["Aftersun", "Past Lives"]:
        db.session.add(CinemaFilm(cinema_id=il_kino.id, film_title=title,
                                   show_type="now_showing"))
    db.session.commit()


# ── STARTUP ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(os.path.join(basedir, "data")):
        os.makedirs(os.path.join(basedir, "data"))
    with app.app_context():
        db.create_all()
        migrate_db()
        populate_films()
        _seed_cinemas()
    app.run(debug=os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true"))
