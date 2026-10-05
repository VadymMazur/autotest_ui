"""Independent browser sessions and cleanup even after assertion failures."""

import json
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import allure
import pytest

from crm_e2e.api import CreatedLead, LeadApi
from crm_e2e.actions import UiActions
from crm_e2e.config import Settings
from crm_e2e.data import LeadData
from crm_e2e.diagnostics import FailureEvidence, active_evidence
from crm_e2e.reporting import VerificationReport, report_step


def pytest_addoption(parser):
    group = parser.getgroup("crm-presentation")
    group.addoption("--demo", action="store_true", help="Animate typing and the mouse, including headless runs.")
    group.addoption("--typing-delay", type=int, default=45, help="Milliseconds per character in headed/demo runs (default: 45).")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    evidence = getattr(item, "crm_failure_evidence", None)
    if evidence:
        evidence.phase = "call"
    try:
        return (yield)
    except Exception as error:
        # Playwright can append the entire authenticated page to a failed expect.
        # Keep the locator/call log without unrelated workspace/account content.
        message = str(error)
        if "\nAria snapshot:" in message:
            error.args = (message.split("\nAria snapshot:", 1)[0]
                          + "\nPage snapshot omitted from the report.",)
        if evidence:
            error.args = (evidence.redact(str(error)),)
            evidence.capture(error)
        raise


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    report = yield
    evidence = getattr(item, "crm_failure_evidence", None)
    if evidence:
        if report.failed and call.excinfo:
            evidence.phase = report.when
            evidence.capture(call.excinfo.value)
        if report.when == "call" or (report.when == "setup" and report.failed):
            evidence.phase = "teardown"
    return report


@pytest.fixture
def failure_evidence(request, pytestconfig, lead_data):
    evidence = FailureEvidence(pytestconfig.rootpath / "test-results" / "failures" / lead_data.token, lead_data.token)
    request.node.crm_failure_evidence = evidence
    token = active_evidence.set(evidence)
    try:
        yield evidence
    finally:
        active_evidence.reset(token)


@pytest.fixture(scope="session")
def settings(pytestconfig):
    try:
        return Settings.load(pytestconfig.rootpath)
    except ValueError as error:
        message = str(error)
    pytest.fail(message, pytrace=False)


@pytest.fixture
def crm_page(browser, settings, failure_evidence):
    # No shared authentication state. Failure images mask credentials and unrelated data.
    context = browser.new_context(
        base_url=settings.base_url,
        viewport={"width": 1440, "height": 1000},
        locale="uk-UA",
    )
    context.set_default_timeout(20_000)
    context.set_default_navigation_timeout(45_000)
    page = context.new_page()
    failure_evidence.bind(page, (settings.email, settings.password, settings.workspace))
    try:
        yield page
    finally:
        context.close()


@pytest.fixture
def ui_actions(crm_page, pytestconfig):
    delay = pytestconfig.getoption("typing_delay")
    if not 0 <= delay <= 500:
        raise pytest.UsageError("--typing-delay must be between 0 and 500 ms.")
    visual = pytestconfig.getoption("headed") or pytestconfig.getoption("demo")
    return UiActions(crm_page, visual=visual, typing_delay=delay)


@pytest.fixture
def lead_api(crm_page, settings):
    return LeadApi(crm_page.context, settings.base_url)


@pytest.fixture
def lead_data():
    return LeadData.unique()


@pytest.fixture
@allure.title("Підсумок фактично виконаних перевірок")
def run_report(lead_data, settings, browser_name, browser, pytestconfig, failure_evidence):
    report = VerificationReport(lead_data.token, settings.base_url, f"{browser_name} {browser.version}")
    output = pytestconfig.getoption("allure_report_dir", default=None)
    if output:
        directory = Path(output)
        directory.mkdir(parents=True, exist_ok=True)
        environment = {
            "Target": settings.base_url,
            "Browser": report.browser,
            "Viewport": "1440 x 1000",
            "Locale": "uk-UA",
            "OS": f"{platform.system()} {platform.release()}",
            "Python": platform.python_version(),
            "pytest": version("pytest"),
            "Playwright": version("playwright"),
            "Test_data": "Synthetic; unique per run",
            "Visual_mode": str(bool(pytestconfig.getoption("headed") or pytestconfig.getoption("demo"))),
        }
        (directory / "environment.properties").write_text(
            "\n".join(f"{key}={value}" for key, value in environment.items()) + "\n", encoding="ascii",
        )
        (directory / "executor.json").write_text(json.dumps({
            "name": "Локальний запуск pytest",
            "buildName": "E2E-LEAD-001 · " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "reportName": "DealFlow CRM — Авторизація та створення ліда",
        }, ensure_ascii=False), encoding="utf-8")
    try:
        yield report
    finally:
        report.failures = failure_evidence.records
        report.publish()


@pytest.fixture
@allure.title("Очищення створених цим запуском даних")
def created_lead(lead_api, lead_data, run_report):
    created = CreatedLead(lead_api, lead_data)
    try:
        yield created
    finally:
        try:
            with report_step("Видалити тестовий лід, контакт і компанію; перевірити HTTP 404 після кожного видалення"):
                created.cleanup()
        finally:
            run_report.record_cleanup(lead_api.cleanup_events, created.cleaned)
