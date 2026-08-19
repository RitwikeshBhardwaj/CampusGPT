import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_data_dir(monkeypatch):
    d = Path(tempfile.mkdtemp(prefix="campusgpt-test-"))
    monkeypatch.setenv("CAMPUSGPT_DATA_DIR", str(d))
    yield d
    shutil.rmtree(d, ignore_errors=True)
