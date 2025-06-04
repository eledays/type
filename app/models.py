from app import app, db

import random
from datetime import datetime


class Word(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(128), unique=True, nullable=False)  # _ instead of missing letters
    explanation = db.Column(db.String(2048))
    answers = db.Column(db.JSON, nullable=False)  # First - correct answer
    task_number = db.Column(db.Integer)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    category = db.relationship('Category', back_populates='words')
    mistake = db.Column(db.Boolean, default=False)

    def get_answers(self) -> list:
        """
        Returns the answers in a random order.
        """
        answers = self.answers[:]
        random.shuffle(answers)
        return answers
    
    def get_html(self) -> str:
        """
        Returns the word with missing letters highlighted in HTML format.
        """
        return self.word.replace('_', '<span class="missing-letter"> </span>')
    

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    words = db.relationship('Word', back_populates='category', lazy='dynamic')
    

class Action(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    word_id = db.Column(db.Integer)
    action = db.Column(db.Integer, nullable=False)
    datetime = db.Column(db.DateTime, default=datetime.now)

    RIGHT_ANSWER = 100
    WRONG_ANSWER = 101
    SKIP = 102
    SAVE_WORD = 103


class Settings(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    strike = db.Column(db.Boolean, default=True)
    notification = db.Column(db.Boolean, default=True)
    notification_time = db.Column(db.Time, nullable=True, default=datetime.time(12, 0))
