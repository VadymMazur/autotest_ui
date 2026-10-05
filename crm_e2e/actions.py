"""Optional presentation pacing around Playwright's normal, actionable controls."""

from playwright.sync_api import Locator, Page

from crm_e2e.diagnostics import active_evidence


CURSOR_SCRIPT = r"""
(() => {
  if (window !== window.top || window.__crmE2eCursorInstalled) return;
  window.__crmE2eCursorInstalled = true;
  const mount = () => {
    const cursor = document.createElement('div');
    cursor.dataset.e2eCursor = '';
    cursor.setAttribute('aria-hidden', 'true');
    cursor.style.cssText = 'position:fixed;left:0;top:0;width:28px;height:32px;'
      + 'pointer-events:none;z-index:2147483647;opacity:0;filter:drop-shadow(0 2px 3px #0006)';
    cursor.innerHTML = '<svg width="28" height="32" viewBox="0 0 28 32">'
      + '<path d="M2 2 L2 25 L9 19 L15 30 L20 27 L14 17 L24 16 Z" '
      + 'fill="#2563eb" stroke="white" stroke-width="2" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(cursor);
    const move = (event) => {
      cursor.style.opacity = '1';
      cursor.style.transform = `translate(${event.clientX}px, ${event.clientY}px)`;
    };
    window.addEventListener('mousemove', move, true);
    window.addEventListener('mousedown', (event) => {
      move(event);
      const ring = document.createElement('div');
      ring.dataset.e2eClick = '';
      ring.style.cssText = `position:fixed;left:${event.clientX - 18}px;top:${event.clientY - 18}px;`
        + 'width:36px;height:36px;border:3px solid #2563eb;border-radius:50%;'
        + 'background:#2563eb22;pointer-events:none;z-index:2147483646;box-sizing:border-box';
      document.documentElement.appendChild(ring);
      ring.animate([{transform:'scale(.3)',opacity:1},{transform:'scale(1.8)',opacity:0}],
        {duration:550,easing:'ease-out'}).finished.finally(() => ring.remove());
    }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once:true});
  else mount();
})();
"""


class UiActions:
    def __init__(self, page: Page, visual: bool = False, typing_delay: int = 45):
        self.page = page
        self.visual = visual
        self.typing_delay = typing_delay
        self.position = (24.0, 24.0)
        if visual:
            page.context.add_init_script(CURSOR_SCRIPT)
            page.evaluate(CURSOR_SCRIPT)

    def _describe(self, label: str) -> None:
        evidence = active_evidence.get()
        if evidence:
            evidence.last_action = label

    def _move_to(self, locator: Locator) -> None:
        if not self.visual:
            return
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        if box is None:
            return  # The regular locator action supplies its actionability failure.
        target = (box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        start = self.position
        for index in range(1, 13):
            fraction = index / 12
            self.page.mouse.move(start[0] + (target[0] - start[0]) * fraction,
                                 start[1] + (target[1] - start[1]) * fraction)
            # Presentation pacing only; readiness still uses Playwright assertions.
            self.page.wait_for_timeout(12)
        self.position = target

    def click(self, locator: Locator, label: str) -> None:
        self._describe(label)
        self._move_to(locator)
        locator.click()

    def fill(self, locator: Locator, value: str, label: str) -> None:
        self._describe(label)
        if not self.visual:
            locator.fill(value)
            return
        self._move_to(locator)
        locator.click()
        locator.fill("")
        locator.press_sequentially(value, delay=self.typing_delay)
