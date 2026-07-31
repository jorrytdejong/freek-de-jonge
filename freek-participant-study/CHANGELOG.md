# Changelog

## Unreleased

### Added

- Durable private Google Sheets progress storage with bounded exponential retry.
- Idempotent recovery when an append succeeds but its API response is lost.
- Runtime selection between local CSV and production Google Sheets storage.
- Secret-backed production session registries for the public repository.
- Balanced generation of 40 private real-participant links.
- Raw progress backup tooling and production operations documentation.

### Verification Pending

- Connect separate staging and production Google Sheets credentials.
- Complete the final two-to-three-person pilot and reboot-resume test.
- Reconcile the repository production branch and create the
  `freek-study-pilot-1` release tag after acceptance.
