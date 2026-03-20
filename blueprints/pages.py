"""Static pages, index, export, import, language switcher."""

import csv
import io
import zipfile
from datetime import datetime

from flask import (Blueprint, flash, make_response, redirect,
                   render_template, request, session as flask_session, url_for)
from flask_login import current_user, login_required
from sqlalchemy import func as sqlfunc

from data_manager import DataManager
from extensions import csrf
from helpers import (fetch_film_news, get_inspiration_with_posters,
                     get_or_create_film)
from models import Film, Movie, Review, db

pages_bp = Blueprint("pages", __name__)
data_manager = DataManager()


@pages_bp.route("/")
def index():
    total_movies = Movie.query.count()
    activity = data_manager.get_recent_activity(limit=8)
    inspiration = get_inspiration_with_posters()
    hero_films = (
        db.session.query(Film, sqlfunc.avg(Movie.rating).label("avg_rating"),
                         sqlfunc.count(Movie.id).label("count"))
        .join(Movie, Movie.film_id == Film.id)
        .filter(Film.poster_url.isnot(None), Movie.rating.isnot(None))
        .group_by(Film.id)
        .having(sqlfunc.count(Movie.id) >= 2)
        .order_by(sqlfunc.avg(Movie.rating).desc())
        .limit(6).all())
    hero_slides = [{"film": f, "avg_rating": round(avg, 1)}
                   for f, avg, _ in hero_films]
    raw_reviews = (Review.query.order_by(Review.created_at.desc())
                   .limit(12).all())
    recent_reviews = []
    for rev in raw_reviews:
        film = Film.query.filter_by(title=rev.movie_title).first()
        movie_entry = Movie.query.filter_by(
            user_id=rev.user_id, title=rev.movie_title).first()
        recent_reviews.append({
            "review": rev, "film": film,
            "rating": movie_entry.rating if movie_entry else None,
        })
    return render_template("index.html", total_movies=total_movies,
                           activity=activity, inspiration=inspiration,
                           hero_slides=hero_slides,
                           recent_reviews=recent_reviews)


@pages_bp.route("/about")
def about():
    return render_template("about.html")


@pages_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")


@pages_bp.route("/inspiration")
def inspiration():
    lists = get_inspiration_with_posters()
    return render_template("inspiration.html", lists=lists)


@pages_bp.route("/news")
def news():
    articles = fetch_film_news(limit=18)
    return render_template("news.html", articles=articles)


@pages_bp.route("/export")
@login_required
def export_data():
    movies = Movie.query.filter_by(user_id=current_user.id).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Title", "Year", "Rating", "Status", "Director",
                     "Genre", "Date Added"])
    for m in movies:
        writer.writerow([
            m.title, m.year or "", m.rating or "", m.status or "watched",
            m.director or "", m.genre or "",
            m.date_added.strftime("%Y-%m-%d") if m.date_added else "",
        ])
    resp = make_response(out.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = (
        f"attachment; filename={current_user.username}-moviwebapp.csv")
    return resp


@pages_bp.route("/import", methods=["GET", "POST"])
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
                        watched_rows = list(csv.DictReader(
                            io.TextIOWrapper(f, encoding="utf-8")))
                if "ratings.csv" in names:
                    with z.open("ratings.csv") as f:
                        for row in csv.DictReader(
                                io.TextIOWrapper(f, encoding="utf-8")):
                            key = (row["Name"].strip(),
                                   row.get("Year", "").strip())
                            r = parse_rating(row.get("Rating"))
                            if r:
                                ratings_map[key] = r
                if "watchlist.csv" in names:
                    with z.open("watchlist.csv") as f:
                        watchlist_rows = list(csv.DictReader(
                            io.TextIOWrapper(f, encoding="utf-8")))
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

    existing = {
        (m.title.lower(), m.year or "")
        for m in Movie.query.filter_by(user_id=current_user.id).all()
    }
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
        year = row.get("Year", "").strip()
        if not title:
            continue
        if (title.lower(), year) in existing:
            skipped_watched += 1
            continue
        rating = ratings_map.get((title, year))
        film = get_or_create_film_fast(title, year)
        db.session.add(Movie(
            title=title, user_id=current_user.id, film_id=film.id,
            rating=rating, status="watched", year=year))
        existing.add((title.lower(), year))
        watched_imported += 1

    for row in watchlist_rows:
        title = row.get("Name", "").strip()
        year = row.get("Year", "").strip()
        if not title:
            continue
        if (title.lower(), year) in existing:
            skipped_watchlist += 1
            continue
        film = get_or_create_film_fast(title, year)
        db.session.add(Movie(
            title=title, user_id=current_user.id, film_id=film.id,
            rating=None, status="watchlist", year=year))
        existing.add((title.lower(), year))
        watchlist_imported += 1

    db.session.commit()

    orphans = (db.session.query(Movie).join(Film, Movie.film_id == Film.id)
               .filter(Movie.user_id == current_user.id,
                       Movie.poster_url.is_(None),
                       Film.poster_url.isnot(None)).all())
    for m in orphans:
        film = db.session.get(Film, m.film_id)
        m.poster_url = film.poster_url
        m.plot = film.plot or m.plot
        m.director = film.director or m.director
        m.genre = film.genre or m.genre
        if not m.year:
            m.year = film.year
    db.session.commit()

    parts = []
    if watched_imported:
        parts.append(f"{watched_imported} watched")
    if watchlist_imported:
        parts.append(f"{watchlist_imported} watchlist")
    skipped = skipped_watched + skipped_watchlist
    if skipped:
        parts.append(f"{skipped} already in your list")
    flash("Import complete! " + " \u00b7 ".join(parts) + ".", "success")
    return redirect(url_for("profiles.user_profile",
                            username=current_user.username))


@pages_bp.route("/lang/<code>")
def set_lang(code):
    if code in ("en", "de"):
        flask_session["lang"] = code
    return redirect(request.referrer or url_for("pages.index"))


# ── HEALTH CHECK ─────────────────────────────────────────────────────────────

@pages_bp.route("/health")
@csrf.exempt
def health_check():
    from flask import jsonify
    return jsonify({"status": "ok"}), 200
