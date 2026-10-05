"""Local-only portfolio configuration; credentials never appear in repr."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


DEFAULT_ORIGIN = "http://127.0.0.1:8000"
ENV_KEYS = {"E2E_BASE_URL", "E2E_EMAIL", "E2E_PASSWORD", "E2E_WORKSPACE"}


@dataclass(frozen=True)
class Settings:
    base_url: str
    email: str = field(repr=False)
    password: str = field(repr=False)
    workspace: str = field(default="", repr=False)

    @classmethod
    def load(cls, root: Path) -> "Settings":
        values = {}
        env_file = root / ".env"
        if env_file.is_file():
            for number, raw in enumerate(env_file.read_text(encoding="utf-8-sig").splitlines(), 1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                key, separator, value = line.partition("=")
                key, value = key.strip(), value.strip()
                if not separator or key not in ENV_KEYS:
                    raise ValueError(f"Unsupported .env entry on line {number}; see .env.example.")
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                values[key] = value
        values.update({key: os.environ[key] for key in ENV_KEYS if key in os.environ})
        try:
            target = urlsplit(values.get("E2E_BASE_URL", DEFAULT_ORIGIN).strip())
            port = target.port
            valid = (
                target.scheme in {"http", "https"}
                and target.hostname in {"localhost", "127.0.0.1", "::1"}
                and target.username is None and target.password is None
                and target.path in {"", "/"}
                and not target.query and not target.fragment
                and (port is None or 1 <= port <= 65535)
                and not target.netloc.endswith(":")
            )
        except ValueError:
            valid = False
        if not valid:
            # Do not echo invalid input: it could contain credentials.
            raise ValueError("E2E_BASE_URL must be a loopback HTTP(S) origin without credentials, path, query or fragment.")
        missing = [key for key in ("E2E_EMAIL", "E2E_PASSWORD") if not values.get(key, "").strip()]
        if missing:
            raise ValueError("Set " + ", ".join(missing) + " in an ignored .env file or environment variables.")
        return cls(
            base_url=f"{target.scheme}://{target.netloc}",
            email=values["E2E_EMAIL"].strip(),
            password=values["E2E_PASSWORD"],
            workspace=values.get("E2E_WORKSPACE", "").strip(),
        )
