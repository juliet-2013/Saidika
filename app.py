from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
from models import db, bcrypt, User, Mood, Chat, Alert
import random

app = Flask(__name__)
app.secret_key = "replace_this_with_a_random_secret"

# ------------------------
# DATABASE CONFIG
# ------------------------
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///saidika.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
bcrypt.init_app(app)

# ------------------------
# Helper: Emotion detection
# ------------------------
def detect_emotion(text):
    text = (text or "").lower()

    happy_words = ["happy", "great", "good", "excited", "joy", "awesome"]
    sad_words = ["sad", "unhappy", "down", "depressed", "cry", "hurt"]
    anxious_words = ["anxious", "worried", "scared", "nervous", "panic"]
    angry_words = ["angry", "mad", "frustrated", "annoyed"]
    hopeless_words = ["hopeless", "tired of life", "give up", "can't go on",
                      "suicide", "kill myself", "end my life", "die"]

    if any(w in text for w in happy_words):
        return "happy"
    if any(w in text for w in sad_words):
        return "sad"
    if any(w in text for w in anxious_words):
        return "anxious"
    if any(w in text for w in angry_words):
        return "angry"
    if any(w in text for w in hopeless_words):
        return "crisis"

    return "neutral"

# ------------------------
# LOGIN PROTECTION decorator
# ------------------------
def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

# ------------------------
# Ensure DB tables exist
# ------------------------
with app.app_context():
    db.create_all()

# ------------------------
# ROOT
# ------------------------
@app.route("/")
def root():
    return redirect(url_for("login"))

# ------------------------
# REGISTER
# ------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        existing = User.query.filter_by(email=email).first()
        if existing:
            error = "Account already exists."
        else:
            hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")
            new_user = User(email=email, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for("login"))

    return render_template("register.html", error=error)

# ------------------------
# LOGIN
# ------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            session["user"] = user.id

            # Clear in-memory UI chat (keeps DB history but not immediately shown in session)
            session.pop("chat_ui", None)

            # OPTIONAL: if you want to hide DB history on next login (UI-only), set flag
            # session["hide_history_on_login"] = True

            return redirect(url_for("home"))
        else:
            error = "Invalid email or password."

    return render_template("login.html", error=error)

# ------------------------
# LOGOUT
# ------------------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("chat_ui", None)
    return redirect(url_for("login"))

# ------------------------
# HOME
# ------------------------
@app.route("/home")
@login_required
def home():
    # use session-safe get to avoid SQLAlchemy legacy warning
    user = db.session.get(User, session["user"])
    email = user.email if user else "Unknown"
    return render_template("home.html", user=email)

# ------------------------
# CHAT (AI + crisis detection + DB history)
# ------------------------
@app.route("/chat", methods=["GET", "POST"])
@login_required
def chat():
    user_id = session["user"]

    # Load chat history from DB (chronological)
    db_messages = Chat.query.filter_by(user_id=user_id).order_by(Chat.id.asc()).all()
    chat_history = [{"sender": m.sender, "text": m.text, "time": m.time} for m in db_messages]

    # If developer wants to hide DB history on login, they can use session flag (optional).
    # Example: if session.pop("hide_history_on_login", False): chat_history = []

    if request.method == "POST":
        user_msg = request.form.get("message", "").strip()
        if user_msg:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Save user message to DB
            db.session.add(Chat(user_id=user_id, sender="user", text=user_msg, time=ts))
            db.session.commit()
            chat_history.append({"sender": "user", "text": user_msg, "time": ts})

            # Detect emotion + smart responses
            emotion = detect_emotion(user_msg)
            t = user_msg.lower()

            if "help" in t or "assist" in t or "support" in t:
                bot_reply = "🤝 Of course, I'm here to help you. What’s worrying you the most right now?"

            elif "not okay" in t or "hurt" in t or "pain" in t:
                bot_reply = "💛 I'm really sorry you're feeling this way. You’re not alone — tell me more."

            elif "alone" in t or "lonely" in t:
                bot_reply = "🤍 Feeling alone can be heavy. I'm here with you — you don’t have to carry this alone."

            elif emotion == "crisis":
                bot_reply = (
                    "🚨 I’m very concerned about your safety. If you feel in danger or are thinking about harming yourself, "
                    "please contact emergency services or a hotline. You deserve care and safety."
                )

                # Save alert record (High risk)
                alert = Alert(user_id=user_id, risk="High", message=user_msg, time=ts)
                db.session.add(alert)
                db.session.commit()

            else:
                responses = {
                    "happy": "😊 That's wonderful! What made you feel good today?",
                    "sad": "😢 I'm sorry you're feeling low. Want to talk about it?",
                    "anxious": "😟 Anxiety can be overwhelming. What's worrying you?",
                    "angry": "😠 Your feelings are valid. What triggered the anger?",
                    "neutral": "🙂 I'm here with you. Tell me more when you're ready."
                }
                bot_reply = responses.get(emotion, "I'm here with you. Tell me more.")

            # Save bot reply to DB
            ts2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.session.add(Chat(user_id=user_id, sender="bot", text=bot_reply, time=ts2))
            db.session.commit()
            chat_history.append({"sender": "bot", "text": bot_reply, "time": ts2})

    return render_template("chat.html", chat=chat_history)

# ------------------------
# MOOD TRACKER (RESTORED)
# ------------------------
@app.route("/tracker", methods=["GET", "POST"])
@login_required
def tracker():
    user_id = session["user"]

    if request.method == "POST":
        mood = request.form.get("mood", "")
        if mood:
            entry = Mood(
                mood=mood,
                time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                user_id=user_id
            )
            db.session.add(entry)
            db.session.commit()

    moods = Mood.query.filter_by(user_id=user_id).order_by(Mood.id.desc()).all()
    return render_template("tracker.html", mood_log=moods)

# ------------------------
# ADVISOR (REAL ALERTS)
# ------------------------
@app.route("/advisor")
@login_required
def advisor():
    # load all alerts (newest first)
    alerts = Alert.query.order_by(Alert.id.desc()).all()

    formatted = []
    for a in alerts:
        # use db.session.get to avoid legacy .get warning if you prefer, but a.user will work if relationship exists
        user = db.session.get(User, a.user_id)
        formatted.append({
            "email": user.email if user else "Unknown",
            "message": a.message,
            "risk": a.risk,
            "time": a.time,
            "user_id": a.user_id
        })

    return render_template("advisor.html", alerts=formatted)

# ------------------------
# THERAPIST REDIRECT PAGE
# ------------------------
@app.route("/therapist/<int:user_id>")
@login_required
def therapist(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return "User not found", 404
    return render_template("therapist.html", email=user.email)

# ------------------------
# REPORT
# ------------------------
@app.route("/report")
@login_required
def report():
    user_id = session["user"]
    moods = Mood.query.filter_by(user_id=user_id).all()

    labels = ["Happy", "Sad", "Anxious", "Stressed", "Calm"]
    counts = [
        sum(1 for m in moods if m.mood == "Happy"),
        sum(1 for m in moods if m.mood == "Sad"),
        sum(1 for m in moods if m.mood == "Anxious"),
        sum(1 for m in moods if m.mood == "Stressed"),
        sum(1 for m in moods if m.mood == "Calm"),
    ]

    return render_template("report.html", labels=labels, counts=counts)

# ------------------------
# RUN APP
# ------------------------
if __name__ == "__main__":
    app.run(debug=True)
