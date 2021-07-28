from pathlib import Path
import shutil
import pytest


@pytest.fixture
def revert_homedir():
    homedir = Path.home() / '.cvdupdate/'

    yield
    if homedir.exists():
        shutil.rmtree(str(homedir))
