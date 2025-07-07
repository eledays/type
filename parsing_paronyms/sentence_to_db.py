import re
from pathlib import Path
from app import app, db
from app.paronym.models import Paronym
import pymorphy3

def get_paronyms(word) -> list[str]:
    with app.app_context():
        par = Paronym.query.filter_by(word=word.strip()).first()
        if par is None:
            return list()
        return par.get_all_group_paronyms()


def to_base_form(word) -> str:
    morph = pymorphy3.MorphAnalyzer()
    parse_word = morph.parse(word.lower())
    return parse_word[0].normal_form


def to_db(sentence, word, correct_word):
    print(sentence, word, correct_word)


if __name__ == '__main__':
    with Path('../words/sentence.txt').open(mode='r', encoding='utf8') as file:
        data = file.readlines()

    k = 0
    while k < len(data):
        line = data[k]
        sentence = []
        answer: str
        while 'Ответ: ' not in line:
            sentence.append(line.rstrip())
            k += 1
            line = data[k]
        answer = line.rstrip().replace('Ответ: ', '')
        k += 1

        base_word = []
        for line in sentence:
            words = re.findall(r'\b[A-ZА-ЯЁ][A-ZА-ЯЁ]+\b', line)
            for word in words:
                if word.isupper():
                    base_word.append(word.lower())
                    break

        if len(base_word) == len(sentence):
            if answer == 'гарантированный':
                pass
            paronyms = get_paronyms(to_base_form(answer))
            if not paronyms:
                print(f'Паронима {answer} нет в базе данных')
            indices = [i for i, bw in enumerate(base_word) if to_base_form(bw) in paronyms]

            if len(indices) != 1:
                for line in sentence:
                    print(line.strip())
                print(f"Ответ: {answer}")

                ind = int(input(f"Введите число от 0 до {len(sentence) - 1} (индекс не правильного предложения): "))
            else:
                ind = indices[0]
            print(ind)
            for i in range(len(sentence)):
                if i == ind:
                    if len(paronyms) != 0:
                        to_db(sentence[i], base_word[i], answer)
                else:
                    to_db(sentence[i], base_word[i], base_word[i])
            print()
        else:
            print("Паронимы не найдены.")
            print(sentence)
            print(base_word)