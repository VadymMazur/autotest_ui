"""Local harness checks; these do not establish CRM coverage."""

from unittest.mock import Mock

import pytest

from crm_e2e.api import CreatedLead
from crm_e2e.config import ENV_KEYS, DEFAULT_ORIGIN, Settings
from crm_e2e.data import LeadData


@pytest.fixture
def isolated_env(monkeypatch):
    for name in ENV_KEYS:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("target", [
    "https://remote.example.test",
    "http://localhost.example.test",
    "http://127.0.0.1@remote.example.test",
    "http://user:secret@localhost:8000",
    "http://localhost:8000?token=secret",
    "http://localhost:8000#private",
    "http://localhost:8000/documents",
    "ftp://localhost",
    "http://localhost:0",
    "http://localhost:99999",
    "http://localhost:invalid",
    "http://localhost:",
    "http://[invalid",
    "http://0.0.0.0:8000",
])
def test_rejects_nonlocal_or_ambiguous_targets(tmp_path, isolated_env, target):
    (tmp_path / ".env").write_text(
        f"E2E_BASE_URL={target}\nE2E_EMAIL=qa@example.test\nE2E_PASSWORD=synthetic-secret\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="loopback") as error:
        Settings.load(tmp_path)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("origin", [DEFAULT_ORIGIN, "http://localhost:8080", "https://localhost", "http://[::1]:8000"])
def test_accepts_loopback_and_keeps_secrets_out_of_repr(tmp_path, isolated_env, origin):
    (tmp_path / ".env").write_text(
        f'E2E_BASE_URL={origin}/\n'
        'E2E_EMAIL=qa@example.test\nE2E_PASSWORD="synthetic=#secret"\n',
        encoding="utf-8-sig",
    )
    settings = Settings.load(tmp_path)
    assert settings.base_url == origin
    assert settings.password == "synthetic=#secret"
    assert settings.password not in repr(settings)
    assert settings.email not in repr(settings)


def test_missing_credentials_is_an_error(tmp_path, isolated_env):
    with pytest.raises(ValueError, match="E2E_EMAIL, E2E_PASSWORD"):
        Settings.load(tmp_path)


def test_environment_overrides_local_file(tmp_path, isolated_env, monkeypatch):
    (tmp_path / ".env").write_text(
        "E2E_EMAIL=qa@example.test\nE2E_PASSWORD=file-placeholder\n", encoding="utf-8",
    )
    monkeypatch.setenv("E2E_PASSWORD", "environment-placeholder")
    settings = Settings.load(tmp_path)
    assert settings.password == "environment-placeholder"
    assert settings.base_url == DEFAULT_ORIGIN


@pytest.fixture
def synthetic_run():
    data = LeadData.unique()
    api = Mock()
    current = {
        "id": "own-lead", "contact": "own-contact", "company": "own-company",
        "title": data.title, "contact_email": data.email, "company_name": data.company,
    }
    api.lead.return_value = current
    api.get.side_effect = [{"email": data.email}, {"name": data.company}]
    created = CreatedLead(api, data)
    created.submitted = True
    created.capture(current)
    return created, api, current


@pytest.mark.parametrize("field", ["title", "contact_email", "company_name"])
def test_cleanup_refuses_records_not_owned_by_this_run(synthetic_run, field):
    created, api, current = synthetic_run
    current[field] = "unrelated-record"
    with pytest.raises(AssertionError, match="Cleanup refused"):
        created.cleanup()
    api.delete.assert_not_called()


def test_cleanup_deletes_only_owned_records_in_dependency_order(synthetic_run):
    created, api, _ = synthetic_run
    created.cleanup()
    assert [call.args for call in api.delete.call_args_list] == [
        ("leads", "own-lead"), ("contacts", "own-contact"), ("companies", "own-company"),
    ]
    assert created.cleaned
    created.cleanup()
    assert api.delete.call_count == 3


def test_cleanup_recovers_a_committed_write_after_browser_timeout(synthetic_run):
    created, api, current = synthetic_run
    created.record = None
    api.get.side_effect = [
        {"results": [current, {"title": "unrelated", "contact_email": "other@example.test"}]},
        {"email": created.data.email}, {"name": created.data.company},
    ]
    created.cleanup()
    assert created.cleaned
    assert api.delete.call_count == 3


def test_cleanup_does_not_touch_the_server_before_submission(synthetic_run):
    created, api, _ = synthetic_run
    created.submitted = False
    created.cleanup()
    assert not api.mock_calls
