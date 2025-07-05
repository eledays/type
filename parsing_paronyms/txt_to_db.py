from app import app, db
from app.paronym.models import Sentence, Paronym, ParonymGroup
from pathlib import Path

def import_txt_to_db(inp_file_path):
    with Path(inp_file_path).open(mode='r', encoding='utf-8') as file:
        for paronym_pair in file.readlines():
            paronyms = paronym_pair.rstrip().lower().split(' – ')

            paronyms_db_obj = [Paronym.query.filter_by(word=i).first() for i in paronyms]
            group_id = -1
            if any(paronyms_db_obj):
                for i in paronyms_db_obj:
                    if i:
                        group_id = i.group_id
                        break
            else:
                group = ParonymGroup()
                db.session.add(group)
                db.session.commit()
                group_id = group.id

            for paronym in paronyms:
                try:
                    par = Paronym(word=paronym, group_id=group_id)
                    db.session.add(par)
                    db.session.commit()
                    print(f"Added word '{paronym}'")
                except Exception as e:
                    print(f"IntegrityError: Could not add word '{paronym}'. It may already exist.")
                    print(e)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        import_txt_to_db('../words/paronyms.txt')
    print("TXT import completed.")

