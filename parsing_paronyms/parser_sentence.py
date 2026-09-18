"""Download paronym exercises from a rendered Sdamgia page."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.webdriver.common.by import By

DEFAULT_URL = (
    "https://rus-ege.sdamgia.ru/test?id=50214784&nt=True&pub=False"
    "&print=true&svg=0&num=true&ans=true&tt=&td="
)


def normalize_text(value: str) -> str:
    """Remove soft hyphens and normalize narrow non-breaking whitespace."""
    return value.replace("\u00ad", "").replace("\u202f", " ").strip()


def collect_pairs(elements: Iterable[Any]) -> list[tuple[list[str], str]]:
    """Extract sentence options and answers from Selenium page elements."""
    pairs: list[tuple[list[str], str]] = []
    for element in elements:
        classes = (element.get_attribute("class") or "").split()
        if "prob_maindiv" not in classes:
            continue
        container = element.find_element(By.CLASS_NAME, "nobreak")
        paragraphs = container.find_elements(By.TAG_NAME, "p")
        options = [normalize_text(item.text) for item in paragraphs[2:] if item.text]
        answer = normalize_text(
            element.find_element(By.CLASS_NAME, "answer").text
        )
        if options and answer:
            pairs.append((options, answer))
    return pairs


def download_sentences(url: str, output_path: Path, *, headless: bool = True) -> int:
    """Open a page in Chrome and write extracted exercises to a text file."""
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        pairs = collect_pairs(driver.find_elements(By.TAG_NAME, "div"))
    finally:
        driver.quit()

    with output_path.open("w", encoding="utf-8") as output_file:
        for sentences, answer in pairs:
            for sentence in sentences:
                print(sentence, file=output_file)
            print(answer, file=output_file)
    return len(pairs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="show Chrome instead of using headless mode",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    count = download_sentences(
        args.url,
        args.output,
        headless=not args.show_browser,
    )
    print(f"Wrote {count} exercises to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
