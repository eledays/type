from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_browser_logic() -> None:
    """Run dependency-free tests for code executed by the browser."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed")
    test_directory = Path(__file__).parent / "js"
    test_files = sorted(test_directory.glob("*.test.cjs"))
    result = subprocess.run(  # noqa: S603
        [node, "--test", *(str(path) for path in test_files)],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
