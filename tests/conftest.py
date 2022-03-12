from textwrap import dedent
from glob import glob
from pathlib import Path

import pytest

# grab all files from fixtures/
pytest_plugins = [
    f'fixtures.{fi.stem}' for fi in Path(__file__).glob("fixtures/*.py") if fi.stem != '__init__'
]

# prevent any test from running if the default .cvdupdate directory already exists
@pytest.fixture(scope='session', autouse=True)
def fail_if_cvdupdate_dir_exists():
    defaultdir = Path.home() / '.cvdupdate'
    if defaultdir.exists():
        pytest.exit(dedent(f'''
            Error: {defaultdir} exists.
            Aborting tests to prevent losing actual cvdupdate data.
            Ensure tests are not running against an actual cvdupdate install.
        '''),
        returncode=1
        )

