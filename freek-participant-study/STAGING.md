# ACL-1 Staging Deployment

- App: <https://freek-participant-pilot.streamlit.app/>
- Admin: <https://freek-participant-pilot.streamlit.app/?admin=1>
- Test link:
  <https://freek-participant-pilot.streamlit.app/?session=acl-test-01-913a93e2>

Deploy `freek-participant-study/streamlit_app.py` with Python 3.11. Staging must
use `data/acl_sessions.staging.csv` or its exact private-secret contents and a
staging-only Google Sheet/worksheet.

Before production:

1. Run `python scripts/run_quality_gate.py` on the release commit.
2. Complete two test links on desktop and mobile.
3. Interrupt one link midway and verify all partial ratings resume.
4. Submit and reopen a test link.
5. Verify the admin dashboard reports four outcomes and six conditions.
6. Download both exports and verify 12 rating rows per complete session.
7. Confirm participant pages never reveal internal condition metadata.
8. Reboot the app and verify Google Sheets progress still resumes.
