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

    def get_all_options(self):
        paronyms = self.word.group.paronyms
        return paronyms
