# Changelog

## Unreleased

### Participant rewards

- Added the Checkpoint 1 provider-neutral reward contract and deterministic
  local fake provider.
- Added an optional fake coffee-reward demonstration to the submitted-session
  debrief page, disabled by default and incapable of external API calls.
- Added a separate atomic reward ledger with pseudonymous participant
  references, durable claim recovery, explicit eligibility enforcement, and
  one-claim behaviour across refreshes, restarts, and concurrent tabs.
- Added a sandbox-only Tremendous adapter for idempotent Dutch EUR link rewards,
  including strict `TEST_` credential validation, safe API errors, persisted
  redemption links, and rejection of non-sandbox destinations.

### ACL-1

- Replaced the pilot grouped-variant interface with 12 individual blinded jokes.
- Added the locked 90-item `gpt-5.6-terra` stimulus bank.
- Added exact balancing for 25 participants across topics, conditions, items,
  and presentation positions.
- Added four required ratings: funniness, Freek resemblance, coherence, and
  originality.
- Added item-level autosave, resume, review, submission, exports, and admin
  summaries.
- Added private generation of 25 participant URLs and a versioned export schema.

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
