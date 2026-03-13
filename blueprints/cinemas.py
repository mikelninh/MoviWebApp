"""Cinema pages: listing, detail, screening requests, votes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from models import Cinema, CinemaFilm, db

cinemas_bp = Blueprint("cinemas", __name__)


@cinemas_bp.route("/cinemas")
def cinemas():
    all_cinemas = Cinema.query.order_by(Cinema.name).all()
    return render_template("cinemas.html", cinemas=all_cinemas)


@cinemas_bp.route("/cinema/<slug>")
def cinema_detail(slug):
    cinema = Cinema.query.filter_by(slug=slug).first_or_404()
    now_showing = [f for f in cinema.films if f.show_type == "now_showing"]
    staff_picks = [f for f in cinema.films if f.show_type == "staff_pick"]
    requests_list = sorted(
        [f for f in cinema.films if f.show_type == "screening_request"],
        key=lambda f: f.votes, reverse=True)
    return render_template("cinema_detail.html", cinema=cinema,
                           now_showing=now_showing, staff_picks=staff_picks,
                           requests_list=requests_list)


@cinemas_bp.route("/cinema/<slug>/request", methods=["POST"])
@login_required
def cinema_request(slug):
    cinema = Cinema.query.filter_by(slug=slug).first_or_404()
    title = request.form.get("title", "").strip()
    if not title:
        flash("Film title required.", "error")
        return redirect(url_for("cinemas.cinema_detail", slug=slug))
    db.session.add(CinemaFilm(cinema_id=cinema.id, film_title=title,
                               show_type="screening_request", votes=0))
    db.session.commit()
    flash(f"Screening request for '{title}' submitted!", "success")
    return redirect(url_for("cinemas.cinema_detail", slug=slug))


@cinemas_bp.route("/cinema/<slug>/request/<int:film_id>/vote",
                  methods=["POST"])
@login_required
def cinema_vote(slug, film_id):
    cf = db.session.get(CinemaFilm, film_id)
    if not cf:
        flash("Film not found.", "error")
        return redirect(url_for("cinemas.cinema_detail", slug=slug))
    cf.votes = (cf.votes or 0) + 1
    db.session.commit()
    return redirect(url_for("cinemas.cinema_detail", slug=slug))
