import csv
from app import app, db
from app.models import Word, Category
import sqlalchemy

def import_csv_to_db(csv_file_path):
    """
    Imports words and their categories from a CSV file into the database.
    """
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file, delimiter=';', fieldnames=['word', 'answers', 'category'])
        for row in reader:
            try:
                category_name = row['category']
                word_text = row['word']
                answers = row['answers'].split(',')

                # Find or create the category
                category = Category.query.filter_by(name=category_name).first()
                if not category:
                    category = Category(name=category_name)
                    db.session.add(category)
                    db.session.commit()

                # Create the word
                word = Word(word=word_text, answers=answers, category_id=category.id)
                db.session.add(word)
                db.session.commit()
                print(f"Added word '{word_text}' with category '{category_name}'.")
            except sqlalchemy.exc.IntegrityError:
                db.session.rollback()
                print(f"IntegrityError: Could not add word '{row['word']}' with category '{row['category']}'. It may already exist.")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        import_csv_to_db('../words/words.csv')
    print("CSV import completed.")
