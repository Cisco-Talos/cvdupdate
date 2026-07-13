# Notable Changes

> _Note_: Changes should be grouped by release and use these icons:
> - Added: ➕
> - Changed: 🌌
> - Deprecated: 👇
> - Removed: ❌
> - Fixed: 🐛
> - Security: 🛡

## Version 1.3.1

- 🐛 Fixed signature download behavior for mirrored databases with custom local
  names: the remote `.sign` filename is now derived from the origin URL, while
  the downloaded signature is still saved locally as `<local-db-name>.sign`.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/92)

- 🐛 Added regression tests to verify origin-name vs local-name signature
  handling, with mocked HTTP and a socket-level guard to ensure tests do not
  perform real network connections.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/92)

- 🐛 Fixed cleanup so pruning an old `.cdiff` or removing a database also
  deletes its matching `.sign` file, keeping rotated files fully removed from
  the mirror.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/92)

## Version 1.3.0

- ➕ Added a `cvd status` command (alias `s`) that reports the status of all
  databases, or of a single database when given a name. Pass `--json` for
  machine-readable output. The `cvd list` command (alias `ls`) now prints just
  the database names — one per line, or a JSON array with `--json` — to make
  its output easy to parse.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/88)

- ➕ Added a `--override` flag to `cvd add` so the remote URL of an existing
  database can be updated without removing and re-adding it.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/88)

- ➕ The `cvd config set` command now exposes every configuration option, with
  names normalized to a consistent style (e.g. `--logs-directory`,
  `--dbs-directory`, `--nameservers`, `--logs-enabled`, `--max-retries`,
  `--state-file`). Short aliases are now available for the common commands:
  `status (s)`, `update (u)`, `list (ls)`, `remove (rm)`, `config (cf)`, and
  `clean (cl)`.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/88)

- 🌌 File logging is now opt-in. New installations no longer write log files
  unless logging is enabled with `cvd config set --logs-enabled`, which keeps
  output quiet for container and systemd usage. Existing v1.2 and older
  configurations that specified a log directory are migrated with logging
  left enabled.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/88)

- ➕ `cvd serve` now accepts port `0`, which lets the OS assign a random free
  port; the chosen port is logged after binding. The default port is unchanged
  (`8000`).

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/88)

- 🛡 The `cvd serve` test mirror now hides dot-prefixed files and directories,
  so hidden files (such as a `.state.json` state file) aren't exposed when
  serving the database directory.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/88)

- 👇 Deprecated the `show` command in favor of `status`; the `--logdir`,
  `--dbdir`, and `--nameserver` options of `config set` in favor of
  `--logs-directory`, `--dbs-directory`, and `--nameservers`; and the
  `CVDUPDATE_NAMESERVER` environment variable in favor of
  `CVDUPDATE_NAMESERVERS`. The deprecated names continue to work, with a
  warning, and will be removed in a future release.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/88)

## Version 1.2.0

- ➕ Support for downloading CVD and CDIFF digital signatures.

  ClamAV 1.5.0 introduced a feature to verify the authenticity of CVD signature
  archives and CDIFF signature archive patch files with an external digital
  signature in support of using ClamAV within FIPS-enabled environments.

  CVD Update will now download the `.sign` files to accompany each `.cvd` and
  `.cdiff` file.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/72)

- 🛡 Migrate from unmaintained "coloredlogs" dependency to "colorlog".
  Work courtesy of Joel Esler.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/71)

- 🌌 Improve the `cvdupdate` package version check to support alternative
  package distributions and to enable signature updates even if the version
  check fails.
  Work courtesy of Joel Esler.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/73)

## Version 1.1.3

- 🐛 Fixed CVD-Update version check in PyPI package repository on startup.
  Work courtesy of Steve Mays.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/67)

- 🌌 Info-level and Debug-level messages will now go to stdout instead of
  stderr.
  Work courtesy of GitHub user backbord.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/65)

## Version 1.1.2

- ➕ Added a Docker Compose file to make it easier to host a private mirror.
  The Docker Compose environment runs two containers:
  1. CVD-Update.
  2. An Apache webserver to host the private mirror.

  Improvement courtesy of Mark Petersen.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/61)

- 🐛 Fixed the CVD-Update Python package so it installs the `setuptools`
  dependency. This fixes a runtime error on some systems.
  Fix courtesy of Craig Andrews.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/59)

- 🐛 Added missing documentation for `cvd add` command to the Readme.
  Fix courtesy of Kim Oliver Drechsel.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/58)

- ➕ Added retries in case the DNS TXT query fails.
  Fix courtesy of backbord.

  [GitHub Pull-Request](https://github.com/Cisco-Talos/cvdupdate/pull/50)

## Version 1.1.1

- 🐛 Fixed an issue where the `.cdiff` files were only downloaded when updating
  a `.cvd` and not when downloading the `.cvd` for the first time.

- 🐛 Fixed an issue where `cvd update` crashes if the DNS query fails, rather
  than printing a helpful error message and exiting.

- 🐛 Fixed support for CVD Update on Windows 🪟. In prior versions, the DNS
  query was failing if a DNS server was not specified manually. Now it will try
  OpenDNS servers if no DNS server is specified.

- ➕ Added Python dependencies to the Readme to help users that are unable to
  install using `pip`.

## Version 1.1.0

- ➕ CVD-Update can now get the DNS nameserver IP from an environment variable.

  Specify the IP address of the nameserver in the environment variable
  `CVDUPDATE_NAMESERVER` to ensure said nameserver is used when querying the
  TXT record containing the current database definition version available.

  Using this environment variable will take precedence over any option specified
  in the config file.

  Feature courtesy of Philippe Ballandras.

- ➕ CVD-Update can now accept multiple DNS nameservers from the `nameserver`
  config option, or from the `CVDUPDATE_NAMESERVER` environment variable.

  To set multiple DNS nameservers, specify the `nameserver` config option or the
  `CVDUPDATE_NAMESERVER` environment variable as a comma separated list.

  E.g.:
  ```bash
  CVDUPDATE_NAMESERVER=1.1.1.1,8.8.8.8 cvd update
  ```

  Feature courtesy of Michael Callahan.

- 🐛 In prior versions, CVD-Update would assume that a CVD file exists because
  it is listed in the `config.json` "dbs" record. So if you delete that file by
  accident and try to update, it would not notice and would instead claim that
  it is up-to-date. In this release, CVD-Update will detect that a deleted file
  is missing from the database directory and will re-download it.

  Fix courtesy of Brent Clark.

- - 🌌 CVD-Update will no longer remove extra files from the database directory
  when you run `cvd clean dbs`. It will only remove those file managed by the
  CVD-Update tool.

  This means that you can now store third-party extra signature databases in the
  CVD-Update database directory and CVD-Update will not delete them if you run
  the clean command.

  Improvement courtesy of Brent Clark.

- 🌌 CVD-Update now stores the database state information separately from the
  configuration information. If you're upgrading from CVD-Update version 1.0.2,
  your `config.json` file will be migrated automatatically when you run
  `cvd update` to split it into `config.json` + `state.json`.

  This change allows you to administrate the CVD-Update config files with a
  config management tool.

  Improvement courtesy of Bill Sanders.

Special thanks to:
- Bill Sanders
- Brent Clark
- Michael Callahan
- Philippe Ballandras

## Version 1.0.2

- 🐛 Fixed a Python 3.6 compatibility issue in the package version check.

## Version 1.0.1

- 🐛 Fixed a bug where the CVD-Update PyPI package version check prints an
  error message on some systems where `pip` doesn't return the available
  package versions.

## Version 1.0.0

- ➕ Added a check to make sure that version check for the daily, main, and
  bytecode databases are done using DNS when downloading from
  `database.clamav.net`.

  CVD-Update, like FreshClam, is capable of checking with an HTTP Range request
  which only downloads the CVD header to check the version. This doesn't use
  much data, but the CDN does not appear to differentiate between whole and
  partial downloads for tracking download activity.

  The requirement to use DNS for the version check is to reduce CDN costs and
  should reduce the chance that the user is rate-limited or blocked by the CDN
  for downloading these files too frequently.

- ➕ Added a PyPI package version check when running `cvd update` to encourage
  users to update when there is a new version.

- 🐛 CVD-Update now requires dnspython version 2.1.0 or newer. This fixes
  compatibility issues with older dnspython versions.
  Special thanks to Byron Collins for this fix.

- 🐛 Added explicit timeout for the DNS resolver. This fixes a DNS query issue
  on some systems.
  Special thanks to Colin Tilley for this fix.

- 🐛 Fixed a bug when pruning older CDIFFs where the CDIFF files were already
  removed by the user.

## Version 0.3.0

- ➕ `cvd update` will now retry up to 3x if the downloaded content length is
  less than the content-length in the response header. This is to resolve
  issues with flakey connections.

- ➕ `cvd update` now has a `--debug-mode` (`-D`) option to print out the HTTP
  headers to debug issues with the update process.

- ➕ The update process will now save the DNS TXT record containing version
  metadata as `dns.txt` in the database directory so it may be served by the
  private mirror.

  Some common check scripts (on clients) use `dns.txt` to check if ClamAV is up
  to date instead of using DNS or the HTTP CVD-header check.

- 🌌 CVDUpdate will now have a unique User-Agent: `CVDUPDATE/<version> (<UUID>)`

  The UUID is randomly generated, and will help with anonymous usage metrics.

- 🐛 Fixed a couple issues with the `cvd update <specific database>` option.

## Version 0.2.0

- ➕ Two ways to set a custom DNS nameserver.
  DNS queries are required to check the latest available database versions.

  1. Set the nameserver in the config. Eg:

     ```bash
     cvd config set --nameserver 208.67.222.222
     cvd update
     ```

  2. Set the environment variable `CVDUPDATE_NAMESERVER`. Eg:

     ```bash
     CVDUPDATE_NAMESERVER="208.67.222.222" cvd update
     ```

  Special thanks to Michael Callahan for this feature.

- 🐛 Error handling so `dns update` fails if a DNS query fails.

## Version 0.1.0

First release!
