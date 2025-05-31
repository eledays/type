import re


ipt = 'words/a.txt'
out = 'words/3_7_5.txt'
err = 'words/3_7_5_errors.txt'


def count_differences(str1, str2):
    if len(str1) != len(str2):
        return -1
    pattern = r'(?=.)' 
    differences = re.findall(pattern, str1) + re.findall(pattern, str2)
    
    # Считаем отличия
    count = sum(1 for a, b in zip(str1, str2) if a != b)
    return count


lets = {
    'а': ['а', 'о'],
    'е': ['е', 'и'],
    'и': ['и', 'ы', 'е'],
    'о': ['о', 'а'],
    'я': ['я', 'е'],
}

with open(ipt, 'r', encoding='utf-8') as file:
    lines = file.readlines()

lines = [e.strip() for e in lines if e.strip()]

words = []
is_word_line = False

for line in lines:
    if re.search(r'\d\)', line):
        is_word_line = True
    elif is_word_line:
        words.extend(line.split(', '))
        is_word_line = False

from bs4 import BeautifulSoup as bs 
import requests

with open(out, 'w', encoding='utf-8') as file:
    with open(err, 'w', encoding='utf-8') as error_file:
        for word_i, word in enumerate(words):
            response = requests.get(f'https://gramota.ru/poisk?query={word.replace("..", "-")}&mode=slovari')
            soup = bs(response.text, 'html.parser')
            try:
                right_word = soup.find_all('a', class_='title')[0].text
            except:
                print(word, file=error_file)
                continue

            diff = count_differences(word.replace('..', '.'), right_word)

            if diff != 1:
                print(word, file=error_file)
                continue

            word = word.replace('..', '.')

            new_word = ''
            for i in range(len(word)):
                if word[i] == '.':
                    new_word += right_word[i].upper()
                else:
                    new_word += word[i]

            print(new_word, file=file)
            print(f'{round(word_i / len(words) * 100, 2)}% ({word_i})', ' ' * 10, end='\r')

print('Done!' + ' ' * 20)
with open(out, 'r', encoding='utf-8') as file:
    print('Success:', len(file.readlines()), end=' ')
with open(err, 'r', encoding='utf-8') as file:
    print('Errors:', len(file.readlines()))

