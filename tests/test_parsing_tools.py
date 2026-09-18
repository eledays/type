import csv

import pytest

from parsing.parse import count_differences, extract_words
from parsing.to_csv import convert_sources, convert_word
from parsing_paronyms.parser_sentence import normalize_text


def test_extract_words_and_count_differences() -> None:
    assert extract_words(["1) задание", "сл..во, тр..ва", "", "2) ещё"]) == [
        "сл..во",
        "тр..ва",
    ]
    assert count_differences("сл.во", "слово") == 1
    assert count_differences("коротко", "короткий") == -1


def test_convert_word_validates_marker() -> None:
    assert convert_word("мОлоко", {"о": ("о", "а")}) == (
        "м_локо",
        "о",
        "о,а",
    )
    with pytest.raises(ValueError, match="one uppercase marker"):
        convert_word("молоко", {"о": ("о", "а")})


def test_convert_sources_writes_current_import_format(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "sample.txt").write_text("мОлоко\n", encoding="utf-8")
    output = tmp_path / "words.csv"

    count = convert_sources(source, output, {"sample.txt": "Проверка"})

    assert count == 1
    with output.open(encoding="utf-8", newline="") as output_file:
        assert list(csv.reader(output_file, delimiter=";")) == [
            ["м_локо", "о", "о,а,ё", "Проверка"]
        ]


def test_normalize_sentence_text() -> None:
    assert normalize_text("  по\u00adле\u202f\u202fслов  ") == "поле  слов"
