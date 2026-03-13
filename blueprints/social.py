"""Social features: follow, like, feed, notifications, comments."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from helpers import create_notification, send_notification_email
from models import (Film, Follow, Movie, Notification, Review, ReviewComment,
                    ReviewLike, User, db)

social_bp = Blueprint("social", __name__)


@social_bp.route("/users/<int:user_id>/follow", methods=["POST"])
@login_required
def follow_user(user_id):
    if current_user.id == user_id:
        flash("You can't follow yourself.", "error")
        return redirect(url_for("profiles.user_profile",
                                username=current_user.username))
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
                f"Hi {target.username},\n\n{current_user.username} started "
                f"following you on MoviWebApp.\n\nVisit their profile: "
                f"/u/{current_user.username}\n")
        if not request.headers.get("HX-Request"):
            flash(f"You're now following {target.username}!", "success")
    db.session.commit()
    if request.headers.get("HX-Request"):
        is_following = Follow.query.filter_by(
            follower_id=current_user.id, followed_id=user_id).first() is not None
        return render_template("_follow_btn.html", target_user_id=user_id,
                               target_username=target.username,
                               is_following=is_following)
    return redirect(url_for("profiles.user_profile", username=target.username))


@social_bp.route("/reviews/<int:review_id>/like", methods=["POST"])
@login_required
def like_review(review_id):
    review = db.session.get(Review, review_id)
    if not review:
        if request.headers.get("HX-Request"):
            return "", 204
        flash("Review not found.", "error")
        return redirect(request.referrer or url_for("pages.index"))
    existing = ReviewLike.query.filter_by(
        user_id=current_user.id, review_id=review_id).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(ReviewLike(user_id=current_user.id, review_id=review_id))
        if review.user_id != current_user.id:
            film = Film.query.filter_by(title=review.movie_title).first()
            link = f"/film/{film.id}" if film else None
            create_notification(
                review.user_id, current_user.id, "like",
                f'{current_user.username} liked your review of '
                f'"{review.movie_title}".',
                link=link)
            review_owner = db.session.get(User, review.user_id)
            if review_owner and review_owner.email and \
               review_owner.email_notifications:
                send_notification_email(
                    review_owner.email,
                    f"{current_user.username} liked your review on MoviWebApp",
                    f"Hi {review_owner.username},\n\n"
                    f'{current_user.username} liked your review of '
                    f'"{review.movie_title}".\n')
    db.session.commit()
    if request.headers.get("HX-Request"):
        liked = ReviewLike.query.filter_by(
            user_id=current_user.id, review_id=review_id).first() is not None
        like_count = ReviewLike.query.filter_by(review_id=review_id).count()
        return render_template("_like_btn.html", review=review,
                               liked=liked, like_count=like_count)
    return redirect(request.referrer or url_for("pages.index"))


@social_bp.route("/feed")
@login_required
def feed():
    followed_ids = [f.followed_id for f in current_user.following]
    movies, reviews = [], []
    if followed_ids:
        movies = (Movie.query.filter(Movie.user_id.in_(followed_ids))
                  .order_by(Movie.date_added.desc()).limit(30).all())
        reviews = (Review.query.filter(Review.user_id.in_(followed_ids))
                   .order_by(Review.created_at.desc()).limit(20).all())
    suggested = []
    if len(movies) < 5:
        exclude = set(followed_ids) | {current_user.id}
        candidates = User.query.filter(User.id.notin_(exclude)).all()
        candidates.sort(key=lambda u: len(u.movies), reverse=True)
        suggested = candidates[:8]
    review_titles = [r.movie_title for r in reviews]
    film_map = {}
    if review_titles:
        for f in Film.query.filter(Film.title.in_(review_titles)).all():
            film_map[f.title] = f.id
    return render_template("feed.html", movies=movies, reviews=reviews,
                           film_map=film_map,
                           following_count=len(followed_ids),
                           suggested=suggested)


@social_bp.route("/notifications")
@login_required
def notifications():
    notifs = (Notification.query.filter_by(user_id=current_user.id)
              .order_by(Notification.created_at.desc()).limit(50).all())
    Notification.query.filter_by(
        user_id=current_user.id, read=False).update({"read": True})
    db.session.commit()
    return render_template("notifications.html", notifs=notifs)


# ── COMMENTS ─────────────────────────────────────────────────────────────────

@social_bp.route("/reviews/<int:review_id>/comment", methods=["POST"])
@login_required
def add_comment(review_id):
    review = db.session.get(Review, review_id)
    if not review:
        if request.headers.get("HX-Request"):
            return "", 204
        flash("Review not found.", "error")
        return redirect(request.referrer or url_for("pages.index"))
    body = request.form.get("body", "").strip()
    if not body or len(body) > 500:
        if request.headers.get("HX-Request"):
            return "", 400
        flash("Comment must be 1\u2013500 characters.", "error")
        return redirect(request.referrer or url_for("pages.index"))
    db.session.add(ReviewComment(
        review_id=review_id, user_id=current_user.id, body=body))
    db.session.commit()
    if request.headers.get("HX-Request"):
        return render_template("_review_comments.html", review=review)
    return redirect(request.referrer or url_for("pages.index"))


@social_bp.route("/reviews/<int:review_id>/comment/<int:comment_id>/delete",
                 methods=["POST"])
@login_required
def delete_comment(review_id, comment_id):
    comment = db.session.get(ReviewComment, comment_id)
    if not comment or comment.review_id != review_id:
        flash("Comment not found.", "error")
        return redirect(request.referrer or url_for("pages.index"))
    if comment.user_id != current_user.id:
        flash("You can only delete your own comments.", "error")
        return redirect(request.referrer or url_for("pages.index"))
    db.session.delete(comment)
    db.session.commit()
    if request.headers.get("HX-Request"):
        review = db.session.get(Review, review_id)
        return render_template("_review_comments.html", review=review)
    return redirect(request.referrer or url_for("pages.index"))
