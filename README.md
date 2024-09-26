<p align="center">A tool to download and update clamav databases and database patch files
for the purposes of hosting your own database mirror.
<p align="center"><em>Copyright (C) 2021-2022 Cisco Systems, Inc. and/or its affiliates. All rights reserved.</em></p>

<p align="center">
<a href="https://pypi.org/project/cvdupdate/">
  <img src="https://badge.fury.io/py/cvdupdate.svg" alt="PyPI version" height="18">
</a>
<img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/cvdupdate" height="18">
<a href="https://discord.gg/6vNAqWnVgw"><img src="https://img.shields.io/discord/636023333074370595.svg?logo=discord" height="18"/></a>
<a href="https://twitter.com/clamav"><img src="https://abs.twimg.com/favicons/twitter.ico" width="18" height="18"></a>
</p>

## About

This tool downloads the latest ClamAV databases along with the latest database patch files.

This project replaces the `clamdownloader.pl` Perl script by Frederic Vanden Poel, formerly provided here: https://www.clamav.net/documents/private-local-mirrors

Run this tool as often as you like, but it will only download new content if there is new content to download. If you somehow manage to download too frequently (eg: by using `cvd clean all` and `cvd update` repeatedly), then the official database server may refuse your download request, and one or more databases may go on cool-down until it's safe to try again.

## Requirements

- Python 3.6 or newer.
- An internet connection with DNS enabled.
- The following Python packages.  These will be installed automatically if you use `pip`, but may need to be installed manually otherwise:
  - `click` v7.0 or newer
  - `coloredlogs` v10.0 or newer
  - `colorama`
  - `requests`
  - `dnspython` v2.1.0 or newer
  - `rangehttpserver`

## Installation

You may install `cvdupdate` from PyPI using `pip`, or you may clone the project Git repository and use `pip` to install it locally.

Install `cvdupdate` from PyPI:

```bash
python3 -m pip install --user cvdupdate
```

### Updating Your Installation

When running `cvd update` to update the databases, it will also check if there is a new version of the `cvdupdate` package on Python's PyPI package repository. If there is a newer version of `cvdupdate`, you will see a message prompting you to upgrade. It will look someething like this:
```
WARNING You are running cvdupdate version: 1.1.0.
WARNING There is a newer version on PyPI: 1.1.1. Please update!
```

To upgrade the `cvdupdate` package through PyPI, run:

```bash
python3 -m pip install --user --upgrade cvdupdate
```

## Basic Usage

Use the `--help` option with any `cvd` command to get help.

```bash
cvd --help
```

> _Tip_: You may not be able to run the `cvd` or `cvdupdate` shortcut directly if your Python Scripts directory is not in your `PATH` environment variable. If you run into this issue, and do not wish to add the Python Scripts directory to your path, you can run CVD-Update like this:
>
> ```bash
> python -m cvdupdate --help
> ```

(optional) You may wish to customize where the databases are stored:

```bash
cvd config set --dbdir <your www path>
```

Run this to download the latest database and associated CDIFF patch files:

```bash
cvd update
```

Downloaded databases will be placed in `~/.cvdupdate/database` unless you customized it to use a different directory.

Newly downloaded databases will replace the previous database version, but the CDIFF patch files will accumulate up to a configured maximum before it starts deleting old CDIFFs (default: 30 CDIFFs). You can configure it to keep more CDIFFs by manually editing the config (default: `~/.cvdupdate/config.json`). The same behavior applies for CVD-Update log rotation.

Run this to serve up the database directory on `http://localhost:8000` so you can test it with FreshClam.

```bash
cvd serve
```

> _Disclaimer_: The `cvd serve` feature is not intended for production use, just for testing. You probably want to use a more robust HTTP server for production work.

Install ClamAV if you don't already have it and, in another terminal window, modify your `freshclam.conf` file. Replace:
```
DatabaseMirror database.clamav.net
```

... with:
```
DatabaseMirror http://localhost:8000
```

> _Tip_: A default install on Linux/Unix places `freshclam.conf` in `/usr/local/etc/freshclam.conf`. If one does not exist, you may need to create it using `freshclam.conf.sample` as a template.

Now, run `freshclam -v` or `freshclam.exe -v` to see what happens. You should see FreshClam successfully update it's own database directory from your private database server.

Run `cvd update` as often as you need.  Maybe put it in a `cron` job.

> _Tip_: Each command supports a `--verbose` (`-V`) mode, which often provides more details about what's going on under the hood.

### Cron Example

Cron is a popular choice to automate frequent tasks on Linux / Unix systems.

1. Open a terminal running as the user which you want CVD-Update to run under, do the following:

   ```bash
   crontab -e
   ```

2. Press `i` to insert new text, and add this line:

   ```bash
   30 */4 * * * /bin/sh -c "~/.local/bin/cvd update &> /dev/null"
   ```

   Or instead of `~/`, you can do this, replacing `username` with your user name:

   ```bash
   30 */4 * * * /bin/sh -c "/home/username/.local/bin/cvd update &> /dev/null"
   ```

3. Press <Escape>, then type `:wq` and press <Enter> to write the file to disk and quit.

**About these settings**:

I selected `30 */4 * * *` to run at minute 30 past every 4th hour. CVD-Update uses a DNS check to do version checks before it attempts to download any files, just like FreshClam. Running CVD-Update more than once a day should not be an issue.

CVD-Update will write logs to the `~/.cvdupdate/logs` directory, which is why I directed `stdout` and `stderr` to `/dev/null` instead of a log file. You can use the `cvd config set` command to customize the log directory if you like, or redirect `stdout` and `stderr` to a log file if you prefer everything in one log instead of separate daily logs.

## Optional Functionality

### Using a custom DNS server

DNS is required for CVD-Update to function properly (to gather the TXT record containing the current definition database version). You can select a specific nameserver to ensure said nameserver is used when querying the TXT record containing the current database definition version available

1. Set the nameserver in the config. Eg:

   ```bash
   cvd config set --nameserver 208.67.222.222
   ```

2. Set the environment variable `CVDUPDATE_NAMESERVER`. Eg:

   ```bash
   CVDUPDATE_NAMESERVER="208.67.222.222" cvd update
   ```

The environment variable will take precedence over the nameserver config setting.

Note:  Both options can be used to provide a comma-delimited list of nameservers to utilize for resolution.

### Using a proxy

Depending on your type of proxy, you may be able to use CVD-Update with your proxy by running CVD-Update like this:

First, set a custom domain name server to use the proxy:

```bash
cvd config set --nameserver <proxy_ip>
```

Then run CVD-Update like this:

```bash
http_proxy=http://<proxy_ip>:<proxy_port> https_proxy=http://<proxy_ip>:<proxy_port> cvd update -V
```

Or create a script to wrap the CVD-Update call. Something like:

```bash
#!/bin/bash
http_proxy=http://<proxy_ip>:<proxy_port>
export http_proxy
https_proxy=http://<proxy_ip>:<proxy_port>
export https_proxy
cvd update -V
```

> _Disclaimer_: CVD-Update doesn't support proxies that require authentication at this time. If your network admin allows it, you may be able to work around it by updating your proxy to allow HTTP requests through unauthenticated if the User-Agent matches your specific CVD-Update user agent. The CVD-Update User-Agent follows the form `CVDUPDATE/<version> (<uuid>)` where the `uuid` is unique to your installation and can be found in the `~/.cvdupdate/state.json` file (or `~/.cvdupdate/config.json` for cvdupdate <=1.0.2). See https://github.com/Cisco-Talos/cvdupdate/issues/9 for more details.
>
> Adding support for proxy authentication is a ripe opportunity for a community contribution to the project.

## Files and directories created by CVD-Update

This tool is to creates the following directories:
 - `~/.cvdupdate`
 - `~/.cvdupdate/logs`
 - `~/.cvdupdate/databases`

This tool creates the following files:
 - `~/.cvdupdate/config.json`
 - `~/.cvdupdate/state.json`
 - `~/.cvdupdate/databases/<database>.cvd`
 - `~/.cvdupdate/databases/<database>-<version>.cdiff`
 - `~/.cvdupdate/logs/<date>.log`

> _Tip_: You can set custom `database` and `logs` directories with the `cvd config set` command. It is likely you will want to customize the `database` directory to point to your HTTP server's `www` directory (or equivalent). Bare in mind that if you already downloaded the databases to the old directory, you may want to move them to the new directory.

> _Important_: If you want to use a custom config path, you'll have to use it in every command. If you're fine with having it go in `~/.cvdupdate/config.json`, don't worry about it.

## Additional Usage

### Get familiar with the tool

Familiarize yourself with the various commands using the `--help` option.

```bash
cvd --help
cvd config --help
cvd update --help
cvd add --help
cvd clean --help
```

Print out the current list of databases.

```bash
cvd list -V
```

Print out the config to see what it looks like.

```bash
cvd config show
```

### Do an update

Do an update, use "verbose mode" to so you can get a feel for how it works.

```bash
cvd update -V
```

List out the databases again:

```bash
cvd list -V
```

The print out the config again so you can see what's changed.

```bash
cvd config show
```

And maybe take a peek in the database directory as well to see it for yourself.

```bash
ls ~/.cvdupdate/database
```

Have a look at the logs if you wish.

```bash
ls ~/.cvdupdate/logs

cat ~/.cvdupdate/logs/*
```

### Add an additional database

Maybe add an additional database that is not part of the default set of databases.

```bash
cvd add linux.cvd https://database.clamav.net/linux.cvd
```

List out the databases again:

```bash
cvd list -V
```

### Serve it up, Test out FreshClam

Test out your mirror with FreshClam on the same computer.

This tool includes a `--serve` feature that will host the current database directory on http://localhost (default port: 8000).

You can test it by running `freshclam` or `freshclam.exe` locally, where you've configured `freshclam.conf` with:

```
DatabaseMirror http://localhost:8000
```

## Use docker

Build docker image

```bash
docker build . --tag cvdupdate:latest
```

Run image, that will automaticly update databases in folder `/srv/cvdupdate` and write logs to `/var/log/cvdupdate`

```bash
docker run -d \
  -v /srv/cvdupdate:/cvdupdate/database \
  -v /var/log/cvdupdate:/cvdupdate/logs \
  cvdupdate:latest
```

Run image, that will automaticly update databases in folder `/srv/cvdupdate`, write logs to `/var/log/cvdupdate` and set owner of files to user with ID 1000

```bash
docker run -d \
  -v /srv/cvdupdate:/cvdupdate/database \
  -v /var/log/cvdupdate:/cvdupdate/logs \
  -e USER_ID=1000 \
  cvdupdate:latest
```

Default update interval is `30 */4 * * *` (see [Cron Example](#cron-example))

You may pass custom update interval in environment variable `CRON`

For example - update every day in 00:00

```bash
docker run -d \
  -v /srv/cvdupdate:/cvdupdate/database \
  -v /var/log/cvdupdate:/cvdupdate/logs \
  -e CRON='0 0 * * *' \
  cvdupdate:latest
  ```
## Use Docker Compose

A Docker `compose.yaml` is provided to:
1. Regularly update a Docker volume with the latest ClamAV databases.
2. Serve a database mirror on port 8000 using the Apache webserver. 

Edit the `compose.yaml` file if you need to change the default values:

* Port 8000
* USER_ID=0
* CRON=30 */4 * * *

### Build
```bash
docker compose build
```

### Start
```bash
docker compose up -d
```

### Stop
```bash
docker compose down
```

### Volumes
Volumes are defined in `compose.yaml` and will be auto-created when you run `docker compose up`
```
DRIVER    VOLUME NAME
local     cvdupdate_database
local     cvdupdate_log
```

## Contribute

We'd love your help. There are many ways to contribute!

### Community

Join the ClamAV community on the [ClamAV Discord chat server](https://discord.gg/sGaxA5Q).

### Report issues

If you find an issue with CVD-Update or the CVD-Update documentation, please submit an issue to our [GitHub issue tracker](https://github.com/Cisco-Talos/cvdupdate/issues).  Before you submit, please check to if someone else has already reported the issue.

### Development

If you find a bug and you're able to craft a fix yourself, consider submitting the fix in a [pull request](https://github.com/Cisco-Talos/cvdupdate/pulls). Your help will be greatly appreciated.

If you want to contribute to the project and don't have anything specific in mind, please check out our [issue tracker](https://github.com/Cisco-Talos/cvdupdate/issues).  Perhaps you'll be able to fix a bug or add a cool new feature.

_By submitting a contribution to the project, you acknowledge and agree to assign Cisco Systems, Inc the copyright for the contribution. If you submit a significant contribution such as a new feature or capability or a large amount of code, you may be asked to sign a contributors license agreement comfirming that Cisco will have copyright license and patent license and that you are authorized to contribute the code._

#### Development Set-up

The following steps are intended to help users that wish to contribute to development of the CVD-Update project get started.

1. Create a fork of the [CVD-Update git repository](https://github.com/Cisco-Talos/cvdupdate), and then clone your fork to a local directory.

    For example:

    ```bash
    git clone https://github.com/<your username>/cvdupdate.git
    ```

2. Make sure CVD-Update is not already installed.  If it is, remove it.

    ```bash
    python3 -m pip uninstall cvdupdate
    ```

3. Use pip to install CVD-Update in "edit" mode.

    ```bash
    python3 -m pip install -e --user ./cvdupdate
    ```

Once installed in "edit" mode, any changes you make to your clone of the CVD-Update code will be immediately usable simply by running the `cvdupdate` / `cvd` commands.

### Conduct

This project has not selected a specific Code-of-Conduct document at this time. However, contributors are expected to behave in professional and respectful manner. Disrespectful or inappropriate behavior will not be tolerated.

## License

CVD-Update is licensed under the Apache License, Version 2.0 (the "License"). You may not use the CVD-Update project except in compliance with the License.

A copy of the license is located [here](LICENSE), and is also available online at [apache.org](http://www.apache.org/licenses/LICENSE-2.0).

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
