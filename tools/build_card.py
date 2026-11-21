"""Render the counting study’s before-and-after figure as the social preview using Playwright Chromium."""
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 630}, color_scheme="light")
        page.goto((ROOT / "index.html").as_uri(), wait_until="load")
        page.evaluate("""() => {
          const name = document.querySelector('.project-name');
          const title = document.querySelector('.hero h1');
          const results = document.querySelector('#fig-overview');
          for (const link of results.querySelectorAll('figcaption a')) link.remove();
          document.body.replaceChildren(name, title, results);
        }""")
        page.add_style_tag(content="""
          body { box-sizing: border-box; padding: 32px 48px; width: 1200px; height: 630px; }
          .project-name { font-size: 24px; text-align: left; }
          h1 { margin: 10px 0 18px; font-size: 40px; text-align: left; }
          #fig-overview { margin: 0; max-width: none; padding: 18px 26px; }
          .result-model { display: none; }
          .result h3 { margin: 0 0 12px; font-size: 25px; }
          .result h3 a { text-decoration: none; }
          .overview-pair { padding: 0; text-align: center; }
          .overview-pair svg { height: 214px; }
          .overview-pair p, .overview-pair h4 { font-size: 19px; }
          .result figcaption { margin-top: 12px; font-size: 17px; line-height: 1.35; }
          .result figcaption > b { display: none; }
        """)
        page.evaluate("document.fonts.ready")
        bounds = page.locator("#fig-overview").bounding_box()
        assert bounds and bounds["y"] + bounds["height"] <= 630, "Result panels exceed the preview height"
        page.screenshot(path=ROOT / "assets" / "og-card.png")
        browser.close()


if __name__ == "__main__":
    main()
