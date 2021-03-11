# Notable Changes

Changes in this document should be grouped per release using the following types:

- Added
- Changed
- Deprecated
- Removed
- Fixed
- Security

## Version 0.3.0

### Added

- `cvd update` will now retry up to 3x if the downloaded content length is
  less than the content-length in the response header. This is to resolve
  issues with flakey connections.

- `cvd update` now has a `--debug-mode` (`-D`) option to print out the HTTP
  headers to debug issues with the update process.

- The update process will now save the DNS TXT record containing version
  metadata as `dns.txt` in the database directory so it may be served by the
  private mirror.

  Some common check scripts (on clients) use `dns.txt` to check if ClamAV is up
  to date instead of using DNS or the HTTP CVD-header check.

### Changed

- CVDUpdate will now have a unique User-Agent: `CVDUPDATE/<version> (<UUID>)`

  The UUID is randomly generated, and will help with anonymous usage metrics.

### Fixed

- Fixed a couple issues with the `cvd update <specific database>` option.

## Version 0.2.0

### Added

- Two ways to set a custom DNS nameserver.
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

### Fixed

- Error handling so `dns update` fails if a DNS query fails.

### Acknowledgements

Special thanks to Michael Callahan for adding the custom nameserver feature.

## Version 0.1.0

First release!
