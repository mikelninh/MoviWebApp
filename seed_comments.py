from app import app, db
from models import User, Review, ReviewComment
import random
from datetime import datetime, timedelta

# Comment templates per "type" of review
AGREEMENTS = [
    "Completely agree — {}",
    "This is exactly how I felt. {}",
    "Yes! {} That's the perfect way to put it.",
    "Hard agree. {}",
    "You nailed it. {}",
]
PUSHBACKS = [
    "Interesting take, though I'd argue {}",
    "I can see that, but for me {}",
    "Respectfully disagree — {}",
    "That's fair, though {}",
]
ADDITIONS = [
    "Also worth mentioning: {}",
    "I'd add that {}",
    "What got me too was {}",
    "The thing I keep coming back to is {}",
]

# Rich, specific film-community comment bodies
COMMENT_BODIES = [
    # Agreements
    ("agree", "the score alone justifies it"),
    ("agree", "this is the one I keep recommending to people who say they don't like subtitles"),
    ("agree", "rewatched for the third time last week — still hits differently"),
    ("agree", "this is why I got into film in the first place"),
    ("agree", "every frame could be a photograph"),
    ("agree", "the ending is still the only ending that could have worked"),
    ("agree", "the tension in the third act is almost unbearable"),
    ("agree", "underrated cinematography — no one talks about the lighting"),
    ("agree", "first watched this at 3am and I genuinely couldn't move for twenty minutes after it ended"),
    ("agree", "the sound design does half the emotional work and no one ever mentions it"),
    ("agree", "it's the kind of film you watch and then immediately have to call someone about"),
    ("agree", "I've recommended this to six people now and every single one has come back changed"),
    ("agree", "this completely reset my expectations for what a film can do"),
    ("agree", "the pacing feels slow until you realise it's been doing something to you the whole time"),

    # Additions
    ("add", "the director's cut is even better if you can find it"),
    ("add", "had to take a walk after this one"),
    ("add", "saw this at Intimes last month — whole room was silent for ten minutes after"),
    ("add", "I showed this to my flatmate and they texted me three days later still thinking about it"),
    ("add", "the way the colour palette shifts in the second half is almost subliminal"),
    ("add", "watched it twice in one sitting — not recommended but also completely necessary"),
    ("add", "there's an interview with the DP that explains the visual choices and it made me love it even more"),
    ("add", "worth reading about the production — the making-of is almost as interesting as the film itself"),
    ("add", "the script is available online and it reads completely differently to how it plays on screen"),
    ("add", "a friend dragged me to this and I owe them everything"),
    ("add", "the first ten minutes are a masterclass in establishing tone"),
    ("add", "I went in completely blind and that's the only way to do it — don't read anything first"),
    ("add", "the final shot lives in my head rent-free"),
    ("add", "there's a deleted scene that would have changed the entire meaning — glad they cut it but also devastated"),

    # Pushbacks
    ("push", "I actually think the ambiguous ending weakens it slightly — felt like the filmmakers didn't commit"),
    ("push", "the performances do the heavy lifting and the script is thinner than people give it credit for"),
    ("push", "I loved it but the pacing in the second act dragged for me — might be a rewatch fix"),
    ("push", "it didn't land emotionally the first time — took a second watch for it to fully click"),
    ("push", "I can see why people love this but it felt slightly airless to me — maybe wrong headspace"),
    ("push", "it's brilliant but also the most exhausting film I've seen in years, in a way I'm still not sure was earned"),
    ("push", "the cinematography is stunning but I kept feeling like the characters were serving the visuals rather than the other way around"),
    ("push", "I need to sit with it longer — first watch left me admiring it more than feeling it"),

    # Standalone reactions
    ("agree", "I don't think I breathed for the last twenty minutes"),
    ("agree", "this is the film I'd use to convince someone that cinema is still the most powerful art form"),
    ("add", "the opening sequence is doing so much and no one talks about it"),
    ("add", "saw it at a rep cinema with a full house and the collective silence during the climax was something I'll never forget"),
    ("agree", "came for the hype, stayed because it earned every bit of it"),
    ("agree", "watched this when I was going through something and it felt like it was made specifically for that moment"),
    ("add", "the international cut is reportedly different — has anyone seen both?"),
    ("add", "the score by itself is worth the two hours — I have it on constantly"),
    ("push", "the ending is polarising and I landed in the 'not quite' camp — but the journey there is undeniable"),
    ("agree", "this is the kind of film that makes you want to immediately read about everyone who made it"),
    ("agree", "I went in knowing the twist and it still completely floored me"),
    ("add", "there's something about the aspect ratio choice that changes how claustrophobic it feels — noticed it on a rewatch"),
    ("add", "the supporting cast is doing incredible work that gets overshadowed by the lead performance — worth watching for them alone"),
    ("agree", "rewatched this specifically to show a friend and their reaction made me love it all over again"),
    ("push", "I think there's a slightly better version of this film where they trusted the audience more in the final act, but even this version is essential"),
    ("agree", "three days later I'm still thinking about one specific scene — you'll know the one"),
]

# Extra standalone one-liners to mix in
STANDALONES = [
    "The score alone justifies it.",
    "Saw this at Intimes last month. Whole room was silent for ten minutes after.",
    "This is the one I keep recommending to people who say they don't like subtitles.",
    "Rewatched for the third time last week. Still hits differently.",
    "This is why I got into film in the first place.",
    "The director's cut is even better if you can find it.",
    "Had to take a walk after this one.",
    "Every frame could be a photograph.",
    "The ending is still the only ending that could have worked.",
    "I showed this to my flatmate and they texted me three days later still thinking about it.",
    "The tension in the third act is almost unbearable.",
    "Underrated cinematography. No one talks about the lighting.",
    "I don't think I breathed for the last twenty minutes.",
    "Came for the hype, stayed because it earned every bit of it.",
    "The final shot lives in my head rent-free.",
    "Three days later I'm still thinking about one specific scene — you'll know the one.",
    "Went in completely blind and that's the only way to do it.",
    "The sound design does half the emotional work and no one ever mentions it.",
    "The first ten minutes are a masterclass in establishing tone.",
    "A friend dragged me to this and I owe them everything.",
]


def make_comment_body(review_body, comment_type):
    """Generate a comment body that references or responds to the review."""
    body_snippet = review_body.strip()[:60].rstrip(",. ") if review_body else ""

    if random.random() < 0.3:
        # Pure standalone
        return random.choice(STANDALONES)

    ctype, content = random.choice(COMMENT_BODIES)

    if ctype == "agree":
        template = random.choice(AGREEMENTS)
        return template.format(content)
    elif ctype == "add":
        template = random.choice(ADDITIONS)
        return template.format(content)
    else:
        template = random.choice(PUSHBACKS)
        return template.format(content)


def run():
    with app.app_context():
        existing = ReviewComment.query.count()
        if existing > 0:
            print(f"Comments already seeded ({existing} exist). Skipping.")
            return

        all_users = User.query.all()
        all_reviews = Review.query.all()

        if not all_users or not all_reviews:
            print("No users or reviews found.")
            return

        user_ids_by_id = {u.id: u for u in all_users}
        total_added = 0

        base_time = datetime.utcnow() - timedelta(days=180)

        for review in all_reviews:
            reviewer_id = review.user_id
            # Pick users who aren't the reviewer
            eligible = [u for u in all_users if u.id != reviewer_id]
            if len(eligible) < 2:
                continue

            # 2-3 comments per review
            n_comments = random.choices([2, 3], weights=[40, 60])[0]
            commenters = random.sample(eligible, min(n_comments, len(eligible)))

            # Spread comments over a plausible time window after the review
            review_time = review.created_at or base_time
            time_offsets = sorted(random.uniform(1, 72) for _ in commenters)

            for i, commenter in enumerate(commenters):
                body = make_comment_body(review.body, "agree")
                # Cap at 500 chars
                body = body[:500]
                comment_time = review_time + timedelta(hours=time_offsets[i])

                comment = ReviewComment(
                    review_id=review.id,
                    user_id=commenter.id,
                    body=body,
                    created_at=comment_time,
                )
                db.session.add(comment)
                total_added += 1

            # Flush every 50 reviews to avoid huge transactions
            if total_added % 150 == 0:
                db.session.flush()
                print(f"  ... {total_added} comments added so far")

        db.session.commit()
        final_count = ReviewComment.query.count()
        print(f"\nDone. Added {total_added} comments. Total in DB: {final_count}")


if __name__ == "__main__":
    run()
