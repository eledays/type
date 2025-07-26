import sqlite3
import json


def import_from_json(db_path, json_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    with open(json_path, 'r', encoding='utf-8') as json_file:
        database_data = json.load(json_file)

    for table, rows in database_data.items():
        if not rows:
            continue

        # Здесь предполагается, что таблица уже существует
        try:
            columns = list(rows[0].keys())
            placeholders = ', '.join(['?'] * len(columns))
            query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"

            for row in rows:
                values = [row[column] if type(row[column]) is not list else '[' + ','.join(f'"{e}"' for e in row[column]) + ']' for column in columns]
                cursor.execute(query, values)
        except sqlite3.IntegrityError:
            print(rows, 'is exists already')


    conn.commit()
    conn.close()


import_from_json('instance/app.db', 'fixtures/accents.json')
