"""Shared helpers, AI functions, and utilities used across blueprints."""

import copy
import json
import logging
import os
import re
import threading
import urllib.request as _urllib_req
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import urlparse

import anthropic as _anthropic_sdk
from flask import current_app, session as flask_session
from flask_mail import Message as MailMessage

from extensions import mail
from models import Film, FilmStreaming, Movie, Notification, db

logger = logging.getLogger("moviwebapp")

# ── AI HELPERS ────────────────────────────────────────────────────────────────

_ai_cache = {}
_ai_client = None


def _get_ai_client():
    global _ai_client
    if _ai_client is None:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if key:
            _ai_client = _anthropic_sdk.Anthropic(api_key=key)
    return _ai_client


def ai_review_synthesis(film_title: str, reviews: list) -> str | None:
    """1-2 sentence community consensus, or None."""
    client = _get_ai_client()
    if not client or len(reviews) < 2:
        return None
    cache_key = ("synth", film_title, len(reviews))
    if cache_key in _ai_cache:
        return _ai_cache[cache_key]
    try:
        texts = "\n".join(f"- {r.body}" for r in reviews[:15])
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=100,
            messages=[{"role": "user", "content":
                f"Summarize what people think of '{film_title}' in 1-2 sentences "
                f"based on:\n{texts}\nBe specific, no preamble."}])
        result = msg.content[0].text.strip()
        _ai_cache[cache_key] = result
        return result
    except Exception:
        logger.exception("AI review synthesis failed for '%s'", film_title)
        return None


def ai_why_love(user_movies: list, film) -> str | None:
    """1-sentence personalised reason, or None."""
    client = _get_ai_client()
    if not client or not user_movies:
        return None
    cache_key = ("why", film.id, len(user_movies))
    if cache_key in _ai_cache:
        return _ai_cache[cache_key]
    try:
        top = sorted([m for m in user_movies if m.rating and m.rating >= 4],
                     key=lambda m: m.rating, reverse=True)[:8]
        if not top:
            return None
        favs = ", ".join(m.title for m in top)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=80,
            messages=[{"role": "user", "content":
                f"Someone loves: {favs}. One sentence starting with "
                f"'You'll love this because' explaining why they'd enjoy "
                f"'{film.title}' ({film.genre or ''}). No preamble."}])
        result = msg.content[0].text.strip()
        _ai_cache[cache_key] = result
        return result
    except Exception:
        logger.exception("AI why_love failed for film %s", film.title)
        return None


def ai_taste_report(user_movies: list) -> str | None:
    """2-sentence taste profile, or None."""
    client = _get_ai_client()
    watched = [m for m in user_movies if m.status == "watched"]
    if not client or len(watched) < 5:
        return None
    cache_key = ("taste", len(watched), sum(m.id for m in watched[-20:]))
    if cache_key in _ai_cache:
        return _ai_cache[cache_key]
    try:
        top = sorted([m for m in watched if m.rating],
                     key=lambda m: m.rating, reverse=True)[:10]
        titles = ", ".join(m.title for m in (top or watched[:10]))
        gc = Counter(g for m in watched if m.genre for g in m.genre.split(", "))
        genres = ", ".join(g for g, _ in gc.most_common(3))
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=120,
            messages=[{"role": "user", "content":
                f"Write a 2-sentence film taste profile for someone who loves: "
                f"{titles}. Top genres: {genres}. Make it feel personal and "
                f"insightful. No preamble."}])
        result = msg.content[0].text.strip()
        _ai_cache[cache_key] = result
        return result
    except Exception:
        logger.exception("AI taste report failed")
        return None


def ai_year_summary(total: int, top_genres: list, top_directors: list,
                    avg_rating, year: int) -> str | None:
    """2-sentence year-in-film summary, or None."""
    client = _get_ai_client()
    if not client or total < 3:
        return None
    cache_key = ("year", total, year, str(top_genres[:2]))
    if cache_key in _ai_cache:
        return _ai_cache[cache_key]
    try:
        genres = ", ".join(g for g, _ in top_genres[:3]) if top_genres else "various"
        dirs = ", ".join(d for d, _ in top_directors[:2]) if top_directors else "various directors"
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=100,
            messages=[{"role": "user", "content":
                f"Write 2 sentences describing someone's {year} in film: "
                f"{total} films watched, top genres: {genres}, favourite "
                f"directors: {dirs}, avg rating: {avg_rating or 'N/A'}/5. "
                f"Make it feel celebratory and personal. No preamble."}])
        result = msg.content[0].text.strip()
        _ai_cache[cache_key] = result
        return result
    except Exception:
        logger.exception("AI year summary failed for %s", year)
        return None


# ── TRANSLATIONS ──────────────────────────────────────────────────────────────

TRANSLATIONS = {
    "de": {
        "Home": "Startseite", "Trending": "Trending", "Browse": "Entdecken",
        "Nights": "Filmabende", "My List": "Meine Liste", "Feed": "Feed",
        "Challenges": "Herausforderungen", "Login": "Anmelden",
        "Register": "Registrieren", "Logout": "Abmelden",
        "Import": "Importieren", "Settings": "Einstellungen",
        "Cinemas": "Kinos", "About": "\u00dcber uns", "Privacy": "Datenschutz",
        "Watched": "Gesehen", "Watchlist": "Merkliste", "Watching": "Schaue ich",
        "All": "Alle", "Add": "Hinzuf\u00fcgen", "Edit": "Bearbeiten",
        "Delete": "L\u00f6schen", "Post review": "Rezension posten",
        "Update review": "Rezension aktualisieren", "Your Feed": "Dein Feed",
        "Reviews": "Rezensionen", "Recently Added": "Zuletzt hinzugef\u00fcgt",
        "Recent Reviews": "Aktuelle Rezensionen",
        "No recent movies.": "Keine aktuellen Filme.",
        "No recent reviews.": "Keine aktuellen Rezensionen.",
        "Filter\u2026": "Filtern\u2026", "Search movies\u2026": "Filme suchen\u2026",
        "Movie title": "Filmtitel", "Rating": "Bewertung", "Status": "Status",
        "People to follow \u2014 find your people": "Personen folgen \u2014 finde deine Community",
        "You might also enjoy": "Das k\u00f6nnte dir auch gefallen",
        "Diary": "Tagebuch", "Recap": "R\u00fcckblick",
    }
}


def _t(key: str) -> str:
    lang = flask_session.get("lang", "en")
    if lang == "en":
        return key
    return TRANSLATIONS.get(lang, {}).get(key, key)


# ── UTILITY FUNCTIONS ─────────────────────────────────────────────────────────

def is_safe_redirect_url(target: str) -> bool:
    """Validate that redirect target is a relative URL on the same host."""
    if not target:
        return False
    parsed = urlparse(target)
    return parsed.scheme == "" and parsed.netloc == "" and target.startswith("/")


def compute_taste_match(movies_a: list, movies_b: list) -> int:
    if not movies_a or not movies_b:
        return 0
    a = {m.title.lower(): m.rating for m in movies_a}
    b = {m.title.lower(): m.rating for m in movies_b}
    common = set(a) & set(b)
    if not common:
        return 0
    jaccard = len(common) / len(set(a) | set(b))
    common_rated = [(a[t], b[t]) for t in common if a.get(t) and b.get(t)]
    if common_rated:
        avg_diff = sum(abs(ra - rb) for ra, rb in common_rated) / len(common_rated)
        score = (jaccard * 0.5 + (1 - avg_diff / 4) * 0.5) * 100
    else:
        score = jaccard * 100
    return round(min(score, 99))


def compute_profile_stats(movies: list) -> dict:
    watched = [m for m in movies if m.status == "watched"]
    rated = [m for m in movies if m.rating]
    avg_rating = round(sum(m.rating for m in rated) / len(rated), 1) if rated else None
    gc = Counter()
    for m in movies:
        if m.genre:
            for g in m.genre.split(", "):
                gc[g] += 1
    dc = Counter(m.director for m in movies if m.director)
    return {
        "watched": len(watched),
        "avg_rating": avg_rating,
        "top_genres": gc.most_common(3),
        "top_director": dc.most_common(1)[0][0] if dc else None,
    }


def compute_challenges(movies: list, review_count: int = 0) -> list:
    watched = [m for m in movies if m.status == "watched"]
    rated = [m for m in movies if m.rating]
    gc = Counter()
    for m in movies:
        if m.genre:
            for g in m.genre.split(", "):
                gc[g] += 1
    decades = {m.year[:3] for m in rated if m.year and len(m.year) >= 3}
    return [
        {"name": "First Steps",     "icon": "\u25ce", "desc": "Watch your first movie",               "progress": min(len(watched), 1),            "target": 1},
        {"name": "Getting Serious", "icon": "\u25ce", "desc": "Watch 10 movies",                      "progress": min(len(watched), 10),           "target": 10},
        {"name": "Film Buff",       "icon": "\u25ce", "desc": "Watch 25 movies",                      "progress": min(len(watched), 25),           "target": 25},
        {"name": "Cinephile",       "icon": "\u25c9", "desc": "Watch 50 movies",                      "progress": min(len(watched), 50),           "target": 50},
        {"name": "Harsh Critic",    "icon": "\u2605", "desc": "Rate 10 movies",                       "progress": min(len(rated), 10),             "target": 10},
        {"name": "Genre Hopper",    "icon": "\u25c8", "desc": "Watch films in 5 different genres",    "progress": min(len(gc), 5),                 "target": 5},
        {"name": "Anime Pilgrim",   "icon": "\u2726", "desc": "Watch 5 animated films",               "progress": min(gc.get("Animation", 0), 5), "target": 5},
        {"name": "Time Traveller",  "icon": "\u29d7", "desc": "Rate films from 3 different decades",  "progress": min(len(decades), 3),            "target": 3},
        {"name": "Critic",          "icon": "\u270d", "desc": "Write your first review",              "progress": min(review_count, 1),            "target": 1},
        {"name": "Voice",           "icon": "\u270d", "desc": "Write 5 reviews",                      "progress": min(review_count, 5),            "target": 5},
    ]


def get_or_create_film(title: str, meta: dict | None = None) -> Film:
    from data_manager import DataManager
    dm = DataManager()
    film = Film.query.filter_by(title=title).first()
    if not film:
        if meta is None:
            meta = dm.fetch_omdb_data(title)
        film = Film(title=title, year=meta.get("year"),
                    director=meta.get("director"), plot=meta.get("plot"),
                    poster_url=meta.get("poster_url"), genre=meta.get("genre"))
        db.session.add(film)
        db.session.flush()
    return film


def create_notification(user_id: int, from_user_id: int, ntype: str,
                        message: str, link: str | None = None):
    if user_id == from_user_id:
        return
    db.session.add(Notification(user_id=user_id, from_user_id=from_user_id,
                                type=ntype, message=message, link=link))


def send_notification_email(to_email: str, subject: str, body: str):
    """Send an email asynchronously, silently skip if mail not configured."""
    if not current_app.config.get("MAIL_SERVER"):
        return
    app = current_app._get_current_object()

    def _send():
        with app.app_context():
            try:
                msg = MailMessage(subject, recipients=[to_email], body=body)
                mail.send(msg)
            except Exception:
                logger.exception("Failed to send email to %s", to_email)
    threading.Thread(target=_send, daemon=True).start()


# ── STREAMING (JustWatch) ────────────────────────────────────────────────────

_JUSTWATCH_GQL = """
query GetStreamingOffers($title: String!, $country: Country!) {
  titleSearch(input: {searchQuery: $title, country: $country, first: 1}) {
    edges {
      node {
        ... on Movie {
          offers(country: $country, platform: WEB) {
            monetizationType
            package { clearName shortName }
            standardWebURL
          }
        }
      }
    }
  }
}
"""


def get_streaming(film) -> list:
    """Return list of {service, url, type} dicts, using 7-day cache."""
    try:
        cache = FilmStreaming.query.filter_by(film_id=film.id).first()
        now = datetime.utcnow()
        if cache and (now - cache.fetched_at) < timedelta(days=7):
            return json.loads(cache.data_json or "[]")
        jw_country = os.environ.get("JUSTWATCH_COUNTRY", "DE")
        payload = json.dumps({
            "query": _JUSTWATCH_GQL,
            "variables": {"title": film.title, "country": jw_country},
        }).encode("utf-8")
        req = _urllib_req.Request(
            "https://apis.justwatch.com/graphql",
            data=payload,
            headers={"Content-Type": "application/json",
                     "User-Agent": "MoviWebApp/1.0"},
        )
        with _urllib_req.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        offers = []
        edges = (data.get("data", {})
                     .get("titleSearch", {})
                     .get("edges", []))
        seen = set()
        for edge in edges:
            node = edge.get("node", {})
            for offer in node.get("offers", []):
                pkg = offer.get("package", {})
                name = pkg.get("clearName", "")
                url = offer.get("standardWebURL", "")
                mtype = offer.get("monetizationType", "")
                key = (name, mtype)
                if name and url and key not in seen:
                    seen.add(key)
                    offers.append({"service": name, "url": url, "type": mtype})
        data_str = json.dumps(offers)
        if cache:
            cache.data_json = data_str
            cache.fetched_at = now
        else:
            db.session.add(FilmStreaming(
                film_id=film.id, data_json=data_str, fetched_at=now))
        db.session.commit()
        return offers
    except Exception:
        logger.exception("JustWatch lookup failed for '%s'", film.title)
        return []


# ── FILM NEWS (RSS) ──────────────────────────────────────────────────────────

_news_cache: dict = {"data": [], "fetched_at": None}
_NEWS_SOURCES = [
    ("The Guardian",   "https://www.theguardian.com/film/rss"),
    ("Variety",        "https://variety.com/feed/"),
    ("The Film Stage", "https://thefilmstage.com/feed/"),
]


def fetch_film_news(limit: int = 18) -> list:
    now = datetime.utcnow()
    cached = _news_cache.get("data")
    fetched_at = _news_cache.get("fetched_at")
    if cached and fetched_at and (now - fetched_at).seconds < 1800:
        return cached
    articles = []
    for source_name, url in _NEWS_SOURCES:
        try:
            req = _urllib_req.Request(
                url, headers={"User-Agent": "MoviWebApp/1.0 film-news-reader"})
            with _urllib_req.urlopen(req, timeout=6) as resp:
                raw = resp.read()
            root = ET.fromstring(raw)
            for item in root.findall(".//item")[:6]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc_raw = (item.findtext("description") or "").strip()
                desc = re.sub(r"<[^>]+>", "", desc_raw)[:200].strip()
                pub = (item.findtext("pubDate") or "").strip()[:16]
                img = _extract_rss_image(item)
                if title and link:
                    articles.append({
                        "source": source_name, "title": title,
                        "link": link, "desc": desc, "pub": pub, "img": img,
                    })
        except Exception:
            logger.exception("Failed to fetch news from %s", source_name)
    articles = articles[:limit]
    _news_cache["data"] = articles
    _news_cache["fetched_at"] = now
    return articles


def _extract_rss_image(item) -> str | None:
    MEDIA = "http://search.yahoo.com/mrss/"
    best_w, best_url = 0, None
    for mc in item.findall(f"{{{MEDIA}}}content"):
        try:
            w = int(mc.get("width") or 0)
        except ValueError:
            w = 0
        url_mc = mc.get("url") or ""
        if url_mc and w > best_w:
            best_w, best_url = w, url_mc
    if best_url:
        return best_url
    mt = item.find(f"{{{MEDIA}}}thumbnail")
    if mt is not None:
        return mt.get("url")
    enc = item.find("enclosure")
    if enc is not None and "image" in (enc.get("type") or ""):
        return enc.get("url")
    CE_NS = "http://purl.org/rss/1.0/modules/content/"
    for raw_html in (
        item.findtext(f"{{{CE_NS}}}encoded") or "",
        item.findtext("description") or "",
    ):
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw_html)
        if m:
            return m.group(1)
    return None


# ── INSPIRATION LISTS ─────────────────────────────────────────────────────────

INSPIRATION_LISTS = [
    {"name": "Doomed Romance", "icon": "\u2665",
     "tagline": "Love that burns bright and ends in ashes.",
     "movies": [
         {"title": "In the Mood for Love", "year": "2000"},
         {"title": "Eternal Sunshine of the Spotless Mind", "year": "2004"},
         {"title": "Blue Valentine", "year": "2010"},
         {"title": "Atonement", "year": "2007"},
         {"title": "Brief Encounter", "year": "1945"},
         {"title": "Brokeback Mountain", "year": "2005"},
         {"title": "Portrait of a Lady on Fire", "year": "2019"},
         {"title": "Lost in Translation", "year": "2003"},
         {"title": "Normal People", "year": "2020"},
         {"title": "The Remains of the Day", "year": "1993"},
     ]},
    {"name": "Ghibli Forever", "icon": "\u2726",
     "tagline": "Studio Ghibli \u2014 where every frame is a painting.",
     "movies": [
         {"title": "Spirited Away", "year": "2001"},
         {"title": "Princess Mononoke", "year": "1997"},
         {"title": "My Neighbor Totoro", "year": "1988"},
         {"title": "Howl's Moving Castle", "year": "2004"},
         {"title": "Grave of the Fireflies", "year": "1988"},
         {"title": "Nausicaa of the Valley of the Wind", "year": "1984"},
         {"title": "Kiki's Delivery Service", "year": "1989"},
         {"title": "The Tale of Princess Kaguya", "year": "2013"},
         {"title": "Castle in the Sky", "year": "1986"},
         {"title": "Porco Rosso", "year": "1992"},
     ]},
    {"name": "Mind the Gap", "icon": "\u29d7",
     "tagline": "Time travel, fractured memory, and nonlinear minds.",
     "movies": [
         {"title": "Memento", "year": "2000"},
         {"title": "Arrival", "year": "2016"},
         {"title": "The Butterfly Effect", "year": "2004"},
         {"title": "Primer", "year": "2004"},
         {"title": "Coherence", "year": "2013"},
         {"title": "Predestination", "year": "2014"},
         {"title": "Looper", "year": "2012"},
         {"title": "12 Monkeys", "year": "1995"},
         {"title": "Source Code", "year": "2011"},
         {"title": "Timecrimes", "year": "2007"},
     ]},
    {"name": "Last Night on Earth", "icon": "\u25ce",
     "tagline": "Apocalypse, survival, and the end of everything.",
     "movies": [
         {"title": "Melancholia", "year": "2011"},
         {"title": "Take Shelter", "year": "2011"},
         {"title": "Beasts of the Southern Wild", "year": "2012"},
         {"title": "Children of Men", "year": "2006"},
         {"title": "The Road", "year": "2009"},
         {"title": "Annihilation", "year": "2018"},
         {"title": "I Am Legend", "year": "2007"},
         {"title": "28 Days Later", "year": "2002"},
         {"title": "Seeking a Friend for the End of the World", "year": "2012"},
         {"title": "4:44 Last Day on Earth", "year": "2011"},
     ]},
    {"name": "Ugly Beautiful", "icon": "\u25c8",
     "tagline": "Gritty realism, raw humanity, stories that hurt and heal.",
     "movies": [
         {"title": "Requiem for a Dream", "year": "2000"},
         {"title": "Moonlight", "year": "2016"},
         {"title": "City of God", "year": "2002"},
         {"title": "Shoplifters", "year": "2018"},
         {"title": "Parasite", "year": "2019"},
         {"title": "The Florida Project", "year": "2017"},
         {"title": "Beasts of No Nation", "year": "2015"},
         {"title": "The Wrestler", "year": "2008"},
         {"title": "Roma", "year": "2018"},
         {"title": "Tangerines", "year": "2013"},
     ]},
    {"name": "Men on the Edge", "icon": "\u25b3",
     "tagline": "Lone male protagonists slowly, magnificently unraveling.",
     "movies": [
         {"title": "Taxi Driver", "year": "1976"},
         {"title": "There Will Be Blood", "year": "2007"},
         {"title": "Whiplash", "year": "2014"},
         {"title": "The Lighthouse", "year": "2019"},
         {"title": "Uncut Gems", "year": "2019"},
         {"title": "Nightcrawler", "year": "2014"},
         {"title": "Falling Down", "year": "1993"},
         {"title": "Black Swan", "year": "2010"},
         {"title": "Pi", "year": "1998"},
         {"title": "A Beautiful Mind", "year": "2001"},
     ]},
    {"name": "Girls Who Run", "icon": "\u2192",
     "tagline": "Female escape, reinvention, and hitting the open road.",
     "movies": [
         {"title": "Thelma & Louise", "year": "1991"},
         {"title": "Wild", "year": "2014"},
         {"title": "Promising Young Woman", "year": "2020"},
         {"title": "Lady Bird", "year": "2017"},
         {"title": "Mustang", "year": "2015"},
         {"title": "Fish Tank", "year": "2009"},
         {"title": "The Favourite", "year": "2018"},
         {"title": "Whale Rider", "year": "2002"},
         {"title": "Persepolis", "year": "2007"},
         {"title": "Mona Lisa Smile", "year": "2003"},
     ]},
    {"name": "Anime That Breaks You", "icon": "\u25c9",
     "tagline": "Mind-bending, heartbreaking, unforgettable.",
     "movies": [
         {"title": "Perfect Blue", "year": "1997"},
         {"title": "Akira", "year": "1988"},
         {"title": "Ghost in the Shell", "year": "1995"},
         {"title": "Paprika", "year": "2006"},
         {"title": "Your Name", "year": "2016"},
         {"title": "A Silent Voice", "year": "2016"},
         {"title": "The Girl Who Leapt Through Time", "year": "2006"},
         {"title": "Millennium Actress", "year": "2001"},
         {"title": "5 Centimeters per Second", "year": "2007"},
         {"title": "Wolf Children", "year": "2012"},
     ]},
    {"name": "Invisible Wars", "icon": "\u25c7",
     "tagline": "Cold war, double agents, and the paranoia of loyalty.",
     "movies": [
         {"title": "Tinker Tailor Soldier Spy", "year": "2011"},
         {"title": "Bridge of Spies", "year": "2015"},
         {"title": "The Lives of Others", "year": "2006"},
         {"title": "Munich", "year": "2005"},
         {"title": "A Most Wanted Man", "year": "2014"},
         {"title": "The Spy Who Came in from the Cold", "year": "1965"},
         {"title": "Three Days of the Condor", "year": "1975"},
         {"title": "Syriana", "year": "2005"},
         {"title": "Zero Dark Thirty", "year": "2012"},
         {"title": "The Conversation", "year": "1974"},
     ]},
]


def _fetch_and_cache_posters():
    from data_manager import DataManager
    dm = DataManager()
    basedir = os.path.abspath(os.path.dirname(__file__))
    cache_path = os.path.join(basedir, "data", "inspiration_posters.json")
    lists = copy.deepcopy(INSPIRATION_LISTS)
    from app import app
    with app.app_context():
        for lst in lists:
            for movie in lst["movies"]:
                try:
                    meta = dm.fetch_omdb_data(movie["title"])
                    movie["poster_url"] = meta.get("poster_url", "")
                except Exception:
                    movie["poster_url"] = ""
                film = Film.query.filter(
                    db.func.lower(Film.title) == movie["title"].lower()
                ).first()
                movie["film_id"] = film.id if film else None
    try:
        with open(cache_path, "w") as f:
            json.dump(lists, f)
    except Exception:
        pass


def get_inspiration_with_posters() -> list:
    basedir = os.path.abspath(os.path.dirname(__file__))
    cache_path = os.path.join(basedir, "data", "inspiration_posters.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                lists = json.load(f)
            for lst in lists:
                for movie in lst["movies"]:
                    if not movie.get("film_id") or not movie.get("poster_url"):
                        film = Film.query.filter(
                            db.func.lower(Film.title) == movie["title"].lower()
                        ).first()
                        if film:
                            movie["film_id"] = film.id
                            if not movie.get("poster_url") and film.poster_url:
                                movie["poster_url"] = film.poster_url
            return lists
        except Exception:
            pass
    threading.Thread(target=_fetch_and_cache_posters, daemon=True).start()
    lists = copy.deepcopy(INSPIRATION_LISTS)
    for lst in lists:
        for movie in lst["movies"]:
            movie["poster_url"] = ""
            film = Film.query.filter(
                db.func.lower(Film.title) == movie["title"].lower()
            ).first()
            movie["film_id"] = film.id if film else None
    return lists
