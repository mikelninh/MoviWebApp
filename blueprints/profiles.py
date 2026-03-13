"""User profiles, diary, legacy redirects."""

from collections import Counter, defaultdict
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from data_manager import DataManager
from helpers import (ai_taste_report, compute_profile_stats,
                     compute_taste_match)
from models import Follow, Movie, Review, User, UserList, db

profiles_bp = Blueprint("profiles", __name__)
data_manager = DataManager()


_PROFILE_PER_PAGE = 24


@profiles_bp.route("/u/<username>")
def user_profile(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("pages.index"))
    user_id = user.id
    sort = request.args.get("sort", "title")
    status_filter = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)
    all_sorted = data_manager.get_movies(user_id, sort=sort, status=status_filter)
    total = len(all_sorted)
    total_pages = max(1, (total + _PROFILE_PER_PAGE - 1) // _PROFILE_PER_PAGE)
    page = max(1, min(page, total_pages))
    movies = all_sorted[(page - 1) * _PROFILE_PER_PAGE: page * _PROFILE_PER_PAGE]
    all_count = Movie.query.filter_by(user_id=user_id).count()
    watched_count = Movie.query.filter(
        Movie.user_id == user_id, Movie.status == "watched").count()
    watchlist_count = Movie.query.filter(
        Movie.user_id == user_id, Movie.status == "watchlist").count()
    watching_count = Movie.query.filter(
        Movie.user_id == user_id, Movie.status == "watching").count()
    recommendations = []
    if current_user.is_authenticated and current_user.id == user_id:
        recommendations = data_manager.get_recommendations(user_id)
    all_movies = Movie.query.filter_by(user_id=user_id).all()
    profile_stats = compute_profile_stats(all_movies)
    taste_match = 0
    is_following = False
    if current_user.is_authenticated and current_user.id != user_id:
        taste_match = compute_taste_match(
            Movie.query.filter_by(user_id=current_user.id).all(), all_movies)
        is_following = Follow.query.filter_by(
            follower_id=current_user.id, followed_id=user_id).first() is not None
    user_lists = UserList.query.filter_by(user_id=user_id).all()
    taste_blurb = ai_taste_report(all_movies)
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


@profiles_bp.route("/users/<int:user_id>")
def get_movies(user_id):
    """Legacy numeric URL — redirect to canonical pretty URL."""
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("pages.index"))
    args = request.args.to_dict()
    return redirect(url_for("profiles.user_profile",
                            username=user.username, **args), 301)


@profiles_bp.route("/diary/<int:user_id>")
def diary(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("pages.index"))
    movies = (Movie.query.filter_by(user_id=user_id, status="watched")
              .order_by(Movie.date_added.desc()).all())
    grouped = defaultdict(list)
    for m in movies:
        key = m.date_added.strftime("%B %Y") if m.date_added else "Earlier"
        grouped[key].append(m)
    total = len(movies)
    rated = [m for m in movies if m.rating]
    avg_rating = round(sum(m.rating for m in rated) / len(rated), 1) if rated else None
    genre_counts = Counter()
    for m in movies:
        if m.genre:
            for g in m.genre.split(", "):
                genre_counts[g] += 1
    top_genre = genre_counts.most_common(1)[0][0] if genre_counts else None
    this_year = date.today().year
    this_year_count = sum(
        1 for m in movies if m.date_added and m.date_added.year == this_year)
    return render_template("diary.html", user=user, grouped=dict(grouped),
                           total=total, avg_rating=avg_rating,
                           top_genre=top_genre, this_year=this_year,
                           this_year_count=this_year_count)
