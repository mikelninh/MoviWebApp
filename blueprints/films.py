"""Film detail, search, add/edit/delete movies, reviews."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from data_manager import DataManager
from helpers import (ai_review_synthesis, ai_why_love, get_or_create_film,
                     get_streaming)
from models import (Film, Follow, Movie, Review, User, UserList, db)

films_bp = Blueprint("films", __name__)
data_manager = DataManager()


@films_bp.route("/film/<int:film_id>")
def film_detail(film_id):
    film = db.session.get(Film, film_id)
    if not film:
        flash("Film not found.", "error")
        return redirect(url_for("pages.index"))
    all_instances = Movie.query.filter_by(title=film.title).all()
    users_with_movie = [(db.session.get(User, m.user_id), m) for m in all_instances]
    shared_user_ids = [m.user_id for m in all_instances]
    similar_films = []
    if shared_user_ids:
        similar_titles = (
            db.session.query(Movie.title, func.count(Movie.id).label("c"))
            .filter(Movie.user_id.in_(shared_user_ids),
                    Movie.title != film.title, Movie.status == "watched")
            .group_by(Movie.title)
            .order_by(func.count(Movie.id).desc())
            .limit(12).all())
        for row in similar_titles:
            f = Film.query.filter_by(title=row.title).first()
            if f and f.poster_url:
                similar_films.append(f)
            if len(similar_films) >= 8:
                break
    reviews = (Review.query.filter_by(movie_title=film.title)
               .order_by(Review.created_at.desc()).all())
    user_review = None
    friends_with_movie = []
    ai_synthesis = None
    ai_why = None
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
    current_user_lists = []
    if current_user.is_authenticated:
        current_user_lists = UserList.query.filter_by(
            user_id=current_user.id).all()
    return render_template("film_detail.html", film=film,
                           users_with_movie=users_with_movie,
                           friends_with_movie=friends_with_movie,
                           similar=similar_films,
                           reviews=reviews, user_review=user_review,
                           ai_synthesis=ai_synthesis, ai_why=ai_why,
                           streaming=streaming,
                           current_user_lists=current_user_lists)


@films_bp.route("/movies/<int:movie_id>")
def movie_detail(movie_id):
    """Legacy route — redirect to global film page if possible."""
    movie = db.session.get(Movie, movie_id)
    if not movie:
        flash("Movie not found.", "error")
        return redirect(url_for("pages.index"))
    film = Film.query.filter_by(title=movie.title).first()
    if film:
        return redirect(url_for("films.film_detail", film_id=film.id), 301)
    all_instances = Movie.query.filter_by(title=movie.title).all()
    users_with_movie = [(db.session.get(User, m.user_id), m) for m in all_instances]
    similar = data_manager.get_similar_movies(movie_id)
    reviews = (Review.query.filter_by(movie_title=movie.title)
               .order_by(Review.created_at.desc()).all())
    user_review = None
    if current_user.is_authenticated:
        user_review = Review.query.filter_by(
            movie_title=movie.title, user_id=current_user.id).first()
    return render_template("movie_detail.html", movie=movie,
                           users_with_movie=users_with_movie, similar=similar,
                           reviews=reviews, user_review=user_review)


@films_bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    year_filter = request.args.get("year", "").strip()
    genre_filter = request.args.get("genre", "").strip()
    page = request.args.get("page", 1, type=int)
    results = []
    omdb_film = None
    pagination = None
    if q:
        fq = Film.query.filter(Film.title.ilike(f"%{q}%"))
        if year_filter:
            fq = fq.filter(Film.year.like(f"{year_filter}%"))
        if genre_filter:
            fq = fq.filter(Film.genre.ilike(f"%{genre_filter}%"))
        film_pag = fq.order_by(Film.title).paginate(
            page=page, per_page=20, error_out=False)
        if film_pag.items:
            pagination = film_pag
            film_ids = [f.id for f in film_pag.items]
            counts = dict(
                db.session.query(Movie.film_id, func.count(Movie.id))
                .filter(Movie.film_id.in_(film_ids), Movie.status == "watched")
                .group_by(Movie.film_id).all())
            results = [(f, counts.get(f.id, 0)) for f in film_pag.items]
        else:
            meta = data_manager.fetch_omdb_data(q)
            if meta and meta.get("poster_url"):
                film = get_or_create_film(q, meta)
                db.session.commit()
                return redirect(url_for("films.film_detail", film_id=film.id))
            omdb_film = meta
    return render_template("search.html", q=q, results=results,
                           year_filter=year_filter, genre_filter=genre_filter,
                           omdb_film=omdb_film, pagination=pagination)


@films_bp.route("/users/<int:user_id>/add_movie", methods=["POST"])
@login_required
def add_movie(user_id):
    if current_user.id != user_id:
        flash("You can only add movies to your own list.", "error")
        return redirect(url_for("profiles.get_movies", user_id=user_id))
    title = request.form.get("title", "").strip()
    rating = request.form.get("rating", type=int)
    status = request.form.get("status", "watched")
    if not title:
        flash("Movie title cannot be empty.", "error")
        return redirect(url_for("profiles.get_movies", user_id=user_id))
    if len(title) > 120:
        flash("Title too long (max 120 characters).", "error")
        return redirect(url_for("profiles.get_movies", user_id=user_id))
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
        flash(f"'{title}' added \u2014 no metadata found.", "info")
    return redirect(request.referrer or url_for("profiles.get_movies",
                                                user_id=user_id))


@films_bp.route("/users/<int:user_id>/movies/<int:movie_id>/toggle",
                methods=["POST"])
@login_required
def toggle_status(user_id, movie_id):
    if current_user.id != user_id:
        flash("Not allowed.", "error")
        return redirect(url_for("profiles.get_movies", user_id=user_id))
    data_manager.toggle_status(movie_id)
    return redirect(request.referrer or url_for("profiles.get_movies",
                                                user_id=user_id))


@films_bp.route("/users/<int:user_id>/movies/<int:movie_id>/edit",
                methods=["GET", "POST"])
@login_required
def edit_movie(user_id, movie_id):
    if current_user.id != user_id:
        flash("You can only edit your own movies.", "error")
        return redirect(url_for("profiles.get_movies", user_id=user_id))
    movie = db.session.get(Movie, movie_id)
    if not movie or movie.user_id != user_id:
        flash("Movie not found.", "error")
        return redirect(url_for("profiles.get_movies", user_id=user_id))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        rating = request.form.get("rating", type=int)
        status = request.form.get("status", "watched")
        if not title:
            flash("Title cannot be empty.", "error")
            return render_template("edit_movie.html", movie=movie,
                                   user_id=user_id)
        data_manager.update_movie(movie.id, title, rating, status)
        flash(f"'{title}' updated.", "success")
        return redirect(url_for("profiles.get_movies", user_id=user_id))
    return render_template("edit_movie.html", movie=movie, user_id=user_id)


@films_bp.route("/users/<int:user_id>/movies/<int:movie_id>/delete",
                methods=["POST"])
@login_required
def delete_movie(user_id, movie_id):
    if current_user.id != user_id:
        flash("You can only delete your own movies.", "error")
        return redirect(url_for("profiles.get_movies", user_id=user_id))
    data_manager.delete_movie(movie_id)
    flash("Movie removed.", "success")
    return redirect(url_for("profiles.get_movies", user_id=user_id))


@films_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
def delete_user(user_id):
    if current_user.id != user_id:
        flash("You can only delete your own account.", "error")
        return redirect(url_for("pages.index"))
    from flask_login import logout_user as _logout
    _logout()
    data_manager.delete_user(user_id)
    flash("Your account has been deleted.", "success")
    return redirect(url_for("pages.index"))


# ── REVIEWS ──────────────────────────────────────────────────────────────────

@films_bp.route("/film/<int:film_id>/review", methods=["POST"])
@login_required
def add_film_review(film_id):
    film = db.session.get(Film, film_id)
    if not film:
        return redirect(url_for("pages.index"))
    body = request.form.get("body", "").strip()
    if not body:
        flash("Review cannot be empty.", "error")
        return redirect(url_for("films.film_detail", film_id=film_id))
    if len(body) > 1000:
        flash("Review too long (max 1000 characters).", "error")
        return redirect(url_for("films.film_detail", film_id=film_id))
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
    return redirect(url_for("films.film_detail", film_id=film_id))


@films_bp.route("/movies/<int:movie_id>/review", methods=["POST"])
@login_required
def add_review(movie_id):
    movie = db.session.get(Movie, movie_id)
    if not movie:
        flash("Movie not found.", "error")
        return redirect(url_for("pages.index"))
    body = request.form.get("body", "").strip()
    if not body:
        flash("Review cannot be empty.", "error")
        return redirect(url_for("films.movie_detail", movie_id=movie_id))
    if len(body) > 1000:
        flash("Review too long (max 1000 characters).", "error")
        return redirect(url_for("films.movie_detail", movie_id=movie_id))
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
    return redirect(url_for("films.movie_detail", movie_id=movie_id))
