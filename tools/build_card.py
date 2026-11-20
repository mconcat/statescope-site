"""Render both opening experiments as the social preview using Playwright Chromium."""
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
          const results = document.querySelector('.result-pair');
          for (const link of results.querySelectorAll('figcaption a')) link.remove();
          document.body.replaceChildren(name, title, results);
        }""")
        page.add_style_tag(content="""
          body { box-sizing: border-box; padding: 38px 48px; width: 1200px; height: 630px; }
          .project-name { font-size: 24px; text-align: left; }
          h1 { margin: 10px 0 28px; font-size: 50px; text-align: left; }
          .result-pair { gap: 20px; }
          .result-pair .result { padding: 20px 24px; }
          .result-model { font-size: 18px; }
          .result h3 { font-size: 25px; margin-bottom: 22px; }
          .result h3 a { text-decoration: none; }
          .result figcaption { font-size: 16px; line-height: 1.35; }
          .result figcaption > b { display: none; }
          .overview-pair svg { height: 100px; }
          .rate-preview > div, .overview-pair h4, .rate-preview h4 { font-size: 18px; }
        """)
        page.evaluate("document.fonts.ready")
        bounds = page.locator(".result-pair").bounding_box()
        assert bounds and bounds["y"] + bounds["height"] <= 630, "Result panels exceed the preview height"
        page.screenshot(path=ROOT / "assets" / "og-card.png")
        browser.close()


if __name__ == "__main__":
    main()
