"""Page objects for the shipped UK/EN dashboard and lead workspace."""

import re
from urllib.parse import urlsplit

from playwright.sync_api import Error, Page, expect

from crm_e2e.api import CreatedLead
from crm_e2e.actions import UiActions
from crm_e2e.config import Settings
from crm_e2e.data import LeadData
from crm_e2e.reporting import VerificationReport


def ui(uk: str, en: str) -> re.Pattern:
    return re.compile(f"^(?:{re.escape(uk)}|{re.escape(en)})$")


def api_response(response, path: str, method: str) -> bool:
    return urlsplit(response.url).path == path and response.request.method == method


class LoginPage:
    def __init__(self, page: Page, actions: UiActions):
        self.page = page
        self.actions = actions

    def sign_in(self, settings: Settings) -> dict:
        self.page.goto(settings.base_url + "/login", wait_until="domcontentloaded")
        expect(self.page.locator("#login-email")).to_be_visible()
        try:
            self.actions.fill(self.page.locator("#login-email"), settings.email, "Ввести логін")
            self.actions.fill(self.page.locator("#login-password"), settings.password, "Ввести пароль")
        except Error:
            # Playwright's fill call log can contain its argument; never report it.
            raise AssertionError("Unable to fill the sign-in fields.") from None
        with self.page.expect_response(lambda response: api_response(response, "/api/auth/login/", "POST")) as pending:
            self.actions.click(self.page.locator(".auth-form button[type='submit']"), "Натиснути «Увійти»")
        response = pending.value
        self.last_status = response.status
        assert response.status == 200, f"UI sign-in failed: HTTP {response.status}."
        actor = response.json()
        self.page.wait_for_url(lambda url: urlsplit(url).path in ("/", "/workspaces"))
        if urlsplit(self.page.url).path == "/workspaces":
            assert settings.workspace, "Set E2E_WORKSPACE for this account's workspace selection."
            workspace = self.page.locator(".workspace-options button").filter(
                has=self.page.get_by_text(settings.workspace, exact=True),
            )
            self.actions.click(workspace, "Обрати робочий простір")
        expect(self.page.locator(".dashboard-page")).to_be_visible()
        return actor


class DashboardPage:
    def __init__(self, page: Page, actions: UiActions):
        self.page = page
        self.actions = actions

    def open_new_lead(self) -> "LeadForm":
        self.actions.click(self.page.get_by_role("button", name=ui("Створити", "Create")), "Відкрити меню «Створити»")
        self.actions.click(self.page.get_by_role("menuitem", name=ui("Новий лід", "New lead")), "Обрати «Новий лід»")
        form = LeadForm(self.page, self.actions)
        expect(form.dialog).to_be_visible()
        return form


class LeadForm:
    def __init__(self, page: Page, actions: UiActions):
        self.page = page
        self.actions = actions
        self.dialog = page.get_by_role("dialog", name=ui("Створити новий лід", "Create new lead"))

    def fill(self, data: LeadData, status_labels: list[str]) -> None:
        for name, (label, value) in {
            "first_name": ("Ім'я", data.first_name),
            "last_name": ("Прізвище", data.last_name),
            "phone": ("Телефон", data.phone),
            "title": ("Назва картки", data.title),
            "email": ("Email", data.email),
            "position": ("Посада", data.position),
            # Set after email blur, which otherwise suggests a company name.
            "company_name_input": ("Компанія", data.company),
        }.items():
            self.actions.fill(self.dialog.locator(f"[name='{name}']"), value, f"Заповнити поле «{label}»")
        source = self.dialog.get_by_role("textbox", name=ui("Джерело", "Source"))
        expect(source).to_be_disabled()
        expect(source).to_have_value(ui("Ручне додавання", "Manual entry"))
        self.actions.click(self.dialog.get_by_role("button", name=ui("Кваліфікація", "Qualification")), "Розгорнути «Кваліфікація»")
        status = self.dialog.get_by_role("button", name=ui("Статус", "Status"))
        # Board metadata loads after the modal mounts; an early click is ignored.
        expect(status).not_to_have_text("—", timeout=20_000)
        self.actions.click(status, "Відкрити список статусів")
        label = re.compile("^(?:" + "|".join(re.escape(value) for value in status_labels) + ")$")
        self.actions.click(self.page.get_by_role("option", name=label), "Обрати статус ліда")
        self.actions.fill(self.dialog.locator("[name='notes']"), data.notes, "Заповнити коментар")
        self.actions.click(self.dialog.get_by_role("button", name=ui("Соціальні мережі", "Social networks")), "Розгорнути «Соціальні мережі»")
        for name in ("telegram", "linkedin", "facebook", "instagram"):
            self.actions.fill(self.dialog.locator(f"[name='{name}']"), getattr(data, name), f"Заповнити {name}")

    def submit(self, created: CreatedLead) -> dict:
        with self.page.expect_response(lambda response: api_response(response, "/api/leads/", "POST")) as pending:
            created.submitted = True
            self.actions.click(self.dialog.get_by_role("button", name=ui("Створити лід", "Create lead")), "Натиснути «Створити лід»")
        response = pending.value
        self.last_status = response.status
        assert response.status == 201, f"Lead creation failed: HTTP {response.status}."
        record = response.json()
        created.capture(record)
        expect(self.dialog).to_be_hidden()
        return record


class LeadCard:
    def __init__(self, page: Page, base_url: str, actions: UiActions):
        self.page = page
        self.base_url = base_url
        self.actions = actions

    def open_from_list(self, data: LeadData, identifier: str) -> None:
        self.page.goto(self.base_url + "/app/leads/list", wait_until="domcontentloaded")
        self.actions.fill(self.page.locator("input.board-search"), data.token, "Знайти створений лід за маркером")
        self.actions.click(self.page.get_by_role("link", name=data.title, exact=True), "Відкрити картку створеного ліда")
        expect(self.page).to_have_url(self.base_url + f"/app/leads/{identifier}")
        expect(self.page.locator(".lead-layout")).to_be_visible()

    def set_potential(self, data: LeadData, identifier: str) -> None:
        self.actions.click(self.page.get_by_role("button", name=ui("Редагувати можливу суму угоди", "Edit possible deal amount")), "Редагувати можливу суму угоди")
        self.actions.fill(self.page.get_by_role("spinbutton", name=ui("Можлива сума угоди", "Possible deal amount")), data.estimated_amount, "Ввести можливу суму угоди")
        with self.page.expect_response(lambda response: api_response(response, f"/api/leads/{identifier}/", "PATCH")) as pending:
            self.actions.click(self.page.locator(".finance-edit").get_by_role("button", name=ui("Зберегти", "Save")), "Зберегти можливу суму угоди")
        self.last_status = pending.value.status
        assert self.last_status == 200, f"Saving deal potential failed: HTTP {self.last_status}."
        expect(self.page.locator(".finance-edit")).to_be_hidden()

    def assert_visible(self, data: LeadData, status_labels: list[str], report: VerificationReport) -> None:
        report.ui_contains("Заголовок картки", self.page.get_by_role("heading", name=data.title, exact=True), data.title)
        details = self.page.locator(".lead-info-grid")
        for label, value in {
            "Назва картки": data.title, "Ім'я та прізвище": f"{data.first_name} {data.last_name}",
            "Компанія": data.company, "Коментар": data.notes, "Джерело": "Ручне додавання",
        }.items():
            report.ui_contains(label, details, value)
        contacts = self.page.locator(".contact-grid")
        for label, value in {
            "Телефон": data.phone, "Email": data.email, "Посада": data.position,
            "Telegram": data.telegram, "LinkedIn": data.linkedin,
            "Facebook": data.facebook, "Instagram": data.instagram,
        }.items():
            report.ui_contains(label, contacts, value)
        label = re.compile("^(?:" + "|".join(re.escape(value) for value in status_labels) + ")$")
        report.ui_contains("Статус", self.page.locator(".lead-section__actions .chip"), label, " / ".join(status_labels))
        report.ui_contains("Можлива сума угоди", self.page.locator(".finance-total"), re.compile(r"125\D?000[,.]50"), "125 000,50 грн")
