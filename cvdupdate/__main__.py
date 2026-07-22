#!/usr/bin/env python3

"""
CVD-Update: ClamAV Database Updater
"""

_description = """
A tool to download and update clamav databases and database patch files
for the purposes of hosting your own database mirror.
"""

_copyright = """
Copyright (C) 2021-2025 Cisco Systems, Inc. and/or its affiliates. All rights reserved.
"""

"""
Author: Micah Snyder

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

import json as _json
import logging
import os
import posixpath
import sys
from urllib.parse import unquote
import click
import colorlog
try:
    from importlib.metadata import PackageNotFoundError, version as _get_version
except ImportError:  # pragma: no cover - backport for older Pythons
    from importlib_metadata import PackageNotFoundError, version as _get_version
from http.server import HTTPServer
from RangeHTTPServer import RangeRequestHandler

from cvdupdate import auto_updater
from cvdupdate.cvdupdate import CVDUpdate

handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s %(name)s %(levelname)s %(message)s"
    )
)
logging.basicConfig(level=logging.DEBUG, handlers=[handler])

from colorama import Fore, Style


def _package_version() -> str:
    try:
        return _get_version('cvdupdate')
    except PackageNotFoundError:
        return '0.0'


class MirrorRequestHandler(RangeRequestHandler):
    """
    RangeRequestHandler that hides dot-prefixed files and directories so the
    `serve` test mirror doesn't expose hidden files (e.g. `.state.json`).
    """

    def send_head(self):
        # Decode %xx (so /%2egit can't bypass the check) and normalize, then
        # block any path segment that names a dotfile/dotdir — including files
        # inside one (e.g. /.git/config), not just a dot-prefixed final segment.
        # '.' and '..' are navigation segments, not hidden names.
        path = posixpath.normpath(unquote(self.path.split('?', 1)[0].split('#', 1)[0]))
        segments = [seg for seg in path.split('/') if seg not in ('.', '..')]
        if any(seg.startswith('.') for seg in segments):
            self.send_error(404, "File not found")
            return None
        return super().send_head()

    def list_directory(self, path):
        # Filter dot-prefixed entries out of auto-generated directory listings.
        try:
            names = os.listdir(path)
        except OSError:
            return super().list_directory(path)
        original_listdir = os.listdir
        os.listdir = lambda _p: [n for n in names if not n.startswith('.')]
        try:
            return super().list_directory(path)
        finally:
            os.listdir = original_listdir


class AliasedGroup(click.Group):
    """
    A Click Group subclass that supports command aliases.
    Aliases are shown inline in the help text: "name (alias1, alias2)".
    """

    def __init__(self, *args, **kwargs):
        self._alias_map = {}      # alias → primary command name
        self._reverse_alias = {}  # primary → [alias, ...]
        super().__init__(*args, **kwargs)

    def command(self, *args, aliases=None, **kwargs):
        def decorator(f):
            cmd = super(AliasedGroup, self).command(*args, **kwargs)(f)
            if aliases:
                for alias in aliases:
                    self._alias_map[alias] = cmd.name
                    self._reverse_alias.setdefault(cmd.name, []).append(alias)
            return cmd
        return decorator

    def group(self, *args, aliases=None, **kwargs):
        def decorator(f):
            cmd = super(AliasedGroup, self).group(*args, **kwargs)(f)
            if aliases:
                for alias in aliases:
                    self._alias_map[alias] = cmd.name
                    self._reverse_alias.setdefault(cmd.name, []).append(alias)
            return cmd
        return decorator

    def get_command(self, ctx, cmd_name):
        return super().get_command(ctx, self._alias_map.get(cmd_name, cmd_name))

    def format_commands(self, ctx, formatter):
        commands = []
        for name in self.list_commands(ctx):
            cmd = self.commands.get(name)
            if cmd is None or cmd.hidden:
                continue
            help_text = cmd.get_short_help_str(limit=formatter.width)
            aliases = self._reverse_alias.get(name, [])
            display_name = f"{name} ({', '.join(aliases)})" if aliases else name
            commands.append((display_name, help_text))
        if commands:
            with formatter.section("Commands"):
                formatter.write_dl(commands)


#
# CLI Interface
#
@click.group(
    cls=AliasedGroup,
    epilog=Fore.BLUE
    + __doc__ + "\n"
    + Fore.GREEN
    + _description + "\n"
    + f"\nVersion {_package_version()}\n"
    + Style.RESET_ALL
    + _copyright,
)
def cli():
    pass


@cli.command("list", aliases=["ls"])
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path.")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output.")
@click.option("--json", "use_json", is_flag=True, default=False, help="Output as JSON array.")
def db_list(config: str, verbose: bool, use_json: bool):
    """
    List the DB names found in the database directory.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    names = list(m.state['dbs'].keys())
    if use_json:
        print(_json.dumps(names, indent=4))
    else:
        for name in names:
            print(name)


@cli.command("status", aliases=["s"])
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path.")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output.")
@click.option("--json", "use_json", is_flag=True, default=False, help="Output as JSON.")
@click.argument("db", required=False, default="")
def db_status(config: str, verbose: bool, use_json: bool, db: str):
    """
    Show status of one or all databases.

    With DB argument: show that database. Without: show all.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    if db == "":
        if use_json:
            state_view = dict(m.state)
            state_view['dbs'] = m._index_local_databases()
            print(_json.dumps(state_view, indent=4))
        else:
            m.db_list()
    else:
        if use_json:
            dbs = m._index_local_databases()
            if db not in dbs:
                m.logger.error(f"No such database: {db}")
                sys.exit(1)
            print(_json.dumps(dbs[db], indent=4))
        else:
            if not m.db_show(db):
                sys.exit(1)


@cli.command("show", hidden=True)
@click.pass_context
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path.")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output.")
@click.option("--json", "use_json", is_flag=True, default=False, help="Output as JSON.")
@click.argument("db", required=False, default="")
def db_show_deprecated(ctx, config: str, verbose: bool, use_json: bool, db: str):
    """
    (Deprecated) Alias for 'status'. Use 'status' instead.
    """
    click.echo(
        "Warning: 'show' is deprecated and will be removed in a future release; "
        "use 'status' instead.",
        err=True,
    )
    ctx.forward(db_status)


@cli.command("update", aliases=["u"])
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path.")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output.")
@click.option("--debug-mode", "-D", is_flag=True, default=False, help="Print out HTTP headers for debugging purposes.")
@click.argument("db", required=False, default="")
def db_update(config: str, verbose: bool, db: str, debug_mode: bool):
    """
    Update the DBs from the internet. Will update all DBs if DB not specified.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    errors = m.db_update(db, debug_mode)
    if errors > 0:
        sys.exit(errors)


@cli.command("add")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path.")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output.")
@click.option("--override", is_flag=True, default=False, help="Update URL if DB already exists.")
@click.argument("db", required=True)
@click.argument("url", required=True)
def db_add(config: str, verbose: bool, override: bool, db: str, url: str):
    """
    Add a db to the list of known DBs.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    if not m.config_add_db(db, url=url, override=override):
        sys.exit(1)


@cli.command("remove", aliases=["rm"])
@click.option("--config", "-c", type=str, required=False, default="")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output.")
@click.argument("db", required=True)
def db_remove(config: str, verbose: bool, db: str):
    """
    Remove a db from the list of known DBs and delete local copies of the DB.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    if not m.config_remove_db(db):
        sys.exit(1)


@cli.group(help="Commands to configure.", aliases=["cf"])
def config():
    pass


@config.command("set")
@click.pass_context
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config file path.")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output.")
@click.option("--nameservers", "-n", type=str, default="",
              help="Comma-separated list of DNS nameservers.")
@click.option("--max-retries", type=int, default=0,
              help="Maximum number of download retries (1-5, default 3).")
@click.option("--logs-enabled/--no-logs-enabled", default=None,
              help="Save logs to file.")
@click.option("--logs-directory", "-l", type=click.Path(), default="",
              help="Log directory path.")
@click.option("--logs-rotate/--no-logs-rotate", default=None,
              help="Rotate log files.")
@click.option("--logs-to-keep", type=int, default=0,
              help="Number of log files to keep.")
@click.option("--dbs-directory", "-d", type=click.Path(), default="",
              help="Database directory path.")
@click.option("--cdiffs-rotate/--no-cdiffs-rotate", default=None,
              help="Rotate CDIFF files.")
@click.option("--cdiffs-to-keep", type=int, default=0,
              help="Number of CDIFF files to keep.")
@click.option("--state-file", type=click.Path(), default="",
              help="Path to the state file.")
@click.option("--proxy-url", type=str, default="",
              help="Proxy URL (e.g. http://proxy.example.com:8080).")
@click.option("--proxy-user", type=str, default="",
              help="Proxy username.")
@click.option("--proxy-pass", type=str, default="", is_flag=False, flag_value="__PROMPT__",
              help="Proxy password. Use the flag without a value to be prompted.")
# Deprecated flag names from <= 1.2.0, kept as hidden aliases for backward compatibility.
@click.option("--nameserver", type=str, default="", hidden=True)
@click.option("--logdir", type=click.Path(), default="", hidden=True)
@click.option("--dbdir", type=click.Path(), default="", hidden=True)
def config_set(ctx, config, verbose, nameservers, max_retries, logs_enabled, logs_directory,
               logs_rotate, logs_to_keep, dbs_directory, cdiffs_rotate, cdiffs_to_keep,
               state_file, proxy_url, proxy_user, proxy_pass, nameserver, logdir, dbdir):
    """
    Set configuration options.

    The default configuration directory is ~/.cvdupdate
    """
    # Map deprecated (<= 1.2.0) flags onto their current equivalents.
    for old_flag, old_val, new_flag, new_val in (
        ("--nameserver", nameserver, "--nameservers", nameservers),
        ("--logdir", logdir, "--logs-directory", logs_directory),
        ("--dbdir", dbdir, "--dbs-directory", dbs_directory),
    ):
        if old_val == "":
            continue
        click.echo(
            f"Warning: '{old_flag}' is deprecated; use '{new_flag}' instead.",
            err=True,
        )
        if new_flag == "--nameservers":
            if new_val == "":
                nameservers = old_val
        elif new_flag == "--logs-directory":
            if new_val == "":
                logs_directory = old_val
            # The old --logdir implied file logging was enabled; preserve that
            # unless the user explicitly set --logs-enabled/--no-logs-enabled.
            if logs_enabled is None:
                logs_enabled = True
        else:  # --dbs-directory
            if new_val == "":
                dbs_directory = old_val

    no_options_set = (
        nameservers == ""
        and max_retries == 0
        and logs_enabled is None
        and logs_directory == ""
        and logs_rotate is None
        and logs_to_keep == 0
        and dbs_directory == ""
        and cdiffs_rotate is None
        and cdiffs_to_keep == 0
        and state_file == ""
        and proxy_url == ""
        and proxy_user == ""
        and proxy_pass == ""
    )
    if no_options_set:
        click.echo(ctx.get_help())
        return

    # Prompt for the proxy password when the flag was given without a value.
    if proxy_pass == "__PROMPT__":
        proxy_pass = click.prompt("Proxy password", hide_input=True)

    CVDUpdate(
        config=config,
        verbose=verbose,
        nameservers=nameservers,
        max_retries=max_retries,
        logs_enabled=logs_enabled,
        logs_directory=logs_directory,
        logs_rotate=logs_rotate,
        logs_to_keep=logs_to_keep,
        dbs_directory=dbs_directory,
        cdiffs_rotate=cdiffs_rotate,
        cdiffs_to_keep=cdiffs_to_keep,
        proxy_url=proxy_url,
        proxy_user=proxy_user,
        proxy_pass=proxy_pass,
        state_file=state_file,
    )


@config.command("show")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path.")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
def config_show(config: str, verbose: bool, as_json: bool):
    """
    Print out the current configuration.
    """
    m = CVDUpdate(config=config, verbose=verbose)

    # Redact proxy credentials: mask the password and strip any userinfo in the URL.
    display = dict(m.config)
    if display.get('proxy_pass'):
        display['proxy_pass'] = '********'
    if display.get('proxy_url'):
        display['proxy_url'] = m._sanitize_proxy_url(display['proxy_url'])

    if as_json:
        print(_json.dumps(display, indent=4))
    else:
        for key, value in display.items():
            cli_key = key.replace('_', '-')
            if value == "" or value is None:
                print(f"{cli_key}:")
            else:
                print(f"{cli_key}: {value}")


@cli.group(help="Commands to clean up.", aliases=["cl"])
def clean():
    pass


@clean.command("dbs")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path.")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output.")
def clean_dbs(config: str, verbose: bool):
    """
    Delete all files in the database directory.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    m.clean_dbs()


@clean.command("logs")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path.")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output.")
def clean_logs(config: str, verbose: bool):
    """
    Delete all files in the logs directory
    """
    m = CVDUpdate(config=config, verbose=verbose)
    m.clean_logs()


@clean.command("all")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path.")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output.")
def clean_all(config: str, verbose: bool):
    """
    Delete the logs, databases, and config file.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    m.clean_all()


@cli.command("health")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path.")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output.")
@click.option("--json", "-j", "output_json", is_flag=True, default=False, help="Output in JSON format.")
@click.option("--check", is_flag=True, default=False, help="Exit with non-zero status if databases are not healthy.")
def db_health(config: str, verbose: bool, output_json: bool, check: bool):
    """
    Check the health and currency of downloaded databases.

    Reports each database's local and remote version, file age, and version
    status (current, behind, unknown, or missing). Use --check for scripted
    health checks that return a non-zero exit code on problems.

    Version status comes from comparing the local version against the version
    advertised over DNS. When DNS is unavailable the status is reported as
    unknown rather than behind. The Age column is informational, since some
    databases such as main.cvd change infrequently and a current mirror can
    hold an old but correct file. Age thresholds are fixed at 24, 48, and 72
    hours and are not yet configurable per database.
    """
    import datetime

    # Logs to stderr so `health --json` output stays valid JSON.
    m = CVDUpdate(config=config, verbose=verbose, log_to_stderr=True)
    status = m.db_status()
    summary = status['summary']

    if output_json:
        click.echo(_json.dumps(status, indent=2))
    else:
        databases = status['databases']
        warnings = status['warnings']

        overall = summary['overall_status'].upper()
        if overall == 'HEALTHY':
            status_color = Fore.GREEN
        elif overall == 'WARNING':
            status_color = Fore.YELLOW
        else:
            status_color = Fore.RED

        last_check = datetime.datetime.fromtimestamp(summary['last_check'], tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

        click.echo("")
        click.echo("CVD-Update Database Health")
        click.echo("==========================")
        click.echo(f"Overall Status: {status_color}{overall}{Style.RESET_ALL}")
        click.echo(f"Last Check: {last_check}")
        click.echo("")

        click.echo(f"{'Database':<16} {'Local':<8} {'Remote':<8} {'Age':<10} {'Status':<12} {'Size':<10}")
        click.echo(f"{'-'*16} {'-'*8} {'-'*8} {'-'*10} {'-'*12} {'-'*10}")

        for db in databases:
            name = db['name']
            local_ver = str(db['local_version']) if db['local_version'] is not None else '-'
            remote_ver = str(db['remote_version']) if db['remote_version'] is not None else '-'

            if db['age_hours'] is None:
                age_str = '-'
            elif db['age_hours'] < 1:
                age_str = f"{int(db['age_hours'] * 60)}m"
            elif db['age_hours'] < 24:
                age_str = f"{int(db['age_hours'])}h"
            else:
                days = int(db['age_hours'] / 24)
                hours = int(db['age_hours'] % 24)
                age_str = f"{days}d {hours}h"

            # Color by version state (the Age column already shows file age).
            if db['is_missing']:
                status_str = f"{Fore.RED}MISSING{Style.RESET_ALL}"
            elif db['version_status'] == 'current':
                status_str = f"{Fore.GREEN}CURRENT{Style.RESET_ALL}"
            elif db['version_status'] == 'outdated':
                status_str = f"{Fore.RED}BEHIND{Style.RESET_ALL}"
            else:
                status_str = f"{Fore.YELLOW}UNKNOWN{Style.RESET_ALL}"

            if db['file_size_bytes'] is None:
                size_str = '-'
            elif db['file_size_bytes'] < 1024:
                size_str = f"{db['file_size_bytes']} B"
            elif db['file_size_bytes'] < 1024 * 1024:
                size_str = f"{db['file_size_bytes'] / 1024:.1f} KB"
            else:
                size_str = f"{db['file_size_bytes'] / (1024 * 1024):.1f} MB"

            # The status column needs extra width to account for color codes.
            click.echo(f"{name:<16} {local_ver:<8} {remote_ver:<8} {age_str:<10} {status_str:<23} {size_str:<10}")

        click.echo("")

        if warnings:
            click.echo(f"{Fore.YELLOW}Warnings:{Style.RESET_ALL}")
            for warning in warnings:
                click.echo(f"  - {warning}")
            click.echo("")

        click.echo(f"Summary: {summary['current_count']}/{summary['total_databases']} databases current, {len(warnings)} warnings")
        click.echo("")

    if check:
        if summary['overall_status'] == 'healthy':
            sys.exit(0)
        elif summary['overall_status'] == 'warning':
            sys.exit(1)
        else:  # critical
            sys.exit(2)


@cli.command("metrics")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path.")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output.")
@click.option("--serve", "-s", is_flag=True, default=False, help="Start HTTP server for Prometheus scraping.")
@click.option("--port", "-p", type=int, default=9090, help="Port for metrics server. Default: 9090.")
@click.option("--bind", "-b", type=str, default="127.0.0.1", help="Address to bind metrics server. Default: 127.0.0.1.")
@click.option("--cache-ttl", type=int, default=60, help="Seconds to cache status between scrapes in --serve mode. Default: 60.")
def db_metrics(config: str, verbose: bool, serve: bool, port: int, bind: str, cache_ttl: int):
    """
    Output Prometheus metrics for monitoring.

    By default, outputs metrics to stdout for one-shot collection.
    Use --serve to start a persistent HTTP server for Prometheus scraping.
    """
    from cvdupdate.metrics import PrometheusMetrics
    import http.server
    import threading
    import time

    # Logs to stderr so `cvd metrics > file` stays valid Prometheus text.
    m = CVDUpdate(config=config, verbose=verbose, log_to_stderr=True)

    if serve:
        # Cache status between scrapes so each request doesn't trigger a live
        # DNS query.
        cache_lock = threading.Lock()
        status_cache = {'status': None, 'time': 0.0}

        def get_cached_status():
            now = time.time()
            with cache_lock:
                if status_cache['status'] is None or (now - status_cache['time']) > cache_ttl:
                    status_cache['status'] = m.db_status()
                    status_cache['time'] = now
                return status_cache['status']

        class MetricsHandler(http.server.BaseHTTPRequestHandler):
            verbose_mode = verbose
            timeout = 10  # don't let a slow client stall scrapes

            def do_GET(self):
                if self.path == '/metrics' or self.path == '/':
                    try:
                        status = get_cached_status()
                        content = PrometheusMetrics(status).generate().encode('utf-8')
                    except Exception as exc:
                        # Report 500 rather than dropping the connection.
                        m.logger.error(f'Failed to generate metrics: {exc}')
                        self.send_response(500)
                        self.send_header('Content-Type', 'text/plain; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(b'error generating metrics\n')
                        return

                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain; version=0.0.4; charset=utf-8')
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                elif self.path == '/health':
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'OK')
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                if self.verbose_mode:
                    m.logger.debug(f'{self.address_string()} - {format % args}')

        m.logger.info(f'Starting metrics server on {bind}:{port}')
        m.logger.info(f'Metrics available at http://{bind}:{port}/metrics')

        # Threaded (a slow client can't block scrapes) with address reuse (a
        # quick restart won't hit EADDRINUSE).
        class _MetricsServer(http.server.ThreadingHTTPServer):
            daemon_threads = True

        with _MetricsServer((bind, port), MetricsHandler) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                m.logger.info('Metrics server stopped')
    else:
        status = m.db_status()
        metrics = PrometheusMetrics(status)
        click.echo(metrics.generate())


@cli.command("serve")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path.")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output.")
@click.option("--update-interval-seconds", "-U", type=click.INT, required=False, default=0, help="Time in seconds before the next database update")
@click.argument("port", type=int, required=False, default=8000)
def serve(port: int, config: str, verbose: bool, update_interval_seconds: int):
    """
    Serve up the database directory for testing purposes only. Not a production quality server.

    PORT defaults to 8000. Pass 0 to have the OS pick a random available port.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    os.chdir(str(m.dbs_directory))
    auto_updater.start(update_interval_seconds)

    # Don't expose hidden files (e.g. a dot-prefixed state file) over the mirror.
    MirrorRequestHandler.protocol_version = 'HTTP/1.0'
    httpd = HTTPServer(('', port), MirrorRequestHandler)
    actual_port = httpd.server_address[1]
    m.logger.info(f"Serving up {m.dbs_directory} on localhost:{actual_port}...")
    httpd.serve_forever()


if __name__ == "__main__":
    sys.argv[0] = "cvdupdate"
    cli(sys.argv[1:])
