import csv
import re
from pathlib import Path

import click
from flask import Flask
from flask.cli import with_appcontext
from pymorphy3 import MorphAnalyzer
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import (
    Category,
    Paronym,
    ParonymExercise,
    ParonymGroup,
    SpellingExercise,
)


def _ensure_paronym_group(
    paronym_words: list[str],
    line_number: int,
) -> tuple[dict[str, Paronym], int, int]:
    """Создаёт или дополняет одну непротиворечивую группу паронимов.

    :param paronym_words: Нормальные формы слов из одной группы.
    :param line_number: Номер исходной строки для сообщения об ошибке.
    :return: Словарь паронимов, число созданных и число найденных слов.
    :raises click.ClickException: Если слов мало или они принадлежат разным
        существующим группам.
    """
    unique_words = list(dict.fromkeys(
        word.strip().lower() for word in paronym_words if word.strip()
    ))
    if len(unique_words) < 2:
        raise click.ClickException(
            f"В строке {line_number} должна быть пара или группа паронимов."
        )

    existing = {
        paronym.word: paronym
        for paronym in Paronym.query.filter(Paronym.word.in_(unique_words))
    }
    group_ids = {paronym.group_id for paronym in existing.values()}
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

    imported = 0
    skipped = 0
    for word in unique_words:
        if word in existing:
            skipped += 1
            continue
        paronym = Paronym(word=word, group_id=group_id)
        db.session.add(paronym)
        existing[word] = paronym
        imported += 1
    db.session.flush()
    return existing, imported, skipped


def _import_paronym_csv_row(
    values: list[str],
    line_number: int,
) -> tuple[int, int, bool]:
    """Импортирует группу паронимов и упражнение из строки CSV.

    :param values: Поля строки после удаления окружающих пробелов.
    :param line_number: Номер строки в исходном CSV-файле.
    :return: Число созданных и найденных паронимов, а также признак создания
        упражнения.
    :raises click.ClickException: Если строка не соответствует формату.
    """
    if len(values) != 5 or values[0] != "paronym":
        raise click.ClickException(
            f"Некорректная строка {line_number}: ожидаются либо "
            "word;correct_answer;answer1,answer2;category, либо "
            "paronym;sentence;correct_paronym;group;word_tags"
        )
    _, sentence_text, correct_word, raw_group, word_tags = values
    group_words = [word.strip().lower() for word in raw_group.split(",")]
    correct_word = correct_word.lower()
    if (
        not sentence_text
        or "_______" not in sentence_text
        or not correct_word
        or not word_tags
    ):
        raise click.ClickException(
            f"Некорректная строка паронимов {line_number}."
        )
    if correct_word not in group_words:
        raise click.ClickException(
            f"В строке {line_number} правильный пароним должен входить в группу."
        )

    paronyms, imported, skipped = _ensure_paronym_group(
        group_words,
        line_number,
    )
    if ParonymExercise.query.filter_by(sentence=sentence_text).first() is not None:
        return imported, skipped, False
    db.session.add(ParonymExercise(
        sentence=sentence_text,
        paronym=paronyms[correct_word],
        word_tags=word_tags,
        task_number=5,
    ))
    return imported, skipped, True


@click.command("csv_to_db")
@click.argument(
    "csv_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@with_appcontext
def csv_to_db(csv_path: Path) -> None:
    """Импортирует слова и категории из CSV-файла.

    :param csv_path: Путь к исходному CSV-файлу.
    :return: ``None``.
    """
    imported = 0
    skipped = 0
    imported_paronyms = 0
    skipped_paronyms = 0
    imported_paronym_exercises = 0
    skipped_paronym_exercises = 0

    try:
        with csv_path.open(encoding="utf-8", newline="") as file:
            rows = csv.reader(file, delimiter=";")
            for line_number, row in enumerate(rows, start=1):
                values = [value.strip() for value in row]
                if values and values[0] == "paronym":
                    new_paronyms, known_paronyms, exercise_created = (
                        _import_paronym_csv_row(values, line_number)
                    )
                    imported_paronyms += new_paronyms
                    skipped_paronyms += known_paronyms
                    if exercise_created:
                        imported_paronym_exercises += 1
                    else:
                        skipped_paronym_exercises += 1
                    continue
                if len(values) == 4:
                    word_text, correct_answer, raw_answers, category_name = values
                else:
                    raise click.ClickException(
                        f"Некорректная строка {line_number}: ожидаются "
                        "word;correct_answer;answer1,answer2;category"
                    )
                answers = [
                    answer.strip()
                    for answer in raw_answers.split(",")
                    if answer.strip()
                ]
                if (
                    not word_text
                    or not correct_answer
                    or not category_name
                    or not answers
                ):
                    raise click.ClickException(
                        f"Некорректная строка {line_number}: ожидаются "
                        "word;correct_answer;answer1,answer2;category"
                    )
                if correct_answer not in answers:
                    raise click.ClickException(
                        f"Некорректная строка {line_number}: правильный ответ "
                        "должен входить в список вариантов"
                    )

                if SpellingExercise.query.filter_by(word=word_text).first() is not None:
                    skipped += 1
                    continue

                category = Category.query.filter_by(name=category_name).first()
                if category is None:
                    category = Category()
                    category.name = category_name
                    db.session.add(category)
                    db.session.flush()

                word = SpellingExercise()
                word.word = word_text
                word.answers = answers
                word.correct_answer = correct_answer
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

    click.echo(
        f"Импортировано слов: {imported}; пропущено: {skipped}. "
        f"Паронимов: {imported_paronyms}; уже существовало: "
        f"{skipped_paronyms}. Упражнений на паронимы: "
        f"{imported_paronym_exercises}; пропущено: "
        f"{skipped_paronym_exercises}."
    )


@click.command("txt_to_db")
@click.argument(
    "txt_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@with_appcontext
def txt_to_db(txt_path: Path) -> None:
    """Импортирует группы паронимов из текстового файла.

    :param txt_path: Путь к исходному текстовому файлу.
    :return: ``None``.
    """
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

                _, new_count, known_count = _ensure_paronym_group(
                    paronyms,
                    line_number,
                )
                imported += new_count
                skipped += known_count

        db.session.commit()
    except (OSError, UnicodeError, SQLAlchemyError) as error:
        db.session.rollback()
        raise click.ClickException(str(error)) from error
    except click.ClickException:
        db.session.rollback()
        raise

    click.echo(f"Импортировано паронимов: {imported}; пропущено: {skipped}.")


def _base_form(analyzer: MorphAnalyzer, word: str) -> str:
    """Определяет нормальную форму слова.

    :param analyzer: Морфологический анализатор.
    :param word: Исходная словоформа.
    :return: Нормальная форма в нижнем регистре.
    """
    return analyzer.parse(word.strip().lower())[0].normal_form


def _group_paronyms(word: str) -> list[str]:
    """Находит все паронимы из группы указанного слова.

    :param word: Нормальная форма паронима.
    :return: Слова группы или пустой список.
    """
    paronym = Paronym.query.filter_by(word=word).first()
    return paronym.get_all_group_paronyms() if paronym is not None else []


def _add_sentence(
    analyzer: MorphAnalyzer,
    sentence_text: str,
    highlighted_word: str,
    correct_word: str,
) -> bool:
    """Добавляет одно предложение с пропуском в сессию базы данных.

    :param analyzer: Морфологический анализатор.
    :param sentence_text: Исходный текст предложения.
    :param highlighted_word: Выделенная словоформа в предложении.
    :param correct_word: Правильная словоформа для задания.
    :return: ``True``, если предложение подготовлено к сохранению.
    """
    base_word = _base_form(analyzer, correct_word)
    paronym = Paronym.query.filter_by(word=base_word).first()
    if paronym is None:
        return False

    sentence_text = sentence_text.replace(highlighted_word.upper(), "_______")
    if ParonymExercise.query.filter_by(sentence=sentence_text).first() is not None:
        return False

    parsed_word = analyzer.parse(correct_word.strip().lower())[0]
    exercise = ParonymExercise()
    exercise.sentence = sentence_text
    exercise.word_tags = ",".join(sorted(parsed_word.tag.grammemes))
    exercise.paronym_id = paronym.id
    exercise.task_number = 5
    db.session.add(exercise)
    return True


def _sentence_blocks(lines: list[str]) -> list[tuple[list[str], str]]:
    """Разбирает строки файла на блоки предложений и ответов.

    :param lines: Строки исходного файла.
    :return: Список пар из предложений блока и правильного ответа.
    :raises click.ClickException: Если структура блока некорректна.
    """
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
    """Импортирует предложения для заданий с паронимами.

    :param txt_path: Путь к исходному текстовому файлу.
    :return: ``None``.
    """
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
    """Регистрирует команды импорта в Flask CLI.

    :param app: Flask-приложение, получающее команды.
    :return: ``None``.
    """
    app.cli.add_command(csv_to_db)
    app.cli.add_command(txt_to_db)
    app.cli.add_command(sentence_to_db)
