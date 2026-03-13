"""REST API v1 endpoints."""

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import func

from extensions import csrf, limiter
from models import Film, Follow, Movie, User, db

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

_API_PER_PAGE = 20


def _api_404(msg: str = "Not found"):
    return jsonify({"error": msg}), 404


@api_bp.route("/")
@csrf.exempt
@limiter.limit("100 per hour")
def api_root():
    return jsonify({
        "name": "MoviWebApp API", "version": "1.0",
        "endpoints": [
            "/api/v1/films", "/api/v1/films/<id>",
            "/api/v1/users/<username>", "/api/v1/users/<username>/films",
            "/api/v1/trending",
        ],
    })


@api_bp.route("/films")
@csrf.exempt
@limiter.limit("100 per hour")
def api_films():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    fq = Film.query
    if q:
        fq = fq.filter(Film.title.ilike(f"%{q}%"))
    pag = fq.order_by(Film.title).paginate(
        page=page, per_page=_API_PER_PAGE, error_out=False)
    return jsonify({
        "page": page, "total": pag.total, "pages": pag.pages,
        "films": [{"id": f.id, "title": f.title, "year": f.year,
                   "director": f.director, "genre": f.genre,
                   "poster_url": f.poster_url} for f in pag.items],
    })


@api_bp.route("/films/<int:film_id>")
@csrf.exempt
@limiter.limit("100 per hour")
def api_film_detail(film_id):
    film = db.session.get(Film, film_id)
    if not film:
        return _api_404("Film not found")
    ratings = [m.rating for m in
               Movie.query.filter_by(film_id=film_id) if m.rating]
    avg = round(sum(ratings) / len(ratings), 2) if ratings else None
    return jsonify({
        "id": film.id, "title": film.title, "year": film.year,
        "director": film.director, "genre": film.genre,
        "plot": film.plot, "poster_url": film.poster_url,
        "avg_rating": avg, "rating_count": len(ratings),
    })


@api_bp.route("/users/<username>")
@csrf.exempt
@limiter.limit("100 per hour")
def api_user(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return _api_404("User not found")
    movies = Movie.query.filter_by(user_id=user.id).all()
    watched = sum(1 for m in movies if m.status == "watched")
    ratings = [m.rating for m in movies if m.rating]
    avg = round(sum(ratings) / len(ratings), 2) if ratings else None
    return jsonify({
        "username": user.username, "watched_count": watched,
        "avg_rating": avg, "followers": len(user.followers),
        "following": len(user.following),
    })


@api_bp.route("/users/<username>/films")
@csrf.exempt
@limiter.limit("100 per hour")
def api_user_films(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return _api_404("User not found")
    page = request.args.get("page", 1, type=int)
    pag = (Movie.query.filter_by(user_id=user.id)
           .order_by(Movie.date_added.desc())
           .paginate(page=page, per_page=_API_PER_PAGE, error_out=False))
    return jsonify({
        "page": page, "total": pag.total, "pages": pag.pages,
        "films": [{"id": m.id, "title": m.title, "year": m.year,
                   "rating": m.rating, "status": m.status,
                   "poster_url": m.poster_url} for m in pag.items],
    })


@api_bp.route("/docs")
@csrf.exempt
def api_docs():
    return render_template("api_docs.html")


@api_bp.route("/trending")
@csrf.exempt
@limiter.limit("100 per hour")
def api_trending():
    cutoff = datetime.utcnow() - timedelta(days=14)
    rows = (db.session.query(Movie.title, func.count(Movie.id).label("c"))
            .filter(Movie.date_added >= cutoff, Movie.status == "watched")
            .group_by(Movie.title)
            .order_by(func.count(Movie.id).desc())
            .limit(20).all())
    result = []
    for row in rows:
        f = Film.query.filter_by(title=row.title).first()
        if f:
            result.append({"id": f.id, "title": f.title, "year": f.year,
                           "poster_url": f.poster_url, "watches_14d": row.c})
    return jsonify({"trending": result})
