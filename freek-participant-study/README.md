# Freek Participant Study — ACL Experiment

Dutch Streamlit application for the blinded `acl-1` humor-generation study.

## Locked design

- 90 accepted `gpt-5.6-terra` jokes: 15 topics × 6 conditions.
- Conditions: baseline, script opposition, and validated GTVH, each with Freek
  style guidance off and on.
- Every participant rates 12 jokes from 12 different topics.
- Every participant sees exactly two jokes from each condition.
- Every joke receives four required 1–5 ratings: funniness, Freek-style
  resemblance, coherence, and originality.
- Expected duration: approximately 10 minutes.

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

<http://localhost:8501/?session=acl-test-01-913a93e2>

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

Internal-only routes:

- Stimulus preview: <http://localhost:8501/?preview=1>
- Administration: <http://localhost:8501/?admin=1>

## Test links

1. `?session=acl-test-01-913a93e2`
2. `?session=acl-test-02-979d4f77`
3. `?session=acl-test-03-38452f51`
4. `?session=acl-test-04-cb9df523`
5. `?session=acl-test-05-d63af247`
6. `?session=acl-test-06-7227edfd`
7. `?session=acl-test-07-b5a26fc2`
8. `?session=acl-test-08-8c0b1676`
9. `?session=acl-test-09-030dcad5`
10. `?session=acl-test-10-86726b66`

## Validation

Run the same gate used for release acceptance:

```bash
python scripts/run_quality_gate.py
```

It validates formatting, linting, compilation, the 90-item bank, both test
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
