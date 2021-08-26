from pathlib import Path
import shutil
import pytest


@pytest.fixture
def revert_homedir():
    defaultdir = Path.home() / '.cvdupdate/'

    yield
    if defaultdir.exists():
        shutil.rmtree(str(defaultdir))

