"""Render the two plotted states from the built page as its social preview (Playwright Chromium)."""
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 630}, color_scheme="light")
        page.goto((ROOT / "index.html").as_uri(), wait_until="load")
        page.evaluate("""() => {
          const pair = document.querySelector('.overview-pair').cloneNode(true);
          const title = document.createElement('h1');
          title.textContent = document.querySelector('.hero h1').textContent;
          const model = document.createElement('p');
          model.textContent = 'statescope · Qwen3.5-0.8B';
          const key = document.createElement('p');
          key.className = 'legend';
          key.textContent = 'Each curve is one line width. Gold marks the last ten characters.';
          document.body.replaceChildren(model, title, pair, key);
        }""")
        page.add_style_tag(content="""
          body { box-sizing: border-box; padding: 34px 64px; width: 1200px; height: 630px; }
          body > p { margin: 0; font-size: 22px; color: var(--muted); }
          body > h1 { margin: 12px 0 24px; font-size: 52px; line-height: 1.06; letter-spacing: -.035em; }
          .overview-pair { gap: 36px; }
          .overview-pair > div { background: var(--paper); border-radius: 12px; padding: 17px 22px; }
          .overview-pair h3 { font-size: 23px; }
          .overview-pair svg { width: 100%; height: 216px; }
          body > .legend { margin-top: 20px; }
        """)
        page.evaluate("document.fonts.ready")
        page.screenshot(path=ROOT / "assets" / "og-card.png")
        browser.close()


if __name__ == "__main__":
    main()
