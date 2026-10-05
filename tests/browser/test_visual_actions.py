"""Local browser harness checks; no CRM connection or credentials."""

import pytest
from playwright.sync_api import expect

from crm_e2e.actions import UiActions


@pytest.mark.harness
def test_typing_emits_intermediate_values_and_cursor_survives_navigation(page):
    actions = UiActions(page, visual=True, typing_delay=5)
    page.goto("data:text/html,<label>Name<input id='name'></label><button>Save</button>")
    page.locator("#name").evaluate("el => {window.values=[]; el.addEventListener('input', () => window.values.push(el.value));}")
    actions.fill(page.locator("#name"), "Тест", "Fill synthetic name")
    expect(page.locator("#name")).to_have_value("Тест")
    assert page.evaluate("window.values")[-4:] == ["Т", "Те", "Тес", "Тест"]
    expect(page.locator("[data-e2e-cursor]")).to_be_visible()
    page.get_by_role("button").evaluate("el => el.addEventListener('click', () => el.textContent='Saved')")
    actions.click(page.get_by_role("button"), "Save synthetic form")
    expect(page.get_by_role("button")).to_have_text("Saved")
    page.goto("data:text/html,<textarea></textarea><input type='number' step='0.01'>")
    actions.fill(page.locator("textarea"), "Рядок 1\nРядок 2", "Fill notes")
    expect(page.locator("textarea")).to_have_value("Рядок 1\nРядок 2")
    actions.fill(page.locator("input"), "125000.50", "Fill amount")
    expect(page.locator("input")).to_have_value("125000.50")
    expect(page.locator("[data-e2e-cursor]")).to_have_count(1)


@pytest.mark.harness
def test_default_headless_actions_do_not_install_visual_effects(page):
    page.set_content("<input>")
    UiActions(page).fill(page.locator("input"), "Synthetic", "Fill name")
    expect(page.locator("input")).to_have_value("Synthetic")
    expect(page.locator("[data-e2e-cursor]")).to_have_count(0)
