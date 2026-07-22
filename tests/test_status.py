"""
Tests for database status command.

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

import json
import time
from unittest import mock

import pytest

from tests.fixtures.revert import revert_homedir
from cvdupdate.cvdupdate import CVDUpdate


class TestCalculateAgeStatus:
    """Tests for _calculate_age_status method."""

    def test_returns_missing_for_zero_timestamp(self, revert_homedir):
        """Test that missing status is returned for zero timestamp."""
        c = CVDUpdate()
        age_hours, age_status = c._calculate_age_status(0)
        assert age_hours is None
        assert age_status == 'missing'

    def test_returns_current_for_recent_files(self, revert_homedir):
        """Test that current status is returned for files less than 24 hours old."""
        c = CVDUpdate()
        # 12 hours ago
        last_modified = time.time() - (12 * 3600)
        age_hours, age_status = c._calculate_age_status(last_modified)
        assert 11 < age_hours < 13
        assert age_status == 'current'

    def test_returns_recent_for_24_to_48_hours(self, revert_homedir):
        """Test that recent status is returned for files 24-48 hours old."""
        c = CVDUpdate()
        # 36 hours ago
        last_modified = time.time() - (36 * 3600)
        age_hours, age_status = c._calculate_age_status(last_modified)
        assert 35 < age_hours < 37
        assert age_status == 'recent'

    def test_returns_stale_for_48_to_72_hours(self, revert_homedir):
        """Test that stale status is returned for files 48-72 hours old."""
        c = CVDUpdate()
        # 60 hours ago
        last_modified = time.time() - (60 * 3600)
        age_hours, age_status = c._calculate_age_status(last_modified)
        assert 59 < age_hours < 61
        assert age_status == 'stale'

    def test_returns_outdated_for_over_72_hours(self, revert_homedir):
        """Test that outdated status is returned for files over 72 hours old."""
        c = CVDUpdate()
        # 96 hours ago
        last_modified = time.time() - (96 * 3600)
        age_hours, age_status = c._calculate_age_status(last_modified)
        assert 95 < age_hours < 97
        assert age_status == 'outdated'


class TestDbStatus:
    """Tests for db_status method."""

    def test_returns_correct_structure(self, revert_homedir):
        """Test that db_status returns the expected structure."""
        c = CVDUpdate()

        # Mock DNS query to avoid network calls
        with mock.patch.object(c, '_query_dns_txt_entry', return_value=False):
            status = c.db_status()

        assert 'summary' in status
        assert 'databases' in status
        assert 'warnings' in status

        # Check summary structure
        summary = status['summary']
        assert 'total_databases' in summary
        assert 'current_count' in summary
        assert 'stale_count' in summary
        assert 'missing_count' in summary
        assert 'cooldown_count' in summary
        assert 'overall_status' in summary
        assert 'last_check' in summary

        # Check databases is a list
        assert isinstance(status['databases'], list)

        # Check warnings is a list
        assert isinstance(status['warnings'], list)

    def test_detects_missing_databases(self, revert_homedir):
        """Test that missing databases are detected."""
        c = CVDUpdate()

        # Databases don't exist since we haven't downloaded them
        with mock.patch.object(c, '_query_dns_txt_entry', return_value=False):
            status = c.db_status()

        # All databases should be reported as missing
        assert status['summary']['missing_count'] == len(status['databases'])

    def test_json_output_is_valid(self, revert_homedir):
        """Test that status can be serialized to valid JSON."""
        c = CVDUpdate()

        with mock.patch.object(c, '_query_dns_txt_entry', return_value=False):
            status = c.db_status()

        # Should not raise
        json_str = json.dumps(status)
        assert json_str

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed == status

    def test_overall_status_values(self, revert_homedir):
        """Test that overall_status has valid values."""
        c = CVDUpdate()

        with mock.patch.object(c, '_query_dns_txt_entry', return_value=False):
            status = c.db_status()

        assert status['summary']['overall_status'] in ['healthy', 'warning', 'critical']

    def test_dns_failure_warning(self, revert_homedir):
        """Test that DNS failure adds a warning."""
        c = CVDUpdate()

        with mock.patch.object(c, '_query_dns_txt_entry', return_value=False):
            status = c.db_status()

        dns_warnings = [w for w in status['warnings'] if 'DNS' in w]
        assert len(dns_warnings) > 0


class TestDbStatusDatabaseFields:
    """Tests for individual database fields in db_status."""

    def test_database_has_required_fields(self, revert_homedir):
        """Test that each database entry has required fields."""
        c = CVDUpdate()

        with mock.patch.object(c, '_query_dns_txt_entry', return_value=False):
            status = c.db_status()

        required_fields = [
            'name',
            'local_version',
            'remote_version',
            'is_current',
            'version_status',
            'is_missing',
            'last_modified',
            'age_hours',
            'age_seconds',
            'age_status',
            'on_cooldown',
            'cooldown_until',
            'cdiff_count',
            'file_size_bytes',
        ]

        for db in status['databases']:
            for field in required_fields:
                assert field in db, f"Missing field: {field}"

    def test_cooldown_detection(self, revert_homedir):
        """Test that cooldown is correctly detected."""
        c = CVDUpdate()

        # Set a database on cooldown
        c.state['dbs']['main.cvd']['retry after'] = time.time() + 3600

        with mock.patch.object(c, '_query_dns_txt_entry', return_value=False):
            status = c.db_status()

        main_db = next(db for db in status['databases'] if db['name'] == 'main.cvd')
        assert main_db['on_cooldown'] is True
        assert main_db['cooldown_until'] is not None

        # Check warning was added
        cooldown_warnings = [w for w in status['warnings'] if 'cooldown' in w]
        assert len(cooldown_warnings) > 0


class TestDbStatusVersionState:
    """Tests that version state distinguishes unknown, current, and outdated."""

    def _single_main_db(self, c, local_version, last_modified):
        c.dbs_directory.mkdir(parents=True, exist_ok=True)
        (c.dbs_directory / 'main.cvd').write_bytes(b'x')
        c.state['dbs'] = {
            'main.cvd': {
                'url': 'https://database.clamav.net/main.cvd',
                'retry after': 0,
                'last modified': last_modified,
                'last checked': 0,
                'DNS field': 1,
                'local version': local_version,
                'CDIFFs': [],
            }
        }

    def test_unknown_when_dns_unavailable(self, revert_homedir):
        """A present database with no remote version is unknown, not outdated."""
        c = CVDUpdate()
        self._single_main_db(c, local_version=62, last_modified=time.time())

        with mock.patch.object(c, '_query_dns_txt_entry', return_value=False):
            status = c.db_status()

        main_db = next(db for db in status['databases'] if db['name'] == 'main.cvd')
        assert main_db['version_status'] == 'unknown'
        assert main_db['is_current'] is False
        assert status['summary']['unknown_count'] == 1
        assert status['summary']['outdated_count'] == 0

    def test_outdated_when_local_behind_remote(self, revert_homedir):
        """A database behind the advertised version is outdated and warns."""
        c = CVDUpdate()
        self._single_main_db(c, local_version=60, last_modified=time.time())

        def fake_dns():
            c.dns_version_tokens = ['0', '62']
            return True

        with mock.patch.object(c, '_query_dns_txt_entry', side_effect=fake_dns):
            status = c.db_status()

        main_db = next(db for db in status['databases'] if db['name'] == 'main.cvd')
        assert main_db['version_status'] == 'outdated'
        assert status['summary']['outdated_count'] == 1
        assert status['summary']['overall_status'] == 'warning'
        assert any('behind' in w for w in status['warnings'])

    def test_current_with_old_file_is_healthy(self, revert_homedir):
        """A current database is healthy even when its file is old."""
        c = CVDUpdate()
        self._single_main_db(c, local_version=62, last_modified=time.time() - (200 * 3600))

        def fake_dns():
            c.dns_version_tokens = ['0', '62']
            return True

        with mock.patch.object(c, '_query_dns_txt_entry', side_effect=fake_dns):
            status = c.db_status()

        main_db = next(db for db in status['databases'] if db['name'] == 'main.cvd')
        assert main_db['version_status'] == 'current'
        assert status['summary']['stale_count'] == 0
        assert status['summary']['overall_status'] == 'healthy'

    def test_fresh_non_cvd_database_is_healthy(self, revert_homedir):
        """A freshly downloaded non-CVD database has no version, so it is
        reported as unknown but must not flag the mirror as unhealthy."""
        c = CVDUpdate()
        c.dbs_directory.mkdir(parents=True, exist_ok=True)
        (c.dbs_directory / 'custom.ndb').write_bytes(b'x')
        c.state['dbs'] = {
            'custom.ndb': {
                'url': 'https://example.com/custom.ndb',
                'retry after': 0,
                'last modified': time.time(),
                'last checked': 0,
                'DNS field': 0,
                'local version': 0,
                'CDIFFs': [],
            }
        }

        def fake_dns():
            c.dns_version_tokens = ['0', '62']
            return True

        with mock.patch.object(c, '_query_dns_txt_entry', side_effect=fake_dns):
            status = c.db_status()

        custom = next(db for db in status['databases'] if db['name'] == 'custom.ndb')
        assert custom['version_status'] == 'unknown'
        assert status['summary']['overall_status'] == 'healthy'
