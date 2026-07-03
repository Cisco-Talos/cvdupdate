"""
Prometheus metrics generation for CVD-Update.

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

import time
from typing import Dict, Any, List


METRIC_PREFIX = 'cvdupdate'


class PrometheusMetrics:
    """Generate Prometheus-format metrics from CVD-Update status."""

    def __init__(self, status: Dict[str, Any]):
        """
        Initialize metrics generator with status data.

        Args:
            status: Status dict from CVDUpdate.db_status()
        """
        self.status = status
        self.timestamp = int(time.time())  # Unix seconds; fallback for last_check

    @staticmethod
    def _escape_label_value(value: str) -> str:
        '''
        Escape a label value per the Prometheus text exposition format:
        backslash, double quote, and newline must be escaped.
        '''
        return (
            str(value)
            .replace('\\', '\\\\')
            .replace('"', '\\"')
            .replace('\n', '\\n')
        )

    def generate(self) -> str:
        """
        Generate Prometheus metrics text.

        Returns:
            str: Prometheus exposition format text
        """
        lines: List[str] = []

        # Add metadata comments
        lines.append('# HELP cvdupdate_database_version Local version of ClamAV database')
        lines.append('# TYPE cvdupdate_database_version gauge')

        lines.append('# HELP cvdupdate_database_remote_version Remote version available')
        lines.append('# TYPE cvdupdate_database_remote_version gauge')

        lines.append('# HELP cvdupdate_database_age_seconds Age of database in seconds')
        lines.append('# TYPE cvdupdate_database_age_seconds gauge')

        lines.append('# HELP cvdupdate_database_current Database is current (1) or outdated (0)')
        lines.append('# TYPE cvdupdate_database_current gauge')

        lines.append('# HELP cvdupdate_database_missing Database is missing (1) or present (0)')
        lines.append('# TYPE cvdupdate_database_missing gauge')

        lines.append('# HELP cvdupdate_database_cooldown Database is on cooldown (1) or not (0)')
        lines.append('# TYPE cvdupdate_database_cooldown gauge')

        lines.append('# HELP cvdupdate_database_size_bytes Size of database file in bytes')
        lines.append('# TYPE cvdupdate_database_size_bytes gauge')

        lines.append('# HELP cvdupdate_database_cdiff_count Number of CDIFF patch files')
        lines.append('# TYPE cvdupdate_database_cdiff_count gauge')

        lines.append('# HELP cvdupdate_databases_total Total number of configured databases')
        lines.append('# TYPE cvdupdate_databases_total gauge')

        lines.append('# HELP cvdupdate_databases_current Number of current databases')
        lines.append('# TYPE cvdupdate_databases_current gauge')

        lines.append('# HELP cvdupdate_databases_stale Number of stale databases')
        lines.append('# TYPE cvdupdate_databases_stale gauge')

        lines.append('# HELP cvdupdate_databases_missing Number of missing databases')
        lines.append('# TYPE cvdupdate_databases_missing gauge')

        lines.append('# HELP cvdupdate_health_status Overall health (0=critical, 1=warning, 2=healthy)')
        lines.append('# TYPE cvdupdate_health_status gauge')

        lines.append('# HELP cvdupdate_last_check_timestamp Unix timestamp of last status check')
        lines.append('# TYPE cvdupdate_last_check_timestamp gauge')

        # Per-database metrics
        for db in self.status.get('databases', []):
            name = self._escape_label_value(db['name'])
            labels = f'database="{name}"'

            if db.get('local_version') is not None:
                lines.append(f'cvdupdate_database_version{{{labels}}} {db["local_version"]}')

            if db.get('remote_version') is not None:
                lines.append(f'cvdupdate_database_remote_version{{{labels}}} {db["remote_version"]}')

            if db.get('age_seconds') is not None:
                lines.append(f'cvdupdate_database_age_seconds{{{labels}}} {db["age_seconds"]:.0f}')

            # Skip the gauge when unverified, so 'unknown' isn't reported as 0.
            if db.get('version_status', 'unknown') != 'unknown':
                current = 1 if db.get('is_current') else 0
                lines.append(f'cvdupdate_database_current{{{labels}}} {current}')

            missing = 1 if db.get('is_missing') else 0
            lines.append(f'cvdupdate_database_missing{{{labels}}} {missing}')

            cooldown = 1 if db.get('on_cooldown') else 0
            lines.append(f'cvdupdate_database_cooldown{{{labels}}} {cooldown}')

            if db.get('file_size_bytes') is not None:
                lines.append(f'cvdupdate_database_size_bytes{{{labels}}} {db["file_size_bytes"]}')

            if db.get('cdiff_count') is not None:
                lines.append(f'cvdupdate_database_cdiff_count{{{labels}}} {db["cdiff_count"]}')

        # Summary metrics
        summary = self.status.get('summary', {})

        lines.append(f'cvdupdate_databases_total {summary.get("total_databases", 0)}')
        lines.append(f'cvdupdate_databases_current {summary.get("current_count", 0)}')
        lines.append(f'cvdupdate_databases_stale {summary.get("stale_count", 0)}')
        lines.append(f'cvdupdate_databases_missing {summary.get("missing_count", 0)}')

        # Map status to numeric value
        status_map = {'critical': 0, 'warning': 1, 'healthy': 2}
        health_value = status_map.get(summary.get('overall_status', 'critical'), 0)
        lines.append(f'cvdupdate_health_status {health_value}')

        # Report when the status was collected, not when it was rendered: in
        # --serve mode a cached status is re-rendered on every scrape.
        last_check = summary.get('last_check', self.timestamp)
        lines.append(f'cvdupdate_last_check_timestamp {int(last_check)}')

        return '\n'.join(lines) + '\n'

