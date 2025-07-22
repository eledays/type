from random import shuffle

from pymorphy3 import MorphAnalyzer

from app import app, db


class ParonymGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)


class Paronym(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    word = db.Column(db.String(128), unique=True, nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('paronym_group.id'), nullable=False)
    group = db.relationship(ParonymGroup, backref='paronyms')

    def get_all_group_paronyms(self):
        """
        Returns all group paronyms
        """
        paronyms = [i.word for i in self.group.paronyms]
        return paronyms


class Sentence(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sentence = db.Column(db.String, unique=True, nullable=False)
    word_id = db.Column(db.Integer, db.ForeignKey('paronym.id'), nullable=False)
    word_tags = db.Column(db.String)
    word = db.relationship(Paronym, backref='sentences')
    explanation = ''

    def get_answers(self) -> list:
        """
        Returns the answers in a random order.
        """
        analyzer = MorphAnalyzer()
        tags = set(self.word_tags.split(','))
        paronyms = []
        for i in self.word.group.paronyms:
            word = analyzer.parse(i.word)[0]
            for tag in tags:
                word_in_form = word.inflect({tag})
                if word_in_form is not None:
                    word = word_in_form

            paronyms.append(word.word)
        shuffle(paronyms)
        return paronyms

    def get_html(self) -> str:
        """
        Returns the word with missing letters highlighted in HTML format.
        """
        return self.sentence