# Notable Changes

Changes in this document should be grouped per release using the following types:

- Added
- Changed
- Deprecated
- Removed
- Fixed
- Security

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
