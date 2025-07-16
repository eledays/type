import os.path
import sqlite3
import json


def export_to_json(db_path, json_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [table[0] for table in cursor.fetchall()]

    database_data = {}

    for table in tables:
        cursor.execute(f"SELECT * FROM {table};")
        rows = cursor.fetchall()

        database_data[table] = [dict(row) for row in rows]

    if not os.path.exists('fixtures'):
        os.mkdir('fixtures')

    with open(json_path, 'w', encoding='utf-8') as json_file:
        json.dump(database_data, json_file, indent=4, ensure_ascii=False)

    conn.close()


export_to_json('instance/app.db', 'fixtures/database_dump.json')