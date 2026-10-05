# Scenario contract and limits

## E2E-LEAD-001 — Create and verify a full lead

**Purpose:** demonstrate how to verify a user journey through the UI and independently check persistence through the authenticated API.

**Prerequisites:** a compatible disposable local CRM, a synthetic account allowed to create/update/delete leads and related contacts/companies, an active workspace, and configured lead columns including stable key `in_progress`. Use the Ukrainian locale for this scenario: controls accept several English labels, but source text and currency assertions currently expect Ukrainian values.

The repository does not include a mock of the full application. Changing an arbitrary application's URL is insufficient: its routes, selectors, response schema and semantics must match the Page Objects and API helper.

| Surface | Expected contract |
|---|---|
| Authentication | `/login`, `POST /api/auth/login/` returns actor `id`; same-origin session cookie and CSRF cookie |
| Workspace/dashboard | Optional `/workspaces`, then `/`; dashboard Create menu opens the new-lead dialog |
| Status configuration | `GET /api/board-configurations/leads/` returns `columns` with `stable_key`, `label_uk`, `label_en` |
| Lead creation | `POST /api/leads/` returns HTTP 201 with lead `id`, contact/company identifiers and fields in `LeadData.expected_fields()` |
| Lead UI | `/app/leads/list` search and `/app/leads/{id}` detail/edit view |
| Persistence | `GET/PATCH /api/leads/{id}/`; amount stored as a decimal-compatible string |
| Related deals | `GET /api/leads/{id}/workspace/` provides `deals` and `pagination.deals.count` |
| Cleanup | Lead/contact/company detail routes support GET and CSRF-protected DELETE; deleted records return HTTP 404 |

## Design choices

- UI performs authentication, lead creation and amount editing. API reads provide independent persistence checks.
- A fresh browser context prevents authentication state from leaking across tests.
- UUID-based data markers distinguish each run. Email/social addresses use the reserved `example.test` domain.
- Cleanup records submission before waiting for a response and can reconcile a committed write after a browser timeout.
- Ownership checks inspect the lead and related contact/company before the first DELETE. Cleanup never bulk-deletes a collection.
- Playwright assertions and response waits handle readiness. Optional animation delays are for demonstrations only.
- Failure evidence is captured before teardown alters the page. Screenshots are never retried without privacy masks.

## What passing checks establish

Unit tests exercise configuration, guarded cleanup and report/diagnostic behavior with doubles. Browser harness tests exercise input actions and visual controls in actual Chromium on synthetic HTML. Neither proves the CRM journey passed.

The public edition's CRM journey has not been executed against a bundled application because no application is included. No private-environment results are presented as public verification.

## Known limits

This is one positive desktop Chromium scenario. It does not establish cross-browser, accessibility, performance, mobile, authorization or organization-isolation coverage. Selectors are application-specific. Screenshot masking is selective and needs review when the application changes. Cleanup failures remain visible and can leave synthetic records for manual investigation.
