<p align="center">A tool to download and update clamav databases and database patch files
for the purposes of hosting your own database mirror.
<p align="center"><em>Copyright (C) 2021 Micah Snyder.</em></p>

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

## Installation

You may install `cvdupdate` from PyPI using `pip`, or you may clone the project Git repository and use `pip` to install it locally.

Install `cvdupdate` from PyPI:

```bash
python3 -m pip install --user cvdupdate
```

## Basic Usage

Use the `--help` option with any `cvd` command to get help.

```bash
cvd --help
```

> _Tip_: You may not be able to run the `cvd` or `cvdupdate` shortcut directly if your Python Scripts directory is not in your `PATH` environment variable. If you run into this issue, and do not wish to add the Python Scripts directory to your path, you can run `cvdupdate` like this:
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

Newly downloaded databases will replace the previous database version, but the CDIFF patch files will accumulate up to a configured maximum before it starts deleting old CDIFFs (default: 30 CDIFFs). You can configure it to keep more CDIFFs by manually editing the config (default: `~/.cvdupdate/config.json`). The same behavior applies for cvdupdate log rotation.

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

## Optional Functionality

DNS is required for `cvdupdate` to function properly (to gather the TXT record containing the current definition database version). You can select a specific nameserver to ensure said nameserver is used when querying the TXT record containing the current database definition version available

1. Set the nameserver in the config. Eg:

   ```bash
   cvd config set --nameserver 208.67.222.222
   ```

2. Set the environment variable `CVDUPDATE_NAMESERVER`. Eg:

   ```bash
   CVDUPDATE_NAMESERVER="208.67.222.222" cvd update
   ```

The environment variable will take precedence over the nameserver config setting.

## Files and directories created by cvdupdate

This tool is to creates the following directories:
 - `~/.cvdupdate`
 - `~/.cvdupdate/logs`
 - `~/.cvdupdate/databases`

This tool creates the following files:
 - `~/.cvdupdate/config.json`
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

### Serve it up, Test out FreshClam

Test out your mirror with FreshClam on the same computer.

This tool includes a `--serve` feature that will host the current database directory on http://localhost (default port: 8000).

You can test it by running `freshclam` or `freshclam.exe` locally, where you've configured `freshclam.conf` with:

```
DatabaseMirror http://localhost:8000
```

## Contribute

We'd love your help. There are many ways to contribute!

### Community

Join the ClamAV community on the [ClamAV Discord chat server](https://discord.gg/sGaxA5Q).

### Report issues

If you find an issue with cvdupdate or the cvdupdate documentation, please submit an issue to our [GitHub issue tracker](https://github.com/micahsnyder/cvdupdate/issues).  Before you submit, please check to if someone else has already reported the issue.

### Development

If you find a bug and you're able to craft a fix yourself, consider submitting the fix in a [pull request](https://github.com/micahsnyder/cvdupdate/pulls). Your help will be greatly appreciated.

If you want to contribute to the project and don't have anything specific in mind, please check out our [issue tracker](https://github.com/micahsnyder/cvdupdate/issues).  Perhaps you'll be able to fix a bug or add a cool new feature.

_By submitting a contribution to the project, you acknowledge and agree to assign Cisco Systems, Inc the copyright for the contribution. If you submit a significant contribution such as a new feature or capability or a large amount of code, you may be asked to sign a contributors license agreement comfirming that Cisco will have copyright license and patent license and that you are authorized to contribute the code._

#### Development Set-up

The following steps are intended to help users that wish to contribute to development of the cvdupdate project get started.

1. Create a fork of the [cvdupdate git repository](https://github.com/micahsnyder/cvdupdate), and then clone your fork to a local directory.

    For example:

    ```bash
    git clone https://github.com/<your username>/cvdupdate.git
    ```

2. Make sure cvdupdate is not already installed.  If it is, remove it.

    ```bash
    python3 -m pip uninstall cvdupdate
    ```

3. Use pip to install cvdupdate in "edit" mode.

    ```bash
    python3 -m pip install -e --user ./cvdupdate
    ```

Once installed in "edit" mode, any changes you make to your clone of the cvdupdate code will be immediately usable simply by running the `cvdupdate` / `cvd` commands.

### Conduct

This project has not selected a specific Code-of-Conduct document at this time. However, contributors are expected to behave in professional and respectful manner. Disrespectful or inappropriate behavior will not be tolerated.

## License

cvdupdate is licensed under the Apache License, Version 2.0 (the "License"). You may not use the cvdupdate project except in compliance with the License.

A copy of the license is located [here](LICENSE), and is also available online at [apache.org](http://www.apache.org/licenses/LICENSE-2.0).

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
