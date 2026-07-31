from pathlib import Path

import pytest

from mcp_review.static_rules.base import SourceFile

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    def _load(name: str) -> SourceFile:
        path = FIXTURES_DIR / name
        return SourceFile(path=str(path), content=path.read_text())

    return _load
