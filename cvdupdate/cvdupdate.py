"""
Copyright (C) 2021 Cisco Systems, Inc. and/or its affiliates. All rights reserved.

This module provides a tool to download and update clamav databases and database
patch files (CDIFFs) for the purposes of hosting your own database mirror.

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

from pathlib import Path
import copy
import datetime
from enum import Enum
import json
import logging
import os
import pkg_resources
import re
import time
from typing import *
import uuid
import http.client as http_client

from dns import resolver
import requests
from requests import status_codes

class CvdStatus(Enum):
    NO_UPDATE = 0
    UPDATED = 1
    ERROR = 2

class CVDUpdate:

    default_config_path: Path = Path.home() / ".cvdupdate" / "config.json"

    default_config: dict = {
        "nameserver" : "",
        "max retry" : 3, # No `cvd config set` option to set this, because we don't
                         # _really_ want people hammering the CDN with partial downloads.

        "log directory" : str(Path.home() / ".cvdupdate" / "logs"),
        "rotate logs" : True,
        "# logs to keep" : 30,

        "db directory" : str(Path.home() / ".cvdupdate" / "database"),
        "rotate cdiffs" : True,
        "# cdiffs to keep" : 30,

        "dbs" : {
            "main.cvd" : {
                "url" : "https://database.clamav.net/main.cvd",
                "retry after" : 0,
                "last modified" : 0,
                "last checked" : 0,
                "DNS field" : 1,     # only for CVDs
                "local version" : 0, # only for CVDs
                "CDIFFs" : []        # only for CVDs
            },
            "daily.cvd" : {
                "url" : "https://database.clamav.net/daily.cvd",
                "retry after" : 0,
                "last modified" : 0,
                "last checked" : 0,
                "DNS field" : 2,
                "local version" : 0,
                "CDIFFs" : []
            },
            "bytecode.cvd" : {
                "url" : "https://database.clamav.net/bytecode.cvd",
                "retry after" : 0,
                "last modified" : 0,
                "last checked" : 0,
                "DNS field" : 7,
                "local version" : 0,
                "CDIFFs" : []
            },
        },
    }

    config_path: Path
    config: dict
    db_dir: Path
    log_dir: Path
    version: str

    def __init__(
        self,
        config: str  = "",
        log_dir: str = "",
        db_dir: str  = "",
        nameserver: str  = "",
        verbose: bool = False,
    ) -> None:
        """
        CVDUpdate class.

        Args:
            log_dir:        path output log.
            db_dir:         path where databases will be downloaded.
            verbose:        Enable DEBUG-level logs and other verbose messages.
        """
        self.version = pkg_resources.get_distribution('cvdupdate').version
        self.verbose = verbose
        self._read_config(
            config,
            db_dir,
            log_dir,
            nameserver)
        self._init_logging()

    def _init_logging(self) -> None:
        """
        Initializes the logging parameters.
        """
        self.logger = logging.getLogger(f"cvdupdate-{self.version}")

        if self.verbose:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        formatter = logging.Formatter(
            fmt="%(asctime)s - %(levelname)s:  %(message)s",
            datefmt="%Y-%m-%d %I:%M:%S %p",
        )

        today = datetime.datetime.now()
        self.log_file = self.log_dir / f"{today.strftime('%Y-%m-%d')}.log"

        if not self.log_dir.exists():
            # Make a new log directory
            os.makedirs(os.path.split(self.log_file)[0])
        else:
            # Log dir already exists, lets check if we need to prune old logs
            logs = self.log_dir.glob('*.log')
            for log in logs:
                log_date_str = str(log.stem)
                log_date = datetime.datetime.strptime(log_date_str, "%Y-%m-%d")
                if log_date + datetime.timedelta(days=self.config["# logs to keep"]) < today:
                    # Log is too old, delete!
                    os.remove(str(log))

        self.filehandler = logging.FileHandler(filename=self.log_file)
        self.filehandler.setLevel(self.logger.level)
        self.filehandler.setFormatter(formatter)

        self.logger.addHandler(self.filehandler)

        # Also set the log level for urllib3, because it's "DEBUG" by default,
        # and we may not like that.
        urllib3_logger = logging.getLogger("urllib3.connectionpool")
        urllib3_logger.setLevel(self.logger.level)

    def _read_config(self,
                     config: str,
                     db_dir: str,
                     log_dir: str,
                     nameserver: str) -> None:
        """
        Read in the config file.
        Create a new one if one does not already exist.
        """
        need_save = False

        if config == "":
            self.config_path = self.default_config_path
        else:
            self.config_path = Path(config)

        if self.config_path.exists():
            # Config already exists, load it.
            with self.config_path.open('r') as config_file:
                self.config = json.load(config_file)
        else:
            # Config does not exist, use default
            self.config = self.default_config
            need_save = True

        if 'uuid' not in self.config:
            # Create a UUID to put in our User-Agent for better (anonymous) metrics
            self.config['uuid'] = str(uuid.uuid4())
            need_save = True

        if db_dir != "":
            self.config["db directory"] = db_dir
            need_save = True
        self.db_dir = Path(self.config["db directory"])

        if log_dir != "":
            self.config["log directory"] = log_dir
            need_save = True
        self.log_dir = Path(self.config["log directory"])

        if nameserver != "":
            self.config['nameserver'] = nameserver
            need_save = True

        # For backwards compatibility with older configs.
        if 'nameserver' not in self.config:
            self.config['nameserver'] = ""
            need_save = True
        if 'max retry' not in self.config:
            self.config['max retry'] = 3
            need_save = True

        if need_save:
            self._save_config()

    def _save_config(self) -> None:
        """
        Save the current configuration.
        """
        if not self.config_path.parent.exists():
            # config directory doesn't exist yet
            try:
                os.makedirs(str(self.config_path.parent))
            except Exception as exc:
                print("Failed to create config directory!")
                raise exc

        try:
            with self.config_path.open('w') as config_file:
                json.dump(self.config, config_file, indent=4)
        except Exception as exc:
            print("Failed to create config file!")
            raise exc

        if self.verbose:
            print(f"Saved: {self.config_path}\n")

    def config_show(self):
        """
        Print out the config
        """
        print(f"Config file: {self.config_path}\n")
        print(f"Config:\n{json.dumps(self.config, indent=4)}\n")

    def update(self, db: str = "") -> bool:
        """
        Update a specific database or all the databases.
        """

    def clean_dbs(self):
        """
        Delete all files in the database directory.
        """
        self.logger.info(f"Deleting databases...")
        dbs = self.db_dir.glob('*')
        for db in dbs:
            os.remove(str(db))
            self.logger.info(f"Deleted: {db}")

    def clean_logs(self):
        """
        Delete all files in the log directory.
        """
        self.logger.info(f"Deleting log files...")
        logs = self.log_dir.glob('*')
        for log in logs:
            os.remove(str(log))
            print(f"Deleted: {log}")

    def clean_all(self):
        """
        Delete all logs and databases and the config.
        """
        self.clean_dbs()

        self.clean_logs()

        os.remove(str(self.config_path))
        print(f"Deleted: {self.config_path}")

    def _index_local_databases(self) -> dict:
        need_save = False
        dbs = copy.deepcopy(self.config['dbs'])

        db_paths = self.db_dir.glob('*')
        for db in db_paths:
            if db.name.endswith('.cdiff'):
                # Ignore CDIFFs, they'll get printed later.
                continue

            if db.name not in dbs:
                version = 0

                # Found a file in here that ISN'T a part of the config
                if db.name.endswith('.cvd'):
                    # Found a CVD in here that ISN'T a part of the config!
                    # Very odd BTW.
                    self.logger.warning(f"Found a CVD in the DB directory that isn't in the config: {db.name}")
                    try:
                        version = self._get_cvd_version_from_file(db)
                    except Exception as exc:
                        self.logger.debug(f"EXCEPTION OCCURRED: {exc}")
                        self.logger.error(f"Failed to determine version for {db.name}")

                dbs[db.name] = {
                    "url" : "n/a",
                    "retry after" : 0,
                    "last modified" : os.path.getmtime(str(db)),
                    "last checked" : 0,
                    "DNS field" : 0,
                    "local version" : version,
                    "CDIFFs" : []
                }
            else:
                # DB on disk is from our config
                if db.name.endswith(".cvd") and self.config['dbs'][db.name]['local version'] == 0:
                    # Seems like we somehow got a (config'd) CVD file in our database directory without
                    # saving the CVD info to the config. Let's just update the version field.
                    self.logger.info(f"Found {db.name} in the DB directory, though it wasn't downloaded using this tool.")
                    try:
                        dbs[db.name]['local version'] = self._get_cvd_version_from_file(self.db_dir / db.name)
                        self.logger.info(f"Identified mysterious {db.name} version: {dbs[db.name]['local version']}")

                        # Add the version info for this mysteriously deposited CVD to our config.
                        self.config['dbs'][db.name]['local version'] = dbs[db.name]['local version']
                        need_save = True
                    except Exception as exc:
                        self.logger.debug(f"EXCEPTION OCCURRED: {exc}")
                        self.logger.error(f"Failed to determine version # of mysterious {db.name} file. Perhaps it is corrupted?")

        if need_save:
            self._save_config()

        return dbs

    def db_list(self) -> None:
        """
        Print list of databases
        """
        dbs = self._index_local_databases()

        for db in dbs:
            updated = datetime.datetime.fromtimestamp(dbs[db]['last modified']).strftime('%Y-%m-%d %H:%M:%S')
            checked = datetime.datetime.fromtimestamp(dbs[db]['last checked']).strftime('%Y-%m-%d %H:%M:%S')
            self.logger.info(f"Database: {db}")
            if dbs[db]['last modified'] == 0:
                self.logger.info("  last modified: not downloaded")
            else:
                self.logger.info(f"  last modified: {updated}")
            if dbs[db]['last checked'] == 0:
                self.logger.debug(" last checked:  n/a")
            else:
                self.logger.debug(f" last checked:  {checked}")
            self.logger.debug(f" url:           {dbs[db]['url']}")
            if db.endswith(".cvd"):
                # Only CVD's have versions.
                self.logger.debug(f" local version: {dbs[db]['local version']}")
            if len(dbs[db]['CDIFFs']) > 0:
                self.logger.debug(f" CDIFFs:")
                for cdiff in dbs[db]['CDIFFs']:
                    self.logger.debug(f"   {cdiff}")


    def db_show(self, name) -> bool:
        """
        Show details for a specific database
        """
        found = False
        dbs = self._index_local_databases()

        for db in dbs:
            if db == name:
                found = True;

                updated = datetime.datetime.fromtimestamp(dbs[db]['last modified']).strftime('%Y-%m-%d %H:%M:%S')
                checked = datetime.datetime.fromtimestamp(dbs[db]['last checked']).strftime('%Y-%m-%d %H:%M:%S')
                self.logger.info(f"Database: {db}")
                if dbs[db]['last modified'] == 0:
                    self.logger.info("  last modified: not downloaded")
                else:
                    self.logger.info(f"  last modified: {updated}")
                if dbs[db]['last checked'] == 0:
                    self.logger.info("  last checked:  n/a")
                else:
                    self.logger.info(f"  last checked:  {checked}")
                self.logger.info(f"  url:           {dbs[db]['url']}")
                if db.endswith(".cvd"):
                    self.logger.info(f"  local version: {dbs[db]['local version']}")
                if len(dbs[db]['CDIFFs']) > 0:
                    self.logger.info(f"  CDIFFs: \n{json.dumps(dbs[db]['CDIFFs'], indent=4)}")
                return True

        if not found:
            self.logger.error(f"No such database: {name}")
        return found

    def _query_dns_txt_entry(self) -> bool:
        '''
        Attempt to get version from current.cvd.clamav.net DNS TXT entry
        '''
        got_it = False
        self.logger.debug(f"Checking available versions via DNS TXT entry query of current.cvd.clamav.net")

        try:
            our_resolver = resolver.Resolver()
            nameserver = os.environ.get("CVDUPDATE_NAMESERVER")

            if nameserver != None:
                # Override the default nameserver using the CVDUPDATE_NAMESERVER environment variable.
                our_resolver.nameservers = [nameserver]
                self.logger.info(f"Using nameserver specified in CVDUPDATE_NAMESERVER: {nameserver}")

            elif self.config['nameserver'] != "":
                # Override the default nameserver using a config setting.
                our_resolver.nameservers = [self.config['nameserver']]
                self.logger.info(f"Using nameserver specified in the config: {self.config['nameserver']}")

            answer = str(our_resolver.resolve("current.cvd.clamav.net","TXT").response.answer[0])
            versions = re.search('".*"', answer).group().strip('"')
            self.dns_version_tokens = versions.split(':')
            got_it = True
        except Exception as exc:
            self.logger.debug(f"EXCEPTION OCCURRED: {exc}")
            self.logger.warning(f"Failed to determine available version via DNS TXT query!")

        return got_it

    def _query_cvd_version_dns(self, db: str) -> int:
        '''
        This is a faux query.
        Try to look up the version # from the DNS TXT entry we already have.
        '''
        version = 0

        if self.dns_version_tokens == []:
            # Query DNS if we haven't already
            self._query_dns_txt_entry()
            if self.dns_version_tokens == []:
                # Query failed. Bail out.
                return version

        self.logger.debug(f"Checking {db} version via DNS TXT advertisement.")

        if self.config['dbs'][db]['DNS field'] == 0:
            # Invalid DNS field value for database version.
            self.logger.warning(f"Failed to get DB version from DNS TXT entry: Invalid DNS field value for database version.")
            return version

        try:
            version = int(self.dns_version_tokens[self.config['dbs'][db]['DNS field']])
            self.logger.debug(f"{db} version advertised by DNS: {version}")

            # Update the "last checked" time.
            self.config['dbs'][db]['last checked'] = time.time()

        except Exception as exc:
            self.logger.debug(f"EXCEPTION OCCURRED: {exc}")
            self.logger.warning(f"Failed to get DB version from DNS TXT entry!")

        return version

    def _query_cvd_version_http(self, db: str) -> int:
        '''
        Download the CVD header and read the CVD version

        Return 1+ if queried version.
        Return 0  if failed.
        '''
        version = 0
        retry = 0
        url = self.config['dbs'][db]['url']

        self.logger.debug(f"Checking {db} version via HTTP download of CVD header.")

        ims = datetime.datetime.utcfromtimestamp(self.config['dbs'][db]['last modified']).strftime('%a, %d %b %Y %H:%M:%S GMT')

        while retry < self.config['max retry']:
            response = requests.get(url, headers = {
                'User-Agent': f'CVDUPDATE/{self.version} ({self.config["uuid"]})',
                'Range': 'bytes=0-95',
                'If-Modified-Since': ims,
            })

            if ((response.status_code == 200 or response.status_code == 206) and
                ('content-length' in response.headers) and
                (int(response.headers['content-length']) > len(response.content))):
                self.logger.warning(f"Response was truncated somehow...")
                self.logger.warning(f"   Expected {response.headers['content-length']}")
                self.logger.warning(f"   Received {response.content}, let's retry.")
                retry += 1
            else:
                break

        if response.status_code == 200 or response.status_code == 206:
            # Looks like we downloaded something...
            if (('content-length' in response.headers) and int(response.headers['content-length']) > len(response.content)):
                self.logger.error(f"Failed to download {db} header to check the version #.")
                return 0

            # Successfully downloaded the header.
            # We used the IMS header so this means it's probably newer, but we'll check just in case.
            cvd_header = response.content
            version = self._get_version_from_cvd_header(cvd_header)
            self.logger.debug(f"{db} version available by HTTP download: {version}")

        elif response.status_code == 304:
            # HTTP Not-Modified, it's not newer.than what we already have.
            # Just return the current local version.
            version = self.config['dbs'][db]['local version']
            self.logger.debug(f"{db} not-modified since: {ims} (local version {version})")

        elif response.status_code == 429:
            # Rejected because downloading the same file too frequently.
            self.logger.warning(f"Failed to download {db} header to check the version #.")
            self.logger.warning(f"Download request rejected because we've downloaded the same file too frequently.")

            try_again_seconds = 60 * 60 * 12 # 12 hours
            if 'Retry-After' in response.headers.keys():
                try_again_seconds = int(response.headers['Retry-After'])

            self.config['dbs'][db]['retry after'] = time.time() + float(try_again_seconds)

            try_again_string = str(datetime.timedelta(seconds=try_again_seconds))
            self.logger.warning(f"We won't try {db} again for {try_again_string} hours.")

        else:
            # Check failed!
            self.logger.error(f"Failed to download {db} header to check the version #. Url: {url}")

        if version > 0:
            # Update the "last checked" time.
            self.config['dbs'][db]['last checked'] = time.time()

        return version

    def _download_db_from_url(self, db: str, url: str, last_modified: int, version=0) -> CvdStatus:
        '''
        Download contents from a url and save to a filename in the database directory.
        Will use If-Modified-Since
        If Not-Modified, it will not replace the current database.
        '''
        retry = 0
        ims: str = datetime.datetime.utcfromtimestamp(last_modified).strftime('%a, %d %b %Y %H:%M:%S GMT')

        while retry < self.config['max retry']:
            response = requests.get(url, headers = {
                'User-Agent': f'CVDUPDATE/{self.version} ({self.config["uuid"]})',
                'If-Modified-Since': ims,
            })

            if ((response.status_code == 200 or response.status_code == 206) and
                ('content-length' in response.headers) and
                (int(response.headers['content-length']) > len(response.content))):
                self.logger.warning(f"Response was truncated somehow...")
                self.logger.warning(f"   Expected {response.headers['content-length']}")
                self.logger.warning(f"   Received {response.content}, let's retry.")
                retry += 1
            else:
                break

        if response.status_code == 200:
            # Looks like we downloaded something...
            if (('content-length' in response.headers) and int(response.headers['content-length']) > len(response.content)):
                self.logger.error(f"Failed to download {db}")
                return CvdStatus.ERROR

            # Download Success
            if version > 0:
                self.logger.info(f"Downloaded {db}. Version: {version}")
            else:
                self.logger.info(f"Downloaded {db}")

            try:
                with (self.db_dir / db).open('wb') as new_db:
                    new_db.write(response.content)

                # Update config w/ new db info
                self.config['dbs'][db]['last modified'] = time.time()
                if db.endswith('.cvd'):
                    self.config['dbs'][db]['local version'] = self._get_version_from_cvd_header(response.content[:96])

            except Exception as exc:
                self.logger.debug(f"EXCEPTION OCCURRED: {exc}")
                self.logger.error(f"Failed to save {db} to {self.db_dir}")
                return CvdStatus.ERROR

        elif response.status_code == 304:
            # Not modified since IMS. We have the latest version.
            version = self.config['dbs'][db]['local version']
            self.logger.info(f"{db} not-modified since: {ims} (local version {version})")
            return CvdStatus.NO_UPDATE

        elif response.status_code == 429:
            # Rejected because downloading the same file too frequently.
            self.logger.warning(f"Failed to download {db}.")
            self.logger.warning(f"Download request rejected because we've downloaded the same file too frequently.")

            try_again_seconds = 60 * 60 * 12 # 12 hours
            if 'Retry-After' in response.headers.keys():
                try_again_seconds = int(response.headers['Retry-After'])

            self.config['dbs'][db]['retry after'] = time.time() + float(try_again_seconds)

            try_again_string = str(datetime.timedelta(seconds=try_again_seconds))
            self.logger.warning(f"We won't try {db} again for {try_again_string} hours.")

            # We'll have to retry after the cooldown.
            return CvdStatus.ERROR

        else:
            # HTTP Get failed.
            self.logger.error(f"Failed to download {db} from {url}")
            return CvdStatus.ERROR

        return CvdStatus.UPDATED

    def _download_cvd(self, db: str, available_version: int) -> CvdStatus:
        '''
        Download the latest available version
        If we already have some version of the database, attempt to download all CDIFFs in between.
        If we don't, just get the last two CDIFFs.
        '''
        local_version = self.config['dbs'][db]['local version']
        desired_version = local_version + 1

        if local_version >= available_version:
            # Oh! We're already up to date, don't worry about it.
            self.logger.info(f"{db} is up-to-date. Version: {local_version}")
            return CvdStatus.NO_UPDATE

        elif local_version == 0:
            # We don't have any version of the DB, let's just get the newest version + the last CDIFF
            desired_version = available_version

        # First try to get CDIFFs
        self.logger.debug(f"Downloading CDIFFs first...")
        while desired_version <= available_version:
            # Attempt to download each CDIFF betwen our local version and the available version
            # The url for CVDs should be https://database.clamav.net/<db>
            # Eg:
            #   https://database.clamav.net/daily.cvd
            # For the daily cdiffs, we would want:
            #   https://database.clamav.net/daily-<version>.cdiff
            retry = 0
            cdiff_filename = f"{db[:-len('.cvd')]}-{desired_version}.cdiff"

            original_url = self.config['dbs'][db]['url']
            url = f"{original_url[:-len(db)]}{cdiff_filename}"

            if (self.db_dir / cdiff_filename).exists():
                self.logger.debug(f"We already have {cdiff_filename}. Skipping...")

            self.logger.debug(f"Checking for {cdiff_filename}")

            while retry < self.config['max retry']:
                response = requests.get(url, headers = {
                    'User-Agent': f'CVDUPDATE/{self.version} ({self.config["uuid"]})',
                })

                if ((response.status_code == 200 or response.status_code == 206) and
                    ('content-length' in response.headers) and
                    (int(response.headers['content-length']) > len(response.content))):
                    self.logger.warning(f"Response was truncated somehow...")
                    self.logger.warning(f"   Expected {response.headers['content-length']}")
                    self.logger.warning(f"   Received {response.content}, let's retry.")
                    retry += 1
                else:
                    break

            if response.status_code == 200:
                # Looks like we downloaded something...
                if (('content-length' in response.headers) and int(response.headers['content-length']) > len(response.content)):
                    self.logger.error(f"Failed to download {db} header to check the version #.")
                    return CvdStatus.ERROR

                # Download Success
                self.logger.info(f"Downloaded {cdiff_filename}")
                try:
                    with (self.db_dir / f"{cdiff_filename}").open('wb') as new_db:
                        new_db.write(response.content)

                    # Update config with CDIFF, for posterity
                    self.config['dbs'][db]['CDIFFs'].append(cdiff_filename)

                    # Prune old CDIFFs if needed
                    if len(self.config['dbs'][db]['CDIFFs']) > self.config['# cdiffs to keep']:
                        os.remove(self.db_dir / self.config['dbs'][db]['CDIFFs'][0])
                        self.config['dbs'][db]['CDIFFs'] = self.config['dbs'][db]['CDIFFs'][1:]

                except Exception as exc:
                    self.logger.debug(f"EXCEPTION OCCURRED: {exc}")
                    self.logger.error(f"Failed to save {cdiff_filename} to {self.db_dir}.")

            elif response.status_code == 429:
                # Rejected because downloading the same file too frequently.
                self.logger.warning(f"Failed to download {cdiff_filename}")
                self.logger.warning(f"Download request rejected because we've downloaded the same file too frequently.")

                try_again_seconds = 60 * 60 * 12 # 12 hours
                if 'Retry-After' in response.headers.keys():
                    try_again_seconds = int(response.headers['Retry-After'])

                self.config['dbs'][db]['retry after'] = time.time() + float(try_again_seconds)

                try_again_string = str(datetime.timedelta(seconds=try_again_seconds))
                self.logger.warning(f"We won't try {db} again for {try_again_string} hours.")

                # Sure only a CDIFF failed, but if we want any chance of trying the CDIFF again
                # in the future, let's bail out now and retry the CVD + CDIFFs after the cooldown.
                return CvdStatus.ERROR

            else:
                # HTTP Get failed.
                self.logger.info(f"No CDIFF found for {db} version # {desired_version}")

                if desired_version < available_version:
                    desired_version = available_version - 1
                    self.logger.info(f"Will just skip to the last CDIFF instead.")
                else:
                    self.logger.info(f"Giving up on CDIFFs for {db}")
                    break

            desired_version += 1

        # Now download the available version.
        desired_version = available_version

        url = f"{self.config['dbs'][db]['url']}?version={desired_version}"

        return self._download_db_from_url(db, url, last_modified=0, version=desired_version)

    def _get_version_from_cvd_header(self, cvd_header: bytes) -> int:
        '''
        Parse a CVD header to read the database version.
        '''
        header_fields = cvd_header.decode('utf-8', 'ignore').strip().split(':')

        version_found = 0
        try:
            version_found = int(header_fields[2])
        except Exception as exc:
            self.logger.debug(f"EXCEPTION OCCURRED: {exc}")
            self.logger.error(f"Failed to determine version from CVD header!")

        return version_found

    def _get_cvd_version_from_file(self, path: Path) -> int:
        cvd_header: bytes = b''
        version_found = 0

        try:
            with path.open('rb') as cvd_fd:
                cvd_header = cvd_fd.read(96)

            if len(cvd_header) < 96:
                # Most likely a corrupted CVD. Delete.
                self.logger.debug(f"Failed to read CVD header, perhaps {path.name} is corrupted.")
                self.logger.debug(f"Will delete {path.name} so it will not cause further problems.")
                os.remove(str(path))
            else:
                # Got the header, lets parse out the version.
                version_found = self._get_version_from_cvd_header(cvd_header)

        except Exception as exc:
            self.logger.debug(f"EXCEPTION OCCURRED: {exc}")
            self.logger.error(f"Failed to read version from CVD header from {path}.")

        if version_found == 0:
            self.logger.error(f"Failed to determine version from CVD header.")

        return version_found

    def db_update(self, db="", debug_mode=False) -> int:
        """
        Update one or all of the databases.

        Returns: Number of errors.
        """
        self.update_errors = 0
        self.dbs_updated = 0
        self.dns_version_tokens = []

        # Make sure we have a database directory to save files to
        if not self.db_dir.exists():
            os.makedirs(self.db_dir)

        # Query DNS so we can efficiently query CVD version #'s
        self._query_dns_txt_entry()
        if self.dns_version_tokens == []:
            # Query failed. Bail out.
            self.logger.error(f"Failed to update {db}. Missing or invalid URL: {self.config['dbs'][db]['url']}")
            return 1

        if debug_mode:
            http_client.HTTPConnection.debuglevel = 1

        def update(db) -> CvdStatus:
            '''
            Update a database
            '''
            if self.config['dbs'][db]['retry after'] > 0:
                cooldown_date = datetime.datetime.fromtimestamp(self.config['dbs'][db]['retry after']).strftime('%Y-%m-%d %H:%M:%S')

                if self.config['dbs'][db]['retry after'] > time.time():
                    self.logger.warning(f"Skipping {db} which is on cooldown until {cooldown_date}")
                    return CvdStatus.ERROR
                else:
                    # Cooldown expired. Ok to try again.
                    self.config['dbs'][db]['retry after'] = 0
                    self.logger.info(f"{db} cooldown expired {cooldown_date}. OK to try again...")

            if not self.config['dbs'][db]['url'].startswith('http'):
                self.logger.error(f"Failed to update {db}. Missing or invalid URL: {self.config['dbs'][db]['url']}")
                return CvdStatus.ERROR

            self.logger.debug(f"Checking {db} for update from {self.config['dbs'][db]['url']}")

            if db.endswith('.cvd'):
                # It's a CVD (official signed clamav database)
                advertised_version = 0

                if self.config['dbs'][db]['local version'] == 0 and (self.db_dir / db).exists():
                    # Seems like we somehow got a CVD in our database directory without
                    # saving the CVD info to the config. Let's just update the version field.
                    self.config['dbs'][db]['local version'] = self._get_cvd_version_from_file(self.db_dir / db)


                if self.config['dbs'][db]['DNS field'] > 0:
                    # We can use the DNS TXT fields to check if our version is old.
                    advertised_version = self._query_cvd_version_dns(db)

                else:
                    # We can't use DNS to see if our version is old.
                    # Use HTTP to pull just the CVD header to check.
                    advertised_version = self._query_cvd_version_http(db)

                if advertised_version == 0:
                    self.logger.error(f"Failed to update {db}. Failed to query available CVD version")
                    return CvdStatus.ERROR

                return self._download_cvd(db, advertised_version)

            else:
                # Try the download.
                # Will use If-Modified-Since
                # If Not-Modified, it will not replace the current database.
                return self._download_db_from_url(
                    db,
                    self.config['dbs'][db]['url'],
                    self.config['dbs'][db]['last modified'])

        if db == "":
            # Update every DB.
            for db in self.config['dbs']:
                status = update(db)
                if status == CvdStatus.ERROR:
                    self.update_errors += 1
                elif status == CvdStatus.UPDATED:
                    self.dbs_updated += 1

        else:
            # Update a specific DB.
            if db not in self.config['dbs']:
                self.logger.error(f"Update failed. Unknown database: {db}")
            else:
                status = update(db)
                if status == CvdStatus.ERROR:
                    self.update_errors += 1
                elif status == CvdStatus.UPDATED:
                    self.dbs_updated += 1

        self._save_config()

        if self.update_errors == 0 and self.dbs_updated > 0:
            with (self.db_dir / 'dns.txt').open('w') as dns_file:
                dns_file.write(':'.join(self.dns_version_tokens))
            self.logger.debug(f"Updated {self.db_dir / 'dns.txt'}")

        return self.update_errors

    def config_add_db(self, db: str, url: str) -> bool:
        """
        Add another database + url to check when we update.
        """
        extension = db.split('.')[-1]
        if extension not in [
            'cvd', 'cld', 'cud',
            'cfg', 'cat', 'crb',
            'ftm',
            'ndb', 'ndu',
            'ldb', 'ldu', 'idb',
            'ydb', 'yar', 'yara',
            'cdb',
            'cbc',
            'pdb', 'gdb', 'wdb',
            'hdb', 'hsb', 'hdu', 'hsu',
            'mdb', 'msb', 'mdu', 'msu',
            'ign', 'ign2',
            'info',
            ]:
            self.logger.warning(f"{db} does not have valid clamav database file extension.")

        if db in self.config['dbs']:
            self.logger.info(f"Cannot add {db}, it is already in our list.")
            self.logger.info(f"Hint: Try `db list -V` or `db show {db}` for more information.")
            return False

        self.config['dbs'][db] = {
            "url" : url,
            "retry after" : 0,
            "last modified" : 0,
            "last checked" : 0,
            "DNS field" : 0,
            "local version" : 0,
            "CDIFFs" : []
        }

        self.logger.info(f"Added {db} ({url}) to DB list.")
        self.logger.info(f"{db} will be downloaded next time you run `cvd update` or `cvd update {db}`")

        self._save_config()

        return True

    def config_remove_db(self, db: str) -> bool:
        """
        Remove a database from our list, and delete copies of the DB from the database directory.
        """
        if db not in self.config['dbs']:
            self.logger.info(f"Cannot remove {db}, it is not in our list.")
            self.logger.info(f"Hint: Try `db list -V` for more information.")
            return False

        try:
            if (self.db_dir / db).exists():
                os.remove(str(self.db_dir / db))
                self.logger.info(f"Deleted {db} from database directory.")

        except Exception as exc:
            self.logger.debug(f"An exception occured: {exc}")
            self.logger.error(f"Failed to delete {db} from databse directory!")

        for cdiff in self.config['dbs'][db]['CDIFFs']:
            try:
                if (self.db_dir / cdiff).exists():
                    os.remove(str(self.db_dir / cdiff))
                    self.logger.info(f"Deleted {cdiff} from database directory.")

            except Exception as exc:
                self.logger.debug(f"An exception occured: {exc}")
                self.logger.error(f"Failed to delete {cdiff} from databse directory!")

        self.config['dbs'].pop(db)

        self.logger.info(f"Removed {db} from DB list.")

        self._save_config()

        return True
