"""Movie nights: create, vote, suggest, declare winner."""

import secrets

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from data_manager import DataManager
from models import (MovieNight, MovieNightFilm, MovieNightVote, db)

nights_bp = Blueprint("nights", __name__)
data_manager = DataManager()


@nights_bp.route("/movie-nights")
def movie_nights():
    nights = MovieNight.query.order_by(MovieNight.created_at.desc()).all()
    return render_template("movie_nights.html", nights=nights)


@nights_bp.route("/movie-nights/create", methods=["POST"])
@login_required
def create_movie_night():
    name = request.form.get("name", "").strip()
    date = request.form.get("date", "").strip()
    desc = request.form.get("description", "").strip()
    if not name:
        flash("Movie night needs a name.", "error")
        return redirect(url_for("nights.movie_nights"))
    night = MovieNight(
        creator_id=current_user.id, name=name,
        date=date or None, description=desc or None,
        invite_token=secrets.token_hex(16))
    db.session.add(night)
    db.session.commit()
    flash(f"'{name}' created!", "success")
    return redirect(url_for("nights.movie_night_detail", night_id=night.id))


@nights_bp.route("/movie-nights/<int:night_id>")
def movie_night_detail(night_id):
    night = db.session.get(MovieNight, night_id)
    if not night:
        flash("Movie night not found.", "error")
        return redirect(url_for("nights.movie_nights"))
    user_vote = None
    if current_user.is_authenticated:
        user_vote = MovieNightVote.query.filter_by(
            user_id=current_user.id).first()
    sorted_films = sorted(night.films, key=lambda f: len(f.votes), reverse=True)
    return render_template("movie_night_detail.html", night=night,
                           sorted_films=sorted_films, user_vote=user_vote)


@nights_bp.route("/movie-nights/<int:night_id>/suggest", methods=["POST"])
@login_required
def suggest_film(night_id):
    night = db.session.get(MovieNight, night_id)
    if not night:
        flash("Movie night not found.", "error")
        return redirect(url_for("nights.movie_nights"))
    title = request.form.get("title", "").strip()
    if not title:
        flash("Film title required.", "error")
        return redirect(url_for("nights.movie_night_detail", night_id=night_id))
    meta = data_manager.fetch_omdb_data(title)
    film = MovieNightFilm(
        night_id=night_id, movie_title=title,
        poster_url=meta.get("poster_url"),
        suggested_by=current_user.id)
    db.session.add(film)
    db.session.commit()
    flash(f"'{title}' suggested!", "success")
    return redirect(url_for("nights.movie_night_detail", night_id=night_id))


@nights_bp.route("/movie-nights/<int:night_id>/film/<int:film_id>/delete",
                 methods=["POST"])
@login_required
def delete_suggestion(night_id, film_id):
    film = db.session.get(MovieNightFilm, film_id)
    if not film or film.night_id != night_id:
        flash("Film not found.", "error")
        return redirect(url_for("nights.movie_night_detail", night_id=night_id))
    night = db.session.get(MovieNight, night_id)
    if film.suggested_by != current_user.id and \
       night.creator_id != current_user.id:
        flash("You can only remove your own suggestions.", "error")
        return redirect(url_for("nights.movie_night_detail", night_id=night_id))
    db.session.delete(film)
    db.session.commit()
    flash("Suggestion removed.", "info")
    return redirect(url_for("nights.movie_night_detail", night_id=night_id))


@nights_bp.route("/movie-nights/<int:night_id>/vote/<int:film_id>",
                 methods=["POST"])
@login_required
def vote_film(night_id, film_id):
    film = db.session.get(MovieNightFilm, film_id)
    if not film or film.night_id != night_id:
        flash("Film not found.", "error")
        return redirect(url_for("nights.movie_night_detail", night_id=night_id))
    existing = MovieNightVote.query.filter_by(
        user_id=current_user.id, film_id=film_id).first()
    if existing:
        db.session.delete(existing)
    else:
        old_votes = (MovieNightVote.query.join(MovieNightFilm)
                     .filter(MovieNightFilm.night_id == night_id,
                             MovieNightVote.user_id == current_user.id).all())
        for v in old_votes:
            db.session.delete(v)
        db.session.add(MovieNightVote(
            user_id=current_user.id, film_id=film_id))
    db.session.commit()
    if request.headers.get("HX-Request"):
        user_voted = MovieNightVote.query.filter_by(
            user_id=current_user.id, film_id=film_id).first() is not None
        vote_count = MovieNightVote.query.filter_by(film_id=film_id).count()
        return render_template("_vote_btn.html", film=film,
                               user_voted=user_voted, vote_count=vote_count,
                               night_id=night_id)
    return redirect(url_for("nights.movie_night_detail", night_id=night_id))


@nights_bp.route("/nights/join/<token>")
def join_night(token):
    night = MovieNight.query.filter_by(invite_token=token).first()
    if not night:
        flash("Invalid invite link.", "error")
        return redirect(url_for("nights.movie_nights"))
    flash(f"You've been invited to '{night.name}'!", "info")
    return redirect(url_for("nights.movie_night_detail", night_id=night.id))


@nights_bp.route("/movie-nights/<int:night_id>/declare-winner/<int:film_id>",
                 methods=["POST"])
@login_required
def declare_winner(night_id, film_id):
    night = db.session.get(MovieNight, night_id)
    if not night or night.creator_id != current_user.id:
        flash("Only the creator can declare a winner.", "error")
        return redirect(url_for("nights.movie_night_detail", night_id=night_id))
    film = db.session.get(MovieNightFilm, film_id)
    if not film or film.night_id != night_id:
        flash("Film not found.", "error")
        return redirect(url_for("nights.movie_night_detail", night_id=night_id))
    night.winner_film_id = film_id
    db.session.commit()
    flash(f"'{film.movie_title}' declared the winner!", "success")
    return redirect(url_for("nights.movie_night_detail", night_id=night_id))


@nights_bp.route("/movie-nights/<int:night_id>/clear-winner", methods=["POST"])
@login_required
def clear_winner(night_id):
    night = db.session.get(MovieNight, night_id)
    if not night or night.creator_id != current_user.id:
        flash("Only the creator can change the winner.", "error")
        return redirect(url_for("nights.movie_night_detail", night_id=night_id))
    night.winner_film_id = None
    db.session.commit()
    return redirect(url_for("nights.movie_night_detail", night_id=night_id))
