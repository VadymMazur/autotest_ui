# UI Test Automation · QA Portfolio

**Python · Playwright · pytest · Page Object Model · REST API checks · Allure**

A focused automation sample by **Vadym Mazur**: one CRM lead journey, supported by reusable page objects, synthetic test data, API verification, guarded cleanup and failure diagnostics.

This is a sanitized portfolio edition. You can run the unit tests and real Chromium checks against synthetic HTML without an account or CRM server. The application itself is not included; the full CRM scenario requires a compatible disposable local application and is excluded by default.

[Manual QA portfolio](https://github.com/VadymMazur/Portfolio) · [GitHub profile](https://github.com/VadymMazur)

## What to review

| Skill | Evidence in this repository |
|---|---|
| Test design | [Lead journey](tests/test_lead_creation.py): create → edit → reload → verify → clean up |
| Maintainable UI automation | [Page Objects](crm_e2e/pages.py), role-based locators, Ukrainian/English control labels, explicit response waits |
| UI + API verification | [API helper](crm_e2e/api.py): same browser session, persisted fields, CSRF-aware cleanup |
| Test isolation | [Synthetic data factory](crm_e2e/data.py): unique marker per run; cleanup checks ownership before deletion |
| Debugging | [Failure evidence](crm_e2e/diagnostics.py): masked screenshot, failing step, last action, redacted messages |
| Honest reporting | [Verification report](crm_e2e/reporting.py): expected/actual checks; incomplete or failed cleanup prevents a success claim |
| Framework verification | [Unit tests](tests/unit) and [browser harness](tests/browser): local, repeatable checks of the automation support code |

## Run the self-contained checks

Requires **Python 3.11+**. Commands below use PowerShell; on macOS/Linux activate with `source .venv/bin/activate`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m pytest
```

The default command runs unit tests and two browser tests on synthetic HTML. It does not load CRM credentials or connect to a CRM service. Dependencies and Chromium need internet access during installation.

```powershell
# Fast checks without launching a browser
python -m pytest tests/unit

# Watch the synthetic browser checks
python -m pytest tests/browser --headed
```

## The CRM scenario

`E2E-LEAD-001` demonstrates a single positive desktop journey:

1. Sign in through the UI and select a workspace when required.
2. Read configured lead status labels through the API.
3. Create a lead with synthetic contact, company, notes and social links.
4. Verify HTTP 201, saved fields, source and assigned owner.
5. Find the lead and edit its potential amount to `125000.50`.
6. Reload and verify visible values and persisted API state.
7. Check that creating the lead did not implicitly create a deal.
8. Delete only records owned by this run and verify that they return HTTP 404.

See the [application contract and coverage limits](docs/scenario.md). This repository does **not** claim full CRM coverage. Negative login, duplicates, permissions, organization isolation, mobile browsers and lead conversion are outside this scenario.

### Optional local integration run

Use an existing compatible disposable local CRM with synthetic data and a dedicated local test account. This repository supplies neither that application nor deployment instructions. The configuration accepts only `localhost`, `127.0.0.1` or `::1` origins; no remote server is configured.

```powershell
Copy-Item .env.example .env
# Set credentials for your disposable LOCAL account in the ignored .env file.
python -m pytest -m e2e tests/test_lead_creation.py --browser chromium --alluredir=allure-results/e2e-lead-001
```

`-m e2e` explicitly overrides the default exclusion. The scenario creates and deletes synthetic lead, contact and company records. Do not point a local proxy at a real environment.

## Reports and diagnostics

Named Allure steps connect the UI action, expected value and observed result. The scenario's checks are assertion rows within **one** E2E test, not separate test cases. A report is complete only when the scenario body and cleanup both finish successfully.

With Allure CLI 2 and Java installed, generate a report from your own local results:

```powershell
allure generate allure-results/e2e-lead-001 -o allure-report/e2e-lead-001 --clean
allure open allure-report/e2e-lead-001
```

On Windows, [generate_report.ps1](scripts/generate_report.ps1) optionally adds readable table styling. Reports and screenshots remain ignored. Masking reduces accidental disclosure but is not a guarantee for an arbitrary application: review every artifact before sharing it.

The [failure capture probe](tests/probes/failure_capture_probe.py) deliberately causes failures against synthetic HTML. It is excluded from normal discovery. Run it separately only when investigating diagnostics; a nonzero exit is expected.

## Repository guide

```text
crm_e2e/          Page Objects, actions, data, API, configuration and reporting
tests/unit/      Configuration, cleanup and reporting/diagnostic checks
tests/browser/   Self-contained Chromium checks using synthetic HTML
tests/probes/    Explicit diagnostic probes with intentional failures
tests/test_lead_creation.py   Optional CRM integration journey
docs/            Scenario contract and publication scope
scripts/         Optional local report formatting
```

No private repository history, environment files, server addresses, account data, deployment runbooks or historical execution artifacts are included. See [publication scope](docs/publication.md).
