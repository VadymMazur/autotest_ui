"""Synthetic, unique values; no messages are sent to these contact channels."""

from dataclasses import dataclass
from secrets import randbelow
from uuid import uuid4


@dataclass(frozen=True)
class LeadData:
    token: str
    title: str
    first_name: str
    last_name: str
    phone: str
    email: str
    company: str
    position: str
    notes: str
    telegram: str
    linkedin: str
    facebook: str
    instagram: str
    status: str = "in_progress"
    estimated_amount: str = "125000.50"

    @classmethod
    def unique(cls) -> "LeadData":
        token = uuid4().hex[:12]
        return cls(
            token=token,
            title=f"E2E-{token} — впровадження CRM",
            first_name="Тестовий",
            last_name=f"Лід-{token}",
            phone=f"+38000{randbelow(10_000_000):07d}",
            email=f"e2e.{token}@example.test",
            company=f"E2E Company {token}",
            position="Керівник відділу закупівель",
            notes=f"Synthetic E2E record {token}.\nПотрібна CRM для 12 менеджерів. Тестові дані.",
            telegram=f"https://example.test/telegram/{token}",
            linkedin=f"https://example.test/linkedin/{token}",
            facebook=f"https://example.test/facebook/{token}",
            instagram=f"https://example.test/instagram/{token}",
        )

    def expected_fields(self) -> dict:
        return {
            "title": self.title,
            "contact_first_name": self.first_name,
            "contact_last_name": self.last_name,
            "contact_phone": self.phone,
            "contact_email": self.email,
            "company_name": self.company,
            "contact_position": self.position,
            "notes": self.notes,
            "contact_telegram": self.telegram,
            "contact_linkedin": self.linkedin,
            "contact_facebook": self.facebook,
            "contact_instagram": self.instagram,
            "status": self.status,
            "source_name": "Ручне додавання",
            "is_converted": False,
        }
