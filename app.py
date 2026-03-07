from flask import Flask, request, redirect, url_for, render_template
from models import db, Movie
from data_manager import DataManager

app = Flask(__name__)
data_manager = DataManager()

@app.route("/add", methods=["POST"])
def add_movie():
    title = request.form.get("title")

    # 1) fetch OMDb info here (omitted) and construct Movie:
    # omdb_data = ...
    movie = Movie(
        title=title,
        # year=omdb_data["Year"],
        # imdb_id=omdb_data["imdbID"],
        # poster_url=omdb_data["Poster"],
        user_id=1,  # or current_user.id etc.
    )

    # 2) persist via DataManager
    data_manager.add_movie(movie)
    return redirect(url_for("index"))
