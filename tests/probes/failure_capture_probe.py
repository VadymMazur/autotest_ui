"""Explicit local diagnostic probe: expected failures, never normal suite coverage.

Run this exact filename separately with its own --alluredir. It is intentionally
outside pytest's test_*.py discovery pattern and never accesses a CRM service.
"""

import allure
import pytest

from crm_e2e.reporting import report_step


pytestmark = pytest.mark.harness


@pytest.fixture
def probe_page(page, failure_evidence):
    failure_evidence.bind(page, ("hidden-login@example.test", "hidden-password"))
    page.set_content("""
        <style>body{font:20px system-ui;padding:40px;background:#f1f5f9}
        input{display:block;padding:12px;margin:12px 0;width:400px}
        main{background:white;border-radius:16px;padding:24px;max-width:650px}</style>
        <main><h1>Failure capture self-check</h1><p>Intentional local failure before cleanup.</p>
        <label>Login<input id="login-email" value="hidden-login@example.test"></label>
        <label>Password<input id="login-password" type="password" value="hidden-password"></label>
        <label>Synthetic lead<input value="E2E screenshot probe"></label>
        <p data-e2e-private>Unrelated private account</p><button>Save lead</button></main>
    """)
    allure.dynamic.parent_suite("Local diagnostics self-check — expected failures")
    try:
        yield page
    finally:
        page.set_content("<h1>Cleanup already ran</h1>")


def test_assertion_failure(probe_page):
    with report_step("Probe: create synthetic lead"):
        with report_step("Probe: saved phone differs"):
            raise AssertionError("Intentional assertion failure to verify screenshot capture.")


def test_playwright_timeout(probe_page):
    with report_step("Probe: missing Save control"):
        probe_page.get_by_role("button", name="Missing button", exact=True).click(timeout=150)


@pytest.fixture
def broken_setup(probe_page):
    raise RuntimeError("Intentional setup failure outside a named step.")


def test_setup_failure(broken_setup):
    pass


@pytest.fixture
def broken_teardown(probe_page):
    yield
    with report_step("Probe: cleanup failure while page is still open"):
        raise RuntimeError("Intentional teardown failure.")


def test_teardown_failure(broken_teardown):
    pass
