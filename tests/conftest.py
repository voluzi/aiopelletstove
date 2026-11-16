import json
from pathlib import Path

import pytest
from aioresponses import aioresponses


@pytest.fixture
def frames():
    return {
        category: json.loads(
            (Path(__file__).parent / f"fixtures/category_{category}.json").read_text()
        )
        for category in (2, 5, 11)
    }


@pytest.fixture
def http():
    with aioresponses() as mocked:
        yield mocked
