"""Custom user lists."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from data_manager import DataManager
from models import Film, User, UserList, UserListItem, db

lists_bp = Blueprint("lists", __name__)
data_manager = DataManager()


@lists_bp.route("/lists")
def lists_directory():
    all_lists = (UserList.query.join(User, UserList.user_id == User.id).all())
    all_lists = sorted(all_lists, key=lambda l: len(l.items), reverse=True)
    return render_template("lists_directory.html", all_lists=all_lists)


@lists_bp.route("/users/<int:user_id>/lists/create", methods=["POST"])
@login_required
def create_list(user_id):
    if current_user.id != user_id:
        flash("Not allowed.", "error")
        return redirect(url_for("profiles.get_movies", user_id=user_id))
    name = request.form.get("name", "").strip()
    if not name:
        flash("List needs a name.", "error")
        return redirect(url_for("profiles.get_movies", user_id=user_id))
    lst = UserList(user_id=user_id, name=name)
    db.session.add(lst)
    db.session.commit()
    flash(f"List '{name}' created.", "success")
    return redirect(url_for("lists.view_list", list_id=lst.id))


@lists_bp.route("/lists/<int:list_id>")
def view_list(list_id):
    lst = db.session.get(UserList, list_id)
    if not lst:
        flash("List not found.", "error")
        return redirect(url_for("pages.index"))
    enriched_items = []
    for item in lst.items:
        film = Film.query.filter(
            db.func.lower(Film.title) == item.movie_title.lower()).first()
        enriched_items.append({"item": item, "film": film})
    return render_template("user_list.html", lst=lst,
                           enriched_items=enriched_items)


@lists_bp.route("/lists/<int:list_id>/add", methods=["POST"])
@login_required
def add_to_list(list_id):
    lst = db.session.get(UserList, list_id)
    if not lst or lst.user_id != current_user.id:
        flash("Not allowed.", "error")
        return redirect(url_for("pages.index"))
    title = request.form.get("title", "").strip()
    if not title:
        flash("Title required.", "error")
        return redirect(url_for("lists.view_list", list_id=list_id))
    meta = data_manager.fetch_omdb_data(title)
    db.session.add(UserListItem(list_id=list_id, movie_title=title,
                                poster_url=meta.get("poster_url")))
    db.session.commit()
    flash(f"'{title}' added to list.", "success")
    return redirect(url_for("lists.view_list", list_id=list_id))


@lists_bp.route("/list/add-film", methods=["POST"])
@login_required
def add_to_list_by_name():
    list_id = request.form.get("list_id", type=int)
    film_title = request.form.get("film_title", "").strip()
    poster_url = request.form.get("poster_url", "").strip()
    if not list_id or not film_title:
        flash("Invalid request.", "error")
        return redirect(request.referrer or url_for("pages.index"))
    ul = UserList.query.filter_by(id=list_id, user_id=current_user.id).first()
    if not ul:
        flash("List not found.", "error")
        return redirect(request.referrer or url_for("pages.index"))
    existing = UserListItem.query.filter_by(
        list_id=list_id, movie_title=film_title).first()
    if not existing:
        db.session.add(UserListItem(
            list_id=list_id, movie_title=film_title, poster_url=poster_url))
        db.session.commit()
        flash(f"Added to \u201c{ul.name}\u201d.", "success")
    else:
        flash("Already in that list.", "info")
    return redirect(request.referrer or url_for("pages.index"))


@lists_bp.route("/lists/<int:list_id>/remove/<int:item_id>", methods=["POST"])
@login_required
def remove_from_list(list_id, item_id):
    lst = db.session.get(UserList, list_id)
    if not lst or lst.user_id != current_user.id:
        flash("Not allowed.", "error")
        return redirect(url_for("pages.index"))
    item = db.session.get(UserListItem, item_id)
    if item and item.list_id == list_id:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for("lists.view_list", list_id=list_id))
