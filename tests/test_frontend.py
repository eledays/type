from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


def test_analytics_search_browser_logic() -> None:
    """Run dependency-free tests for code executed by the browser."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed")
    test_file = Path(__file__).parent / "js" / "analytics_search.test.cjs"
    result = subprocess.run(  # noqa: S603
        [node, "--test", str(test_file)],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
