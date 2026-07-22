"""
Tests for proxy authentication support.

Copyright (C) 2021-2025 Cisco Systems, Inc. and/or its affiliates. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os
from unittest import mock

import pytest
from click.testing import CliRunner

from tests.fixtures.revert import revert_homedir
from cvdupdate.cvdupdate import CVDUpdate
from cvdupdate.__main__ import cli


class TestGetProxyConfiguration:
    """Tests for _get_proxy_configuration method."""

    def test_returns_none_when_not_configured(self, revert_homedir):
        """Test that None is returned when no proxy is configured."""
        c = CVDUpdate()
        result = c._get_proxy_configuration()
        assert result is None

    def test_returns_proxy_from_config(self, revert_homedir):
        """Test that proxy URL is returned from config."""
        c = CVDUpdate()
        c.config['proxy_url'] = 'http://proxy.example.com:8080'
        result = c._get_proxy_configuration()
        assert result == {
            'http': 'http://proxy.example.com:8080',
            'https': 'http://proxy.example.com:8080',
        }

    def test_env_var_takes_precedence(self, revert_homedir):
        """Test that environment variable takes precedence over config."""
        c = CVDUpdate()
        c.config['proxy_url'] = 'http://config-proxy.example.com:8080'

        with mock.patch.dict(os.environ, {'CVDUPDATE_PROXY_URL': 'http://env-proxy.example.com:3128'}):
            result = c._get_proxy_configuration()
            assert result == {
                'http': 'http://env-proxy.example.com:3128',
                'https': 'http://env-proxy.example.com:3128',
            }

    def test_embeds_credentials_in_proxy_url(self, revert_homedir):
        """Test that user/pass are embedded in the proxy URL for Proxy-Authorization."""
        c = CVDUpdate()
        c.config['proxy_url'] = 'http://proxy.example.com:8080'
        c.config['proxy_user'] = 'testuser'
        c.config['proxy_pass'] = 'testpass'
        result = c._get_proxy_configuration()
        assert result == {
            'http': 'http://testuser:testpass@proxy.example.com:8080',
            'https': 'http://testuser:testpass@proxy.example.com:8080',
        }

    def test_url_encodes_special_chars_in_credentials(self, revert_homedir):
        """Test that special characters in credentials are URL-encoded."""
        c = CVDUpdate()
        c.config['proxy_url'] = 'http://proxy.example.com:8080'
        c.config['proxy_user'] = 'user@domain'
        c.config['proxy_pass'] = 'p@ss:word/123'
        result = c._get_proxy_configuration()
        assert 'user%40domain' in result['http']
        assert 'p%40ss%3Aword%2F123' in result['http']
        assert '@proxy.example.com:8080' in result['http']

    def test_does_not_double_embed_credentials(self, revert_homedir):
        """Test that credentials already in the URL are not duplicated."""
        c = CVDUpdate()
        c.config['proxy_url'] = 'http://existinguser:existingpass@proxy.example.com:8080'
        c.config['proxy_user'] = 'newuser'
        c.config['proxy_pass'] = 'newpass'
        result = c._get_proxy_configuration()
        assert 'existinguser:existingpass@' in result['http']
        assert 'newuser' not in result['http']

    def test_env_credentials_take_precedence(self, revert_homedir):
        """Test that env var credentials take precedence over config."""
        c = CVDUpdate()
        c.config['proxy_url'] = 'http://proxy.example.com:8080'
        c.config['proxy_user'] = 'config_user'
        c.config['proxy_pass'] = 'config_pass'

        with mock.patch.dict(os.environ, {
            'CVDUPDATE_PROXY_USER': 'env_user',
            'CVDUPDATE_PROXY_PASS': 'env_pass',
        }):
            result = c._get_proxy_configuration()
            assert 'env_user:env_pass@' in result['http']

    def test_no_credentials_without_both_user_and_pass(self, revert_homedir):
        """Test that credentials are not embedded when only user or only pass is set."""
        c = CVDUpdate()
        c.config['proxy_url'] = 'http://proxy.example.com:8080'
        c.config['proxy_user'] = 'testuser'
        result = c._get_proxy_configuration()
        assert 'testuser' not in result['http']
        assert result == {
            'http': 'http://proxy.example.com:8080',
            'https': 'http://proxy.example.com:8080',
        }


class TestPasswordMasking:
    """Tests for credential masking in the 'config show' command."""

    def test_config_show_masks_password(self, revert_homedir):
        """Test that password is masked in config show output."""
        c = CVDUpdate()
        c.config['proxy_pass'] = 'supersecret'
        c._save_config()

        result = CliRunner().invoke(cli, ['config', 'show', '--config', str(c.config_path)])
        assert result.exit_code == 0
        assert 'supersecret' not in result.output
        assert '********' in result.output

    def test_config_show_masks_credentials_in_proxy_url(self, revert_homedir):
        """Credentials embedded directly in proxy_url must be masked too."""
        c = CVDUpdate()
        c.config['proxy_url'] = 'http://user:supersecret@proxy.example.com:8080'
        c._save_config()

        result = CliRunner().invoke(cli, ['config', 'show', '--config', str(c.config_path)])
        assert result.exit_code == 0
        assert 'supersecret' not in result.output
        assert '***:***@proxy.example.com:8080' in result.output

    def test_config_show_masks_scheme_less_embedded_credentials(self, revert_homedir):
        """A scheme-less proxy_url with userinfo must be masked in config show."""
        c = CVDUpdate()
        c.config['proxy_url'] = 'user:supersecret@proxy.example.com:8080'
        c._save_config()

        result = CliRunner().invoke(cli, ['config', 'show', '--config', str(c.config_path)])
        assert result.exit_code == 0
        assert 'supersecret' not in result.output
        assert '***:***@proxy.example.com:8080' in result.output


class TestSanitizeProxyUrl:
    """Tests for the _sanitize_proxy_url helper."""

    def test_masks_userinfo(self, revert_homedir):
        url = 'http://user:secret@proxy.example.com:8080/path'
        sanitized = CVDUpdate._sanitize_proxy_url(url)
        assert 'secret' not in sanitized
        assert sanitized == 'http://***:***@proxy.example.com:8080/path'

    def test_leaves_url_without_userinfo_unchanged(self, revert_homedir):
        url = 'http://proxy.example.com:8080'
        assert CVDUpdate._sanitize_proxy_url(url) == url

    def test_masks_ipv6_userinfo(self, revert_homedir):
        url = 'http://user:secret@[::1]:3128'
        sanitized = CVDUpdate._sanitize_proxy_url(url)
        assert 'secret' not in sanitized
        assert sanitized == 'http://***:***@[::1]:3128'

    def test_does_not_crash_on_invalid_port(self, revert_homedir):
        # urlparse validates the port lazily; a malformed one must not raise.
        url = 'http://user:secret@proxy.example.com:notaport'
        sanitized = CVDUpdate._sanitize_proxy_url(url)
        assert 'secret' not in sanitized

    def test_masks_scheme_less_userinfo(self, revert_homedir):
        # urlparse reads 'alice' as the scheme unless we normalize first.
        url = 'alice:secret@proxy.example.com:8080'
        sanitized = CVDUpdate._sanitize_proxy_url(url)
        assert 'secret' not in sanitized
        assert sanitized == '***:***@proxy.example.com:8080'

    def test_leaves_scheme_less_url_without_userinfo_unchanged(self, revert_homedir):
        url = 'proxy.example.com:8080'
        assert CVDUpdate._sanitize_proxy_url(url) == url


class TestProxyUrlHardening:
    """Malformed / IPv6 / scheme-less proxy URLs must not crash sibling commands."""

    def test_ipv6_with_credentials_composes_valid_url(self, revert_homedir):
        c = CVDUpdate()
        c.config['proxy_url'] = 'http://[::1]:3128'
        c.config['proxy_user'] = 'alice'
        c.config['proxy_pass'] = 'pw'
        result = c._get_proxy_configuration()
        # IPv6 host must stay bracketed so requests/urllib3 accepts it.
        assert result['http'] == 'http://alice:pw@[::1]:3128'

    def test_scheme_less_url_gets_http_prefix_and_keeps_port(self, revert_homedir):
        c = CVDUpdate()
        c.config['proxy_url'] = 'proxy.example.com:8080'
        c.config['proxy_user'] = 'alice'
        c.config['proxy_pass'] = 'pw'
        result = c._get_proxy_configuration()
        assert result['http'] == 'http://alice:pw@proxy.example.com:8080'

    def test_malformed_port_does_not_crash(self, revert_homedir):
        c = CVDUpdate()
        c.config['proxy_url'] = 'http://user:pw@proxy.example.com:notaport'
        # Must return a dict (or None) rather than raising ValueError.
        assert c._get_proxy_configuration() is not None

    def test_config_show_survives_malformed_proxy_url(self, revert_homedir):
        c = CVDUpdate()
        c.config['proxy_url'] = 'http://user:secret@proxy.example.com:notaport'
        c._save_config()
        result = CliRunner().invoke(cli, ['config', 'show', '--config', str(c.config_path)])
        assert result.exit_code == 0, result.output
        assert 'secret' not in result.output


class TestProxiesReachRequests:
    """The composed proxies dict must actually be handed to requests.get."""

    def test_proxies_passed_to_requests_get(self, revert_homedir, monkeypatch):
        c = CVDUpdate()
        c.config['proxy_url'] = 'http://proxy.example.com:8080'

        captured = {}

        class _Resp:
            status_code = 200
            headers = {}
            def raise_for_status(self):
                pass
            def json(self):
                return {'info': {'version': '0.0'}}

        def _fake_get(url, **kwargs):
            captured['proxies'] = kwargs.get('proxies')
            return _Resp()

        monkeypatch.setattr('cvdupdate.cvdupdate.requests.get', _fake_get)
        c.pypi_update_check()
        assert captured['proxies'] == {
            'http': 'http://proxy.example.com:8080',
            'https': 'http://proxy.example.com:8080',
        }


class TestConfigFilePermissions:
    """The config may hold a plaintext password, so it must not be world-readable."""

    @pytest.mark.skipif(os.name != 'posix', reason='POSIX file modes only')
    def test_config_file_is_owner_only_after_saving_password(self, revert_homedir, tmp_path):
        import stat
        cfg = tmp_path / 'config.json'
        c = CVDUpdate(
            config=str(cfg),
            state_file=str(tmp_path / 'state.json'),
            dbs_directory=str(tmp_path / 'db'),
        )
        c.config['proxy_pass'] = 'secret'
        c._save_config()
        mode = stat.S_IMODE(os.stat(cfg).st_mode)
        assert mode == 0o600

    @pytest.mark.skipif(os.name != 'posix', reason='POSIX file modes only')
    def test_pre_existing_loose_config_is_tightened(self, revert_homedir, tmp_path):
        import stat
        cfg = tmp_path / 'config.json'
        cfg.write_text('{}')
        os.chmod(str(cfg), 0o644)
        c = CVDUpdate(
            config=str(cfg),
            state_file=str(tmp_path / 'state.json'),
            dbs_directory=str(tmp_path / 'db'),
        )
        c.config['proxy_pass'] = 'secret'
        c._save_config()
        mode = stat.S_IMODE(os.stat(cfg).st_mode)
        assert mode == 0o600


class TestProxyLogging:
    """Tests that proxy credentials are never written to the logs."""

    def test_log_does_not_leak_credentials_in_proxy_url(self, revert_homedir):
        import logging

        c = CVDUpdate()
        c.config['proxy_url'] = 'http://user:supersecret@proxy.example.com:8080'

        messages = []

        class _Capture(logging.Handler):
            def emit(self, record):
                messages.append(record.getMessage())

        handler = _Capture()
        c.logger.addHandler(handler)
        try:
            result = c._get_proxy_configuration()
        finally:
            c.logger.removeHandler(handler)

        # The returned proxy URL still carries the real credentials for use.
        assert 'supersecret' in result['http']
        # Nothing logged may contain the secret.
        assert all('supersecret' not in msg for msg in messages)
        assert any('***:***@proxy.example.com:8080' in msg for msg in messages)
