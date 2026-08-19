from pathlib import Path

import pytest

from tests.base import AppTestCase

from app.extensions import db
from app.models import (
    Category,
    Paronym,
    ParonymExercise,
    ParonymGroup,
    SpellingExercise,
)


class TestImportCommands(AppTestCase):
    @pytest.fixture(autouse=True)
    def cli_context(self, app_context, tmp_path: Path):
        self.runner = self.app.test_cli_runner()
        self.temp_dir = tmp_path

    def fixture(self, name: str, contents: str) -> Path:
        path = self.temp_dir / name
        path.write_text(contents, encoding="utf-8")
        return path

    def test_csv_import_creates_categories_words_and_skips_duplicates(self) -> None:
        source = self.fixture(
            "words.csv",
            "м_локо;о;а,о;Корни\nр_ка;е;и,е;Корни\n",
        )
        first = self.runner.invoke(args=["csv_to_db", str(source)])
        second = self.runner.invoke(args=["csv_to_db", str(source)])
        assert first.exit_code == 0, first.output
        assert "Импортировано слов: 2; пропущено: 0" in first.output
        assert "Импортировано слов: 0; пропущено: 2" in second.output
        with self.app.app_context():
            assert Category.query.count() == 1
            assert SpellingExercise.query.count() == 2
            word = SpellingExercise.query.filter_by(word="м_локо").one()
            assert word.answers == ["а", "о"]
            assert word.correct_answer == "о"

    def test_invalid_csv_rolls_back_the_entire_import(self) -> None:
        source = self.fixture(
            "broken.csv", "м_локо;о;о,а;Корни\nнет категории;о;о;\n"
        )
        result = self.runner.invoke(args=["csv_to_db", str(source)])
        assert result.exit_code != 0
        assert "Некорректная строка 2" in result.output
        with self.app.app_context():
            assert SpellingExercise.query.count() == 0
            assert Category.query.count() == 0

    def test_csv_import_rejects_correct_answer_outside_options(self) -> None:
        source = self.fixture(
            "broken-answer.csv",
            "м_локо;о;а,и;Корни\n",
        )
        result = self.runner.invoke(args=["csv_to_db", str(source)])
        assert result.exit_code != 0
        assert "должен входить в список вариантов" in result.output

    def test_paronym_import_creates_groups_and_extends_existing_group(self) -> None:
        first_source = self.fixture("first.txt", "эффектный – эффективный\n")
        second_source = self.fixture("second.txt", "эффективный – эффектность\n")
        first = self.runner.invoke(args=["txt_to_db", str(first_source)])
        second = self.runner.invoke(args=["txt_to_db", str(second_source)])
        assert first.exit_code == 0, first.output
        assert second.exit_code == 0, second.output
        with self.app.app_context():
            assert ParonymGroup.query.count() == 1
            assert {item.word for item in Paronym.query.all()} == {
                "эффектный", "эффективный", "эффектность"
            }

    def test_paronym_import_rejects_single_words(self) -> None:
        source = self.fixture("broken.txt", "одиночный\n")
        result = self.runner.invoke(args=["txt_to_db", str(source)])
        assert result.exit_code != 0
        assert "должна быть пара" in result.output
        with self.app.app_context():
            assert Paronym.query.count() == 0

    def test_sentence_import_replaces_highlighted_paronym_and_skips_duplicate(self) -> None:
        paronyms = self.fixture(
            "paronyms.txt", "эффектный – эффективный\n"
        )
        imported_paronyms = self.runner.invoke(
            args=["txt_to_db", str(paronyms)]
        )
        assert imported_paronyms.exit_code == 0, imported_paronyms.output
        source = self.fixture(
            "sentences.txt",
            "Это был ЭФФЕКТНЫЙ метод.\nОтвет: эффективный\n",
        )

        first = self.runner.invoke(args=["sentence_to_db", str(source)])
        second = self.runner.invoke(args=["sentence_to_db", str(source)])
        assert first.exit_code == 0, first.output
        assert second.exit_code == 0, second.output
        assert "Импортировано предложений: 1; пропущено: 0" in first.output
        assert "Импортировано предложений: 0; пропущено: 1" in second.output
        with self.app.app_context():
            sentence = ParonymExercise.query.one()
            assert sentence.sentence == "Это был _______ метод."
            assert sentence.paronym.word == "эффективный"
