"""E2E-LEAD-001: real sign-in and full lead capture from the dashboard."""

from decimal import Decimal
from urllib.parse import urlsplit

import allure
import pytest

from crm_e2e.pages import DashboardPage, LeadCard, LoginPage
from crm_e2e.reporting import FIELD_LABELS, report_step


@pytest.mark.e2e
@allure.epic("DealFlow CRM")
@allure.feature("Ліди")
@allure.story("Авторизація та повне заповнення нового ліда з робочого стола")
@allure.parent_suite("DealFlow CRM")
@allure.suite("Ліди")
@allure.sub_suite("Авторизація та створення")
@allure.title("E2E-LEAD-001 — Вхід → створення ліда → збереження всіх даних")
@allure.severity(allure.severity_level.CRITICAL)
def test_login_and_create_full_lead(crm_page, settings, lead_api, lead_data, created_lead, run_report, ui_actions):
    with report_step("1. Авторизація через форму входу та перехід на робочий стіл"):
        login = LoginPage(crm_page, ui_actions)
        actor = login.sign_in(settings)
        run_report.equal("Авторизація", "POST /api/auth/login/", login.last_status, 200)
        run_report.equal("Авторизація", "Сервер визначив користувача", bool(actor.get("id")), True)
        run_report.equal("Авторизація", "Адреса робочого стола після входу", urlsplit(crm_page.url).path, "/")

    with report_step("2. Читання налаштованого статусу ліда «В роботі»"):
        board = lead_api.get("/api/board-configurations/leads/")
        run_report.equal("Налаштування статусу", "GET /api/board-configurations/leads/", lead_api.last_status, 200)
        column = next(item for item in board["columns"] if item["stable_key"] == lead_data.status)
        status_labels = [column["label_uk"], column["label_en"]]

    with report_step("3. Робочий стіл → Створити → Новий лід: контакт, компанія, кваліфікація та 4 соцмережі"):
        form = DashboardPage(crm_page, ui_actions).open_new_lead()
        form.fill(lead_data, status_labels)

    with report_step("4. Створення ліда: HTTP 201, усі поля, автоматичне джерело та відповідальний"):
        record = form.submit(created_lead)
        group = "Створення ліда — API"
        run_report.equal(group, "POST /api/leads/", form.last_status, 201)
        for name, expected in lead_data.expected_fields().items():
            run_report.equal(group, FIELD_LABELS[name], record.get(name), expected)
        run_report.equal(group, "Відповідальний — поточний користувач", str(record["owner"]) == str(actor["id"]), True)
        run_report.equal(group, "Джерело має збережений ідентифікатор", bool(record["source"]), True)

    card = LeadCard(crm_page, settings.base_url, ui_actions)
    with report_step("5. Пошук створеного ліда у списку та відкриття саме його картки"):
        card.open_from_list(lead_data, record["id"])
        run_report.equal("Відкриття картки", "URL відповідає ідентифікатору створеного ліда",
                         urlsplit(crm_page.url).path == f"/app/leads/{record['id']}", True)

    with report_step("6. Збереження можливої суми угоди 125 000,50 грн у картці"):
        card.set_potential(lead_data, record["id"])
        run_report.equal("Збереження суми", "PATCH /api/leads/{id}/", card.last_status, 200)

    with report_step("7. Перезавантаження сторінки: дані контакту, соцмережі, статус і сума залишилися на картці"):
        crm_page.reload(wait_until="domcontentloaded")
        card.assert_visible(lead_data, status_labels, run_report)

    with report_step("8. Незалежна перевірка збережених даних через API; пов'язаних угод — 0"):
        saved = lead_api.lead(record["id"])
        group = "Після перезавантаження — API"
        run_report.equal(group, "GET /api/leads/{id}/", lead_api.last_status, 200)
        for name, expected in lead_data.expected_fields().items():
            run_report.equal(group, FIELD_LABELS[name], saved.get(name), expected)
        run_report.equal(group, "Відповідальний — поточний користувач", str(saved["owner"]) == str(actor["id"]), True)
        run_report.equal(group, "Джерело не змінилося після перезавантаження", saved["source"] == record["source"], True)
        run_report.equal(group, "Можлива сума угоди, грн", Decimal(saved["estimated_amount"]), Decimal(lead_data.estimated_amount))
        workspace = lead_api.get(lead_api.detail_path("leads", record["id"]) + "workspace/")
        group = "Відсутність автоматично створеної угоди"
        run_report.equal(group, "GET /api/leads/{id}/workspace/", lead_api.last_status, 200)
        run_report.equal(group, "Список пов'язаних угод порожній", workspace["deals"] == [], True)
        run_report.equal(group, "Загальна кількість угод за пагінацією", workspace["pagination"]["deals"]["count"], 0)
    run_report.body_completed = True
