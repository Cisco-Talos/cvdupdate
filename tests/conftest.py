from glob import glob
from pathlib import Path

# grab all files from fixtures
pytest_plugins = [
    f'fixtures.{fi.stem}' for fi in Path(__file__).glob("fixtures/*.py") if fi.stem != '__init__'
]