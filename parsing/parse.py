"""Resolve masked spelling words through Gramota.ru.

This is an offline maintenance utility, not part of the web application.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterable
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://gramota.ru/poisk"


def count_differences(first: str, second: str) -> int:
    """Return the Hamming distance, or -1 for strings of different lengths."""
    if len(first) != len(second):
        return -1
    return sum(left != right for left, right in zip(first, second, strict=True))


def extract_words(lines: Iterable[str]) -> list[str]:
    """Extract the comma-separated word line following each numbered heading."""
    words: list[str] = []
    expect_words = False
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if re.search(r"\d\)", line):
            expect_words = True
        elif expect_words:
            words.extend(word.strip() for word in line.split(",") if word.strip())
            expect_words = False
    return words


def resolve_word(
    session: requests.Session,
    masked_word: str,
    *,
    timeout: float,
) -> str | None:
    """Fetch and validate one masked word, returning the marked spelling."""
    query = masked_word.replace("..", "-")
    response = session.get(
        SEARCH_URL,
        params={"query": query, "mode": "slovari"},
        timeout=timeout,
    )
    response.raise_for_status()
    title = BeautifulSoup(response.text, "html.parser").select_one("a.title")
    if title is None:
        return None

    candidate = masked_word.replace("..", ".")
    correct_word = title.get_text(strip=True)
    if count_differences(candidate, correct_word) != 1:
        return None

    missing_index = candidate.find(".")
    if missing_index < 0:
        return None
    return (
        candidate[:missing_index]
        + correct_word[missing_index].upper()
        + candidate[missing_index + 1 :]
    )


def parse_words(
    input_path: Path,
    output_path: Path,
    error_path: Path,
    *,
    timeout: float = 10.0,
) -> tuple[int, int]:
    """Resolve all source words and classify successes and errors."""
    words = extract_words(input_path.read_text(encoding="utf-8").splitlines())
    successes: list[str] = []
    errors: list[str] = []
    with requests.Session() as session:
        session.headers["User-Agent"] = "type-data-maintenance/1.0"
        for word in words:
            try:
                resolved = resolve_word(session, word, timeout=timeout)
            except requests.RequestException:
                resolved = None
            if resolved is None:
                errors.append(word)
            else:
                successes.append(resolved)

    success_text = "\n".join(successes)
    error_text = "\n".join(errors)
    output_path.write_text(
        success_text + ("\n" if success_text else ""), encoding="utf-8"
    )
    error_path.write_text(
        error_text + ("\n" if error_text else ""), encoding="utf-8"
    )
    return len(successes), len(errors)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="source text file")
    parser.add_argument("output", type=Path, help="resolved words file")
    parser.add_argument("errors", type=Path, help="unresolved words file")
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    success_count, error_count = parse_words(
        args.input,
        args.output,
        args.errors,
        timeout=args.timeout,
    )
    print(f"Success: {success_count}; errors: {error_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
