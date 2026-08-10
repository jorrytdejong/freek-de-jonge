# Freek Participant Study — ACL Experiment

Dutch Streamlit application for the blinded `acl-1` humor-generation study.

## Locked design

- 120 accepted `gpt-5.6-terra` jokes: 20 topics × 6 conditions.
- Conditions: baseline, script opposition, and validated GTVH, each with Freek
  style guidance off and on.
- Every participant rates 20 unique jokes: exactly one from each topic.
- Every participant sees four jokes from two conditions and three jokes from
  each of the other four conditions; the larger condition slots rotate.
- A single precomputed registry supports recruitment from 25 up to 50 valid
  participants; every six-person block rotates all conditions over every topic.
- Every joke receives four required 1–5 ratings: funniness, Freek-style
  resemblance, coherence, and originality.
- Expected duration: approximately 7–9 minutes.

The old `pilot-1` modules and CSV files remain in the repository for historical
reproducibility. The deployed `streamlit_app.py` uses only the `app/acl_*`
modules and `data/acl_*` files.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
streamlit run streamlit_app.py
```

Example test link:

<http://localhost:8501/?session=acl-test-01-d4df9936>

### Fake participant reward

Checkpoint 1 includes an optional local-only reward demonstration. Enable it
when starting the app:

```bash
FREEK_STUDY_REWARDS_ENABLED=true \
FREEK_STUDY_REWARD_MODE=fake \
FREEK_STUDY_REWARD_AMOUNT_EUR=3.40 \
FREEK_STUDY_REWARD_LEDGER_PATH=data/runtime/acl_rewards.csv \
streamlit run streamlit_app.py
```

After a test submission, the debrief page shows a fake coffee-reward button.
It never calls Tremendous, requests payment details, or transfers money. Reward
configuration is disabled by default. Issued fake claims are kept in the
separate ignored `data/runtime/acl_rewards.csv` ledger. The ledger contains a
one-way participant reference and operational reward metadata, but no raw
session ID, survey answer, email address, or bank-account information. Reopening
the submitted participant link restores the same claim; repeated clicks and
concurrent tabs cannot issue another one.

### Tremendous sandbox reward

Checkpoint 3 can replace the local fake provider with Tremendous's test
environment. Create a separate account at
<https://app.testflight.tremendous.com>, configure a campaign, and create a
read/write API key under **Team Settings → Developers**. Sandbox keys must start
with `TEST_`; the application rejects `PROD_` keys and has no production API
endpoint.

For local testing, set:

```bash
FREEK_STUDY_REWARDS_ENABLED=true \
FREEK_STUDY_REWARD_MODE=tremendous_sandbox \
FREEK_STUDY_REWARD_AMOUNT_EUR=3.40 \
FREEK_STUDY_REWARD_MAX_ISSUED=25 \
FREEK_STUDY_REWARD_BUDGET_EUR=85.00 \
FREEK_STUDY_REWARD_LEDGER_PATH=data/runtime/acl_rewards_sandbox.csv \
TREMENDOUS_API_KEY=TEST_your_key \
TREMENDOUS_CAMPAIGN_ID=your_campaign_id \
TREMENDOUS_FUNDING_SOURCE_ID=BALANCE \
streamlit run streamlit_app.py
```

Use a separate sandbox ledger path so an already-issued local fake claim cannot
be confused with a Tremendous sandbox claim. After submission, the app creates
an idempotent `LINK` reward and displays the sandbox redemption button. The
participant enters any redemption details on Tremendous, not in the research
app. The API order uses only the generic required recipient name `Deelnemer`;
it sends no participant email, phone number, session ID, or survey data. API
keys are never stored in the reward ledger or displayed in errors.

The equivalent Streamlit secrets are:

```toml
rewards_enabled = true
reward_mode = "tremendous_sandbox"
reward_amount_eur = "3.40"
reward_max_issued = 25
reward_budget_eur = "85.00"
reward_ledger_path = "data/runtime/acl_rewards_sandbox.csv"

[tremendous]
api_key = "TEST_your_key"
campaign_id = "your_campaign_id"
funding_source_id = "BALANCE"
```

### Participant reward choice

Checkpoint 4 presents the reward as a separate, voluntary decision after the
research submission is final. Participants can accept the test reward or choose
`Geen testvergoeding, bedankt`. A decline is stored only in the separate reward
ledger and can be reversed with `Toch een testvergoeding ontvangen`; it never
changes the submitted answers.

After acceptance, the debrief links to Tremendous in a separate page. Tremendous
collects any details needed for the participant's selected payout method. The
research app does not collect those details. Reopening an already-used link
shows Tremendous's current payout status, while reopening the study link restores
the same reward decision.

Reward visibility can also be fixed per participant link through the private
session registry's `reward_eligible` column. The production builder marks P01–P10
as `false` and P11–P50 as `true`. A reward-free participant receives the same
study and plain debrief, but no coffee background, reward text, or reward controls.
Eligibility is resolved from the registered session ID and cannot be enabled with
a query-string change. Older registries without the column remain compatible and
default to eligible.

### Reward recovery

Checkpoint 5 makes sandbox issuance safe to retry. If an order request times out
or returns a temporary server error, the app looks up the deterministic external
order ID before allowing another attempt. This recovers orders whose response was
lost without creating a second reward. Interrupted `issuing` records can likewise
resume with the same ID.

The participant sees separate, non-sensitive messages for insufficient sandbox
funding, rejected configuration, temporary unavailability, and an uncertain
order status. An issued reward remains recorded even if its link cannot currently
be opened, and the debrief provides a link retry action.

Redemption URLs are treated as short-lived bearer secrets: they are not stored in
the reward ledger. The app retains only the Tremendous reward ID and asks
Tremendous for a fresh link when the submitted study page is reopened. On startup,
legacy ledgers containing a `redemption_url` column are atomically rewritten
without that column or its values.

### Reward operations

Checkpoint 6 adds reward-delivery monitoring to the password-protected
`?admin=1` dashboard. The reward section has its own real/test/all selector,
defaulting to all reward records, and reports choices, issued rewards, declines,
failures, in-progress claims, issued value, and claims stuck in `issuing` for at
least ten minutes. Failed and stuck records produce an explicit operator warning.

The authenticated dashboard also offers `reward_operations.csv` for audit and
reconciliation. This export is deliberately separate from research responses:
it contains pseudonymous reward references and provider IDs, but no raw session
IDs, participant contact details, survey answers, or redemption URLs. Checkpoint
6 remains sandbox-only and does not enable production payments.

### Launch limits

Checkpoint 7 adds two atomic hard stops before any provider request:

- `FREEK_STUDY_REWARD_MAX_ISSUED` / `reward_max_issued` limits the combined
  number of issued and currently issuing rewards (default: 25).
- `FREEK_STUDY_REWARD_BUDGET_EUR` / `reward_budget_eur` limits their combined
  value (default: €85.00, or 25 × €3.40).

Retries for the same participant do not reserve a second slot, and previously
issued rewards remain accessible after a limit is reached. Failed and declined
records do not consume capacity. When a hard stop is reached, the participant
gets a neutral message and Tremendous is not called. The authenticated reward
dashboard shows remaining claims and remaining budget.

The CSV ledger lock is process-local. Run one Streamlit application process for
this pilot; use a transactional shared database before deploying multiple app
replicas. Checkpoint 7 still uses Tremendous Testflight only and deliberately
does not accept production API keys.

### Emergency pause

Checkpoint 8 adds a persistent issuance kill switch to the authenticated reward
dashboard. While issuance is active, an explicit confirmation checkbox enables
`Nieuwe uitgifte pauzeren`. Once paused, the dashboard displays a prominent
warning and offers `Nieuwe uitgifte hervatten`.

The state is atomically stored beside the ignored reward ledger in
`*.csv.control.json`. A pause is checked under the same process lock immediately
before reserving a reward, so Tremendous is not called for a newly blocked claim.
Existing issued rewards remain accessible and declines remain possible. A
participant without an issued reward sees a neutral message inviting them to
reopen the page later. Missing control state defaults to active; corrupt or
unreadable control state fails closed instead of issuing rewards.

Use the pause before maintenance, credential rotation, campaign changes, or an
unexpected delivery incident. Checkpoint 8 remains sandbox-only.

### Tremendous reconciliation

Checkpoint 9 adds a manual `Tremendous-bezorgstatussen vernieuwen` action to the
authenticated reward dashboard. It retrieves each issued sandbox reward by its
provider reward ID, stores the current delivery status and check timestamp, and
adds both fields to `reward_operations.csv`. One failed lookup does not prevent
the remaining rewards from being checked.

The dashboard distinguishes `SUCCEEDED`, `FAILED`, and not-yet-checked rewards.
For a Tremendous `LINK` reward, `SUCCEEDED` means the link is active; it does
**not** prove that the participant selected or completed a payout. The interface
therefore labels this as a delivery status rather than a redemption or payment
status. Refreshing is read-only at Tremendous and never creates, resends, or
cancels a reward.

Older ledgers are atomically migrated with blank provider status fields on app
startup. Checkpoint 9 continues to use only the Testflight API.

### Pilot preflight

Checkpoint 10 adds the final offline release gate to the authenticated dashboard
and as a command-line check:

```bash
python scripts/reward_preflight.py
```

The command exits successfully only when rewards are enabled in Testflight mode,
the admin password exists, issuance is active, capacity remains, no failed or
stuck claims exist, no provider delivery is marked `FAILED`, and all issued
rewards were reconciled within the previous 24 hours. It reads only local
configuration and ledgers, makes no Tremendous request, and never prints API
keys or other secret values.

The dashboard presents the same checks under `Checkpoint 10 · pilot-preflight`.
At Checkpoint 10 this was a sandbox-pilot readiness signal, not authorization
for real payments, and the CLI always reported `PRODUCTION PAYMENTS: disabled`.

### Guarded production capability

Checkpoint 11 adds the production Tremendous adapter but does **not** activate
it. The production provider is pinned to `https://api.tremendous.com/api/v2`
and accepts only `PROD_` API keys. Sandbox continues to accept only `TEST_`
keys, so credentials cannot silently cross environments.

Real rewards require every one of these independent controls:

- `FREEK_STUDY_REWARD_MODE=tremendous_production`
- `FREEK_STUDY_DEPLOYMENT_ENVIRONMENT=production`
- `FREEK_STUDY_REAL_REWARDS_ACK=I_UNDERSTAND_THIS_SENDS_REAL_MONEY`
- a separate ledger path whose name does not contain `sandbox`
- complete production campaign, funding-source, and API-key values
- enabled rewards, an active kill switch, remaining count/budget capacity, and a
  passing production preflight

The service rejects test participants before creating a ledger record or making
a provider call. Checkpoint 11 tests the production adapter with an in-memory
transport only; no production credentials are stored and no real reward is sent.

### One-participant production canary

Checkpoint 12 narrows the production path to one deliberately authorized
participant and one €3.40 reward. Production configuration is rejected unless
the maximum issued count is `1`, the total budget equals the reward amount, the
canary switch is explicitly enabled, and exactly one valid pseudonymous reward
reference is configured. Every test participant and every real participant not
on that allowlist is stopped before the ledger is written or Tremendous is
called.

Generate the reference from the chosen private production session ID without
putting that raw ID in the reward ledger:

```bash
python scripts/reward_reference.py PRIVATE_SESSION_ID
```

Then add these settings alongside the Checkpoint 11 production gates:

```text
FREEK_STUDY_REWARD_MAX_ISSUED=1
FREEK_STUDY_REWARD_BUDGET_EUR=3.40
FREEK_STUDY_PRODUCTION_CANARY_ENABLED=true
FREEK_STUDY_PRODUCTION_CANARY_REWARD_REFERENCE=reward-...generated value...
```

The authenticated dashboard reports the canary gate without displaying the
allowlisted reference. The local environment remains on Testflight, so
Checkpoint 12 does not create a real order or activate production credentials.

Internal-only routes:

- Stimulus preview: <http://localhost:8501/?preview=1>
- Administration: <http://localhost:8501/?admin=1>

## Test links

1. `?session=acl-test-01-d4df9936`
2. `?session=acl-test-02-51509e02`
3. `?session=acl-test-03-2a523785`
4. `?session=acl-test-04-7dbcde52`
5. `?session=acl-test-05-40f33984`
6. `?session=acl-test-06-9a03d107`
7. `?session=acl-test-07-0f91cf5e`
8. `?session=acl-test-08-42b9cc91`
9. `?session=acl-test-09-48dc81b7`
10. `?session=acl-test-10-03614420`

## Validation

Run the same gate used for release acceptance:

```bash
python scripts/run_quality_gate.py
```

It validates formatting, linting, compilation, the 120-item bank, both test
registries, the mathematical assignment constraints, all unit and Streamlit
flow tests, and a process-level HTTP startup check.

## Data and exports

Local ACL progress is written to the ignored
`data/runtime/acl_progress.csv`. Generate validated analysis tables with:

```bash
python scripts/export_results.py
```

Outputs are written to `data/runtime/acl_exports/`. See
[`EXPORT_SCHEMA.md`](EXPORT_SCHEMA.md) for the exact columns.

Real participant tokens and URL files belong in the ignored `data/private/`
directory. See [`PRODUCTION.md`](PRODUCTION.md) before generating or deploying
them.
