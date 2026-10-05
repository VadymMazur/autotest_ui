"""Capture masked failure evidence while the original page and failing step exist."""

import json
import re
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import allure


active_evidence: ContextVar = ContextVar("crm_failure_evidence", default=None)


class FailureEvidence:
    def __init__(self, directory: Path, token: str):
        self.directory = directory
        self.token = token
        self.page = None
        self.secrets = []
        self.phase = "setup"
        self.steps = []
        self.last_step = ""
        self.last_action = ""
        self.records = []
        self._seen_errors = []

    def bind(self, page, secrets=()) -> None:
        self.page = page
        self.secrets = [value for value in secrets if value]

    def redact(self, message: str) -> str:
        message = message.split("Aria snapshot:", 1)[0].rstrip()
        for value in self.secrets:
            message = message.replace(value, "[приховано]")
        return message

    def _masks(self):
        page = self.page
        # Keep this run's form/card visible; hide credentials and unrelated data.
        masks = [page.locator(
            'input[type="password"], #login-email, #login-password, '
            '[autocomplete="username"], [autocomplete="current-password"], '
            '.account-menu, .account-menu-panel, .account-trigger, .user-menu, .profile-menu, '
            '.workspace-options, .dashboard-grid, .timeline, .comment-list, '
            '.kanban-card-foot, tbody tr td:nth-child(5), '
            '.notification-menu, .notification-panel, .notification-center-menu, [data-e2e-private]'
        )]
        masks.append(page.locator('tbody tr, .kanban-card, .board-card').filter(has_not_text=self.token))
        masks.append(page.locator('.lead-info-grid dt').filter(
            has_text=re.compile(r'Відповідальн|Вла[сд]ник|Responsible|Owner|Assignee', re.I),
        ).locator('xpath=following-sibling::dd[1]'))
        for secret in self.secrets:
            masks.append(page.get_by_text(re.compile(re.escape(secret))))
        return masks

    def capture(self, error: BaseException, step: str = "") -> None:
        if any(error is previous for previous in self._seen_errors):
            return
        self._seen_errors.append(error)
        # Diagnostic failures must never replace the original test failure.
        try:
            self._capture(error, step)
        except Exception as capture_error:
            try:
                allure.attach(type(capture_error).__name__, name="Не вдалося зберегти діагностику",
                              attachment_type=allure.attachment_type.TEXT)
            except Exception:
                pass

    def _capture(self, error: BaseException, step: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        stem = f"{self.phase}-{len(self.records) + 1:02d}"
        context = {
            "phase": self.phase,
            "step": self.redact(step or (self.steps[-1] if self.steps else "Помилка поза іменованим кроком")),
            "step_path": [self.redact(value) for value in self.steps],
            "last_recorded_step": self.redact(self.last_step),
            "last_action": self.redact(self.last_action),
            "exception_type": type(error).__name__,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "synthetic_run": self.token,
            "screenshot": None,
        }
        if self.page is None or self.page.is_closed():
            context["screenshot_unavailable"] = "Сторінку ще не створено або вже закрито."
        else:
            url = urlsplit(self.page.url)
            # Exclude queries, fragments, data URLs and credentials in URLs.
            context["page"] = self.redact(f"{url.scheme}://{url.hostname or ''}{url.path}") if url.scheme in {"http", "https"} else url.scheme + ":"
            try:
                screenshot = self.page.screenshot(
                    type="png", full_page=False, mask=self._masks(), mask_color="#334155",
                    caret="initial", timeout=5_000,
                )
                image_path = self.directory / f"{stem}.png"
                image_path.write_bytes(screenshot)
                context["screenshot"] = image_path.name
                allure.attach(screenshot, name=f"Скріншот у момент збою — {context['step']}",
                              attachment_type=allure.attachment_type.PNG)
            except Exception as screenshot_error:
                # Never retry without masks; report the capture limitation instead.
                context["screenshot_unavailable"] = type(screenshot_error).__name__
        self.records.append(context)
        payload = json.dumps(context, ensure_ascii=False, indent=2)
        (self.directory / f"{stem}.json").write_text(payload, encoding="utf-8")
        allure.attach(payload, name="Момент збою — крок, остання дія та сторінка",
                      attachment_type=allure.attachment_type.JSON)
