from app import app, db, login

import random


# @login.user_loader
# def load_user(user_id):
#     return User.query.get(int(user_id))


# class User(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     username = db.Column(db.String(24), unique=True, nullable=False)
#     password_hash = db.Column(db.String(128), nullable=False)


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
    