"""Read persisted state and remove only this run's synthetic records.

Authentication, lead creation and amount editing stay in the browser UI.
"""

from urllib.parse import quote

import allure
from playwright.sync_api import BrowserContext

from crm_e2e.data import LeadData


class LeadApi:
    def __init__(self, context: BrowserContext, base_url: str):
        self.context = context
        self.base_url = base_url
        self.last_status = None
        self.cleanup_events = []

    def get(self, path: str, **kwargs) -> dict:
        response = self.context.request.get(self.base_url + path, **kwargs)
        self.last_status = response.status
        assert response.status == 200, f"CRM read failed: HTTP {response.status} at {path.split('?')[0]}"
        return response.json()

    @staticmethod
    def detail_path(resource: str, identifier: str) -> str:
        return f"/api/{resource}/{quote(str(identifier), safe='')}/"

    def lead(self, identifier: str) -> dict:
        return self.get(self.detail_path("leads", identifier))

    def delete(self, resource: str, identifier: str) -> None:
        cookies = self.context.cookies([self.base_url])
        csrf = next((cookie["value"] for cookie in cookies if cookie["name"] == "csrftoken"), None)
        assert csrf, "Cleanup requires the current browser session's CSRF cookie."
        path = self.detail_path(resource, identifier)
        with allure.step(f"DELETE /api/{resource}/{{id}}/ — видалення запису, очікуємо HTTP 204"):
            response = self.context.request.delete(
                self.base_url + path,
                headers={"X-CSRFToken": csrf, "Referer": self.base_url + "/"},
            )
            self.cleanup_events.append({"resource": resource, "method": "DELETE", "status": response.status, "expected_status": 204})
            assert response.status == 204, f"Cleanup failed for {resource}: HTTP {response.status}."
        with allure.step(f"GET /api/{resource}/{{id}}/ — запис уже недоступний, очікуємо HTTP 404"):
            check = self.context.request.get(self.base_url + path)
            self.cleanup_events.append({"resource": resource, "method": "GET", "status": check.status, "expected_status": 404})
            assert check.status == 404, f"Deleted {resource} remains accessible: HTTP {check.status}."


class CreatedLead:
    """Track writes before assertions so failed checks still get cleanup."""

    def __init__(self, api: LeadApi, data: LeadData):
        self.api = api
        self.data = data
        self.submitted = False
        self.record = None
        self.cleaned = False

    def capture(self, record: dict) -> None:
        self.record = record

    def cleanup(self) -> None:
        if not self.submitted or self.cleaned:
            return
        record = self.record
        if record is None:
            # A browser timeout after POST can occur after the server committed.
            collection = self.api.get("/api/leads/", params={"search": self.data.token})
            matches = collection if isinstance(collection, list) else collection["results"]
            matches = [item for item in matches if item.get("title") == self.data.title
                       and item.get("contact_email") == self.data.email]
            assert len(matches) <= 1, "Cleanup refused: more than one record matches this run."
            if not matches:
                return
            record = matches[0]
        current = self.api.lead(record["id"])
        assert current["title"] == self.data.title, "Cleanup refused: lead title does not match this run."
        assert current["contact_email"] == self.data.email, "Cleanup refused: contact does not match this run."
        assert current["company_name"] == self.data.company, "Cleanup refused: company does not match this run."
        contact_id, company_id = current["contact"], current["company"]
        contact = self.api.get(self.api.detail_path("contacts", contact_id))
        company = self.api.get(self.api.detail_path("companies", company_id))
        assert contact["email"] == self.data.email, "Cleanup refused: unrelated contact."
        assert company["name"] == self.data.company, "Cleanup refused: unrelated company."
        self.api.delete("leads", current["id"])
        self.api.delete("contacts", contact_id)
        self.api.delete("companies", company_id)
        self.cleaned = True
