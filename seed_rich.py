"""
Rich seed — adds more movies, reviews, follows, and likes to existing users.
Safe to re-run: skips anything that already exists.
"""
from dotenv import load_dotenv
load_dotenv()

import random
from datetime import datetime, timedelta

from app import app, db
from data_manager import DataManager
from models import Film, Follow, Movie, Review, ReviewLike, User, UserList, UserListItem

random.seed(42)
dm = DataManager()


def u(name):
    return User.query.filter_by(username=name).first()


def add_movie(username, title, rating=None, status="watched", days_ago=None):
    user = u(username)
    if not user:
        return
    if Movie.query.filter_by(user_id=user.id, title=title).first():
        return
    meta = dm.fetch_omdb_data(title)
    date = datetime.utcnow() - timedelta(days=days_ago or random.randint(1, 400))
    film = Film.query.filter_by(title=title).first()
    if not film and meta:
        film = Film(title=title, year=meta.get("year"), director=meta.get("director"),
                    plot=meta.get("plot"), poster_url=meta.get("poster_url"),
                    genre=meta.get("genre"))
        db.session.add(film)
        db.session.flush()
    movie = Movie(
        user_id=user.id, title=title, rating=rating, status=status,
        date_added=date, film_id=film.id if film else None,
        year=meta.get("year") if meta else None,
        director=meta.get("director") if meta else None,
        plot=meta.get("plot") if meta else None,
        poster_url=meta.get("poster_url") if meta else None,
        genre=meta.get("genre") if meta else None,
    )
    db.session.add(movie)
    db.session.commit()
    print(f"  + {username}: {title}")


# ── MOVIES ────────────────────────────────────────────────────────────────────

MOVIES = {
    "ninh": [
        ("Burning", 5), ("The Handmaiden", 5), ("A Separation", 5),
        ("Portrait of a Lady on Fire", 4), ("Cache", 4), ("Yi Yi", 5),
        ("Spring Summer Fall Winter and Spring", 4), ("Still Walking", 4),
        ("The Wild Pear Tree", 4), ("Capernaum", 4), ("Atlantics", 4),
        ("The Wailing", 5), ("Okja", 3), ("Mother", 5),
    ],
    "voidpilot": [
        ("Interstellar", 5), ("Annihilation", 5), ("Dune", 5),
        ("The Martian", 4), ("Sunshine", 4), ("Contact", 5),
        ("Stalker", 5), ("Solaris", 4), ("District 9", 4),
        ("Children of Men", 5), ("Ex Machina", 5), ("Gravity", 4),
        ("Dune Part Two", 5), ("The Terminator", 4),
    ],
    "nolancore": [
        ("Inception", 5), ("Tenet", 4), ("Dunkirk", 5),
        ("Interstellar", 5), ("The Prestige", 5), ("Oppenheimer", 5),
        ("Heat", 5), ("Se7en", 5), ("Zodiac", 5),
        ("Gone Girl", 5), ("Fight Club", 5), ("Shutter Island", 4),
        ("Prisoners", 5), ("Sicario", 4),
    ],
    "softcinema": [
        ("Call Me by Your Name", 5), ("Aftersun", 5), ("Past Lives", 5),
        ("The Worst Person in the World", 4), ("Marriage Story", 4),
        ("Frances Ha", 4), ("20th Century Women", 4), ("Paterson", 5),
        ("Lost in Translation", 5), ("Before Sunset", 5), ("Before Midnight", 5),
        ("Normal People", 4), ("About Time", 4), ("Blue Is the Warmest Color", 4),
    ],
    "ghiblicore": [
        ("Castle in the Sky", 5), ("Kiki's Delivery Service", 5),
        ("Nausicaa of the Valley of the Wind", 5), ("Howl's Moving Castle", 5),
        ("The Wind Rises", 4), ("When Marnie Was There", 4),
        ("Wolf Children", 5), ("Your Name", 5), ("A Silent Voice", 5),
        ("In This Corner of the World", 4), ("The Red Turtle", 4),
        ("Ernest and Celestine", 4), ("The Tale of Princess Kaguya", 5),
    ],
    "worldframes": [
        ("Roma", 5), ("The Tree of Life", 4), ("Amarcord", 5),
        ("8½", 5), ("Tokyo Story", 5), ("Bicycle Thieves", 5),
        ("Pan's Labyrinth", 4), ("The Lives of Others", 5),
        ("A Prophet", 4), ("Winter Sleep", 4), ("Once Upon a Time in Anatolia", 4),
        ("Three Colors: Blue", 5), ("Three Colors: Red", 5),
    ],
    "darkstardave": [
        ("Under the Skin", 5), ("Enemy", 5), ("Upstream Color", 4),
        ("Possessor", 4), ("Crimes of the Future", 3), ("The Lighthouse", 4),
        ("First Reformed", 5), ("A Ghost Story", 4), ("mother!", 3),
        ("The Witch", 5), ("Dogtooth", 4), ("Holy Motors", 5),
        ("In the House", 4), ("Funny Games", 4),
    ],
    "screamjane": [
        ("The Babadook", 5), ("It Follows", 5), ("Suspiria", 5),
        ("The Conjuring", 4), ("Halloween", 4), ("A Quiet Place", 4),
        ("Us", 4), ("Get Out", 5), ("The Invisible Man", 4),
        ("Ari Aster: Beau Is Afraid", 3), ("X", 4), ("Pearl", 5),
        ("Talk to Me", 4), ("Smile", 3),
    ],
    "pulpkings": [
        ("Pulp Fiction", 5), ("Reservoir Dogs", 5), ("Jackie Brown", 4),
        ("Miller's Crossing", 5), ("Blood Simple", 5), ("Fargo", 5),
        ("L.A. Confidential", 5), ("Training Day", 4), ("Heat", 5),
        ("Goodfellas", 5), ("Casino", 4), ("The Departed", 5),
        ("Once Upon a Time in Hollywood", 4), ("True Romance", 5),
    ],
    "a24head": [
        ("Everything Everywhere All at Once", 5), ("The Lighthouse", 5),
        ("Midsommar", 4), ("Uncut Gems", 5), ("The Florida Project", 5),
        ("A24: Men", 3), ("Saint Maud", 4), ("The Farewell", 5),
        ("Waves", 4), ("First Cow", 4), ("Minari", 5),
        ("The Killing of a Sacred Deer", 4), ("Eighth Grade", 5),
    ],
    "primerhead": [
        ("Timecrimes", 5), ("Predestination", 4), ("The One I Love", 4),
        ("Triangle", 4), ("Synchronic", 3), ("Tenet", 3),
        ("Donnie Darko", 5), ("Looper", 4), ("12 Monkeys", 5),
        ("Interstellar", 4), ("Source Code", 4), ("About Time", 3),
        ("Frequencies", 4), ("Safety Not Guaranteed", 4),
    ],
    "chiaroscuro": [
        ("The Third Man", 5), ("Double Indemnity", 5), ("Laura", 5),
        ("Sunset Boulevard", 5), ("Touch of Evil", 5), ("The Maltese Falcon", 5),
        ("Rebecca", 5), ("Vertigo", 5), ("Rope", 4),
        ("Strangers on a Train", 5), ("Notorious", 4), ("Shadow of a Doubt", 4),
        ("Blue Velvet", 4), ("Mulholland Drive", 5),
    ],
    "oldboyfan": [
        ("Memories of Murder", 5), ("A Tale of Two Sisters", 5),
        ("I Saw the Devil", 5), ("The Man from Nowhere", 4),
        ("Train to Busan", 4), ("The Wailing", 5), ("Burning", 5),
        ("Silenced", 5), ("A Bittersweet Life", 5), ("The Yellow Sea", 4),
        ("Poetry", 4), ("Peppermint Candy", 5), ("Secret Sunshine", 4),
    ],
    "truestorykat": [
        ("Spotlight", 5), ("The Big Short", 5), ("Erin Brockovich", 5),
        ("All the President's Men", 5), ("Sully", 4), ("The Social Network", 5),
        ("Moneyball", 5), ("Hidden Figures", 4), ("The Imitation Game", 4),
        ("Catch Me If You Can", 4), ("Frost/Nixon", 4), ("Rush", 5),
        ("Bohemian Rhapsody", 3), ("Rocketman", 4),
    ],
    "furyroaded": [
        ("John Wick", 5), ("Fury", 4), ("Sicario", 5),
        ("Edge of Tomorrow", 5), ("The Raid", 5), ("Kill Bill Vol. 1", 5),
        ("Kill Bill Vol. 2", 4), ("Crouching Tiger Hidden Dragon", 4),
        ("Ip Man", 5), ("Oldboy", 5), ("Atomic Blonde", 4),
        ("Top Gun Maverick", 5), ("The Batman", 4), ("Extraction", 4),
    ],
    "laughreels": [
        ("What We Do in the Shadows", 5), ("The Nice Guys", 5),
        ("In Bruges", 5), ("Seven Psychopaths", 4), ("The Death of Stalin", 5),
        ("Game Night", 4), ("Knives Out", 5), ("The Favourite", 4),
        ("Hunt for the Wilderpeople", 5), ("Paddington 2", 5),
        ("Sorry to Bother You", 4), ("The Lobster", 4), ("Dolemite Is My Name", 4),
    ],
    "spaghettimarc": [
        ("Once Upon a Time in the West", 5), ("A Fistful of Dollars", 5),
        ("For a Few Dollars More", 5), ("Duck You Sucker", 4),
        ("True Grit", 5), ("Tombstone", 5), ("Unforgiven", 5),
        ("Butch Cassidy and the Sundance Kid", 5), ("The Magnificent Seven", 4),
        ("High Noon", 5), ("3:10 to Yuma", 4), ("Bone Tomahawk", 4),
        ("The Proposition", 5), ("Slow West", 4),
    ],
    "goldenager": [
        ("Casablanca", 5), ("Singin' in the Rain", 5), ("All About Eve", 5),
        ("The Apartment", 5), ("Sunset Boulevard", 5), ("Roman Holiday", 5),
        ("Some Like It Hot", 5), ("North by Northwest", 5),
        ("12 Angry Men", 5), ("On the Waterfront", 5),
        ("Strangers on a Train", 4), ("A Streetcar Named Desire", 4),
        ("To Kill a Mockingbird", 5), ("Dr. Strangelove", 5),
    ],
    "warreels": [
        ("Saving Private Ryan", 5), ("Apocalypse Now", 5), ("Full Metal Jacket", 5),
        ("Platoon", 4), ("The Thin Red Line", 5), ("Letters from Iwo Jima", 4),
        ("Das Boot", 5), ("Fury", 4), ("Come and See", 5),
        ("Dunkirk", 5), ("Hacksaw Ridge", 4), ("The Great Escape", 5),
        ("Bridge of Spies", 4), ("Midway", 3),
    ],
    "lalalaland": [
        ("La La Land", 5), ("Whiplash", 5), ("Begin Again", 4),
        ("Once", 5), ("Inside Llewyn Davis", 4), ("Dancer in the Dark", 5),
        ("Moulin Rouge", 4), ("Les Misérables", 4), ("Hamilton", 5),
        ("Tick Tick Boom", 5), ("Nashville", 4), ("Cabaret", 5),
        ("The Umbrellas of Cherbourg", 5), ("All That Jazz", 4),
    ],
    "rushfanatic": [
        ("Rush", 5), ("Le Mans 66", 5), ("Senna", 5), ("Ronin", 4),
        ("Baby Driver", 5), ("Drive", 5), ("Gone in 60 Seconds", 3),
        ("The Italian Job", 4), ("Bullitt", 5), ("Speed Racer", 4),
        ("Ferrari", 4), ("Overdrive", 2), ("Need for Speed", 2),
        ("The Fast and the Furious", 3),
    ],
    "periodpiece": [
        ("Atonement", 5), ("The Favourite", 5), ("Emma", 4),
        ("Sense and Sensibility", 5), ("Little Women", 5),
        ("Portrait of a Lady on Fire", 5), ("Mary Queen of Scots", 3),
        ("Downton Abbey", 4), ("Barry Lyndon", 5), ("Amadeus", 5),
        ("The Crown", 4), ("Victoria and Abdul", 3), ("Colette", 4),
        ("Gentleman Jack", 5),
    ],
    "capepilled": [
        ("Everything Everywhere All at Once", 5), ("The Dark Knight", 5),
        ("Logan", 5), ("Avengers Endgame", 4), ("Black Panther", 4),
        ("Thor Ragnarok", 4), ("Guardians of the Galaxy", 5),
        ("Doctor Strange in the Multiverse of Madness", 3),
        ("The Batman", 5), ("Spider-Man No Way Home", 5),
        ("Shazam", 4), ("The Boys", 5), ("Invincible", 5), ("V for Vendetta", 4),
    ],
    "mikel": [
        ("El Laberinto del Fauno", 5), ("La La Land", 4), ("Amélie", 5),
        ("Cinema Paradiso", 5), ("Life is Beautiful", 5), ("Bicycle Thieves", 5),
        ("The Great Beauty", 4), ("8½", 5), ("Nuovo Cinema Paradiso", 5),
        ("Mediterraneo", 4), ("Perfume: The Story of a Murderer", 4),
        ("Run Lola Run", 4), ("The Lives of Others", 5), ("Goodbye Lenin", 4),
    ],
}

# ── EXTRA REVIEWS ─────────────────────────────────────────────────────────────

EXTRA_REVIEWS = [
    ("voidpilot", "Annihilation",
     "Garland doesn't explain the shimmer. He doesn't need to. It's grief made physical — something that refracts everything that enters it. Haunting and correct."),
    ("voidpilot", "Dune",
     "Villeneuve treated Herbert's book like scripture. The sandworm scenes felt genuinely mythic. Cinema as ritual."),
    ("nolancore", "Oppenheimer",
     "Three hours and it never loses you. The Trinity sequence is one of cinema's great set-pieces. Nolan earned this one."),
    ("nolancore", "The Prestige",
     "Every single frame is a misdirection. You think you know what the trick is. You don't. The ending changes the whole film."),
    ("softcinema", "Past Lives",
     "Celine Song made a film about the lives we don't live. The final scene — both of them on the street — is perfect and unbearable."),
    ("softcinema", "Aftersun",
     "What is this film about? A holiday. Grief. The things we only understand too late. Paul Mescal will never not wreck me after this."),
    ("ghiblicore", "Your Name",
     "Shinkai made me cry over two people who haven't met. The comet scene is cinematic perfection. Animation as pure emotion."),
    ("ghiblicore", "The Tale of Princess Kaguya",
     "Takahata's farewell. Painted in brushstrokes that look like they're dissolving as you watch. Beautiful and devastating."),
    ("worldframes", "Tokyo Story",
     "Ozu holds his camera still and lets time do the work. What the film is 'about' is impossible to say. What it makes you feel is everything."),
    ("worldframes", "Roma",
     "Cuarón filmed his own childhood and made it universal. Cleo carrying the groceries uphill. The beach scene. The whole film is an apology and a love letter."),
    ("darkstardave", "Under the Skin",
     "Glazer strips Scarlett Johansson's star power and turns it into threat. The pool sequences are unlike anything else in cinema."),
    ("darkstardave", "Enemy",
     "Villeneuve made a film about doubling and dread and I think about the spider every single day. Gyllenhaal doing career-best subtle work."),
    ("screamjane", "It Follows",
     "Mitchell found the perfect horror metaphor — something that walks toward you at human speed, inevitably. You can outrun it. You can't escape it."),
    ("screamjane", "Pearl",
     "Ti West and Mia Goth created the most unhinged character study of the decade. That smile at the end. I want my mommy."),
    ("pulpkings", "Miller's Crossing",
     "The Coens at their most literary. Finney's Irish-mob poetry is so dense you need a flowchart. Tom Reagan is the most complex coward in film history."),
    ("pulpkings", "The Departed",
     "Scorsese playing genre cinema like jazz — riffing on Infernal Affairs and making something completely his own. The elevator. The end."),
    ("a24head", "Everything Everywhere All at Once",
     "The Daniels used the multiverse to say the most human thing: existence is absurd, and that's exactly why kindness matters. I ugly-cried."),
    ("a24head", "The Florida Project",
     "Baker filmed childhood with the exact texture childhood has — episodic, joyful, unaware of its own precarity. The ending is a gut-punch."),
    ("primerhead", "Donnie Darko",
     "Kelly made a film that rewards obsession. The Philosophy of Time Travel appendix isn't supplementary — it's the key. First watch bewilders. Third watch clarifies."),
    ("chiaroscuro", "Sunset Boulevard",
     "Wilder opens with a dead man narrating his own murder and somehow that's the least audacious thing in the film. Swanson is terrifying and tragic and perfect."),
    ("chiaroscuro", "Vertigo",
     "Hitchcock's most personal film is about a man trying to turn a woman into someone else. It is not a love story. It is an obsession story. Huge difference."),
    ("oldboyfan", "I Saw the Devil",
     "Kim Jee-woon made a film about what happens when the hunter becomes the hunted — and how becoming a monster destroys the only thing that made you human."),
    ("oldboyfan", "Memories of Murder",
     "Bong Joon-ho before Parasite was already making masterpieces. The final frame — the detective looking into the camera — has lived in my head for years."),
    ("truestorykat", "All the President's Men",
     "Pakula made a procedural so tense it feels like a thriller. Two men in a newsroom dismantling a presidency by following the money. This is what journalism looks like."),
    ("furyroaded", "The Raid",
     "Evans choreographed violence like Busby Berkeley choreographed musicals. There is a stairwell fight in this film that I have rewatched more times than I can count."),
    ("furyroaded", "John Wick",
     "Stahelski and Leitch created a new grammar for action cinema. The gun-fu sequences are so precisely edited they feel like choreography. Three films later, still the best."),
    ("laughreels", "What We Do in the Shadows",
     "Taika Waititi found the perfect form for his voice — the mockumentary of vampire flatmates is genuinely one of the funniest films made this century."),
    ("laughreels", "The Nice Guys",
     "Black wrote the best buddy-cop script since Lethal Weapon and then made it funnier and sadder than either of them. Gosling falling into the pool. Chef's kiss."),
    ("spaghettimarc", "Once Upon a Time in the West",
     "Leone's masterpiece took three hours to tell you that the age of the outlaw was over. Charles Bronson arriving to a harmonica sting. Perfect cinema."),
    ("goldenager", "Singin' in the Rain",
     "Kelly dances in actual rain on a soundstage and makes it feel like the most joyful thing ever committed to film. The joy is real. You can feel it."),
    ("warreels", "Come and See",
     "Klimov made a war film so visceral you feel complicit just watching it. Flyora's face aging across 90 minutes is the most affecting performance I've encountered."),
    ("warreels", "Apocalypse Now",
     "Coppola's breakdown became art. Brando appears for 15 minutes and rewrites what a villain can be. 'The horror, the horror' — it's not a metaphor. It's a diagnosis."),
    ("lalalaland", "Dancer in the Dark",
     "Von Trier made a musical that uses joy as a weapon. Björk carrying the entire emotional register of the film. The final song sequence broke something in me."),
    ("rushfanatic", "Drive",
     "Refn made an action film where the driver barely speaks and the violence is sudden and awful and the soundtrack makes it feel like a dream. Somehow it works completely."),
    ("periodpiece", "Atonement",
     "Wright's split-screen letter scene and the Dunkirk tracking shot in the same film. The entire structure is an act of atonement. Heartbreaking and formally bold."),
    ("capepilled", "Logan",
     "Mangold made the superhero film where everyone gets old and tired and dies. It felt like permission to take the genre seriously. Best X-Men film by miles."),
    ("mikel", "Cinema Paradiso",
     "Tornatore made a film about how cinema saves lives. The projection booth. The final reel of all the kisses the priest cut. I have never recovered."),
    ("ninh", "Yi Yi",
     "Yang's three-hour family portrait is one of the most complete visions of life on film. Yang-Yang photographing the backs of people's heads. We never see what's behind us."),
    ("softcinema", "Before Sunset",
     "Linklater's sequel is the rarest thing — better than the original. Two people rediscovering each other in real time. 'Baby, you are gonna miss that plane.' Yes."),
]

# ── EXTRA FOLLOWS ─────────────────────────────────────────────────────────────

EXTRA_FOLLOWS = [
    ("ninh", "oldboyfan"), ("ninh", "a24head"), ("ninh", "chiaroscuro"),
    ("voidpilot", "ghiblicore"), ("voidpilot", "a24head"),
    ("nolancore", "pulpkings"), ("nolancore", "furyroaded"),
    ("softcinema", "lalalaland"), ("softcinema", "periodpiece"),
    ("ghiblicore", "lalalaland"), ("ghiblicore", "softcinema"),
    ("worldframes", "chiaroscuro"), ("worldframes", "ninh"),
    ("darkstardave", "voidpilot"), ("darkstardave", "primerhead"),
    ("screamjane", "a24head"), ("screamjane", "darkstardave"),
    ("pulpkings", "nolancore"), ("pulpkings", "furyroaded"),
    ("a24head", "worldframes"), ("a24head", "oldboyfan"),
    ("primerhead", "darkstardave"), ("primerhead", "a24head"),
    ("chiaroscuro", "goldenager"), ("chiaroscuro", "worldframes"),
    ("oldboyfan", "ninh"), ("oldboyfan", "pulpkings"),
    ("truestorykat", "warreels"), ("truestorykat", "rushfanatic"),
    ("furyroaded", "pulpkings"), ("furyroaded", "capepilled"),
    ("laughreels", "softcinema"), ("laughreels", "ghiblicore"),
    ("spaghettimarc", "goldenager"), ("spaghettimarc", "warreels"),
    ("goldenager", "chiaroscuro"), ("goldenager", "spaghettimarc"),
    ("warreels", "truestorykat"), ("warreels", "furyroaded"),
    ("lalalaland", "softcinema"), ("lalalaland", "periodpiece"),
    ("rushfanatic", "furyroaded"), ("rushfanatic", "truestorykat"),
    ("periodpiece", "softcinema"), ("periodpiece", "lalalaland"),
    ("capepilled", "furyroaded"), ("capepilled", "a24head"),
    ("mikel", "worldframes"), ("mikel", "ninh"),
]

# ── EXTRA LIKES ───────────────────────────────────────────────────────────────

EXTRA_LIKES = [
    ("voidpilot",    "Annihilation",    ["ninh", "darkstardave", "primerhead"]),
    ("voidpilot",    "Dune",            ["nolancore", "furyroaded"]),
    ("nolancore",    "Oppenheimer",     ["voidpilot", "truestorykat", "warreels"]),
    ("softcinema",   "Past Lives",      ["ninh", "a24head", "lalalaland", "periodpiece"]),
    ("softcinema",   "Aftersun",        ["a24head", "worldframes", "darkstardave"]),
    ("ghiblicore",   "Your Name",       ["softcinema", "ninh", "lalalaland"]),
    ("worldframes",  "Roma",            ["ninh", "softcinema", "a24head"]),
    ("darkstardave", "Under the Skin",  ["voidpilot", "primerhead", "chiaroscuro"]),
    ("screamjane",   "It Follows",      ["darkstardave", "a24head"]),
    ("pulpkings",    "The Departed",    ["nolancore", "furyroaded", "chiaroscuro"]),
    ("a24head",      "Everything Everywhere All at Once", ["ninh", "ghiblicore", "softcinema", "capepilled"]),
    ("oldboyfan",    "Memories of Murder", ["ninh", "worldframes", "pulpkings"]),
    ("truestorykat", "All the President's Men", ["nolancore", "warreels"]),
    ("furyroaded",   "John Wick",       ["capepilled", "nolancore", "pulpkings"]),
    ("laughreels",   "What We Do in the Shadows", ["softcinema", "ghiblicore"]),
    ("spaghettimarc","Once Upon a Time in the West", ["goldenager", "pulpkings", "chiaroscuro"]),
    ("warreels",     "Come and See",    ["worldframes", "darkstardave", "nolancore"]),
    ("lalalaland",   "Dancer in the Dark", ["softcinema", "periodpiece"]),
    ("mikel",        "Cinema Paradiso", ["worldframes", "goldenager", "ninh"]),
    ("ninh",         "Yi Yi",           ["worldframes", "softcinema", "chiaroscuro"]),
]


with app.app_context():
    db.create_all()

    # ── MOVIES ────────────────────────────────────────────────────────────────
    print("=== Seeding movies ===")
    for username, films in MOVIES.items():
        for title, rating in films:
            add_movie(username, title, rating=rating,
                      days_ago=random.randint(1, 500))

    # ── REVIEWS ───────────────────────────────────────────────────────────────
    print("\n=== Seeding reviews ===")
    now = datetime.utcnow()
    for username, movie_title, body in EXTRA_REVIEWS:
        user = u(username)
        if not user:
            print(f"  (skip) {username}")
            continue
        if Review.query.filter_by(user_id=user.id, movie_title=movie_title).first():
            continue
        created = now - timedelta(days=random.uniform(1, 60))
        db.session.add(Review(user_id=user.id, movie_title=movie_title,
                              body=body, created_at=created))
        print(f"  + {username}: {movie_title[:45]}")
    db.session.commit()

    # ── FOLLOWS ───────────────────────────────────────────────────────────────
    print("\n=== Seeding follows ===")
    for follower_name, followed_name in EXTRA_FOLLOWS:
        follower = u(follower_name)
        followed = u(followed_name)
        if not follower or not followed:
            continue
        if Follow.query.filter_by(follower_id=follower.id,
                                   followed_id=followed.id).first():
            continue
        db.session.add(Follow(follower_id=follower.id, followed_id=followed.id))
        print(f"  + {follower_name} -> {followed_name}")
    db.session.commit()

    # ── LIKES ─────────────────────────────────────────────────────────────────
    print("\n=== Seeding likes ===")
    for author_name, movie_title, likers in EXTRA_LIKES:
        author = u(author_name)
        if not author:
            continue
        review = Review.query.filter_by(
            user_id=author.id, movie_title=movie_title).first()
        if not review:
            continue
        for liker_name in likers:
            liker = u(liker_name)
            if not liker or liker.id == author.id:
                continue
            if ReviewLike.query.filter_by(user_id=liker.id,
                                           review_id=review.id).first():
                continue
            db.session.add(ReviewLike(user_id=liker.id, review_id=review.id))
            print(f"  + {liker_name} liked {author_name}'s review of {movie_title}")
    db.session.commit()

    # ── FINAL COUNTS ──────────────────────────────────────────────────────────
    from models import Film as F
    print(f"""
=== Done ===
  Users:   {User.query.count()}
  Films:   {F.query.count()}
  Movies:  {Movie.query.count()}
  Reviews: {Review.query.count()}
  Follows: {Follow.query.count()}
  Likes:   {ReviewLike.query.count()}
""")
