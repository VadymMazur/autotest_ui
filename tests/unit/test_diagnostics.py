"""Failure evidence must preserve the original failure and never retry unmasked."""

import json
from unittest.mock import Mock

import pytest

from crm_e2e.diagnostics import FailureEvidence, active_evidence
from crm_e2e.reporting import report_step


def page_double():
    page = Mock()
    page.is_closed.return_value = False
    page.url = "https://example.test/lead?token=private-token#private-fragment"
    page.screenshot.return_value = b"synthetic-image"
    return page


def test_nested_failure_captures_once_at_the_innermost_step(tmp_path):
    evidence = FailureEvidence(tmp_path, "own-run")
    page = page_double()
    evidence.bind(page, ("private-password",))
    token = active_evidence.set(evidence)
    try:
        with pytest.raises(AssertionError, match="bad field") as failed:
            with report_step("Create lead"):
                with report_step("Check phone"):
                    raise AssertionError("bad field private-password\nAria snapshot:\nunrelated-account")
    finally:
        active_evidence.reset(token)
    evidence.capture(failed.value)  # pytest's fallback hook sees the same exception.
    assert page.screenshot.call_count == 1
    assert evidence.records[0]["step_path"] == ["Create lead", "Check phone"]
    assert evidence.records[0]["step"] == "Check phone"
    assert evidence.records[0]["page"] == "https://example.test/lead"
    assert "private-password" not in str(failed.value)
    assert "unrelated-account" not in str(failed.value)
    assert len(list(tmp_path.glob("*.png"))) == 1
    assert page.screenshot.call_args.kwargs["mask"]


def test_screenshot_failure_never_retries_unmasked_or_hides_original_error(tmp_path):
    evidence = FailureEvidence(tmp_path, "own-run")
    page = page_double()
    page.screenshot.side_effect = RuntimeError("private capture details")
    evidence.bind(page)
    error = AssertionError("original failure")
    evidence.capture(error, "Save lead")
    assert str(error) == "original failure"
    assert page.screenshot.call_count == 1
    assert not list(tmp_path.glob("*.png"))
    payload = next(tmp_path.glob("*.json")).read_text(encoding="utf-8")
    assert "private capture details" not in payload
    assert json.loads(payload)["screenshot_unavailable"] == "RuntimeError"


def test_closed_page_keeps_step_evidence_without_claiming_a_screenshot(tmp_path):
    evidence = FailureEvidence(tmp_path, "own-run")
    page = page_double()
    page.is_closed.return_value = True
    evidence.bind(page)
    evidence.phase = "teardown"
    evidence.last_step = "A previously successful step"
    evidence.capture(RuntimeError("cleanup"))
    page.screenshot.assert_not_called()
    assert evidence.records[0]["screenshot"] is None
    assert evidence.records[0]["phase"] == "teardown"
    assert evidence.records[0]["step"] != evidence.last_step
    assert evidence.records[0]["last_recorded_step"] == evidence.last_step
