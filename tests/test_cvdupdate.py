import json
import os
import time
import datetime
import socket
from pathlib import Path
from typing import Any

from tests.fixtures.revert import revert_homedir

from cvdupdate.cvdupdate import CVDUpdate, CvdStatus

def test_instantiation(revert_homedir):
    c = CVDUpdate()

def test_alternate_config_locations(revert_homedir, tmp_path):
    ''' Test that we can save config and state files to alternative locations '''
    # ensure we're starting with a clean slate
    default_cvdupdate_dir = Path.home() / '.cvdupdate'
    assert not default_cvdupdate_dir.exists()

    # set config and state to be in pytests's /tmp/pytest-*
    config_file_path = tmp_path / 'config.json'
    state_file_path = tmp_path / 'state.json'
    c = CVDUpdate(
        config=config_file_path,
        state_file=str(state_file_path),
    )

    # verify config file is created and matches in-memory config
    assert config_file_path.exists()
    assert json.loads(config_file_path.read_text()) == c.config
    expected_config = {**c.default_config, 'state_file': str(state_file_path)}
    assert c.config == expected_config

    # verify state file is created and has the three default databases
    assert state_file_path.exists()
    state_file_json = json.loads(state_file_path.read_text())
    assert state_file_json == c.state
    assert set(state_file_json['dbs'].keys()) == {'main.cvd', 'daily.cvd', 'bytecode.cvd'}
    del c.state['uuid']
    assert c.state == c.default_state

    # logs are disabled by default, so ~/.cvdupdate should not be created at all
    assert not default_cvdupdate_dir.exists()


def test_custom_config_colocates_state_file(revert_homedir, tmp_path):
    ''' A custom config path without an explicit state file should default the
    state file next to that config (as in <= 1.2.0), not in $HOME/.cvdupdate. '''
    default_cvdupdate_dir = Path.home() / '.cvdupdate'
    assert not default_cvdupdate_dir.exists()

    config_dir = tmp_path / 'altconfig'
    config_dir.mkdir()
    config_file_path = config_dir / 'config.json'

    c = CVDUpdate(config=str(config_file_path))

    assert c.config['state_file'] == str(config_dir / 'state.json')
    assert (config_dir / 'state.json').exists()
    # the default ~/.cvdupdate must not be created for a custom config path
    assert not default_cvdupdate_dir.exists()


def test_logs_enabled(revert_homedir, tmp_path):
    ''' Test that when logs_enabled=True, a dated log file is created in the logs directory '''
    logs_dir_path = tmp_path / 'logs'
    CVDUpdate(
        config=tmp_path / 'config.json',
        state_file=str(tmp_path / 'state.json'),
        logs_enabled=True,
        logs_directory=str(logs_dir_path),
    )

    assert logs_dir_path.exists()
    log_files = list(logs_dir_path.iterdir())
    assert len(log_files) == 1
    assert log_files[0].name == f"{datetime.date.today():%Y-%m-%d}.log"


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

    assert all(val == b.config[key] for key,val in a.config.items() if key != 'state_file')
    assert id(a.config) != id(b.config)
    assert id(a.default_config) == id(b.default_config) == id(CVDUpdate.default_config)
    assert id(a.state) != id(b.state)
    assert id(a.default_state) == id(b.default_state)


def test_v1_config_migrates_successfully(revert_homedir):
    ''' Test that a v1.0.x config.json is migrated to the current format on load:
    - old space-separated keys are renamed to underscore keys
    - values are preserved across the rename
    - dbs and uuid are moved out of config into a separate state.json
    - new keys absent from the old config are filled in from defaults
    - logs_enabled is set to True (old configs always had logging on)
    '''
    default_cvdupdate_dir = Path.home() / '.cvdupdate'
    default_cvdupdate_dir.mkdir(parents=True)

    logs_dir = str(default_cvdupdate_dir / 'logs')
    db_dir   = str(default_cvdupdate_dir / 'database')

    old_config = json.loads(Path('tests/files/v1.0.2.config.json').read_text())
    old_config['log directory'] = logs_dir
    old_config['db directory']  = db_dir
    with (default_cvdupdate_dir / 'config.json').open('w') as f:
        json.dump(old_config, f)

    a = CVDUpdate()

    # --- key renames: old keys must be gone ---
    old_keys = {'nameserver', 'max retry', 'log directory', 'rotate logs',
                '# logs to keep', 'db directory', 'rotate cdiffs',
                '# cdiffs to keep', 'dbs', 'uuid'}
    assert old_keys.isdisjoint(a.config.keys())

    # --- key renames: values must be preserved ---
    assert a.config['nameservers']    == old_config['nameserver']
    assert a.config['max_retries']    == old_config['max retry']
    assert a.config['logs_directory'] == logs_dir
    assert a.config['logs_rotate']    == old_config['rotate logs']
    assert a.config['logs_to_keep']   == old_config['# logs to keep']
    assert a.config['dbs_directory']  == db_dir
    assert a.config['cdiffs_rotate']  == old_config['rotate cdiffs']
    assert a.config['cdiffs_to_keep'] == old_config['# cdiffs to keep']

    # --- state_file defaults next to the config when not set ---
    assert a.config['state_file'] == str(default_cvdupdate_dir / 'state.json')

    # --- config must have exactly the current key set ---
    assert a.config.keys() == CVDUpdate.default_config.keys()

    # --- old config implies logs were always on: logs_enabled must be True and log file present ---
    assert a.config['logs_enabled'] == True
    log_files = list(Path(logs_dir).iterdir())
    assert len(log_files) == 1
    assert log_files[0].name == f"{datetime.date.today():%Y-%m-%d}.log"

    # --- dbs and uuid must have been moved to state ---
    assert a.state['dbs']  == old_config['dbs']
    assert a.state['uuid'] == old_config['uuid']

    # --- verify config.json on disk matches in-memory config ---
    with (default_cvdupdate_dir / 'config.json').open() as f:
        disk_config = json.load(f)
    assert disk_config == a.config

    # --- verify state.json on disk matches in-memory state ---
    with Path(disk_config['state_file']).open() as f:
        disk_state = json.load(f)
    assert disk_state == a.state


def test_sign_download_uses_origin_name_for_url_and_local_name_for_file(revert_homedir, tmp_path, monkeypatch):
    db_dir = tmp_path / 'db'
    db_dir.mkdir()

    c = CVDUpdate(
        config=str(tmp_path / 'config.json'),
        state_file=str(tmp_path / 'state.json'),
        dbs_directory=str(db_dir),
    )

    called = {}

    class FakeResponse:
        status_code = 200
        content = b'sigdata'
        headers = {'content-length': str(len(content))}

    def fake_get(url, headers):
        called['url'] = url
        called['headers'] = headers
        return FakeResponse()

    def fail_network(*args, **kwargs):
        raise AssertionError('Real network usage is forbidden in this test')

    local_sign_path = db_dir / 'local-main.cvd.sign'
    real_exists = Path.exists
    real_open = Path.open
    wrote: dict[str, Any] = {}

    class FakeBinaryWriter:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def write(self, data: bytes) -> int:
            wrote['data'] = data
            return len(data)

    def fake_exists(self):
        if self == local_sign_path:
            # Force the code path that performs the download + save.
            return False
        return real_exists(self)

    def fake_open(self, mode='r', *args, **kwargs):
        if self == local_sign_path and mode == 'wb':
            wrote['opened'] = True
            return FakeBinaryWriter()
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr('cvdupdate.cvdupdate.requests.get', fake_get)
    # Hard guard: if anything tries to open a real socket.
    monkeypatch.setattr(socket.socket, 'connect', fail_network)
    monkeypatch.setattr(socket.socket, 'connect_ex', fail_network)
    monkeypatch.setattr(Path, 'exists', fake_exists)
    monkeypatch.setattr(Path, 'open', fake_open)

    status = c._download_sign_file_for(
        file='local-main.cvd',
        file_url='https://database.clamav.net/main.cvd?version=12345',
        last_modified=0,
        version=12345,
    )

    assert status == CvdStatus.UPDATED
    assert called['url'] == 'https://database.clamav.net/main-12345.cvd.sign'
    assert wrote['opened'] is True
    assert wrote['data'] == b'sigdata'
    # Confirm no file was actually created by this test.
    assert not real_exists(local_sign_path)


def test_cdiff_rotation_removes_matching_sign_file(revert_homedir, tmp_path, monkeypatch):
    db_dir = tmp_path / 'db'
    db_dir.mkdir()

    c = CVDUpdate(
        config=str(tmp_path / 'config.json'),
        state_file=str(tmp_path / 'state.json'),
        dbs_directory=str(db_dir),
        cdiffs_to_keep=1,
    )

    class FakeResponse:
        status_code = 200
        headers = {'content-length': '7'}
        content = b'cdiff-1'

    requested_urls = []

    def fake_get(url, headers):
        requested_urls.append(url)
        return FakeResponse()

    monkeypatch.setattr('cvdupdate.cvdupdate.requests.get', fake_get)

    first_cdiff = db_dir / 'daily-1.cdiff'
    first_sign = db_dir / 'daily-1.cdiff.sign'
    first_cdiff.write_bytes(b'cdiff-1')
    first_sign.write_bytes(b'sign-1')
    c.state['dbs']['daily.cvd']['CDIFFs'] = ['daily-1.cdiff']

    result = c._download_cdiff(
        db='daily.cvd',
        file='daily-2.cdiff',
        db_url='https://database.clamav.net/daily.cvd',
        last_modified=0,
        desired_version=2,
        available_version=2,
    )

    assert result == CvdStatus.UPDATED
    assert not first_cdiff.exists()
    assert not first_sign.exists()
    assert (db_dir / 'daily-2.cdiff').exists()
    assert c.state['dbs']['daily.cvd']['CDIFFs'] == ['daily-2.cdiff']
    assert requested_urls == ['https://database.clamav.net/daily-2.cdiff']


def test_config_remove_db_removes_database_and_related_sign_files(revert_homedir, tmp_path):
    db_dir = tmp_path / 'db'
    db_dir.mkdir()

    c = CVDUpdate(
        config=str(tmp_path / 'config.json'),
        state_file=str(tmp_path / 'state.json'),
        dbs_directory=str(db_dir),
    )

    db_path = db_dir / 'daily.cvd'
    db_sign_path = db_dir / 'daily.cvd.sign'
    cdiff_path = db_dir / 'daily-1.cdiff'
    cdiff_sign_path = db_dir / 'daily-1.cdiff.sign'

    db_path.write_bytes(b'db')
    db_sign_path.write_bytes(b'db-sign')
    cdiff_path.write_bytes(b'cdiff')
    cdiff_sign_path.write_bytes(b'cdiff-sign')
    c.state['dbs']['daily.cvd']['CDIFFs'] = ['daily-1.cdiff']

    assert c.config_remove_db('daily.cvd') is True

    assert not db_path.exists()
    assert not db_sign_path.exists()
    assert not cdiff_path.exists()
    assert not cdiff_sign_path.exists()
    assert 'daily.cvd' not in c.state['dbs']


def _db_download_client(tmp_path, monkeypatch, content: bytes, content_length=None):
    db_dir = tmp_path / 'db'
    db_dir.mkdir()

    c = CVDUpdate(
        config=str(tmp_path / 'config.json'),
        state_file=str(tmp_path / 'state.json'),
        dbs_directory=str(db_dir),
    )

    requests_made = []

    class FakeResponse:
        status_code = 200
        headers = {'content-length': str(len(content) if content_length is None else content_length)}

        def iter_content(self, chunk_size):
            # Small chunks to exercise the streaming write path.
            for i in range(0, len(content), 16):
                yield content[i:i + 16]

        def close(self):
            pass

    class NoSignResponse:
        status_code = 404
        headers = {}
        content = b''

    def fake_get(url, headers, stream=False):
        if url.endswith('.sign'):
            return NoSignResponse()
        requests_made.append({'url': url, 'stream': stream})
        return FakeResponse()

    monkeypatch.setattr('cvdupdate.cvdupdate.requests.get', fake_get)
    return c, db_dir, requests_made


PROVIDER_NOTICE = (
    b"Do you want to download additional signatures?\n"
    b"Please go to :\n\n"
    b"https://example.com/subscribe\n"
)

THIRD_PARTY_DB_STATE = {'retry after': 0, 'last modified': 0, 'local version': 0}


def test_download_rejects_non_signature_text_and_keeps_existing_db(revert_homedir, tmp_path, monkeypatch):
    c, db_dir, _ = _db_download_client(tmp_path, monkeypatch, PROVIDER_NOTICE)
    url = 'https://example.com/provider.ign2'
    c.state['dbs']['provider.ign2'] = dict(THIRD_PARTY_DB_STATE, url=url)
    existing = db_dir / 'provider.ign2'
    existing.write_bytes(b'Provider.Old.Sig\n')

    status = c._download_db_from_url('provider.ign2', url, 0)

    assert status == CvdStatus.ERROR
    assert existing.read_bytes() == b'Provider.Old.Sig\n'
    assert c.state['dbs']['provider.ign2']['last modified'] == 0
    assert sorted(f.name for f in db_dir.iterdir()) == ['provider.ign2']


def test_download_streams_valid_text_db_into_place(revert_homedir, tmp_path, monkeypatch):
    content = b'# comment\nProvider.Some.Sig\r\nOther.Sig:0123456789abcdef0123456789abcdef\n'
    c, db_dir, requests_made = _db_download_client(tmp_path, monkeypatch, content)
    url = 'https://example.com/provider.ign2'
    c.state['dbs']['provider.ign2'] = dict(THIRD_PARTY_DB_STATE, url=url)

    status = c._download_db_from_url('provider.ign2', url, 0)

    assert status == CvdStatus.UPDATED
    assert requests_made[0] == {'url': url, 'stream': True}
    assert (db_dir / 'provider.ign2').read_bytes() == content
    assert not (db_dir / '.provider.ign2.tmp').exists()
    assert c.state['dbs']['provider.ign2']['last modified'] > 0


def test_download_truncated_response_retries_and_keeps_existing_db(revert_homedir, tmp_path, monkeypatch):
    content = b'Some.Sig\n'
    c, db_dir, requests_made = _db_download_client(tmp_path, monkeypatch, content, content_length=len(content) + 100)
    url = 'https://example.com/x.ign2'
    c.state['dbs']['x.ign2'] = dict(THIRD_PARTY_DB_STATE, url=url)
    existing = db_dir / 'x.ign2'
    existing.write_bytes(b'Old.Sig\n')

    status = c._download_db_from_url('x.ign2', url, 0)

    assert status == CvdStatus.ERROR
    assert len(requests_made) == c.config['max_retries']
    assert existing.read_bytes() == b'Old.Sig\n'
    assert sorted(f.name for f in db_dir.iterdir()) == ['x.ign2']


CVD_HEADER = b'ClamAV-VDB:01 Jan 2026 00-00 +0000:27000:100:90:sig:builder:1700000000'.ljust(512, b' ')


def test_download_cvd_sets_local_version_from_saved_file(revert_homedir, tmp_path, monkeypatch):
    c, db_dir, _ = _db_download_client(tmp_path, monkeypatch, CVD_HEADER + b'body')
    url = 'https://example.com/custom.cvd'
    c.state['dbs']['custom.cvd'] = dict(THIRD_PARTY_DB_STATE, url=url)

    status = c._download_db_from_url('custom.cvd', url, 0, version=27000)

    assert status == CvdStatus.UPDATED
    assert c.state['dbs']['custom.cvd']['local version'] == 27000


def test_validate_db_file(revert_homedir, tmp_path):
    c = CVDUpdate(
        config=str(tmp_path / 'config.json'),
        state_file=str(tmp_path / 'state.json'),
        dbs_directory=str(tmp_path / 'db'),
    )

    def check(db, content, version=0):
        path = tmp_path / f'candidate-{db}'
        path.write_bytes(content)
        return c._validate_db_file(db, path, version)

    assert check('daily.cvd', CVD_HEADER + b'body', 27000) is None
    # Advertised (DNS) version may lag behind the published file: newer is fine, older is a stale mirror.
    assert check('daily.cvd', CVD_HEADER + b'body', 26999) is None
    assert check('daily.cvd', CVD_HEADER + b'body', 27001) is not None
    assert check('daily.cvd', b'', 27000) is not None
    assert check('daily.cvd', b'<html>nope</html>', 27000) is not None
    assert check('x.hdb', b'44d88612fea8a8f36de82e1278abb02f:68:Eicar-Test-Signature\n') is None
    assert check('x.hdb', b'not a hash line\n') is not None
    assert check('x.ldb', b'Sig.Name;Engine:51-255,Target:0;0;41424344\n') is None
    assert check('x.ndb', b'<!DOCTYPE html><html></html>') is not None
    assert check('x.yara', b'rule a { condition: true }') is None
    # Empty text databases are valid (e.g. an empty ignore list).
    assert check('x.ign2', b'') is None
    # ClamAV does not forbid whitespace in signature names.
    assert check('x.ndb', b'Name With Spaces:0:*:4142\n') is None
    assert check('x.ign2', b'Name With Spaces\n') is None
    # .ign2 follows cli_loadign(): name, name:md5 or legacy db:line:name.
    assert check('x.ign2', b'Sig.A:44d88612fea8a8f36de82e1278abb02f\n') is None
    assert check('x.ign2', b'daily.ndb:12:Sig.A\n') is None
    assert check('x.ign2', b'Sig.A:not-an-md5\n') is not None
    assert check('x.ign2', b'a:b:c:d\n') is not None
    assert check('x.ign2', b'daily.ndb:12:\n') is not None
    assert check('x.ign2', b'Good.Sig\nBad\x00Sig\n') is not None
    assert check('x.ign2', PROVIDER_NOTICE) is not None


def test_validate_db_file_mirrors_clamav_loaders(revert_homedir, tmp_path):
    c = CVDUpdate(
        config=str(tmp_path / 'config.json'),
        state_file=str(tmp_path / 'state.json'),
        dbs_directory=str(tmp_path / 'db'),
    )

    def check(db, content):
        path = tmp_path / f'candidate-{db}'
        path.write_bytes(content)
        return c._validate_db_file(db, path)

    md5 = b'44d88612fea8a8f36de82e1278abb02f'

    # Field counts per loader (min-max).
    assert check('x.hdb', md5 + b':68:Sig:73:255\n') is None
    assert check('x.hdb', md5 + b':68:Sig:73:255:extra\n') is not None
    assert check('x.ndb', b'Sig:0:*:4142:73:255\n') is None
    assert check('x.ndb', b'Sig:0:*:4142:73:255:extra\n') is not None
    assert check('x.sdb', b'Sig:0:*\n') is not None
    assert check('x.ldb', b'Sig;Engine:81-255,Target:1;0\n') is not None
    assert check('x.cdb', b'Sig:CL_TYPE_ZIP:*:evil\\.exe:*:*:*:*:*:*\n') is None
    assert check('x.cdb', b'Sig:CL_TYPE_ZIP:*\n') is not None
    assert check('x.ftm', b'0:0:4d5a:Sig:CL_TYPE_ANY:CL_TYPE_MSEXE\n') is None
    assert check('x.ftm', b'0:0:4d5a:Sig\n') is not None
    assert check('x.idb', b'Sig:GROUP1:GROUP2:' + md5 + b'\n') is None
    assert check('x.idb', b'Sig:GROUP1:' + md5 + b'\n') is not None
    assert check('x.pwdb', b'Sig;Engine:81-255;0;password\n') is None
    assert check('x.pwdb', b'Sig;password\n') is not None

    # Regex lists: line type letter, then ':'.
    assert check('x.pdb', b'R:.+\\.example\\.com\nH:example.org\nS:F:' + md5 + b'\n') is None
    assert check('x.wdb', b'X:.+\\.example\\.com:.+\\.example\\.org:17-\nM:example.com:example.org\n') is None
    assert check('x.pdb', b'X:.+\\.example\\.com\n') is not None
    assert check('x.wdb', b'S:F:' + md5 + b'\n') is not None
    assert check('x.pdb', b'R.+\\.example\\.com\n') is not None

    # Comments only in the first column; empty lines only where ClamAV skips them.
    assert check('x.ndb', b'# comment\nSig:0:*:4142\n') is None
    assert check('x.ndb', b'  # indented comment\nSig:0:*:4142\n') is not None
    assert check('x.ndb', b'Sig.A:0:*:4142\n\nSig.B:0:*:4142\n') is not None
    assert check('x.ign2', b'Sig.A\n\n') is not None
    assert check('x.pdb', b'R:.+\\.example\\.com\n\nH:example.org\n') is None


def test_download_without_atomic_replace_overwrites_in_place(revert_homedir, tmp_path, monkeypatch):
    content = b'New.Sig\n'
    c, db_dir, _ = _db_download_client(tmp_path, monkeypatch, content)
    c.config['atomic_replace'] = False
    url = 'https://example.com/x.ign2'
    c.state['dbs']['x.ign2'] = dict(THIRD_PARTY_DB_STATE, url=url)
    existing = db_dir / 'x.ign2'
    existing.write_bytes(b'Old.Sig.With.A.Longer.Name\n')
    inode_before = os.stat(existing).st_ino

    status = c._download_db_from_url('x.ign2', url, 0)

    assert status == CvdStatus.UPDATED
    assert existing.read_bytes() == content
    # Same file overwritten, not replaced: what a single-file bind mount needs.
    assert os.stat(existing).st_ino == inode_before
    assert sorted(f.name for f in db_dir.iterdir()) == ['x.ign2']


def test_clean_stale_tmp_files_removes_only_old_temp_files(revert_homedir, tmp_path):
    db_dir = tmp_path / 'db'
    db_dir.mkdir()
    c = CVDUpdate(
        config=str(tmp_path / 'config.json'),
        state_file=str(tmp_path / 'state.json'),
        dbs_directory=str(db_dir),
    )
    assert c.config['tmp_max_age_hours'] == 4

    old = time.time() - 5 * 60 * 60
    stale_tmp = db_dir / '.daily.cvd.tmp'
    fresh_tmp = db_dir / '.main.cvd.tmp'
    old_db = db_dir / 'daily.cvd'
    old_plain_tmp = db_dir / 'notes.tmp'
    for f in (stale_tmp, fresh_tmp, old_db, old_plain_tmp):
        f.write_bytes(b'x')
    for f in (stale_tmp, old_db, old_plain_tmp):
        os.utime(f, (old, old))

    c._clean_stale_tmp_files()

    assert not stale_tmp.exists()
    assert fresh_tmp.exists()
    assert old_db.exists()
    assert old_plain_tmp.exists()
