#!/usr/bin/env python3

"""
CVD-Update: ClamAV Database Updater
"""

_description = """
A tool to download and update clamav databases and database patch files
for the purposes of hosting your own database mirror.
"""

_copyright = """
Copyright (C) 2021 Micah Snyder.
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

import logging
import os
from pathlib import Path
import sys

import click
import coloredlogs
from http.server import HTTPServer
from RangeHTTPServer import RangeRequestHandler


import pkg_resources
from cvdupdate.cvdupdate import CVDUpdate

logging.basicConfig()
module_logger = logging.getLogger("cvdupdate")
coloredlogs.install(level="DEBUG", fmt="%(asctime)s %(name)s %(levelname)s %(message)s")
module_logger.setLevel(logging.DEBUG)

from colorama import Fore, Back, Style

#
# CLI Interface
#
@click.group(
    epilog=Fore.BLUE
    + __doc__ + "\n"
    + Fore.GREEN
    + _description + "\n"
    + f"\nVersion {pkg_resources.get_distribution('cvdupdate').version}\n"
    + Style.RESET_ALL
    + _copyright,
)
def cli():
    pass


@cli.command("list")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path. [optional]")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output. [optional]")
def db_list(config: str, verbose: bool):
    """
    List the DBs found in the database directory.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    m.db_list()

@cli.command("show")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path. [optional]")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output. [optional]")
@click.argument("db", required=True)
def db_show(config: str, verbose: bool, db: str):
    """
    Show details about a specific database.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    if not m.db_show(db):
        sys.exit(1)

@cli.command("update")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path. [optional]")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output. [optional]")
@click.option("--debug-mode", "-D", is_flag=True, default=False, help="Print out HTTP headers for debugging purposes. [optional]")
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
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path. [optional]")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output. [optional]")
@click.argument("db", required=True)
@click.argument("url", required=True)
def db_add(config: str, verbose: bool, db: str, url: str):
    """
    Add a db to the list of known DBs.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    if not m.config_add_db(db, url=url):
        sys.exit(1)

@cli.command("remove")
@click.option("--config", "-c", type=str, required=False, default="")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output. [optional]")
@click.argument("db", required=True)
def db_remove(config: str, verbose: bool, db: str):
    """
    Remove a db from the list of known DBs and delete local copies of the DB.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    if not m.config_remove_db(db):
        sys.exit(1)


@cli.group(help="Commands to configure.")
def config():
    pass

@config.command("set")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path. [optional]")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output. [optional]")
@click.option("--logdir", "-l", type=click.Path(), required=False, default="", help="Set a custom log directory. [optional]")
@click.option("--dbdir", "-d", type=click.Path(), required=False, default="", help="Set a custom database directory. [optional]")
@click.option("--nameserver", "-n", type=click.STRING, required=False, default="", help="Set a custom DNS nameserver. [optional]")
def config_set(config: str, verbose: bool, logdir: str, dbdir: str, nameserver: str):
    """
    Set up first time configuration.

    The default directories will be in ~/.cvdupdate
    """
    CVDUpdate(
        config=config,
        verbose=verbose,
        log_dir=logdir,
        db_dir=dbdir,
        nameserver=nameserver)

@config.command("show")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path. [optional]")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output. [optional]")
def config_show(config: str, verbose: bool):
    """
    Print out the current configuration.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    m.config_show()


@cli.group(help="Commands to clean up.")
def clean():
    pass

@clean.command("dbs")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path. [optional]")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output. [optional]")
def clean_dbs(config: str, verbose: bool):
    """
    Delete all files in the database directory.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    m.clean_dbs()

@clean.command("logs")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path. [optional]")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output. [optional]")
def clean_logs(config: str, verbose: bool):
    """
    Delete all files in the logs directory
    """
    m = CVDUpdate(config=config, verbose=verbose)
    m.clean_logs()

@clean.command("all")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path. [optional]")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output. [optional]")
def clean_all(config: str, verbose: bool):
    """
    Delete the logs, databases, and config file.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    m.clean_all()


@cli.command("serve")
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path. [optional]")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output. [optional]")
@click.argument("port", type=int, required=False, default=8000)
def serve(port: int, config: str, verbose: bool):
    """
    Serve up the database directory. Not a production quality server.
    Intended for testing purposes.
    """
    m = CVDUpdate(config=config, verbose=verbose)
    os.chdir(str(m.db_dir))
    m.logger.info(f"Serving up {m.db_dir} on localhost:{port}...")

    RangeRequestHandler.protocol_version = 'HTTP/1.0'
    # TODO(danvk): pick a random, available port
    httpd = HTTPServer(('', port), RangeRequestHandler)
    httpd.serve_forever()


#
# Command Aliases
#
@cli.command("list")
@click.pass_context
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path. [optional]")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output. [optional]")
def list_alias(ctx, config: str, verbose: bool):
    """
    List the DBs found in the database directory.

    This is just an alias for `db list`.
    """
    ctx.forward(db_list)

@cli.command("show")
@click.pass_context
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path. [optional]")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output. [optional]")
@click.argument("db", required=True)
def show_alias(ctx, config: str, verbose: bool, db: str):
    """
    Show details about a specific database.

    This is just an alias for `db show`.
    """
    ctx.forward(db_show)

@cli.command("update")
@click.pass_context
@click.option("--config", "-c", type=click.Path(), required=False, default="", help="Config path. [optional]")
@click.option("--verbose", "-V", is_flag=True, default=False, help="Verbose output. [optional]")
@click.option("--debug-mode", "-D", is_flag=True, default=False, help="Print out HTTP headers for debugging purposes. [optional]")
@click.argument("db", required=False, default="")
def update_alias(ctx, config: str, verbose: bool, db: str, debug_mode: bool):
    """
    Update local copy of DBs.

    This is just an alias for `db show`.
    """
    ctx.forward(db_update)


if __name__ == "__main__":
    sys.argv[0] = "cvdupdate"
    cli(sys.argv[1:])
