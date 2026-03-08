"""Seed social data: follows, movie nights, custom lists, review likes. Safe to re-run."""
from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timedelta
import random

from app import app, db
from models import (Follow, Movie, MovieNight, MovieNightFilm, MovieNightVote,
                    Review, ReviewLike, User, UserList, UserListItem)

random.seed(99)

FOLLOWS = [
    # (follower, followed)
    ("ninh",        "worldframes"),
    ("ninh",        "softcinema"),
    ("ninh",        "ghiblicore"),
    ("voidpilot",   "nolancore"),
    ("voidpilot",   "darkstardave"),
    ("nolancore",   "voidpilot"),
    ("nolancore",   "primerhead"),
    ("softcinema",  "ninh"),
    ("softcinema",  "periodpiece"),
    ("ghiblicore",  "ninh"),
    ("ghiblicore",  "worldframes"),
    ("worldframes", "oldboyfan"),
    ("worldframes", "a24head"),
    ("primerhead",  "nolancore"),
    ("primerhead",  "voidpilot"),
    ("screamjane",  "furyroaded"),
    ("a24head",     "softcinema"),
    ("a24head",     "ninh"),
    ("oldboyfan",   "worldframes"),
    ("chiaroscuro", "pulpkings"),
    ("pulpkings",   "chiaroscuro"),
]

REVIEWS = [
    # (username, movie_title, body)
    ("ninh",        "Parasite",
     "The elevator scene alone deserves an Oscar. Bong Joon-ho makes class warfare feel inevitable — like a trap everyone walks into with their eyes open."),
    ("ninh",        "Spirited Away",
     "I was 8 when I first saw this and didn't understand it. I'm 27 now and still don't fully understand it, and that's the point."),
    ("voidpilot",   "Blade Runner 2049",
     "Villeneuve did the impossible — made a worthy successor to Ridley's original. The scene with the hologram in the ruins broke me."),
    ("nolancore",   "The Dark Knight",
     "This isn't a superhero film. It's a crime epic about the nature of chaos, and Ledger's Joker is the most compelling villain in cinema history."),
    ("softcinema",  "Eternal Sunshine of the Spotless Mind",
     "The ending isn't sad. It's terrifying and beautiful simultaneously — knowing you'll hurt each other again and choosing it anyway."),
    ("ghiblicore",  "Princess Mononoke",
     "Miyazaki refuses to give you a villain. The forest wants to survive. The humans want to survive. Nobody's wrong and everybody loses."),
    ("worldframes", "City of God",
     "Shot like a music video, hits like a freight train. The chicken's POV opening is one of the greatest scene-setting devices ever put on film."),
    ("darkstardave", "Arrival",
     "The Sapir-Whorf hypothesis as grief therapy. I don't think I've ever felt genuinely smart walking out of a blockbuster before this one."),
    ("screamjane",  "Hereditary",
     "Toni Collette should have won every award in existence. The dinner table scene gave me actual nightmares for a week."),
    ("pulpkings",   "No Country for Old Men",
     "Chigurh asks if you've seen him before killing you. You realise you have — he's every slow dread you've ever felt at 3am."),
    ("a24head",     "Moonlight",
     "Three acts, three actors, one person. Barry Jenkins makes you feel the weight of every word never said between those men."),
    ("primerhead",  "Coherence",
     "$50,000 budget and it out-thinks every big-studio sci-fi of the decade. The dinner party from hell."),
    ("chiaroscuro", "Chinatown",
     "Polanski understood that noir isn't about mystery — it's about the moment you realise the mystery was never solvable."),
    ("oldboyfan",   "Parasite",
     "Watched it twice back to back. The second time you clock everything Bong hides in plain sight. Genius layered in genius."),
    ("truestorykat", "Whiplash",
     "The final drum performance is the most stressful 8 minutes in film. I held my breath through the entire thing."),
    ("furyroaded",  "Mad Max: Fury Road",
     "Two hours of sustained kinetic madness with more character in a single look than most films manage in two hours of dialogue."),
    ("laughreels",  "The Grand Budapest Hotel",
     "Anderson finally found the perfect form for his obsessions. Every frame is a gift box. The story inside is about loss."),
    ("spaghettimarc", "The Good the Bad and the Ugly",
     "The three-way standoff is 10 minutes long and contains zero dialogue. Leone understood silence better than any director alive."),
    ("goldenager",  "Rear Window",
     "Hitchcock basically invented parasocial anxiety 70 years early. Jeffries is us — the camera is his phone, the courtyard is the internet."),
    ("warreels",    "1917",
     "Mendes and Deakins pulled off something that shouldn't be possible. The journey feels genuinely life-sized. I forgot to breathe."),
    ("lalalaland",  "Sing Street",
     "The most purely joyful film I've seen in years. The 80s video sequences are ridiculous and perfect. Cried at the boat. No apologies."),
    ("rushfanatic", "Ford v Ferrari",
     "Bale and Damon are career-best here. The Le Mans sequence had me white-knuckling my armrest. Peak sports cinema."),
    ("periodpiece", "Pride and Prejudice",
     "Wright's 2005 adaptation is criminally underrated. The golden hour cinematography, Keira's performance — it understands Austen at a molecular level."),
    ("capepilled",  "Spider-Man: Into the Spider-Verse",
     "Every frame is a panel. Every cut is intentional. Animation cinema will be measuring itself against this for decades."),
    ("ninh",        "Good Will Hunting",
     "The bench scene is Damon and Williams at their absolute best. 'It's not your fault' — three words that still work every single time."),
    ("voidpilot",   "Arrival",
     "Villeneuve gets better with every film. This one uses language to fold time. 'What is time?' has never been asked with more tenderness."),
    ("softcinema",  "Her",
     "Jonze saw the loneliness of the internet era ten years before everyone else did. Joaquin Phoenix talking to a phone made me feel more than most human performances."),
    ("darkstardave", "2001: A Space Odyssey",
     "Kubrick made a film about evolution, technology, and god. It was 1968. Nobody knew what to do with it. We still don't."),
    ("screamjane",  "Midsommar",
     "The horror is the light. Ari Aster turns grief inside out and hangs it in broad daylight where you can't look away from it."),
    ("ghiblicore",  "Spirited Away",
     "No other film trusts children the way Miyazaki does. Chihiro doesn't need saving — she figures it all out herself."),
    ("a24head",     "Lady Bird",
     "Gerwig captured the specific pain of leaving a place you hate and realising you love it. Sacramento was always beautiful."),
    ("oldboyfan",   "Oldboy",
     "The corridor fight is one take. The revelation is genuinely shocking. Park Chan-wook weaponises genre against you."),
    ("chiaroscuro", "Mulholland Drive",
     "Lynch isn't trying to confuse you. He's trying to show you how dreams actually work — incomplete, emotionally true, narratively wrong."),
    ("nolancore",   "Memento",
     "The backwards structure isn't a gimmick — it IS the story. You experience Leonard's confusion firsthand. Nolan's most perfect film."),
    ("primerhead",  "Primer",
     "Carruth made this for $7,000 and it's still the most technically rigorous time travel film ever made. A flowchart doesn't ruin it."),
    ("worldframes", "Shoplifters",
     "Kore-eda asks what makes a family without announcing that's what he's asking. The final beach scene destroyed me quietly."),
]

MOVIE_NIGHTS = [
    {
        "creator": "ninh",
        "name": "Doomed Romance Double Feature",
        "date": "2026-03-15",
        "description": "Two films that will ruin you emotionally. Bring wine.",
        "films": [
            ("In the Mood for Love", "ninh"),
            ("Eternal Sunshine of the Spotless Mind", "softcinema"),
            ("Blue Valentine", "softcinema"),
        ],
        "votes": {
            "In the Mood for Love": ["ninh", "worldframes", "softcinema"],
            "Eternal Sunshine of the Spotless Mind": ["a24head", "ghiblicore"],
            "Blue Valentine": ["periodpiece"],
        }
    },
    {
        "creator": "voidpilot",
        "name": "Mind-Bender Marathon",
        "date": "2026-03-22",
        "description": "Start with Primer, end with Arrival. No sleep required but recommended.",
        "films": [
            ("Primer", "primerhead"),
            ("Arrival", "voidpilot"),
            ("Coherence", "primerhead"),
            ("Memento", "nolancore"),
        ],
        "votes": {
            "Arrival": ["voidpilot", "darkstardave", "nolancore"],
            "Primer": ["primerhead"],
            "Coherence": ["primerhead", "voidpilot"],
            "Memento": ["nolancore"],
        }
    },
    {
        "creator": "ghiblicore",
        "name": "Ghibli Night",
        "date": None,
        "description": "All Ghibli, all night. Totoro to Mononoke.",
        "films": [
            ("Spirited Away", "ghiblicore"),
            ("Princess Mononoke", "ninh"),
            ("My Neighbor Totoro", "ghiblicore"),
        ],
        "votes": {
            "Spirited Away": ["ghiblicore", "ninh", "worldframes", "a24head"],
            "Princess Mononoke": ["ninh", "ghiblicore"],
            "My Neighbor Totoro": ["softcinema"],
        }
    },
]

CUSTOM_LISTS = [
    {
        "user": "ninh",
        "name": "Essential World Cinema",
        "movies": ["Parasite", "In the Mood for Love", "City of God", "Amelie", "Shoplifters"],
    },
    {
        "user": "voidpilot",
        "name": "Hard Sci-Fi Only",
        "movies": ["Arrival", "Primer", "Blade Runner 2049", "Moon", "Ex Machina"],
    },
    {
        "user": "ghiblicore",
        "name": "Perfect for Kids & Adults",
        "movies": ["Spirited Away", "My Neighbor Totoro", "WALL-E", "Up", "Coco"],
    },
    {
        "user": "softcinema",
        "name": "Cry Freely",
        "movies": ["Her", "Eternal Sunshine of the Spotless Mind", "Before Sunrise", "Normal People"],
    },
    {
        "user": "screamjane",
        "name": "Too Scary To Watch Alone",
        "movies": ["Hereditary", "Midsommar", "The Shining", "Get Out", "The Silence of the Lambs"],
    },
]

REVIEW_LIKES = [
    # (username, movie_title, liked_by_list)
    ("ninh", "Parasite", ["worldframes", "oldboyfan", "a24head", "softcinema"]),
    ("ninh", "Spirited Away", ["ghiblicore", "worldframes"]),
    ("voidpilot", "Blade Runner 2049", ["darkstardave", "nolancore"]),
    ("nolancore", "The Dark Knight", ["voidpilot", "capepilled", "primerhead"]),
    ("softcinema", "Eternal Sunshine of the Spotless Mind", ["ninh", "a24head", "softcinema"]),
    ("ghiblicore", "Princess Mononoke", ["ninh", "ghiblicore", "worldframes"]),
    ("darkstardave", "Arrival", ["voidpilot", "primerhead", "nolancore"]),
    ("screamjane", "Hereditary", ["furyroaded"]),
    ("primerhead", "Coherence", ["nolancore", "voidpilot"]),
    ("chiaroscuro", "Chinatown", ["pulpkings", "goldenager"]),
    ("a24head", "Moonlight", ["ninh", "softcinema", "worldframes"]),
    ("oldboyfan", "Parasite", ["worldframes", "ninh"]),
    ("truestorykat", "Whiplash", ["lalalaland", "rushfanatic"]),
]


def get_user(username):
    return User.query.filter_by(username=username).first()


with app.app_context():
    db.create_all()

    # ── FOLLOWS ──────────────────────────────────────────────────────────────
    print("Seeding follows…")
    for follower_name, followed_name in FOLLOWS:
        follower = get_user(follower_name)
        followed = get_user(followed_name)
        if not follower:
            print(f"  (skip) user not found: {follower_name}")
            continue
        if not followed:
            print(f"  (skip) user not found: {followed_name}")
            continue
        exists = Follow.query.filter_by(
            follower_id=follower.id, followed_id=followed.id).first()
        if not exists:
            db.session.add(Follow(follower_id=follower.id, followed_id=followed.id))
            print(f"  + {follower_name} -> {followed_name}")
    db.session.commit()

    # ── REVIEWS ──────────────────────────────────────────────────────────────
    print("\nSeeding reviews…")
    now = datetime.utcnow()
    for i, (username, movie_title, body) in enumerate(REVIEWS):
        user = get_user(username)
        if not user:
            print(f"  (skip) user not found: {username}")
            continue
        exists = Review.query.filter_by(user_id=user.id, movie_title=movie_title).first()
        if exists:
            print(f"  ~ exists: {username} / {movie_title}")
            continue
        created_at = now - timedelta(days=random.uniform(0, 45))
        review = Review(user_id=user.id, movie_title=movie_title,
                        body=body, created_at=created_at)
        db.session.add(review)
        print(f"  + {username}: {movie_title[:40]}")
    db.session.commit()

    # ── REVIEW LIKES ─────────────────────────────────────────────────────────
    print("\nSeeding review likes…")
    for author_name, movie_title, likers in REVIEW_LIKES:
        author = get_user(author_name)
        if not author:
            continue
        review = Review.query.filter_by(
            user_id=author.id, movie_title=movie_title).first()
        if not review:
            continue
        for liker_name in likers:
            liker = get_user(liker_name)
            if not liker or liker.id == author.id:
                continue
            exists = ReviewLike.query.filter_by(
                user_id=liker.id, review_id=review.id).first()
            if not exists:
                db.session.add(ReviewLike(user_id=liker.id, review_id=review.id))
                print(f"  + {liker_name} liked {author_name}'s review of {movie_title}")
    db.session.commit()

    # ── MOVIE NIGHTS ─────────────────────────────────────────────────────────
    print("\nSeeding movie nights…")
    for night_data in MOVIE_NIGHTS:
        creator = get_user(night_data["creator"])
        if not creator:
            continue
        existing = MovieNight.query.filter_by(
            creator_id=creator.id, name=night_data["name"]).first()
        if existing:
            print(f"  ~ exists: {night_data['name']}")
            night = existing
        else:
            night = MovieNight(
                creator_id=creator.id,
                name=night_data["name"],
                date=night_data["date"],
                description=night_data["description"],
            )
            db.session.add(night)
            db.session.flush()
            print(f"  + night: {night_data['name']}")

        for title, suggester_name in night_data["films"]:
            existing_film = MovieNightFilm.query.filter_by(
                night_id=night.id, movie_title=title).first()
            if existing_film:
                film = existing_film
            else:
                suggester = get_user(suggester_name)
                from data_manager import DataManager
                dm = DataManager()
                meta = dm.fetch_omdb_data(title)
                film = MovieNightFilm(
                    night_id=night.id,
                    movie_title=title,
                    poster_url=meta.get("poster_url"),
                    suggested_by=suggester.id if suggester else None,
                )
                db.session.add(film)
                db.session.flush()
                print(f"    + film: {title}")

            for voter_name in night_data["votes"].get(title, []):
                voter = get_user(voter_name)
                if not voter:
                    continue
                existing_vote = MovieNightVote.query.filter_by(
                    user_id=voter.id, film_id=film.id).first()
                if not existing_vote:
                    db.session.add(MovieNightVote(
                        user_id=voter.id, film_id=film.id))

        db.session.commit()

    # ── CUSTOM LISTS ─────────────────────────────────────────────────────────
    print("\nSeeding custom lists…")
    for list_data in CUSTOM_LISTS:
        user = get_user(list_data["user"])
        if not user:
            continue
        existing = UserList.query.filter_by(
            user_id=user.id, name=list_data["name"]).first()
        if existing:
            print(f"  ~ exists: {list_data['name']}")
            lst = existing
        else:
            lst = UserList(user_id=user.id, name=list_data["name"])
            db.session.add(lst)
            db.session.flush()
            print(f"  + list: {list_data['name']} ({list_data['user']})")

        for title in list_data["movies"]:
            exists = UserListItem.query.filter_by(
                list_id=lst.id, movie_title=title).first()
            if not exists:
                from data_manager import DataManager
                dm = DataManager()
                meta = dm.fetch_omdb_data(title)
                db.session.add(UserListItem(
                    list_id=lst.id,
                    movie_title=title,
                    poster_url=meta.get("poster_url"),
                ))
                print(f"    + {title}")
        db.session.commit()

print("\nSocial seed done.")
