import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
SHA256_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _assert_digest_pinned(reference: str) -> None:
    name, separator, digest = reference.rpartition("@sha256:")
    assert separator == "@sha256:"
    assert name
    assert SHA256_DIGEST.fullmatch(digest)


def test_runtime_container_images_are_digest_pinned() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    from_line = next(
        line for line in dockerfile.splitlines() if line.startswith("FROM ")
    )
    _assert_digest_pinned(from_line.removeprefix("FROM ").split()[0])

    compose = (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")
    image_references = re.findall(r"^\s+image:\s+(\S+)$", compose, re.MULTILINE)

    assert len(image_references) == 2
    for reference in image_references:
        _assert_digest_pinned(reference)


def test_production_requirements_are_exactly_pinned() -> None:
    direct_requirements = (PROJECT_ROOT / "requirements.in").read_text(
        encoding="utf-8"
    )
    direct_entries = [
        line.strip()
        for line in direct_requirements.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(
        encoding="utf-8"
    )
    locked_entries = re.findall(
        r"(?ms)^[A-Za-z0-9][^\n]*==.*?(?=^[A-Za-z0-9][^\n]*==|\Z)",
        requirements,
    )

    assert direct_entries
    assert all("==" in entry for entry in direct_entries)
    assert locked_entries
    assert all("==" in entry and "--hash=sha256:" in entry for entry in locked_entries)
