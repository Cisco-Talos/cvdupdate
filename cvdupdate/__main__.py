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
# Deprecated flag names from <= 1.2.0, kept as hidden aliases for backward compatibility.
@click.option("--nameserver", type=str, default="", hidden=True)
@click.option("--logdir", type=click.Path(), default="", hidden=True)
@click.option("--dbdir", type=click.Path(), default="", hidden=True)
def config_set(ctx, config, verbose, nameservers, max_retries, logs_enabled, logs_directory,
               logs_rotate, logs_to_keep, dbs_directory, cdiffs_rotate, cdiffs_to_keep,
               state_file, nameserver, logdir, dbdir):
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
    )
    if no_options_set:
        click.echo(ctx.get_help())
        return
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
    if as_json:
        print(_json.dumps(m.config, indent=4))
    else:
        for key, value in m.config.items():
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
    auto_updater.start(update_interval_seconds,m)

    # Don't expose hidden files (e.g. a dot-prefixed state file) over the mirror.
    MirrorRequestHandler.protocol_version = 'HTTP/1.0'
    httpd = HTTPServer(('', port), MirrorRequestHandler)
    actual_port = httpd.server_address[1]
    m.logger.info(f"Serving up {m.dbs_directory} on localhost:{actual_port}...")
    httpd.serve_forever()


if __name__ == "__main__":
    sys.argv[0] = "cvdupdate"
    cli(sys.argv[1:])
