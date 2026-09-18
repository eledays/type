"""Convert marked spelling source files to the application CSV format."""

from __future__ import annotations

import argparse
import csv
from collections.abc import Mapping, Sequence
from pathlib import Path

LETTER_OPTIONS: dict[str, tuple[str, ...]] = {
    "а": ("а", "о", "ё"),
    "е": ("е", "и", "ё"),
    "и": ("и", "ы", "е"),
    "о": ("о", "а", "ё"),
    "я": ("я", "е"),
    "ы": ("ы", "и", "е"),
    "ю": ("ю", "у"),
    "у": ("у", "ю"),
    "ё": ("ё", "о", ""),
}
SUFFIX_OPTIONS: dict[str, tuple[str, ...]] = {
    "ъ": ("ъ", "ь"),
    "ь": ("ь", "ъ"),
    "с": ("с", "ск"),
    "з": ("з", "с"),
    "д": ("д", "т"),
    "т": ("т", "д"),
    "щ": ("щ", "ч"),
    "ч": ("ч", "щ"),
}
DEFAULT_SOURCES = {
    "9.txt": "Правописание гласных и согласных в корне",
    "ъь.txt": "Употребление ъ и ь (в том числе разделительных)",
    "3_7_4.txt": "Правописание приставок. Буквы ы – и после приставок",
    "3_7_5.txt": "Правописание суффиксов",
}


def convert_word(
    marked_word: str,
    options: Mapping[str, Sequence[str]],
) -> tuple[str, str, str]:
    """Convert one word with exactly one uppercase answer marker."""
    positions = [index for index, letter in enumerate(marked_word) if letter.isupper()]
    if len(positions) != 1:
        raise ValueError(f"expected one uppercase marker: {marked_word!r}")
    marker_index = positions[0]
    correct_answer = marked_word[marker_index].lower()
    if correct_answer not in options:
        raise ValueError(f"unsupported answer {correct_answer!r}: {marked_word!r}")
    masked_word = marked_word[:marker_index] + "_" + marked_word[marker_index + 1 :]
    return masked_word, correct_answer, ",".join(options[correct_answer])


def convert_sources(
    input_directory: Path,
    output_path: Path,
    sources: Mapping[str, str] = DEFAULT_SOURCES,
) -> int:
    """Write all configured sources in the four-column importer format."""
    row_count = 0
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file, delimiter=";")
        for filename, category in sources.items():
            option_map = SUFFIX_OPTIONS if filename == "3_7_5.txt" else LETTER_OPTIONS
            source_path = input_directory / filename
            for line_number, raw_line in enumerate(
                source_path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                marked_word = raw_line.strip()
                if not marked_word:
                    continue
                try:
                    word, correct_answer, answers = convert_word(
                        marked_word, option_map
                    )
                except ValueError as error:
                    raise ValueError(
                        f"{source_path}:{line_number}: {error}"
                    ) from error
                writer.writerow((word, correct_answer, answers, category))
                row_count += 1
    return row_count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_directory", type=Path)
    parser.add_argument("output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    row_count = convert_sources(args.input_directory, args.output)
    print(f"Wrote {row_count} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
