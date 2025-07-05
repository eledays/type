import csv

writer = csv.DictWriter(open('../words/words.csv', 'w'), fieldnames=['word', 'answers', 'category'], delimiter=';')
lets = {
    'а': ['а', 'о', 'ё'],
    'е': ['е', 'и', 'ё'],
    'и': ['и', 'ы', 'е'],
    'о': ['о', 'а', 'ё'],
    'я': ['я', 'е'],
    'ы': ['ы', 'и', 'е'],
    'ю': ['ю', 'у'],
    'у': ['у', 'ю'],
    'ё': ['ё', 'о', ''],
}

s_lets = {
    'ъ': ['ъ', 'ь'],
    'ь': ['ь', 'ъ'],
    'с': ['с', 'ск'],
    'з': ['з', 'с'],
    'д': ['д', 'т'],
    'т': ['т', 'д'],
    'щ': ['щ', 'ч'],
    'ч': ['ч', 'щ'],
}

for k, v in {
    '9.txt': 'Правописание гласных и согласных в корне',
    'ъь.txt': 'Употребление ъ и ь (в том числе разделительных)',
    '3_7_4.txt': 'Правописание приставок. Буквы ы – и после при ставок',
    '3_7_5.txt': 'Правописание суффиксов',
    }.items():
    with open('../words/' + k, 'r', encoding='utf-8') as file:
        for line in file.readlines():
            word = line.strip()
            right_let = [e for e in word if e.isupper()][0]
            word = word.replace(right_let, '_')
            if k == '3_7_5.txt':
                writer.writerow({'word': word, 'answers': ','.join(s_lets[right_let.lower()]), 'category': v})
            else:
                writer.writerow({'word': word, 'answers': ','.join(lets[right_let.lower()]), 'category': v})