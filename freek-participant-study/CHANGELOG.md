# Changelog

## Unreleased

### Per-link reward eligibility

- Added registry-backed reward eligibility to the ACL participant app.
- Production links P01–P50 now receive a plain debrief without coffee styling or
  reward controls, including links from previously generated registries.
- Added regression coverage for eligible and reward-free submitted sessions.

### Participant rewards

- Added the Checkpoint 1 provider-neutral reward contract and deterministic
  local fake provider.
- Added an optional fake coffee-reward demonstration to the submitted-session
  debrief page, disabled by default and incapable of external API calls.
- Added a separate atomic reward ledger with pseudonymous participant
  references, durable claim recovery, explicit eligibility enforcement, and
  one-claim behaviour across refreshes, restarts, and concurrent tabs.
- Added a sandbox-only Tremendous adapter for idempotent Dutch EUR link rewards,
  including strict `TEST_` credential validation, safe API errors, and rejection
  of non-sandbox destinations.
- Added Tremendous's required generic `Deelnemer` recipient object to link
  orders without disclosing participant contact or research data.
- Added the Checkpoint 4 voluntary accept/decline experience, persistent
  opt-out state, reversible reconsideration, clearer privacy wording, and a
  status-aware external Tremendous handoff.
- Added Checkpoint 5 timeout reconciliation by deterministic external order ID,
  interrupted-claim recovery, participant-safe failure states, and retryable
  link generation.
- Stopped persisting Tremendous redemption URLs and added an atomic migration
  that scrubs URLs from existing reward ledgers.
- Added the Checkpoint 6 authenticated reward-operations dashboard with scoped
  delivery metrics, failed/stuck warnings, issued-value tracking, and a
  privacy-safe reconciliation export.
- Added Checkpoint 7 atomic reward-count and EUR budget limits, participant-safe
  exhaustion handling, and remaining-capacity metrics in the admin dashboard.
- Added the Checkpoint 8 persistent operator kill switch for pausing new reward
  issuance without affecting existing claims, with atomic fail-closed controls
  and participant-safe paused messaging.
- Added Checkpoint 9 manual Tremendous delivery-status reconciliation, persisted
  provider status/check timestamps, delivery-health metrics, and audit export
  fields without treating active links as proof of redemption.
- Added the Checkpoint 10 offline sandbox-pilot preflight in the authenticated
  dashboard and CLI, covering admin protection, kill-switch state, capacity,
  claim health, and reconciliation freshness without exposing credentials.

### ACL-1

- Expanded the unlocked stimulus bank from 90 to 120 jokes by adding five
  transcript-derived topics across all six conditions. The original 90 items
  remain unchanged.
- Redesigned each 20-item assignment to cover every topic exactly once. The six
  conditions rotate in maximally balanced 4/4/3/3/3/3 allocations.

- Expanded the locked assignment schedule to 50 production participants. Each
  participant rates 20 unique jokes and sees all 20 topics exactly once.
- Added a preregistered recruitment range of 25 to 50 valid participants, with
  a target of 40 and stopping independent of observed outcomes.
- Replaced the locked stimulus contents with all 120 jokes from the final
  `acl_3x2_prompt_engineering_a7e5ec5` registry generated on 2026-08-08,
  while preserving every participant/test URL and its precomputed item order.
- Replaced the pilot grouped-variant interface with individual blinded jokes.
- Added the locked 90-item `gpt-5.6-terra` stimulus bank.
- Added cyclic balancing across topics, conditions, items, and recruitment
  prefixes.
- Added four required ratings: funniness, Freek resemblance, coherence, and
  originality.
- Added item-level autosave, resume, review, submission, exports, and admin
  summaries.
- Added private generation of 50 participant URLs and a versioned export schema.

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
