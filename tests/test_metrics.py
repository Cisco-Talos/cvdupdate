"""
Tests for Prometheus metrics generation.

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

import re
from unittest import mock

import pytest

from tests.fixtures.revert import revert_homedir
from cvdupdate.cvdupdate import CVDUpdate
from cvdupdate.metrics import PrometheusMetrics


class TestPrometheusMetricsGenerate:
    """Tests for PrometheusMetrics.generate method."""

    def test_generates_valid_prometheus_format(self):
        """Test that output is valid Prometheus exposition format."""
        status = {
            'summary': {
                'total_databases': 3,
                'current_count': 2,
                'stale_count': 1,
                'missing_count': 0,
                'cooldown_count': 0,
                'overall_status': 'warning',
                'last_check': 1704556800.0,
            },
            'databases': [
                {
                    'name': 'main.cvd',
                    'version_status': 'current',
                    'local_version': 62,
                    'remote_version': 62,
                    'is_current': True,
                    'is_missing': False,
                    'age_seconds': 3600,
                    'on_cooldown': False,
                    'file_size_bytes': 157286400,
                    'cdiff_count': 5,
                },
            ],
            'warnings': [],
        }

        metrics = PrometheusMetrics(status)
        output = metrics.generate()

        # Should end with newline
        assert output.endswith('\n')

        # Should contain HELP and TYPE comments
        assert '# HELP' in output
        assert '# TYPE' in output

        # Should contain metric names
        assert 'cvdupdate_database_version' in output
        assert 'cvdupdate_databases_total' in output
        assert 'cvdupdate_health_status' in output

    def test_includes_all_expected_metrics(self):
        """Test that all expected metrics are present."""
        status = {
            'summary': {
                'total_databases': 1,
                'current_count': 1,
                'stale_count': 0,
                'missing_count': 0,
                'cooldown_count': 0,
                'overall_status': 'healthy',
                'last_check': 1704556800.0,
            },
            'databases': [
                {
                    'name': 'test.cvd',
                    'version_status': 'current',
                    'local_version': 100,
                    'remote_version': 100,
                    'is_current': True,
                    'is_missing': False,
                    'age_seconds': 1800,
                    'on_cooldown': False,
                    'file_size_bytes': 1024,
                    'cdiff_count': 2,
                },
            ],
            'warnings': [],
        }

        metrics = PrometheusMetrics(status)
        output = metrics.generate()

        expected_metrics = [
            'cvdupdate_database_version',
            'cvdupdate_database_remote_version',
            'cvdupdate_database_age_seconds',
            'cvdupdate_database_current',
            'cvdupdate_database_missing',
            'cvdupdate_database_cooldown',
            'cvdupdate_database_size_bytes',
            'cvdupdate_database_cdiff_count',
            'cvdupdate_databases_total',
            'cvdupdate_databases_current',
            'cvdupdate_databases_stale',
            'cvdupdate_databases_missing',
            'cvdupdate_health_status',
            'cvdupdate_last_check_timestamp',
        ]

        for metric in expected_metrics:
            assert metric in output, f'Missing metric: {metric}'

    def test_labels_are_correctly_formatted(self):
        """Test that labels use correct quoting."""
        status = {
            'summary': {
                'total_databases': 1,
                'current_count': 1,
                'stale_count': 0,
                'missing_count': 0,
                'cooldown_count': 0,
                'overall_status': 'healthy',
                'last_check': 1704556800.0,
            },
            'databases': [
                {
                    'name': 'daily.cvd',
                    'version_status': 'current',
                    'local_version': 27456,
                    'remote_version': 27456,
                    'is_current': True,
                    'is_missing': False,
                    'age_seconds': 3600,
                    'on_cooldown': False,
                    'file_size_bytes': 60817408,
                    'cdiff_count': 10,
                },
            ],
            'warnings': [],
        }

        metrics = PrometheusMetrics(status)
        output = metrics.generate()

        # Labels should use double quotes
        assert 'database="daily.cvd"' in output

    def test_health_status_maps_correctly(self):
        """Test that health status maps to correct numeric values."""
        test_cases = [
            ('healthy', 2),
            ('warning', 1),
            ('critical', 0),
        ]

        for status_str, expected_value in test_cases:
            status = {
                'summary': {
                    'total_databases': 1,
                    'current_count': 1,
                    'stale_count': 0,
                    'missing_count': 0,
                    'cooldown_count': 0,
                    'overall_status': status_str,
                    'last_check': 1704556800.0,
                },
                'databases': [],
                'warnings': [],
            }

            metrics = PrometheusMetrics(status)
            output = metrics.generate()

            assert f'cvdupdate_health_status {expected_value}' in output

    def test_handles_none_values_gracefully(self):
        """Test that None values are handled correctly."""
        status = {
            'summary': {
                'total_databases': 1,
                'current_count': 0,
                'stale_count': 0,
                'missing_count': 1,
                'cooldown_count': 0,
                'overall_status': 'critical',
                'last_check': 1704556800.0,
            },
            'databases': [
                {
                    'name': 'missing.cvd',
                    'local_version': None,
                    'remote_version': None,
                    'is_current': False,
                    'is_missing': True,
                    'age_seconds': None,
                    'on_cooldown': False,
                    'file_size_bytes': None,
                    'cdiff_count': 0,
                },
            ],
            'warnings': [],
        }

        metrics = PrometheusMetrics(status)
        output = metrics.generate()

        # Should not contain 'None' as text
        assert 'None' not in output

        # Should still have the missing metric
        assert 'cvdupdate_database_missing{database="missing.cvd"} 1' in output


class TestMetricsIntegration:
    """Integration tests for metrics with CVDUpdate."""

    def test_metrics_from_cvdupdate_status(self, revert_homedir):
        """Test generating metrics from actual CVDUpdate status."""
        c = CVDUpdate()

        with mock.patch.object(c, '_query_dns_txt_entry', return_value=False):
            status = c.db_status()

        metrics = PrometheusMetrics(status)
        output = metrics.generate()

        # Should be non-empty
        assert len(output) > 0

        # The missing gauge is emitted once per database, so it tracks count.
        db_count = output.count('cvdupdate_database_missing{')
        assert db_count == len(status['databases'])

    def test_metrics_output_matches_status_values(self, revert_homedir):
        """Test that metrics output matches status dict values."""
        c = CVDUpdate()

        with mock.patch.object(c, '_query_dns_txt_entry', return_value=False):
            status = c.db_status()

        metrics = PrometheusMetrics(status)
        output = metrics.generate()

        # Check summary metrics match
        total = status['summary']['total_databases']
        assert f'cvdupdate_databases_total {total}' in output

        current = status['summary']['current_count']
        assert f'cvdupdate_databases_current {current}' in output

        stale = status['summary']['stale_count']
        assert f'cvdupdate_databases_stale {stale}' in output

        missing = status['summary']['missing_count']
        assert f'cvdupdate_databases_missing {missing}' in output


class TestMetricsLabelEscaping:
    """Tests for Prometheus label value escaping."""

    def _status_with_name(self, name):
        return {
            'summary': {
                'total_databases': 1,
                'current_count': 1,
                'stale_count': 0,
                'missing_count': 0,
                'cooldown_count': 0,
                'overall_status': 'healthy',
                'last_check': 1704556800.0,
            },
            'databases': [
                {
                    'name': name,
                    'version_status': 'current',
                    'local_version': 1,
                    'remote_version': 1,
                    'is_current': True,
                    'is_missing': False,
                    'age_seconds': 1,
                    'on_cooldown': False,
                    'file_size_bytes': 1,
                    'cdiff_count': 0,
                },
            ],
            'warnings': [],
        }

    def test_escapes_backslash_quote_and_newline(self):
        """Label values must escape backslash, double quote, and newline."""
        output = PrometheusMetrics(self._status_with_name('a\\b"c\nd.cvd')).generate()
        assert 'database="a\\\\b\\"c\\nd.cvd"' in output
        # A raw newline must never appear inside a label value.
        for line in output.splitlines():
            assert not (line.startswith('cvdupdate_database') and line.endswith('database="a'))

    def test_plain_name_is_unchanged(self):
        """A name without special characters is emitted verbatim."""
        output = PrometheusMetrics(self._status_with_name('daily.cvd')).generate()
        assert 'database="daily.cvd"' in output


class TestMetricsTimestampUnit:
    """Tests for the last-check timestamp unit."""

    def test_timestamp_is_seconds_not_milliseconds(self):
        """The timestamp must be Unix seconds (10 digits), not milliseconds."""
        status = {
            'summary': {
                'total_databases': 0,
                'current_count': 0,
                'stale_count': 0,
                'missing_count': 0,
                'cooldown_count': 0,
                'overall_status': 'healthy',
                'last_check': 1704556800.0,
            },
            'databases': [],
            'warnings': [],
        }
        output = PrometheusMetrics(status).generate()
        line = next(l for l in output.splitlines() if l.startswith('cvdupdate_last_check_timestamp '))
        value = int(line.split()[1])
        # Seconds are ~10 digits through the year 2286; milliseconds are ~13.
        assert 10 ** 9 <= value < 10 ** 11

    def test_timestamp_reflects_summary_last_check(self):
        """Must report when the status was collected, not when it was rendered.

        In --serve mode a cached status is re-rendered on every scrape, so using
        the render time would make staleness alerts impossible to trip.
        """
        status = {
            'summary': {
                'total_databases': 0,
                'current_count': 0,
                'stale_count': 0,
                'missing_count': 0,
                'cooldown_count': 0,
                'overall_status': 'healthy',
                'last_check': 1704556800.0,
            },
            'databases': [],
            'warnings': [],
        }
        output = PrometheusMetrics(status).generate()
        line = next(l for l in output.splitlines() if l.startswith('cvdupdate_last_check_timestamp '))
        assert int(line.split()[1]) == 1704556800


class TestMetricsUnknownVersion:
    """Tests that an unverified version is not reported as outdated."""

    def test_current_gauge_omitted_when_unknown(self):
        """The current gauge is skipped when the version could not be verified."""
        status = {
            'summary': {
                'total_databases': 1,
                'current_count': 0,
                'stale_count': 0,
                'missing_count': 0,
                'cooldown_count': 0,
                'overall_status': 'warning',
                'last_check': 1704556800.0,
            },
            'databases': [
                {
                    'name': 'main.cvd',
                    'version_status': 'unknown',
                    'local_version': 62,
                    'remote_version': None,
                    'is_current': False,
                    'is_missing': False,
                    'age_seconds': 1,
                    'on_cooldown': False,
                    'file_size_bytes': 1,
                    'cdiff_count': 0,
                },
            ],
            'warnings': [],
        }
        output = PrometheusMetrics(status).generate()
        assert 'cvdupdate_database_current{database="main.cvd"}' not in output
