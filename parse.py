from bs4 import BeautifulSoup


def split_ignore_parentheses(s, separator=','):
    tokens = []
    current = []
    level = 0
    for char in s:
        if char == '(':
            level += 1
        elif char == ')':
            level -= 1
        if char == separator and level == 0:
            tokens.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        tokens.append(''.join(current).strip())
    return tokens


with open('words/a.html', 'r') as file:
    html_content = file.read()

soup = BeautifulSoup(html_content, 'html.parser')
words = []

for div in soup.find_all('div', class_='react-mathjax-preview-result'):
    ps = div.find_all('p')[1:]
    ps = [p.text.replace(', ', ',') for p in ps if '..' not in p.text]

    if not ps:
        continue
    
    for p in ps:
        words += [e.replace(',', ', ') for e in split_ignore_parentheses(p[3:])]

print(words)

words_with_explanation = []
for word in words:
    try:
        word, explanation = word.split(' (')
        explanation = explanation[:-1]
        words_with_explanation.append((word, explanation))
    except:
        pass

print(words_with_explanation)

from app import db, app
from app.models import Word, Category
import sqlite3

with app.app_context():
    ПГ = Category.query.filter_by(name='Проверяемая гласная').first()
    if not ПГ:
        ПГ = Category(name='Проверяемая гласная')
        db.session.add(ПГ)
        db.session.commit()

    ЧГ = Category.query.filter_by(name='Чередующаяся гласная').first()
    if not ЧГ:
        ЧГ = Category(name='Чередующаяся гласная')
        db.session.add(ЧГ)
        db.session.commit()

    НГ = Category.query.filter_by(name='Непроверяемая гласная').first()
    if not НГ:
        НГ = Category(name='Непроверяемая гласная')
        db.session.add(НГ)
        db.session.commit()

    for word, explanation in words_with_explanation:
        try:
            category, explanation = explanation.split(', ')
            if category == 'ПГ':
                category = ПГ
            elif category == 'ЧГ':
                category = ЧГ
            elif category == 'НГ':
                category = НГ

            mislet = [e for e in word if e.isupper()][0]
            word = word.replace(mislet, '_')
            mislet = mislet.lower()

            try:
                lets = {
                    'а': ['а', 'о'],
                    'е': ['е', 'и'],
                    'и': ['и', 'ы', 'е'],
                    'о': ['о', 'а'],
                    'я': ['я', 'е'],
                }[mislet]
            except KeyError:
                print(word, explanation)
                break

            word_obj = Word.query.filter_by(word=word).first()
            if word_obj:
                continue

            word_obj = Word(word=word, explanation=explanation, answers=lets, category=category, task_number=9)
            db.session.add(word_obj)
            db.session.commit()

            print('added', word_obj.word, word_obj.explanation, word_obj.answers, word_obj.category.name)
        except:
            print('error', word, explanation)
            continue

