# Notable Changes

> _Note_: Changes should be grouped by release and use these icons:
> - Added: ➕
> - Changed: 🌌
> - Deprecated: 👇
> - Removed: ❌
> - Fixed: 🐛
> - Security: 🛡

## Version 1.0.1

🐛 Fixed a bug where the CVD-Update PyPI package version check prints an
  error message on some systems where `pip` doesn't return the available
  package versions.

## Version 1.0.0

➕ Added a check to make sure that version check for the daily, main, and
  bytecode databases are done using DNS when downloading from
  `database.clamav.net`.

  CVD-Update, like FreshClam, is capable of checking with an HTTP Range request
  which only downloads the CVD header to check the version. This doesn't use
  much data, but the CDN does not appear to differentiate between whole and
  partial downloads for tracking download activity.

  The requirement to use DNS for the version check is to reduce CDN costs and
  should reduce the chance that the user is rate-limited or blocked by the CDN
  for downloading these files too frequently.

➕ Added a PyPI package version check when running `cvd update` to encourage
  users to update when there is a new version.

🐛 CVD-Update now requires dnspython version 2.1.0 or newer. This fixes
  compatibility issues with older dnspython versions.
  Special thanks to Byron Collins for this fix.

🐛 Added explicit timeout for the DNS resolver. This fixes a DNS query issue
  on some systems.
  Special thanks to Colin Tilley for this fix.

🐛 Fixed a bug when pruning older CDIFFs where the CDIFF files were already
  removed by the user.

## Version 0.3.0

➕ `cvd update` will now retry up to 3x if the downloaded content length is
  less than the content-length in the response header. This is to resolve
  issues with flakey connections.

➕ `cvd update` now has a `--debug-mode` (`-D`) option to print out the HTTP
  headers to debug issues with the update process.

➕ The update process will now save the DNS TXT record containing version
  metadata as `dns.txt` in the database directory so it may be served by the
  private mirror.

  Some common check scripts (on clients) use `dns.txt` to check if ClamAV is up
  to date instead of using DNS or the HTTP CVD-header check.

🌌 CVDUpdate will now have a unique User-Agent: `CVDUPDATE/<version> (<UUID>)`

  The UUID is randomly generated, and will help with anonymous usage metrics.

🐛 Fixed a couple issues with the `cvd update <specific database>` option.

## Version 0.2.0

### Added

➕ Two ways to set a custom DNS nameserver.
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

🐛 Error handling so `dns update` fails if a DNS query fails.

### Acknowledgements

Special thanks to Michael Callahan for adding the custom nameserver feature.

## Version 0.1.0

First release!
