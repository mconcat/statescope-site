"""Checks on the built page that need no browser.

    python -B tools/lint_page.py --repo <statescope checkout>

1. Numbers: every word of the page's text that holds a digit must occur in the source files (README.md, the model card, the
   demonstration script, the three generated tables) or among the values of the generated data files. A number that is neither is
   reported and the script fails.
2. Sentences: lists the sentences of the page's prose that are not word-for-word in the source files, for reading by eye.
3. Hygiene: no machine path, no external resource, no leftover placeholder in any file of the site.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = "release/qwen35-08b-v2"
SOURCES = ["README.md", f"{REL}/MODEL_CARD.md", "demo/line_count.py", f"{REL}/layers_table.md", f"{REL}/line_count_table.md",
           f"{REL}/line_count_link_table.md"]
SOURCES_4B = ["release/qwen35-4b/layers_table.md", "release/qwen35-4b/MODEL_CARD.md"]                            # read when the page has the Qwen3.5-4B section
PAGE_DATA = ["facts.json", "layers.json", "splice.json", "demo.json"]          # the item texts are data, not claims of the page
OPTIONAL_DATA = ["layers-4b.json", "steer.json", "used-4b.json", "examples-4b.json", "count-curve.json"]
REFERENCES = os.path.join("tools", "references.json")                          # bibliographic data of the works the page refers to
ALLOWED_LINKS = ("https://github.com/mconcat/statescope", "https://huggingface.co/mconcat/statescope-qwen3.5-0.8b",
                 "https://huggingface.co/mconcat/statescope-qwen3.5-4b", "https://arxiv.org/abs/2601.04480", "https://arxiv.org/abs/2502.20332",
                 "https://transformer-circuits.pub/2025/bulk-update/index.html", "https://arxiv.org/abs/2505.21364",
                 "https://arxiv.org/abs/2611.13270")
STRIP = ".,;:!?()[]{}\"'`<>‘’“”"


class Text(HTMLParser):
    """the visible text of a page, the text alternatives in its attributes, and its prose blocks.
    An element with the attribute data-items holds text of the demonstration items (tokens and character counts): it is data, not
    a claim of the page, and tools/verify_browser.py compares it with the item files."""
    VOID = {"meta", "link", "br", "img", "input", "hr", "source", "wbr", "area", "base", "col", "embed", "track"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip, self.parts, self.blocks, self.block, self.links = 0, [], [], None, []
        self.depth, self.items_at = 0, None

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.depth += 1
            if self.items_at is None and any(key == "data-items" for key, _ in attrs):
                self.items_at = self.depth
                self.skip += 1
        if tag in ("script", "style"):
            self.skip += 1
        described = tag == "meta" and dict(attrs).get("name") == "description"
        for key, value in attrs:
            if value and (key in ("aria-label", "alt", "title") or (key == "content" and described)):
                self.parts.append(value)
            if key in ("href", "src") and value:
                self.links.append(value)
        if tag in ("p", "li", "dd", "figcaption") and self.block is None:
            self.block = []

    def handle_endtag(self, tag):
        if tag not in self.VOID:
            if self.items_at == self.depth:
                self.items_at = None
                self.skip -= 1
            self.depth -= 1
        if tag in ("script", "style"):
            self.skip -= 1
        if tag in ("p", "li", "dd", "figcaption") and self.block is not None:
            self.blocks.append(" ".join("".join(self.block).split()))
            self.block = None

    def handle_data(self, data):
        if self.skip:
            return
        self.parts.append(data)
        if self.block is not None:
            self.block.append(data)


def words_with_digits(text: str) -> list[str]:
    out = []
    for word in text.split():
        word = word.strip(STRIP)
        if word.endswith(("'s", "’s")):
            word = word[:-2]
        if any(ch in "0123456789" for ch in word):                            # a superscript, as in "R²", is not a number
            out.append(word)
    return out


def occurs(word: str, corpus: str) -> bool:
    """the word stands in the corpus as a whole number or name, not as a piece of a longer one.
    "layer-7" is the sources' "layer 7", and "2.5%" their "2.5 %"."""
    def whole(w: str) -> bool:
        return re.search(r"(?<![A-Za-z0-9])(?<!\d[.,])" + re.escape(w) + r"(?![A-Za-z0-9]|[.,]\d)", corpus) is not None
    if whole(word):
        return True
    m = re.fullmatch(r"(layer)-(\d+)", word)
    if m:
        return whole(f"{m.group(1)} {m.group(2)}")
    m = re.fullmatch(r"([\d.]+)%", word)
    return bool(m) and whole(f"{m.group(1)} %")


def data_values(names: list[str]) -> str:
    values = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                values.append(str(k))
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, bool) or o is None:
            pass
        elif isinstance(o, int):
            values.extend([str(o), f"{o:,}"])
        else:
            values.append(str(o))

    for name in names:
        with open(os.path.join(HERE, "data", name)) as f:
            walk(json.load(f))
    with open(os.path.join(HERE, REFERENCES)) as f:
        walk(json.load(f))
    return "\n".join(values)


def has(name: str) -> bool:
    return os.path.exists(os.path.join(HERE, "data", name))


def source_text(repo: str) -> str:
    out = []
    paths = [os.path.join(repo, rel) for rel in SOURCES]
    if has("layers-4b.json"):
        paths += [os.path.join(repo, rel) for rel in SOURCES_4B]
    for path in paths:
        with open(path) as f:
            out.append(f.read())
    return "\n".join(out)


def page_data() -> list[str]:
    return PAGE_DATA + [name for name in OPTIONAL_DATA if has(name)]


def untraceable(text: str, corpus: str) -> list[str]:
    return sorted({w for w in words_with_digits(text) if not occurs(w, corpus)})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    args = ap.parse_args()
    failed = False
    with open(os.path.join(HERE, "index.html")) as f:
        raw = f.read()
    parser = Text()
    parser.feed(re.sub(r"<!--.*?-->", "", raw, flags=re.S))
    page_text = "\n".join(parser.parts)
    sources = source_text(args.repo)
    corpus = sources + "\n" + data_values(page_data())

    words = words_with_digits(page_text)
    bad = untraceable(page_text, corpus)
    print(f"1. numbers: {len(words)} words with digits on the page ({len(set(words))} distinct); not traceable: {len(bad)}")
    for w in bad:
        print("   NOT TRACEABLE:", w)
    failed |= bool(bad)

    with open(os.path.join(HERE, "tools", "page.template.html")) as f:
        template = re.sub(r"\{\{[A-Za-z0-9_.:/|, -]+\}\}", "\u00a7", re.sub(r"<!--.*?-->", "", f.read(), flags=re.S))
    typed = Text()
    typed.feed(template)
    typed_words = sorted(set(words_with_digits("\n".join(typed.parts))))
    print(f"   typed in the template, not filled from a data file ({len(typed_words)} distinct; names of layers, sites, cells, models, rules and "
          "licences, bin edges and widths named in the README, and the terms 'position 0', 'share of 0', 'share of 1'): " + ", ".join(typed_words))

    flat = " ".join(sources.replace("`", "").split())
    sentences = []
    for block in parser.blocks:
        sentences += [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z`])", block) if s.strip()]
    own = [s for s in sentences if s.replace("`", "") not in flat]
    print(f"2. sentences: {len(sentences)} in the prose; {len(sentences) - len(own)} word for word in the sources; {len(own)} are the page's own wording:")
    for s in own:
        print("   -", s)

    problems = []
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for name in files:
            path = os.path.join(root, name)
            rel = os.path.relpath(path, HERE)
            if rel.startswith(os.path.join("assets", "fonts")) or name.endswith((".woff2", ".png")):
                continue
            with open(path, errors="replace") as f:
                text = f.read()
            for needle in ("/home/", "/mnt/", "/tmp/", "{{"):
                if needle in text and not rel.startswith("tools"):
                    problems.append(f"{rel}: contains {needle!r}")
            if not rel.startswith("tools") and rel != "README.md":
                for url in re.findall(r"https?://[^\s\"'<>)]+", text):
                    if not url.startswith(ALLOWED_LINKS) and not url.startswith("http://www.w3.org/"):
                        problems.append(f"{rel}: external address {url}")
    for link in parser.links:
        if link.startswith(("http://", "https://", "//")) and not link.startswith(ALLOWED_LINKS):
            problems.append(f"index.html: link or resource {link}")
        if link.startswith("/"):
            problems.append(f"index.html: root-absolute address {link}")
        if not link.startswith(("http", "#")) and not os.path.exists(os.path.join(HERE, link)):
            problems.append(f"index.html: missing file {link}")
    print(f"3. hygiene: {len(problems)} problems; {len(parser.links)} links and resources checked")
    for p in problems:
        print("   PROBLEM:", p)
    failed |= bool(problems)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
