"""Discovery: trending, browse, genre, year-in-review, challenges, discover, pick tonight."""

import random
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from helpers import (ai_year_summary, compute_challenges)
from models import Film, Movie, Review, User, db

discovery_bp = Blueprint("discovery", __name__)


@discovery_bp.route("/trending")
def trending():
    cutoff = datetime.utcnow() - timedelta(days=30)
    rows = (db.session.query(Movie.title,
                             func.count(Movie.id).label("c"),
                             func.avg(Movie.rating).label("avg_r"))
            .filter(Movie.date_added >= cutoff, Movie.status == "watched")
            .group_by(Movie.title)
            .order_by(func.count(Movie.id).desc())
            .limit(20).all())
    films = []
    for row in rows:
        f = Film.query.filter_by(title=row.title).first()
        if f:
            films.append((f, row.c, row.avg_r))
    return render_template("trending.html", films=films)


@discovery_bp.route("/browse")
def browse():
    gc = Counter()
    for m in Movie.query.filter(Movie.genre.isnot(None)).all():
        for g in m.genre.split(", "):
            gc[g.strip()] += 1
    genres = [(g, c) for g, c in gc.most_common() if c >= 2]
    return render_template("browse.html", genres=genres)


@discovery_bp.route("/browse/<genre>")
def genre_page(genre):
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
    films = all_films[(page - 1) * _PER: page * _PER]
    return render_template("genre_page.html", genre=genre, films=films,
                           page=page, total_pages=total_pages,
                           total=len(all_films))


@discovery_bp.route("/u/<username>/year/<int:year>")
def year_in_review(username, year):
    user = User.query.filter_by(username=username).first()
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("pages.index"))
    movies = (Movie.query.filter_by(user_id=user.id, status="watched")
              .filter(db.func.strftime("%Y", Movie.date_added) == str(year))
              .order_by(Movie.date_added).all())
    if not movies:
        flash(f"No watched movies logged in {year}.", "error")
        return redirect(url_for("profiles.user_profile", username=username))
    total = len(movies)
    hours = total * 2
    gc = Counter(g for m in movies if m.genre for g in m.genre.split(", "))
    dc = Counter(m.director for m in movies if m.director)
    top_genres = gc.most_common(5)
    top_directors = dc.most_common(3)
    rated = [m for m in movies if m.rating]
    avg_rating = round(sum(m.rating for m in rated) / len(rated), 1) if rated else None
    rating_dist = {i: sum(1 for m in rated if m.rating == i) for i in range(1, 6)}
    top_film = max(rated, key=lambda m: (m.rating, m.date_added or 0)) if rated else None
    monthly_raw = defaultdict(list)
    for m in movies:
        if m.date_added:
            monthly_raw[m.date_added.month].append(m)
    monthly = [(mo, monthly_raw[mo]) for mo in sorted(monthly_raw)]
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
        badge = ("Film Addict", "\U0001f3ac")
    elif total >= 50:
        badge = ("Cinema Devotee", "\U0001f37f")
    elif total >= 20:
        badge = ("Movie Buff", "\u2b50")
    else:
        badge = ("Film Explorer", "\U0001f52d")
    ai_summary = ai_year_summary(total, top_genres, top_directors,
                                 avg_rating, year)
    return render_template("year_in_review.html",
                           user=user, year=year, total=total, hours=hours,
                           top_genres=top_genres, top_directors=top_directors,
                           avg_rating=avg_rating, rating_dist=rating_dist,
                           contrarian=contrarian, first_film=movies[0],
                           last_film=movies[-1], top_film=top_film,
                           monthly=monthly, badge=badge,
                           rated_count=len(rated), ai_summary=ai_summary,
                           prev_year=year - 1, next_year=year + 1,
                           current_year=date.today().year)


@discovery_bp.route("/challenges")
@login_required
def challenges():
    movies = Movie.query.filter_by(user_id=current_user.id).all()
    review_count = Review.query.filter_by(user_id=current_user.id).count()
    all_challenges = compute_challenges(movies, review_count)
    return render_template("challenges.html", challenges=all_challenges)


@discovery_bp.route("/pick-tonight")
@login_required
def pick_tonight():
    exclude_film_id = request.args.get("exclude", type=int)
    watchlist = Movie.query.filter_by(
        user_id=current_user.id, status="watchlist").all()
    followed_ids = [f.followed_id for f in current_user.following]
    my_titles = {m.title for m in current_user.movies}
    their_gems = []
    if followed_ids:
        their_gems = Movie.query.filter(
            Movie.user_id.in_(followed_ids), Movie.rating >= 4,
            Movie.title.notin_(my_titles), Movie.status == "watched").all()
    cutoff = datetime.utcnow() - timedelta(days=14)
    trending_rows = (
        db.session.query(Movie.title, func.count(Movie.id).label("c"))
        .filter(Movie.date_added >= cutoff, Movie.status == "watched")
        .group_by(Movie.title)
        .order_by(func.count(Movie.id).desc())
        .limit(20).all())
    trending_films = []
    for row in trending_rows:
        if row.title not in my_titles:
            f = Film.query.filter_by(title=row.title).first()
            if f:
                trending_films.append(f)
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
                stars = "\u2605" * m.rating if m.rating else ""
                reason = (f"{recommender.username} gave it {stars}"
                          if recommender else "Loved by your network")
                pool.extend([(f, reason, recommender)] * 2)
    for f in trending_films:
        if not exclude_film_id or f.id != exclude_film_id:
            pool.append((f, "Trending this week", None))
    if not pool:
        return render_template("pick_tonight.html", film=None,
                               reason=None, recommender=None)
    picked_film, reason, recommender = random.choice(pool)
    return render_template("pick_tonight.html", film=picked_film,
                           reason=reason, recommender=recommender,
                           exclude_film_id=picked_film.id)


@discovery_bp.route("/discover")
@login_required
def discover():
    followed_ids = [f.followed_id for f in current_user.following]
    my_titles = {m.title for m in current_user.movies}
    network_films = []
    if followed_ids:
        network_movies = (
            Movie.query.filter(
                Movie.user_id.in_(followed_ids), Movie.rating >= 4,
                Movie.title.notin_(my_titles), Movie.status == "watched")
            .order_by(Movie.rating.desc(), Movie.date_added.desc()).all())
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
    because_films = []
    because_title = None
    my_top = sorted(
        [m for m in current_user.movies
         if m.rating and m.rating >= 4 and m.status == "watched"],
        key=lambda m: m.rating, reverse=True)
    if my_top:
        anchor = my_top[0]
        because_title = anchor.title
        sibling_users = (
            Movie.query.filter(
                Movie.title == anchor.title,
                Movie.user_id != current_user.id, Movie.rating >= 4)
            .with_entities(Movie.user_id).all())
        sibling_ids = [r.user_id for r in sibling_users]
        if sibling_ids:
            loved_by_siblings = (
                Movie.query.filter(
                    Movie.user_id.in_(sibling_ids),
                    Movie.title.notin_(my_titles),
                    Movie.rating >= 4, Movie.status == "watched")
                .order_by(Movie.rating.desc()).all())
            seen_titles = set()
            for m in loved_by_siblings:
                if m.title not in seen_titles and m.film_id:
                    f = db.session.get(Film, m.film_id)
                    if f:
                        because_films.append(f)
                        seen_titles.add(m.title)
                    if len(because_films) >= 8:
                        break
    hidden_gems = []
    rows = (
        db.session.query(
            Movie.title, func.avg(Movie.rating).label("avg_r"),
            func.count(Movie.id).label("cnt"))
        .filter(Movie.status == "watched", Movie.rating.isnot(None))
        .group_by(Movie.title)
        .having(func.avg(Movie.rating) >= 4.0)
        .having(func.count(Movie.id) < 5)
        .order_by(func.avg(Movie.rating).desc())
        .limit(30).all())
    for row in rows:
        if row.title not in my_titles:
            f = Film.query.filter_by(title=row.title).first()
            if f and f.poster_url:
                hidden_gems.append((f, round(row.avg_r, 1)))
            if len(hidden_gems) >= 8:
                break
    watchlist_movies = (
        Movie.query.filter_by(user_id=current_user.id, status="watchlist")
        .order_by(Movie.date_added.asc()).limit(6).all())
    watchlist_films = []
    for m in watchlist_movies:
        if m.film_id:
            f = db.session.get(Film, m.film_id)
            if f:
                watchlist_films.append(f)
        elif m.title:
            f = Film.query.filter_by(title=m.title).first()
            if f:
                watchlist_films.append(f)
    cutoff = datetime.utcnow() - timedelta(days=30)
    fresh_rows = (
        db.session.query(Movie.title, func.max(Movie.date_added).label("added"))
        .filter(Movie.date_added >= cutoff, Movie.status == "watched")
        .group_by(Movie.title)
        .order_by(func.max(Movie.date_added).desc())
        .limit(30).all())
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
        "discover.html", network_films=network_films,
        because_films=because_films, because_title=because_title,
        hidden_gems=hidden_gems, watchlist_films=watchlist_films,
        fresh_films=fresh_films, followed_count=len(followed_ids))
