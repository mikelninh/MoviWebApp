"""Authentication: register, login, logout, settings, password reset, onboarding."""

import secrets
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from data_manager import DataManager
from extensions import limiter
from helpers import (compute_taste_match, create_notification,
                     is_safe_redirect_url, send_notification_email)
from models import (Follow, Movie, Notification, Review, ReviewComment,
                    ReviewLike, User, db)

auth_bp = Blueprint("auth", __name__)
data_manager = DataManager()


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("pages.index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        if not name or not password:
            flash("Username and password are required.", "error")
            return render_template("register.html")
        if len(name) > 80:
            flash("Username too long (max 80 characters).", "error")
            return render_template("register.html")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html")
        user, created = data_manager.create_user(name, password)
        if not created:
            flash("Username already taken.", "error")
            return render_template("register.html")
        login_user(user)
        return redirect(url_for("auth.welcome"))
    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("pages.index"))
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
        if next_page and is_safe_redirect_url(next_page):
            return redirect(next_page)
        return redirect(url_for("profiles.get_movies", user_id=user.id))
    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "success")
    return redirect(url_for("pages.index"))


# ── PASSWORD RESET ───────────────────────────────────────────────────────────

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email:
            flash("Please enter your email address.", "error")
            return render_template("forgot_password.html")
        user = User.query.filter_by(email=email).first()
        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            send_notification_email(
                email,
                "MoviWebApp — Password Reset",
                f"Hi {user.username},\n\nClick this link to reset your password "
                f"(valid for 1 hour):\n\n{reset_url}\n\n"
                f"If you didn't request this, ignore this email.\n",
            )
        # Always show success to prevent email enumeration
        flash("If that email is registered, you'll receive a reset link shortly.", "success")
        return redirect(url_for("auth.login"))
    return render_template("forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_expires or \
       user.reset_token_expires < datetime.utcnow():
        flash("Invalid or expired reset link.", "error")
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("reset_password.html", token=token)
        user.set_password(password)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()
        flash("Password reset successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("reset_password.html", token=token)


# ── SETTINGS ─────────────────────────────────────────────────────────────────

@auth_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        email_notifs = bool(request.form.get("email_notifications"))
        current_user.email = email or None
        current_user.email_notifications = email_notifs
        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("auth.settings"))
    return render_template("settings.html")


@auth_bp.route("/settings/verify-email", methods=["POST"])
@login_required
def verify_email():
    if not current_user.email:
        flash("Please set an email address first.", "error")
        return redirect(url_for("auth.settings"))
    token = secrets.token_urlsafe(32)
    current_user.reset_token = token
    current_user.reset_token_expires = datetime.utcnow() + timedelta(hours=24)
    db.session.commit()
    verify_url = url_for("auth.confirm_email", token=token, _external=True)
    send_notification_email(
        current_user.email,
        "MoviWebApp — Verify Your Email",
        f"Hi {current_user.username},\n\nClick this link to verify your email "
        f"address (valid for 24 hours):\n\n{verify_url}\n\n"
        f"If you didn't request this, ignore this email.\n",
    )
    flash("Verification email sent.", "success")
    return redirect(url_for("auth.settings"))


@auth_bp.route("/verify-email/<token>")
def confirm_email(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_expires or \
       user.reset_token_expires < datetime.utcnow():
        flash("Invalid or expired verification link.", "error")
        return redirect(url_for("pages.index"))
    user.email_verified = True
    user.reset_token = None
    user.reset_token_expires = None
    db.session.commit()
    flash("Email verified successfully!", "success")
    return redirect(url_for("auth.settings"))


@auth_bp.route("/settings/delete-account", methods=["POST"])
@login_required
def delete_account():
    password = request.form.get("confirm_password", "")
    if not current_user.check_password(password):
        flash("Incorrect password. Account not deleted.", "error")
        return redirect(url_for("auth.settings"))
    user_id = current_user.id
    ReviewComment.query.filter_by(user_id=user_id).delete()
    ReviewLike.query.filter_by(user_id=user_id).delete()
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
    return redirect(url_for("pages.index"))


# ── ONBOARDING ───────────────────────────────────────────────────────────────

@auth_bp.route("/welcome")
@login_required
def welcome():
    return render_template("welcome.html")


@auth_bp.route("/welcome/search")
@login_required
def welcome_search():
    from models import Film
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return ""
    films = (Film.query
             .filter(Film.title.ilike(f"%{q}%"), Film.poster_url.isnot(None))
             .order_by(Film.year.desc())
             .limit(12).all())
    return render_template("_welcome_results.html", films=films)


@auth_bp.route("/welcome/pick", methods=["POST"])
@login_required
def welcome_pick():
    from models import Film
    film_ids = request.form.getlist("film_ids")
    if not film_ids:
        flash("Pick at least one film to continue.", "info")
        return redirect(url_for("auth.welcome"))
    for fid in film_ids[:8]:
        film = db.session.get(Film, int(fid))
        if not film:
            continue
        exists = Movie.query.filter_by(
            user_id=current_user.id, film_id=film.id).first()
        if not exists:
            db.session.add(Movie(
                title=film.title, user_id=current_user.id, film_id=film.id,
                rating=5, status="watched", year=film.year,
                director=film.director, plot=film.plot,
                poster_url=film.poster_url, genre=film.genre,
            ))
    db.session.commit()
    return redirect(url_for("auth.welcome_follow"))


@auth_bp.route("/welcome/follow")
@login_required
def welcome_follow():
    my_movies = Movie.query.filter_by(user_id=current_user.id).all()
    already = {f.followed_id for f in
               Follow.query.filter_by(follower_id=current_user.id).all()}
    candidates = User.query.filter(
        User.id != current_user.id, User.id.notin_(already)).all()
    scored = []
    for u in candidates:
        their_movies = Movie.query.filter_by(user_id=u.id).all()
        score = compute_taste_match(my_movies, their_movies)
        if score > 0:
            scored.append((u, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return render_template("welcome_follow.html", suggestions=scored[:8])


@auth_bp.route("/welcome/done", methods=["POST"])
@login_required
def welcome_done():
    follow_ids = request.form.getlist("follow_ids")
    for uid in follow_ids:
        uid = int(uid)
        exists = Follow.query.filter_by(
            follower_id=current_user.id, followed_id=uid).first()
        if not exists:
            db.session.add(Follow(
                follower_id=current_user.id, followed_id=uid))
            db.session.add(Notification(
                user_id=uid, from_user_id=current_user.id, type="follow",
                message=f"{current_user.username} started following you.",
                link=url_for("profiles.user_profile",
                             username=current_user.username),
            ))
    db.session.commit()
    flash(f"Welcome to MoviWebApp, {current_user.username}!", "success")
    return redirect(url_for("social.feed"))
