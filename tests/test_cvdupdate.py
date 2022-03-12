import json
from pathlib import Path
import shutil

from tests.fixtures.revert import revert_homedir

from cvdupdate.cvdupdate import CVDUpdate

def test_instantiation(revert_homedir):
    c = CVDUpdate()

def test_alternate_config_locations(revert_homedir, tmp_path):
    ''' Test that we can save config and state files to alternative locations '''
    # ensure we're starting with a clean slate
    default_cvdupdate_dir = Path.home() / '.cvdupdate'
    assert not default_cvdupdate_dir.exists()

    # set the config file to be in pytests's /tmp/pytest-*
    config_file_path = tmp_path / 'config.json'
    c = CVDUpdate(config=config_file_path)

    # verify the file is created and has default config data inside
    assert config_file_path.exists()
    txt = config_file_path.read_text()
    assert txt
    config_file_json = json.loads(txt)
    assert config_file_json == c.config
    # state file value will differ, so blank it out for comparing
    c.config['state file'] = ''
    assert c.config == c.default_config

    # verify the state file is created and has default data inside
    state_file_path = tmp_path / 'state.json'
    assert state_file_path.exists()
    txt = state_file_path.read_text()
    assert txt
    state_file_json = json.loads(txt)
    assert state_file_json == c.state
    # again, uuid will differ, so toss it out
    del c.state['uuid']
    assert c.state == c.default_state

    # ~/.cvdupdate exists, because we haven't changed the logdir location
    # but that's all it should have in it
    default_cvdupdate_dir = Path.home() / '.cvdupdate'
    assert default_cvdupdate_dir.exists()
    children = list(default_cvdupdate_dir.iterdir())
    assert len(children) == 1
    assert children[0] == default_cvdupdate_dir / 'logs'


def test_default_config_not_mutated(revert_homedir, tmp_path):
    ''' default_config and default_state are both class-level attributes
    Ensure that when we copy these, we are actually copying them and not simply reassigning
    note that this typically won't be a problem in normal usage,
    but it was a problem during testing and was really annoying to track down
    '''
    a = CVDUpdate()
    config_file_path = tmp_path / 'config.json'
    # set the config file to be in pytests /tmp/pytest-*
    b = CVDUpdate(config=config_file_path)

    assert all(val == b.config[key] for key,val in a.config.items() if key != 'state file')
    assert id(a.config) != id(b.config)
    assert id(a.default_config) == id(b.default_config) == id(CVDUpdate.default_config)
    assert a.state != b.state
    assert id(a.default_state) == id(b.default_state)


def test_existing_state_migrates_successfully(revert_homedir):
    ''' specifically test migrating an existing config.json to config + state.json'''
    default_cvdupdate_dir = Path.home() / '.cvdupdate'
    default_cvdupdate_dir.mkdir(parents=True)

    # create a .cvdupdate/config.json which also contains dbs definitions
    old_config_file = 'tests/files/v1.0.2.config.json'
    old_config_json = json.loads(Path(old_config_file).read_text())
    old_config_json["log directory"] = str(default_cvdupdate_dir / 'logs')
    old_config_json["db directory"] = str(default_cvdupdate_dir / 'database')

    with (default_cvdupdate_dir / 'config.json').open('w') as test_config:
        json.dump(old_config_json, test_config)

    # create cvdupdate object, which will read config.json and split state into state.json
    a = CVDUpdate()

    new_config_json = old_config_json

    # create expected state.json contents by copying the bits that move
    new_state_json = {}
    new_state_json['dbs'] = old_config_json['dbs']
    new_state_json['uuid'] = old_config_json['uuid']

    # new update the config.json contents
    del new_config_json['dbs']
    del new_config_json['uuid']
    new_config_json['state file'] = str(default_cvdupdate_dir / 'state.json')

    # compare actual result with expected transform
    with open(default_cvdupdate_dir / 'config.json') as config:
        assert new_config_json == json.loads(config.read())
    with open(default_cvdupdate_dir / 'state.json') as state:
        from pprint import pprint
        assert new_state_json == json.loads(state.read())
