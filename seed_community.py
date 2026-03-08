"""
seed_community.py — add rich reviews + follows to make the community feel alive.
Run once: python seed_community.py
"""
import random
from datetime import datetime, timedelta

from app import app, db
from models import Follow, Movie, Review, ReviewLike, User

# ── Reviews by persona ────────────────────────────────────────────────────────
# Format: (movie_title, rating, review_body)
REVIEWS = {
    "nolancore": [
        ("Interstellar", 5, "The IMAX sequence in the tesseract still breaks me. Nolan trusts his audience to feel before they understand — that's rare."),
        ("The Dark Knight", 5, "Ledger's Joker isn't a character, he's a force of nature. The interrogation scene is the best dialogue-driven scene of the decade."),
        ("Memento", 5, "First watch is a puzzle. Third watch is tragedy. The reverse chronology isn't a gimmick — it IS the point."),
        ("Inception", 4, "The layered dream logic holds up on rewatch in ways I didn't expect. The spinning top is the most argued-about prop in cinema since the briefcase in Pulp Fiction."),
        ("The Prestige", 5, "Both halves of the film are separately brilliant. Together they're devastating. Bowie as Tesla is casting perfection."),
        ("Dunkirk", 4.5, "No exposition. No backstory. Just the visceral arithmetic of survival. Zimmer's score is a clock wound too tight."),
        ("2001: A Space Odyssey", 5, "Kubrick figured out that the most terrifying thing in the universe is something that thinks. Still hasn't been topped."),
        ("Tenet", 3.5, "The action geometry is genuinely inventive and I respect the ambition. The emotional throughline got lost in the mechanism. Rewatchable though."),
        ("Full Metal Jacket", 5, "Two films in one, neither comfortable. The Parris Island section might be the most suffocating 40 minutes in cinema."),
    ],
    "ghiblicore": [
        ("Spirited Away", 5, "The bathhouse is the most detailed world in animation. Every background painting deserves its own frame. I grew up with this film and it keeps growing with me."),
        ("Princess Mononoke", 5, "Miyazaki refuses to give you a villain. The forest is dying and everyone has a reason. That's harder to write than any monster."),
        ("Howl's Moving Castle", 4.5, "Hisaishi's waltz alone justifies the film's existence. Sophie's transformation back and forth is quiet and devastating."),
        ("My Neighbor Totoro", 5, "There is no conflict. There is no villain. There is only childhood and wonder and a giant forest spirit who waits for you. Perfect."),
        ("Nausicaa of the Valley of the Wind", 5, "She doesn't fight to win — she fights to understand. Proto-Miyazaki, fully formed. The ohmu sequence is still breathtaking."),
        ("Castle in the Sky", 4.5, "The sequence where the robots tend the garden in silence is one of the most quietly beautiful things I've ever seen in animation."),
        ("The Tale of Princess Kaguya", 5, "Studio Ghibli's most adult film and their most heartbreaking. The animation style looks like it's being drawn live — rough edges, full of motion. Extraordinary."),
        ("Grave of the Fireflies", 5, "I have never recovered from this film and I don't expect to. Not a war film. A film about what war costs children."),
        ("Wolf Children", 4.5, "One of the few films that captures what parenting actually feels like — the fear, the letting go, the quiet devastation of watching them become themselves."),
        ("The Wind Rises", 4, "Miyazaki's most personal and most complicated film. He's mourning something and building something at the same time. The love story is gentle and the history is not."),
    ],
    "a24head": [
        ("Midsommar", 5, "The breakup scene at the start is the scariest part of the film. Aster shoots grief like a horror director because it IS horror."),
        ("Hereditary", 5, "The dinner table scene. The car scene. The attic scene. Aster has a gift for staging dread at the exact human scale that makes it unbearable."),
        ("Everything Everywhere All at Once", 5, "Made me cry in a way I didn't understand until two days later when I realized it was about my mother. No film has done that before."),
        ("The Witch", 4.5, "Eggers commits entirely to the period. The language, the light, the theology — all real. Black Phillip is the best character introduction of the decade."),
        ("Moonlight", 5, "Three chapters, one life, no wasted frame. The tenderness is what makes it devastating. Barry Jenkins shoots faces like they're landscapes."),
        ("Ex Machina", 4.5, "The dance scene is the most unsettling thing in the film and it shouldn't be. Garland is very good at making comfort feel wrong."),
        ("Lady Bird", 4.5, "The argument in the car. The application essay. The phone call at the end. Gerwig earns every one of these moments because she respects the small ones."),
        ("The Lighthouse", 5, "Defoe and Pattinson in an aspect ratio built to trap them. Every scene feels like it's about to crack. The foghorn is a character."),
        ("Men", 3, "The imagery is extraordinary. The allegory gets heavy-handed by the third act. Still glad it exists — Harper's house sequences are perfect."),
    ],
    "voidpilot": [
        ("2001: A Space Odyssey", 5, "The cut from bone to spacecraft is the greatest edit in cinema history. Everything after is a consequence of that one gesture."),
        ("Blade Runner", 5, "The final monologue by Rutger Hauer is still the most moving death speech ever filmed. The film earns it by letting the Replicants be more human than anyone."),
        ("Annihilation", 5, "Garland commits to the uncanny without explaining it. The lighthouse sequence is something I think about when I wake up at 3am."),
        ("Ex Machina", 5, "The Turing Test isn't really about AI — it's about what we project onto faces we want to believe in. Vikander gives the performance of the decade."),
        ("Arrival", 5, "The twist reframes time itself. The emotional weight hits on rewatch in a way that is genuinely rare. Villeneuve at his most precise."),
        ("Stalker", 5, "Tarkovsky trusts the camera more than dialogue. Three men walking. The Zone watching. Nothing happens and everything is at stake."),
        ("Under the Skin", 4.5, "Glazer strips performance to pure sensation. Johansson's face as an alien learning to feel — that is the film. No more explanation needed."),
        ("Moon", 4.5, "Sam Rockwell against Sam Rockwell is the best performance of 2009. The loneliness is real and the twists are earned. Jones's best film."),
        ("Coherence", 4, "Shot on a $50k budget with an improvised script and it out-thinks most sci-fi blockbusters. The dinner party as quantum horror."),
    ],
    "darkstardave": [
        ("Alien", 5, "The chest-burster scene works because we've spent an hour with these people. Giger's creature design is a Freudian nightmare made practical. Perfection."),
        ("The Thing", 5, "Carpenter's best film and the most paranoid monster movie ever made. The blood test scene is a masterclass in suspense construction."),
        ("Hereditary", 5, "The sound design alone deserves an award. The click. You know the click. I will never forgive it."),
        ("Suspiria (1977)", 5, "Argento isn't interested in logic. He's interested in color and sound and dread as pure sensation. The opening sequence is unlike anything else."),
        ("The Shining", 5, "Kubrick breaks every horror convention and arrives somewhere colder and stranger. Room 237 means something different every time."),
        ("Midsommar", 4.5, "A horror film with no darkness. Aster forces you to watch everything. The maypole sequence is beautiful and completely wrong."),
        ("Nope", 4.5, "Peele is making films about what it means to look — at spectacle, at cinema, at Black joy. The cloud is unforgettable once you understand what it is."),
        ("Green Room", 5, "The most efficiently terrifying film of the decade. Saulnier traps his cast and never lets them — or us — breathe."),
        ("Mandy", 4, "Nicolas Cage takes the grief seriously. The film around him is operatic and neon-soaked and completely committed to its own fever dream."),
    ],
    "screamjane": [
        ("Get Out", 5, "The sunken place is one of the great images in American cinema. Peele encoded everything about the film in that one visual."),
        ("Rosemary's Baby", 5, "Polanski turns domestic life into a conspiracy. Mia Farrow carries every frame. The horror is in how everyone she trusts betrays her — and we see it happening."),
        ("The Babadook", 5, "The monster is grief. The film earns this metaphor because it makes the monster real first. Jennifer Kent's direction is immaculate."),
        ("It Follows", 4.5, "The concept is so strong it could coast on premise alone. Mitchell doesn't — the cinematography and score create a genuinely unique texture."),
        ("A Quiet Place", 4, "The opening sequence is the bravest narrative choice in recent horror. Everything after earns that promise. Krasinski directing his own wife through that is extraordinary."),
        ("Us", 4.5, "The doppelganger mythology is richer than people gave it credit for. Lupita Nyong'o gives two performances and both are better than most actors manage in a career."),
        ("The Witch", 5, "The puritanical theology is real and that makes it terrifying. The family tears itself apart before anything supernatural happens."),
        ("Halloween (1978)", 5, "Carpenter invented vocabulary that horror still uses. The Shape is terrifying because he has no psychology — just presence and proximity."),
        ("Parasite", 5, "The best horror film disguised as a social comedy disguised as a thriller. The basement reveal is the most elegant plot mechanism in recent memory."),
    ],
    "worldframes": [
        ("Parasite", 5, "Bong Joon-ho writes poverty with architectural precision. Every object in that house means something. The stone is a burden from the first frame."),
        ("A Separation", 5, "The most morally complex film I've ever seen. Every character is right and everyone suffers for it. Farhadi makes you complicit in the verdict."),
        ("Capernaum", 5, "Zain's testimony to the court that brought him into existence is one of the great monologues in cinema. The kid is extraordinary."),
        ("The Square", 4, "Östlund dissects liberal art-world hypocrisy with anthropological cruelty. The gala sequence is the most uncomfortable 20 minutes in recent memory."),
        ("Yi Yi", 5, "Yang's three-generation epic is three hours of quiet precision. The boy photographing the backs of people's heads because they can't see them themselves. That's the film."),
        ("Burning", 5, "The most patient thriller ever made. Lee Chang-dong never confirms what happened and that restraint is the whole point. The barn burning sequence."),
        ("Shoplifters", 5, "Kore-eda makes a family out of people who shouldn't be one, then watches what happens when the world intrudes. The final shots are gutting."),
        ("Cold War", 5, "55 minutes. Black and white. Decades and borders and one impossible love. Pawlikowski compresses everything until it's almost unbearable."),
        ("Portrait of a Lady on Fire", 5, "The gaze as love language. Sciamma films looking as an act of intimacy. The memory of fire is the ending the film deserves."),
        ("Pan's Labyrinth", 5, "Del Toro insists the fantasy is real. The Pale Man is the most frightening creation in 21st century cinema. The ending asks you to decide."),
    ],
    "pulpkings": [
        ("Pulp Fiction", 5, "The structure is the point. Tarantino shuffles time to show that everything is happening simultaneously and nothing is more important than the present scene."),
        ("Goodfellas", 5, "The camera never stops moving because the life never stops moving. Scorsese's editing is cocaine. The helicopter shot is the beginning of the end."),
        ("Reservoir Dogs", 5, "A heist film with no heist. The tension is in what we don't see and what everyone knows that we don't. The ear scene is about nerve, not gore."),
        ("The Departed", 5, "The rat reveal. The elevator. Nicholson using his own mythology as a weapon. This is Scorsese writing with fire."),
        ("No Country for Old Men", 5, "Chigurh isn't the devil — he's logic applied without mercy. The Coens give us a Western where the West has already ended."),
        ("Fargo", 5, "Marge Gunderson is the most quietly heroic character in cinema. The Coens surround her with absurdity and she just... does her job."),
        ("Jackie Brown", 4.5, "Tarantino's most underrated film. Pam Grier commands every scene. The triple-POV cash exchange sequence is surgical filmmaking."),
        ("Drive", 5, "Refn strips the heist genre to its laconic core. The elevator scene is 90 seconds of the most perfectly calibrated violence in modern film."),
        ("Heat", 5, "The diner scene is two hours of film compressed into four minutes. Mann then stages the most realistic gunfight ever put on screen. Two masterpieces in one film."),
    ],
    "furyroaded": [
        ("Mad Max: Fury Road", 5, "Miller storyboarded every frame for years. The chase scene is the whole film. The whole film is the chase scene. Practical effects as moral statement."),
        ("Apocalypse Now", 5, "The film went insane making itself and that insanity is in every frame. Brando emerges from the darkness like an idea the jungle produced."),
        ("Full Metal Jacket", 5, "The first half is Kubrick. The second half is Vietnam. Neither is the other. The juxtaposition IS the film."),
        ("Saving Private Ryan", 5, "Spielberg broke the visual language of war on that beach and nobody has put it back together the same way since. The first 25 minutes are still unmatched."),
        ("Dunkirk", 4.5, "The structural time compression means the film feels like being inside the event. No backstory, no characters — just the relentless present of survival."),
        ("1917", 4.5, "The one-take conceit forces you to experience the duration. Deakins shoots the no-man's-land as a fever landscape. The journey earns the ending."),
        ("Platoon", 4.5, "Stone's most personal film. The two sergeants as competing moral poles is crude but effective. The village sequence is genuinely harrowing."),
        ("The Hurt Locker", 5, "Bigelow refuses the war film's usual catharsis. The last scene is the most quietly devastating ending of the decade — he chooses to go back."),
    ],
    "softcinema": [
        ("Portrait of a Lady on Fire", 5, "Three days of looking. The beach, the fire, the opera — Sciamma builds a memory palace for a love that history tried to erase. I cried twice."),
        ("Call Me by Your Name", 5, "Guadagnino shoots summer as a state of heightened consciousness. The peach scene is brave filmmaking. The fireplace monologue is one of cinema's great parent speeches."),
        ("Moonlight", 5, "The tenderness is the politics. Jenkins films Black masculinity with a gentleness that feels revolutionary. The diner scene is the most quietly brave scene of the decade."),
        ("The Before Trilogy", 5, "Three films made across 18 years that understand love better than any other screen romance. Linklater gives the actors time and trusts what grows."),
        ("Lost in Translation", 5, "The whisper. Coppola earns the ambiguity because she films Tokyo with the same loneliness she films the hotel. Two people not quite touching — that's the whole film."),
        ("Carol", 5, "Haynes films desire as attention. The way Blanchett looks at Mara. The gloves. The letter. Todd Haynes restores what the production codes took away."),
        ("Normal People", 4.5, "The most emotionally accurate depiction of young love I've ever seen on screen. The intimacy direction is extraordinary — you feel like you shouldn't be watching."),
        ("Brokeback Mountain", 5, "Ang Lee films the landscape as a third character. Everything they can't say to each other is in the mountains. The shirt scene is unbearable."),
        ("Her", 5, "The film understands loneliness better than most love stories understand love. Joaquin Phoenix falls for a voice and you completely believe him. Jonze's most vulnerable film."),
        ("Eternal Sunshine of the Spotless Mind", 5, "Kaufman and Gondry make forgetting look like a kind of grief. The bedroom dissolving into the beach. I've never recovered."),
    ],
    "laughreels": [
        ("The Grand Budapest Hotel", 5, "Anderson's most precise film. Every frame is a diorama, every performance a tiny clockwork miracle. Tony Revolori and Fiennes have extraordinary chemistry."),
        ("Game Night", 4, "The best pure comedy of the decade. The ceramic dog sequence escalates perfectly. Bateman and McAdams are a genuinely great comedy duo."),
        ("What We Do in the Shadows", 5, "Waititi found a tone so specific it spawned a franchise. The flat meetings. The cape. Vladislav's portrait. Endlessly quotable."),
        ("In Bruges", 5, "McDonagh writes dialogue that is simultaneously hilarious and devastating. The canal conversation about purgatory. The ending earns its tragedy."),
        ("The Nice Guys", 5, "Crowe and Gosling are the best comedy duo of the 21st century. Black writes banter that sounds accidental but is actually surgical. Severely underseen."),
        ("Knives Out", 5, "A whodunit where you learn whodunit in the first act — then it becomes something better. Johnson trusts his audience to enjoy the mechanism without the mystery."),
        ("Hot Fuzz", 5, "Edgar Wright's editing IS the comedy. The cornetto trilogy peaks here. The third act reveal reframes every previous scene and you have to immediately rewatch."),
        ("Three Billboards Outside Ebbing, Missouri", 4.5, "McDonagh refuses to let anyone be simply sympathetic. Rockwell earns his redemption arc. Hawkins is extraordinary at playing a woman with nothing left to lose."),
    ],
    "truestorykat": [
        ("I, Tonya", 4.5, "Robbie disappears into Tonya Harding and finds someone more complicated than the tabloid version. The fourth-wall breaks shouldn't work and they do."),
        ("Spotlight", 5, "McCarthy shoots journalism like a procedural thriller. The real horror is the filing cabinet — the knowledge that existed and was never used."),
        ("The Eyes of Tammy Faye", 4, "Chastain commits entirely. The makeup is extraordinary but it's the voice that does it — she finds the person inside the performance."),
        ("The Disaster Artist", 4.5, "Franco's best performance. The relationship between Tommy and Greg is both hilarious and genuinely sad — two people who need each other's delusions."),
        ("Vice", 3.5, "McKay's maximalism occasionally undermines his argument. Bale is phenomenal though — the physical transformation is extraordinary."),
        ("All the President's Men", 5, "The great journalism film. Redford and Hoffman as methodical investigators, Pakula making a parking garage terrifying. The methodology IS the drama."),
        ("Judas and the Black Messiah", 5, "Kaluuya gives one of the best performances in recent memory. The FBI as institutional horror. Shaka King refuses the biopic's usual consolations."),
    ],
    "spaghettimarc": [
        ("The Good the Bad and the Ugly", 5, "Leone uses silence as violence. The three-way standoff is the greatest scene in Western history and nothing before or since has matched its geometry."),
        ("Once Upon a Time in the West", 5, "The opening sequence kills off the biggest star in the film before the credits. Leone announces his intentions immediately — this is about time, not plot."),
        ("For a Few Dollars More", 4.5, "Van Cleef's revenge psychology adds a moral dimension the first film lacked. The pocket watch is as good an object as cinema has ever invented."),
        ("Fistful of Dollars", 4, "The blueprint. Eastwood's Man with No Name is pure cinematic ideology — competence as charisma, silence as mystery."),
        ("Django Unchained", 4.5, "Tarantino's love letter to the form comes with genuine fury attached. Waltz and DiCaprio are phenomenal. The ending is cathartic in a way that is complicated and correct."),
        ("True Grit (2010)", 4.5, "The Coens understand the genre better than almost anyone. Steinfeld is extraordinary — she outplays every adult in the film, including Bridges."),
        ("Unforgiven", 5, "Eastwood's elegy for the Western is the Western's greatest film. The barn scene. The ending. The cost of violence made real."),
    ],
    "lalalaland": [
        ("La La Land", 5, "The 'Lovely Night' dance sequence on the hilltop is one of the great romantic scenes in musical history. Chazelle films disappointment as beautiful as hope."),
        ("Whiplash", 5, "The relationship between Fletcher and Neiman is the most intense power dynamic in recent cinema. The final performance is exhilarating and terrifying simultaneously."),
        ("Singin' in the Rain", 5, "The title number is pure joy in 3 minutes. Donen and Kelly understood that cinema could do things no other art form could — they just... demonstrated it."),
        ("Mulholland Drive", 5, "Lynch makes the Hollywood dream machine eat itself. The audition scene ('No hay banda') is simultaneously beautiful and deeply wrong. The film refuses to let you rest."),
        ("Once", 4.5, "The simplest love story. Two musicians, a week, songs that needed to exist. Glen Hansard and Markéta Irglová wrote something that will outlast both of them."),
        ("Damien Chazelle makes pain look beautiful and I'm not sure that's entirely ethical", 4, "First Man is underseen. The landing sequence is the most restrained and therefore the most powerful depiction of the Moon landing on film."),
    ],
    "oldboyfan": [
        ("Oldboy", 5, "Park Chan-wook builds the most elaborate revenge structure in cinema and then burns it down to show you what revenge actually costs. The corridor fight. The ending."),
        ("The Handmaiden", 5, "Three-act structure where each act reframes the previous one. Sook-hee and Hideko's love story is the spine of the film and Park never lets it collapse under the plot."),
        ("Sympathy for Mr. Vengeance", 4.5, "The quietest and most devastating of the trilogy. Every death is an accident that follows logically from the previous accident. Tragedy as mechanism."),
        ("I Saw the Devil", 5, "Kim Jee-woon asked what happens when a hero becomes the monster to catch one, then answered it with 141 minutes of escalating dread."),
        ("A Bittersweet Life", 5, "Lee Byung-hun carries every frame. The gun-cleaning scene is a masterclass in composure before catastrophe. Korean noir at its most aesthetically precise."),
        ("Burning", 5, "Steven Yeun's smile is the most unsettling performance detail of the decade. Lee Chang-dong makes you complicit in the protagonist's paranoia."),
        ("Joint Security Area", 4.5, "Park's most humanist film. Cross-border friendship as an act of quiet political courage. The frozen frame at the end is devastating."),
    ],
    "primerhead": [
        ("Primer", 5, "Shot for $7,000. Carruth assumes you're smart enough to follow it and you're not — and then you rewatch it and you start to be. The most honest time travel film."),
        ("Upstream Color", 4.5, "Carruth's second film is about identity theft on a cellular level. It makes Primer look conventional. I've watched it four times and found something different each time."),
        ("Another Earth", 4, "The premise is the metaphor. Cahill doesn't explain the second Earth — she uses it as a visual correlative for the second chance you can never actually take."),
        ("Coherence", 4.5, "The improvised dialogue grounds the quantum horror completely. That it cost almost nothing and achieves this much is genuinely remarkable."),
        ("Arrival", 5, "The Sapir-Whorf hypothesis as emotional structure. Villeneuve and Heisserer found the science fiction premise that earns genuine tragedy. One of the decade's best films."),
        ("Dark (S1)", 5, "The most rigorously constructed time travel narrative in any medium. Four generations. Six time periods. Zero plot holes. German television as philosophical inquiry."),
        ("Ex Machina", 4.5, "Garland asks whether consciousness requires empathy and then refuses to answer. The dancing scene is the moment you realize who the real test subject is."),
    ],
    "chiaroscuro": [
        ("Schindler's List", 5, "The girl in the red coat. Spielberg shoots a black and white film about moral clarity, then introduces the only color you can't look away from."),
        ("Casablanca", 5, "The greatest screenplay ever written. Every character is at the intersection of history and personal desire. 'We'll always have Paris' earns its place in the language."),
        ("Vertigo", 5, "Hitchcock's most personal and most disturbing film. Scotty is both the villain and the victim. The spiral staircase is the subconscious made architectural."),
        ("Sunset Boulevard", 5, "A dead man narrates his own story. The opening is one of cinema's great structural choices. Holden and Swanson playing complicity and self-destruction — magnificent."),
        ("Tokyo Story", 5, "Ozu's greatest film and the most quietly heartbreaking. The tatami mat perspective makes you feel exactly the right size for the tragedy you're watching."),
        ("Wild Strawberries", 5, "Bergman's most compassionate film. The dream sequences as memory architecture. Sjöström in the final frame — everything he knows is in that face."),
        ("The Third Man", 5, "Carol Reed tilts the whole frame because the whole world is tilted. Welles appears and owns the film with twenty minutes of screen time. The zither is a character."),
        ("8½", 5, "Fellini making a film about not being able to make a film — and making the greatest film. Mastroianni as the director's doppelganger is the cleverest mise en abyme in cinema."),
    ],
    "rushfanatic": [
        ("Rush", 5, "Howard found a way to make you understand both men — Hunt's recklessness as appetite, Lauda's precision as survival. The rivalry IS the film."),
        ("Ford v Ferrari", 5, "Mangold stages the Le Mans sequences with documentary immediacy. Bale and Damon are magnificent, but it's the car noise that convinces you."),
        ("Senna", 5, "The greatest sports documentary ever made. Kapadia uses only archival footage and you still feel the inevitability building from the first frame."),
        ("Whiplash", 4.5, "Not a music film — a film about what obsessive pursuit costs. Fletcher as villain and teacher simultaneously. The finale is one of the great sequences."),
        ("Creed", 5, "Coogler brought new life to the Rocky universe by understanding that the real subject was always legacy and identity. Jordan is extraordinary."),
        ("Moneyball", 4.5, "The most intelligent sports film ever made. It's really about the epistemology of winning — how you know what you know. Sorkin's dialogue is its own sport."),
    ],
    "periodpiece": [
        ("Barry Lyndon", 5, "Kubrick shot by candlelight with NASA lenses. The result is the most beautiful film ever made. The narration as ironic counterpoint. The duel."),
        ("Amadeus", 5, "Salieri's jealousy as the frame allows Miloš Forman to write about mediocrity watching genius at close range. F. Murray Abraham gives the defining performance."),
        ("The Favourite", 5, "Lanthimos strips the period film of its decorum and finds the power struggle underneath. Weisz, Stone, and Colman circling each other — three distinct orbits."),
        ("Cold War", 5, "Pawlikowski condenses twenty years into 88 minutes and you feel every year passing. The black and white Polish landscapes are the most beautiful cinematography of the decade."),
        ("Atonement", 4.5, "The single tracking shot on the beach at Dunkirk is one of the great sequences in British cinema. Wright uses the form against itself."),
        ("The Piano", 5, "Campion films silence as a language and Ada speaks it fluently. Holly Hunter without a voice is more present than most performers with full dialogue."),
        ("Lincoln", 4.5, "Spielberg and DDL find the backroom politician who made the amendment possible. The vote sequence is as tense as any thriller. The Thirteenth Amendment as the real subject."),
    ],
    "capepilled": [
        ("The Dark Knight", 5, "Nolan made a crime film that happens to have Batman in it. The coin flip. The hospital. The truck flip. Heath Ledger gave us the decade's defining villain."),
        ("Spider-Man: Into the Spider-Verse", 5, "The most formally inventive superhero film ever made. Every Spider-Person has their own animation style. Miles' leap of faith is the best moment in any Marvel-adjacent film."),
        ("Logan", 5, "The Western as superhero film works because Mangold commits entirely. Wolverine as an aging man failing his body. Laura as the next chapter. The X-23 reveal."),
        ("Thor: Ragnarok", 4, "Waititi understood that the character needed to be freed from its own mythology. Cate Blanchett having the time of her life. The Immigrant Song sequence."),
        ("Avengers: Infinity War", 4.5, "Thanos works as a villain because the film commits to his perspective. The snap is the most audacious narrative choice a Marvel film has made."),
    ],
    "warreels": [
        ("Come and See", 5, "The most devastating war film ever made. Klimov doesn't frame war — he implicates the audience in it. Flyora's face aging across 136 minutes."),
        ("Apocalypse Now", 5, "Coppola's madness and the film's madness became the same madness. The river trip into the self. Kurtz's compound as the end of Western ideology."),
        ("Paths of Glory", 5, "Kubrick's fury is cold and precise. The officers at the feast while their men are court-martialed — the tracking shot across the battlefield before the assault."),
        ("The Thin Red Line", 5, "Malick turns war into a meditation on consciousness. Witt choosing goodness in a world organized around destruction. The most spiritual war film."),
        ("Letters from Iwo Jima", 5, "Eastwood films the same battle from the Japanese side and finds the same humanity and the same waste. Saigo writing home in the tunnels."),
        ("Hacksaw Ridge", 4, "Gibson stages the carnage with the same intensity Desmond refuses it. The tension between the two is the film's engine."),
    ],
    "goldenager": [
        ("Singin' in the Rain", 5, "Donald O'Connor's 'Make 'Em Laugh' is the most physically exhausting thing I've ever watched with a smile on my face. The greatest Hollywood musical."),
        ("All About Eve", 5, "Mankiewicz's dialogue is still the sharpest in American film. Every scene is a chess match disguised as a conversation. Bette Davis arriving late was the right call."),
        ("Sunset Boulevard", 5, "Norma Desmond is ready for her close-up because she always has been. Swanson plays delusion as tragedy and Wilder earns the tragedy."),
        ("Rear Window", 5, "Hitchcock's most self-aware film. Jefferies watching the courtyard is Hitchcock watching the audience watch. The medium is the message."),
        ("Some Like It Hot", 5, "The funniest film ever made. Lemmon and Curtis discover that impersonating women teaches them something about men they couldn't learn any other way."),
        ("12 Angry Men", 5, "One room, twelve men, 96 minutes. Lumet proves that moral argument is as suspenseful as any action. Fonda as the hold-out — patience as heroism."),
    ],
}

# ── Follow graph (who follows who beyond existing) ───────────────────────────
EXTRA_FOLLOWS = [
    ("nolancore", "primerhead"),
    ("nolancore", "voidpilot"),
    ("nolancore", "furyroaded"),
    ("ghiblicore", "softcinema"),
    ("ghiblicore", "worldframes"),
    ("ghiblicore", "lalalaland"),
    ("a24head", "screamjane"),
    ("a24head", "darkstardave"),
    ("a24head", "chiaroscuro"),
    ("voidpilot", "primerhead"),
    ("voidpilot", "nolancore"),
    ("darkstardave", "screamjane"),
    ("screamjane", "darkstardave"),
    ("worldframes", "chiaroscuro"),
    ("worldframes", "softcinema"),
    ("worldframes", "oldboyfan"),
    ("pulpkings", "spaghettimarc"),
    ("pulpkings", "laughreels"),
    ("spaghettimarc", "pulpkings"),
    ("spaghettimarc", "furyroaded"),
    ("softcinema", "lalalaland"),
    ("softcinema", "ghiblicore"),
    ("laughreels", "lalalaland"),
    ("laughreels", "pulpkings"),
    ("primerhead", "voidpilot"),
    ("primerhead", "nolancore"),
    ("chiaroscuro", "goldenager"),
    ("chiaroscuro", "worldframes"),
    ("rushfanatic", "furyroaded"),
    ("rushfanatic", "capepilled"),
    ("periodpiece", "chiaroscuro"),
    ("periodpiece", "goldenager"),
    ("capepilled", "nolancore"),
    ("capepilled", "darkstardave"),
    ("warreels", "furyroaded"),
    ("warreels", "chiaroscuro"),
    ("goldenager", "chiaroscuro"),
    ("oldboyfan", "worldframes"),
    ("oldboyfan", "darkstardave"),
    ("truestorykat", "worldframes"),
    ("lalalaland", "softcinema"),
    ("lalalaland", "ghiblicore"),
]


def seed():
    with app.app_context():
        users = {u.username: u for u in User.query.all()}

        # ── Reviews ──────────────────────────────────────────────────────────
        added_reviews = 0
        base_date = datetime.utcnow() - timedelta(days=180)

        for username, review_list in REVIEWS.items():
            user = users.get(username)
            if not user:
                continue
            user_movies = {m.title.lower(): m for m in Movie.query.filter_by(user_id=user.id).all()}
            existing = {(r.user_id, r.movie_title.lower()) for r in Review.query.filter_by(user_id=user.id).all()}

            for title, rating, body in review_list:
                if (user.id, title.lower()) in existing:
                    continue
                # Update movie rating if provided
                movie = user_movies.get(title.lower())
                if movie and rating:
                    movie.rating = float(rating)

                offset_days = random.randint(0, 170)
                review = Review(
                    user_id=user.id,
                    movie_title=title,
                    body=body,
                    created_at=base_date + timedelta(days=offset_days, hours=random.randint(0, 23)),
                )
                db.session.add(review)
                added_reviews += 1

        db.session.commit()
        print(f"Added {added_reviews} reviews")

        # ── Follow graph ─────────────────────────────────────────────────────
        added_follows = 0
        existing_follows = {(f.follower_id, f.followed_id) for f in Follow.query.all()}
        for follower_name, followed_name in EXTRA_FOLLOWS:
            fr = users.get(follower_name)
            fd = users.get(followed_name)
            if not fr or not fd:
                continue
            if (fr.id, fd.id) in existing_follows:
                continue
            db.session.add(Follow(follower_id=fr.id, followed_id=fd.id))
            existing_follows.add((fr.id, fd.id))
            added_follows += 1

        db.session.commit()
        print(f"Added {added_follows} follows")

        # ── ReviewLikes — everyone likes reviews from people they follow ─────
        all_reviews = Review.query.all()
        review_map = {}
        for r in all_reviews:
            review_map.setdefault(r.user_id, []).append(r)

        existing_likes = {(l.user_id, l.review_id) for l in ReviewLike.query.all()}
        added_likes = 0
        follows = Follow.query.all()

        for follow in follows:
            target_reviews = review_map.get(follow.followed_id, [])
            # Like 60-90% of followed user's reviews
            for rev in target_reviews:
                if (follow.follower_id, rev.id) in existing_likes:
                    continue
                if random.random() < 0.75:
                    db.session.add(ReviewLike(user_id=follow.follower_id, review_id=rev.id))
                    existing_likes.add((follow.follower_id, rev.id))
                    added_likes += 1

        db.session.commit()
        print(f"Added {added_likes} review likes")
        print("Done! Community is alive.")


if __name__ == "__main__":
    seed()
