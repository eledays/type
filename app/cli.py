import csv
import re
from pathlib import Path

import click
from flask import Flask
from flask.cli import with_appcontext
from pymorphy3 import MorphAnalyzer
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Category, Paronym, ParonymGroup, Sentence, Word


@click.command("csv_to_db")
@click.argument(
    "csv_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@with_appcontext
def csv_to_db(csv_path: Path) -> None:
    """Import words and categories from CSV_PATH."""
    imported = 0
    skipped = 0

    try:
        with csv_path.open(encoding="utf-8", newline="") as file:
            rows = csv.DictReader(
                file,
                delimiter=";",
                fieldnames=("word", "answers", "category"),
            )
            for line_number, row in enumerate(rows, start=1):
                word_text = (row.get("word") or "").strip()
                category_name = (row.get("category") or "").strip()
                answers = [
                    answer.strip()
                    for answer in (row.get("answers") or "").split(",")
                    if answer.strip()
                ]
                if not word_text or not category_name or not answers:
                    raise click.ClickException(
                        f"Некорректная строка {line_number}: ожидаются "
                        "word;answer1,answer2;category"
                    )

                if Word.query.filter_by(word=word_text).first() is not None:
                    skipped += 1
                    continue

                category = Category.query.filter_by(name=category_name).first()
                if category is None:
                    category = Category()
                    category.name = category_name
                    db.session.add(category)
                    db.session.flush()

                word = Word()
                word.word = word_text
                word.answers = answers
                word.category_id = category.id
                db.session.add(word)
                imported += 1

        db.session.commit()
    except (OSError, UnicodeError, SQLAlchemyError) as error:
        db.session.rollback()
        raise click.ClickException(str(error)) from error
    except click.ClickException:
        db.session.rollback()
        raise

    click.echo(f"Импортировано слов: {imported}; пропущено: {skipped}.")


@click.command("txt_to_db")
@click.argument(
    "txt_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@with_appcontext
def txt_to_db(txt_path: Path) -> None:
    """Import paronym groups from TXT_PATH."""
    imported = 0
    skipped = 0

    try:
        with txt_path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                paronyms = [word.strip().lower() for word in line.split("–")]
                paronyms = [word for word in paronyms if word]
                if not paronyms:
                    continue
                if len(paronyms) < 2:
                    raise click.ClickException(
                        f"В строке {line_number} должна быть пара или группа "
                        "паронимов, разделённых символом '–'."
                    )

                existing = {
                    paronym.word: paronym
                    for paronym in Paronym.query.filter(
                        Paronym.word.in_(paronyms)
                    )
                }
                group_ids = {
                    paronym.group_id for paronym in existing.values()
                }
                if len(group_ids) > 1:
                    raise click.ClickException(
                        f"Строка {line_number} объединяет паронимы из разных "
                        "существующих групп."
                    )

                if group_ids:
                    group_id = group_ids.pop()
                else:
                    group = ParonymGroup()
                    db.session.add(group)
                    db.session.flush()
                    group_id = group.id

                for word in paronyms:
                    if word in existing:
                        skipped += 1
                        continue
                    paronym = Paronym()
                    paronym.word = word
                    paronym.group_id = group_id
                    db.session.add(paronym)
                    imported += 1

        db.session.commit()
    except (OSError, UnicodeError, SQLAlchemyError) as error:
        db.session.rollback()
        raise click.ClickException(str(error)) from error
    except click.ClickException:
        db.session.rollback()
        raise

    click.echo(f"Импортировано паронимов: {imported}; пропущено: {skipped}.")


def _base_form(analyzer: MorphAnalyzer, word: str) -> str:
    return analyzer.parse(word.strip().lower())[0].normal_form


def _group_paronyms(word: str) -> list[str]:
    paronym = Paronym.query.filter_by(word=word).first()
    return paronym.get_all_group_paronyms() if paronym is not None else []


def _add_sentence(
    analyzer: MorphAnalyzer,
    sentence_text: str,
    highlighted_word: str,
    correct_word: str,
) -> bool:
    base_word = _base_form(analyzer, correct_word)
    paronym = Paronym.query.filter_by(word=base_word).first()
    if paronym is None:
        return False

    sentence_text = sentence_text.replace(highlighted_word.upper(), "_______")
    if Sentence.query.filter_by(sentence=sentence_text).first() is not None:
        return False

    parsed_word = analyzer.parse(correct_word.strip().lower())[0]
    sentence = Sentence()
    sentence.sentence = sentence_text
    sentence.word_tags = ",".join(sorted(parsed_word.tag.grammemes))
    sentence.word_id = paronym.id
    db.session.add(sentence)
    return True


def _sentence_blocks(lines: list[str]) -> list[tuple[list[str], str]]:
    blocks: list[tuple[list[str], str]] = []
    sentences: list[str] = []

    for line_number, line in enumerate(lines, start=1):
        text = line.rstrip()
        if not text:
            continue
        if text.startswith("Ответ: "):
            answer = text.removeprefix("Ответ: ").strip()
            if not sentences or not answer:
                raise click.ClickException(
                    f"Некорректный блок около строки {line_number}."
                )
            blocks.append((sentences, answer))
            sentences = []
        else:
            sentences.append(text)

    if sentences:
        raise click.ClickException(
            "В конце файла отсутствует строка 'Ответ: ...'."
        )
    return blocks


@click.command("sentence_to_db")
@click.argument(
    "txt_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@with_appcontext
def sentence_to_db(txt_path: Path) -> None:
    """Import paronym exercise sentences from TXT_PATH."""
    analyzer = MorphAnalyzer()
    imported = 0
    skipped = 0

    try:
        lines = txt_path.read_text(encoding="utf-8").splitlines()
        for sentences, answer in _sentence_blocks(lines):
            highlighted_words: list[str] = []
            for sentence in sentences:
                matches = re.findall(r"\b[A-ZА-ЯЁ][A-ZА-ЯЁ]+\b", sentence)
                if not matches:
                    raise click.ClickException(
                        f"Не найдено выделенное слово: {sentence}"
                    )
                highlighted_words.append(matches[0].lower())

            answer_paronyms = _group_paronyms(_base_form(analyzer, answer))
            if not answer_paronyms:
                click.echo(f"Паронима '{answer}' нет в базе; блок пропущен.")
                skipped += len(sentences)
                continue

            incorrect_indices = [
                index
                for index, word in enumerate(highlighted_words)
                if _base_form(analyzer, word) in answer_paronyms
            ]
            if len(incorrect_indices) == 1:
                incorrect_index = incorrect_indices[0]
            else:
                click.echo("\n".join(
                    f"[{index}] {sentence}"
                    for index, sentence in enumerate(sentences)
                ))
                incorrect_index = click.prompt(
                    "Индекс неправильного предложения",
                    type=click.IntRange(0, len(sentences) - 1),
                )

            for index, sentence_text in enumerate(sentences):
                correct_word = (
                    answer
                    if index == incorrect_index
                    else highlighted_words[index]
                )
                if _add_sentence(
                    analyzer,
                    sentence_text,
                    highlighted_words[index],
                    correct_word,
                ):
                    imported += 1
                else:
                    skipped += 1

        db.session.commit()
    except (OSError, UnicodeError, SQLAlchemyError) as error:
        db.session.rollback()
        raise click.ClickException(str(error)) from error
    except click.ClickException:
        db.session.rollback()
        raise

    click.echo(f"Импортировано предложений: {imported}; пропущено: {skipped}.")


def register_commands(app: Flask) -> None:
    app.cli.add_command(csv_to_db)
    app.cli.add_command(txt_to_db)
    app.cli.add_command(sentence_to_db)
