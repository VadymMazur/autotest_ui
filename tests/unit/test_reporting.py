"""Ensure report evidence cannot claim a complete run on partial or failed checks."""

from contextlib import contextmanager

import pytest

from crm_e2e.reporting import VerificationReport, report_step


def test_failed_check_remains_failed_even_when_body_and_cleanup_finish():
    report = VerificationReport("synthetic", "https://example.test", "chromium")
    with pytest.raises(AssertionError):
        report.equal("API", "HTTP status", 400, 201)
    report.body_completed = report.cleanup_completed = True
    assert not report.complete
    assert report.checks[0].status == "failed"
    assert report.checks[0].actual == "400"
    assert "0 із 1" in report.render_html()


def test_passed_assertions_do_not_hide_missing_or_failed_cleanup():
    report = VerificationReport("synthetic", "https://example.test", "chromium")
    report.equal("API", "HTTP status", 201, 201)
    report.body_completed = True
    assert not report.complete
    report.record_cleanup([
        {"resource": "leads", "method": "DELETE", "status": 403, "expected_status": 204},
    ], completed=False)
    assert not report.complete
    assert report.checks[-1].status == "failed"
    assert report.checks[-1].actual == "HTTP 403"


def test_report_escapes_values_in_html():
    report = VerificationReport("synthetic", "https://example.test", "chromium")
    value = '<script>alert("synthetic")</script>'
    report.equal("API", "Notes", value, value)
    rendered = report.render_html()
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_step_removes_page_snapshot_before_allure_observes_failure(monkeypatch):
    recorded = []

    @contextmanager
    def capture_step(title):
        try:
            yield
        except AssertionError as error:
            recorded.append(str(error))
            raise

    monkeypatch.setattr("crm_e2e.reporting.allure.step", capture_step)
    with pytest.raises(AssertionError):
        with report_step("Synthetic failing UI check"):
            raise AssertionError("Locator did not match.\nAria snapshot:\nprivate unrelated account")
    assert "Locator did not match." in recorded[0]
    assert "private unrelated account" not in recorded[0]
