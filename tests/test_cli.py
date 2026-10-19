import json
import re
import threading
import http.client
from http.server import HTTPServer

from click.testing import CliRunner

from tests.fixtures.revert import revert_homedir

from cvdupdate.cvdupdate import CVDUpdate
from cvdupdate.__main__ import cli, MirrorRequestHandler


def _init_config(tmp_path):
    """Create an isolated config + state in tmp_path and return the config path (str)."""
    config_path = tmp_path / 'config.json'
    CVDUpdate(
        config=str(config_path),
        state_file=str(tmp_path / 'state.json'),
        dbs_directory=str(tmp_path / 'database'),
    )
    return str(config_path)


def _load_config(tmp_path):
    return json.loads((tmp_path / 'config.json').read_text())


def _load_state(tmp_path):
    return json.loads((tmp_path / 'state.json').read_text())


def _all_output(result):
    """Combined stdout+stderr, regardless of whether Click mixes the streams."""
    text = result.output or ''
    try:
        err = result.stderr
        if err:
            text += err
    except (ValueError, AttributeError):
        # stderr was mixed into stdout already (older Click).
        pass
    return text


# --- status / list ---------------------------------------------------------

def test_list_prints_only_names(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    result = CliRunner().invoke(cli, ['list', '--config', cfg])
    assert result.exit_code == 0
    names = set(result.output.split())
    assert names == {'main.cvd', 'daily.cvd', 'bytecode.cvd'}


def test_list_json_is_an_array(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    result = CliRunner().invoke(cli, ['list', '--config', cfg, '--json'])
    assert result.exit_code == 0
    assert set(json.loads(result.output)) == {'main.cvd', 'daily.cvd', 'bytecode.cvd'}


def test_status_all_json_matches_state(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    result = CliRunner().invoke(cli, ['status', '--config', cfg, '--json'])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert set(payload['dbs'].keys()) == {'main.cvd', 'daily.cvd', 'bytecode.cvd'}


def test_status_single_json(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    result = CliRunner().invoke(cli, ['status', '--config', cfg, '--json', 'daily.cvd'])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload['url'] == 'https://database.clamav.net/daily.cvd'


def test_status_single_unknown_json_exits_nonzero(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    result = CliRunner().invoke(cli, ['status', '--config', cfg, '--json', 'nope.cvd'])
    assert result.exit_code == 1


def test_status_json_includes_local_dbs(revert_homedir, tmp_path):
    # A DB file present on disk but not yet in state must appear in both the
    # text and --json forms (both go through the indexed database view).
    cfg = _init_config(tmp_path)
    db_dir = tmp_path / 'database'
    db_dir.mkdir(exist_ok=True)
    (db_dir / 'local.hdb').write_bytes(b'signatures')

    result = CliRunner().invoke(cli, ['status', '--config', cfg, '--json'])
    assert result.exit_code == 0
    assert 'local.hdb' in json.loads(result.output)['dbs']

    single = CliRunner().invoke(cli, ['status', '--config', cfg, '--json', 'local.hdb'])
    assert single.exit_code == 0
    assert json.loads(single.output)['url'] == 'n/a'


# --- aliases ---------------------------------------------------------------

def test_short_aliases_resolve(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    # 's' -> status, 'ls' -> list
    assert CliRunner().invoke(cli, ['s', '--config', cfg, '--json']).exit_code == 0
    ls = CliRunner().invoke(cli, ['ls', '--config', cfg, '--json'])
    assert ls.exit_code == 0
    assert set(json.loads(ls.output)) == {'main.cvd', 'daily.cvd', 'bytecode.cvd'}


def test_show_is_deprecated_alias_for_status(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    result = CliRunner().invoke(cli, ['show', '--config', cfg, 'daily.cvd'])
    assert result.exit_code == 0
    assert 'deprecated' in _all_output(result).lower()
    # It should still show the requested database.
    assert 'daily.cvd' in result.output


def test_show_is_hidden_from_help():
    result = CliRunner().invoke(cli, ['--help'])
    assert result.exit_code == 0
    # `show` is a deprecated hidden alias; it must not be listed as a command.
    assert not re.search(r'(?m)^\s+show\b', result.output)
    # sanity: a visible command is still listed
    assert re.search(r'(?m)^\s+status\b', result.output)


def test_show_json_behaves_like_status(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    result = CliRunner().invoke(cli, ['show', '--config', cfg, '--json', 'daily.cvd'])
    assert result.exit_code == 0
    # The deprecation warning goes to stderr; the JSON payload is still parseable
    # from the tail of the combined output.
    json_start = result.output.index('{')
    payload = json.loads(result.output[json_start:])
    assert payload['url'] == 'https://database.clamav.net/daily.cvd'


# --- add --override --------------------------------------------------------

def test_add_existing_without_override_fails(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    result = CliRunner().invoke(
        cli, ['add', '--config', cfg, 'main.cvd', 'https://example.com/main.cvd'])
    assert result.exit_code == 1
    assert _load_state(tmp_path)['dbs']['main.cvd']['url'] == 'https://database.clamav.net/main.cvd'


def test_add_existing_with_override_updates_url(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    result = CliRunner().invoke(
        cli, ['add', '--config', cfg, '--override', 'main.cvd', 'https://example.com/main.cvd'])
    assert result.exit_code == 0
    assert _load_state(tmp_path)['dbs']['main.cvd']['url'] == 'https://example.com/main.cvd'


# --- config set: deprecated flag aliases -----------------------------------

def test_config_set_no_options_prints_help(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    result = CliRunner().invoke(cli, ['config', 'set', '--config', cfg])
    assert result.exit_code == 0
    assert 'Usage:' in result.output


def test_config_set_deprecated_dbdir_maps_to_dbs_directory(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    new_dir = str(tmp_path / 'new-db-dir')
    result = CliRunner().invoke(cli, ['config', 'set', '--config', cfg, '--dbdir', new_dir])
    assert result.exit_code == 0
    assert 'deprecated' in _all_output(result).lower()
    assert _load_config(tmp_path)['dbs_directory'] == new_dir


def test_config_set_deprecated_nameserver_maps_to_nameservers(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    result = CliRunner().invoke(
        cli, ['config', 'set', '--config', cfg, '--nameserver', '208.67.222.222'])
    assert result.exit_code == 0
    assert 'deprecated' in _all_output(result).lower()
    assert _load_config(tmp_path)['nameservers'] == '208.67.222.222'


def test_config_set_deprecated_logdir_maps_and_enables_logging(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    new_dir = str(tmp_path / 'new-log-dir')
    result = CliRunner().invoke(cli, ['config', 'set', '--config', cfg, '--logdir', new_dir])
    assert result.exit_code == 0
    assert 'deprecated' in _all_output(result).lower()
    cfg_json = _load_config(tmp_path)
    assert cfg_json['logs_directory'] == new_dir
    # The old --logdir implied file logging was on; the alias must preserve that.
    assert cfg_json['logs_enabled'] is True


def test_config_set_logdir_respects_explicit_no_logs(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    new_dir = str(tmp_path / 'no-log-dir')
    result = CliRunner().invoke(
        cli, ['config', 'set', '--config', cfg, '--logdir', new_dir, '--no-logs-enabled'])
    assert result.exit_code == 0
    cfg_json = _load_config(tmp_path)
    assert cfg_json['logs_directory'] == new_dir
    assert cfg_json['logs_enabled'] is False


def test_config_set_atomic_replace_and_tmp_max_age(revert_homedir, tmp_path):
    cfg = _init_config(tmp_path)
    assert _load_config(tmp_path)['atomic_replace'] is True
    assert _load_config(tmp_path)['tmp_max_age_hours'] == 4

    result = CliRunner().invoke(
        cli, ['config', 'set', '--config', cfg, '--no-atomic-replace', '--tmp-max-age-hours', '12'])
    assert result.exit_code == 0
    cfg_json = _load_config(tmp_path)
    assert cfg_json['atomic_replace'] is False
    assert cfg_json['tmp_max_age_hours'] == 12


# --- serve -----------------------------------------------------------------

def test_serve_help_documents_default_and_random_port():
    result = CliRunner().invoke(cli, ['serve', '--help'])
    assert result.exit_code == 0
    assert '8000' in result.output
    assert 'random' in result.output.lower()


def test_serve_handler_hides_dotfiles_and_dotdirs(tmp_path, monkeypatch):
    db_dir = tmp_path / 'database'
    db_dir.mkdir()
    (db_dir / 'daily.cvd').write_bytes(b'CVD-DATA')
    (db_dir / '.state.json').write_text('{"uuid": "secret"}')
    (db_dir / '.hidden').write_text('nope')
    dotdir = db_dir / '.git'
    dotdir.mkdir()
    (dotdir / 'config').write_text('secret')

    monkeypatch.chdir(db_dir)

    httpd = HTTPServer(('127.0.0.1', 0), MirrorRequestHandler)
    port = httpd.server_address[1]
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    def get(path):
        conn = http.client.HTTPConnection('127.0.0.1', port)
        try:
            conn.request('GET', path)
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    try:
        status, body = get('/daily.cvd')
        assert status == 200
        assert body == b'CVD-DATA'

        assert get('/.state.json')[0] == 404
        assert get('/.hidden')[0] == 404
        # A file inside a dotdir must be blocked too, not just dot-prefixed files.
        assert get('/.git/config')[0] == 404
        # Percent-encoding the leading dot must not bypass the check.
        assert get('/%2estate.json')[0] == 404
        assert get('/%2egit/config')[0] == 404

        status, listing = get('/')
        assert status == 200
        assert b'daily.cvd' in listing
        assert b'.state.json' not in listing
        assert b'.hidden' not in listing
        assert b'.git' not in listing
    finally:
        httpd.shutdown()
        httpd.server_close()
        server_thread.join(timeout=5)
