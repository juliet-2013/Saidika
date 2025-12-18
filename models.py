from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    chats = db.relationship("Chat", backref="user", lazy=True)
    moods = db.relationship("Mood", backref="user", lazy=True)
    alerts = db.relationship("Alert", backref="user", lazy=True)

class Mood(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mood = db.Column(db.String(50))
    time = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(10))    # user | bot
    text = db.Column(db.Text)
    time = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    risk = db.Column(db.String(50))      # High | Moderate | Low
    message = db.Column(db.Text)
    time = db.Column(db.String(50))

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
