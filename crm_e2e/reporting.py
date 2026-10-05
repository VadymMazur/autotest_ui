"""Readable Allure evidence built from executed assertions, never account payloads."""

import json
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from html import escape

import allure
from playwright.sync_api import expect

from crm_e2e.diagnostics import active_evidence


FIELD_LABELS = {
    "title": "Назва картки",
    "contact_first_name": "Ім'я",
    "contact_last_name": "Прізвище",
    "contact_phone": "Телефон",
    "contact_email": "Email",
    "company_name": "Компанія",
    "contact_position": "Посада",
    "notes": "Коментар",
    "contact_telegram": "Telegram",
    "contact_linkedin": "LinkedIn",
    "contact_facebook": "Facebook",
    "contact_instagram": "Instagram",
    "status": "Статус ліда",
    "source_name": "Джерело ліда",
    "is_converted": "Лід конвертований у клієнта",
}


def display(value) -> str:
    if isinstance(value, bool):
        return "Так" if value else "Ні"
    if value is None:
        return "Не задано"
    return str(value)


@contextmanager
def report_step(title: str):
    """Remove the full authenticated page before Allure records an assertion failure."""
    evidence = active_evidence.get()
    if evidence:
        evidence.steps.append(title)
        evidence.last_step = title
    try:
        with allure.step(title):
            try:
                yield
            except Exception as error:
                message = str(error)
                if "Aria snapshot:" in message:
                    message = (message.split("Aria snapshot:", 1)[0].rstrip()
                               + "\nPage snapshot omitted from the report.")
                if evidence:
                    message = evidence.redact(message)
                error.args = (message,)
                if evidence:
                    evidence.capture(error, title)
                raise
    finally:
        if evidence:
            evidence.steps.pop()


@dataclass
class Check:
    group: str
    name: str
    expected: str
    actual: str
    status: str


class VerificationReport:
    def __init__(self, token: str, base_url: str, browser: str):
        self.token = token
        self.base_url = base_url
        self.browser = browser
        self.checks: list[Check] = []
        self.body_completed = False
        self.cleanup_completed = False
        self.failures = []

    @property
    def complete(self) -> bool:
        return (self.body_completed and self.cleanup_completed and bool(self.checks) and not self.failures
                and all(check.status == "passed" for check in self.checks))

    def equal(self, group: str, name: str, actual, expected) -> None:
        status = "passed" if actual == expected else "failed"
        self.checks.append(Check(group, name, display(expected), display(actual), status))
        with report_step(f"{name}: очікуване «{display(expected)}»; фактичне «{display(actual)}»"):
            if status != "passed":
                raise AssertionError(f"Перевірка «{name}» не пройшла; див. очікуване та фактичне у звіті.")

    def ui_contains(self, name: str, locator, expected, expected_label: str | None = None) -> None:
        label = expected_label or (expected.pattern if isinstance(expected, re.Pattern) else expected)
        row = Check("Картка після перезавантаження — UI", name, label, "Не підтверджено", "broken")
        self.checks.append(row)
        with report_step(f"На картці відображено {name.lower()}: {label}"):
            try:
                expect(locator).to_be_visible()
                expect(locator).to_contain_text(expected)
                observed = locator.inner_text()
                if isinstance(expected, re.Pattern):
                    match = expected.search(observed)
                else:
                    match = re.search(re.escape(" ".join(expected.split())), " ".join(observed.split()))
                if not match:
                    raise AssertionError(f"Не вдалося повторно прочитати поле «{name}» після UI-перевірки.")
                # Keep only the verified fragment, never neighboring account/workspace data.
                row.actual = match.group(0)
                row.status = "passed"
            except AssertionError:
                row.status = "failed"
                raise

    def record_cleanup(self, events: list[dict], completed: bool) -> None:
        labels = {"leads": "Лід", "contacts": "Контакт", "companies": "Компанія"}
        for event in events:
            name = f"{labels[event['resource']]} — {event['method']} /api/{event['resource']}/{{id}}/"
            expected = event["expected_status"]
            actual = event["status"]
            self.checks.append(Check("Очищення тестових даних", name, f"HTTP {expected}",
                                     f"HTTP {actual}", "passed" if actual == expected else "failed"))
        self.cleanup_completed = completed

    def render_html(self, detailed: bool = True) -> str:
        passed = sum(check.status == "passed" for check in self.checks)
        state = "Сценарій і очищення завершені" if self.complete else "Виконання не завершене — див. невдалі кроки"
        parts = [
            "<h2>E2E-LEAD-001 · Що саме перевірено</h2>",
            f"<p><strong>{state}</strong></p>",
            f"<p>Підтверджено <strong>{passed} із {len(self.checks)}</strong> перевірок у межах "
            "<strong>одного E2E-сценарію</strong>. Це не кількість окремих тестів.</p>",
            f"<p>Стенд: {escape(self.base_url)} · Браузер: {escape(self.browser)} · "
            f"Вікно: 1440 × 1000 · Дані: синтетичні · Маркер: {escape(self.token)}</p>",
            "<p>Маршрут: вхід → робочий стіл → новий лід → повна картка → "
            "125 000,50 грн → перезавантаження → перевірка API → очищення.</p>",
            "<table><thead><tr><th>Етап перевірки</th><th>Підтверджено</th></tr></thead><tbody>",
        ]
        if self.failures:
            # Place the failure pointer before the potentially long field tables.
            details = "".join(f"<li>{escape(item['phase'])}: {escape(item['step'])} "
                              f"({escape(item['exception_type'])})</li>" for item in self.failures)
            parts.insert(2, "<h3>Де зупинився тест</h3><ul>" + details + "</ul>"
                         "<p>Відкрийте PNG «Скріншот у момент збою» та JSON «Момент збою» "
                         "під невдалим кроком. Якщо сторінка недоступна, причина вказана в JSON.</p>")
        groups = list(dict.fromkeys(check.group for check in self.checks))
        for group in groups:
            rows = [check for check in self.checks if check.group == group]
            count = sum(check.status == "passed" for check in rows)
            parts.append(f"<tr><td>{escape(group)}</td><td>{count} / {len(rows)}</td></tr>")
        parts.append("</tbody></table>")
        if detailed:
            for group in groups:
                parts.append(f"<h3>{escape(group)}</h3><table><thead><tr><th>Перевірка</th>"
                             "<th>Очікуване</th><th>Фактичне</th><th>Результат</th></tr></thead><tbody>")
                for check in (item for item in self.checks if item.group == group):
                    status = {"passed": "✓ Пройдено", "failed": "✗ Не пройдено", "broken": "Не завершено"}[check.status]
                    cells = [check.name, check.expected, check.actual, status]
                    parts.append("<tr>" + "".join(f"<td>{escape(cell).replace(chr(10), '<br>')}</td>" for cell in cells) + "</tr>")
                parts.append("</tbody></table>")
        parts.append("<p><strong>Межі покриття:</strong> позитивний сценарій на desktop Chromium. "
                     "Негативний вхід, дублікати, права доступу, ізоляція організацій, мобільні "
                     "браузери та конвертація тут не перевіряються.</p>")
        return "\n".join(parts)

    def publish(self) -> None:
        html = self.render_html()
        allure.dynamic.description_html(html)
        allure.attach(html, name="Очікуване та фактичне — повна таблиця перевірок", attachment_type=allure.attachment_type.HTML)
        allure.attach(json.dumps({
            "scenario": "E2E-LEAD-001", "synthetic_run": self.token,
            "body_completed": self.body_completed, "cleanup_completed": self.cleanup_completed,
            "failures": self.failures,
            "checks": [asdict(check) for check in self.checks],
        }, ensure_ascii=False, indent=2), name="Перевірки з фактичними результатами (JSON)", attachment_type=allure.attachment_type.JSON)
