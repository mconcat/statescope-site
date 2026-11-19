"""Subset the two typefaces of the site to Latin and write them as woff2 into assets/fonts/.

    python tools/build_fonts.py --sans <PretendardVariable.ttf> --mono <GeistMonoVariable.ttf> \
        --sans-license <LICENSE-Pretendard.txt> --mono-license <LICENSE-Geist.txt>

Needs fontTools and brotli. Both typefaces are under the SIL Open Font License 1.1. Pretendard's licence declares Reserved Font
Names, and a subset is a Modified Version, so the subset's internal names are changed to "Site Sans" (OFL clause 3). Geist Mono
declares no Reserved Font Name and keeps its names. The weight axis is kept in both files.
"""
import argparse
import os
import shutil

from fontTools import subset
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "assets", "fonts")
# Basic Latin, Latin-1, and the few symbols the page uses (dashes, quotes, arrows, minus, times, middle dot, ellipsis, comparisons)
UNICODES = (list(range(0x20, 0x7F)) + list(range(0xA0, 0x100))
            + [0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026, 0x2190, 0x2191, 0x2192, 0x2193, 0x2212, 0x00D7, 0x00B7,
               0x2264, 0x2265, 0x2248, 0x25CF, 0x25CB, 0x25C6, 0x2032])
RENAME = "Site Sans"


def make(src: str, dst: str, rename: str | None) -> None:
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["kern", "liga", "calt", "tnum", "zero", "ss01", "case", "ccmp", "locl", "mark", "mkmk"]
    options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14, 16, 17]
    options.notdef_outline = True
    font = subset.load_font(src, options)
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=UNICODES)
    subsetter.subset(font)
    if rename is not None:
        for record in font["name"].names:
            if record.nameID in (1, 16):
                record.string = rename
            elif record.nameID in (3, 4):
                record.string = rename + " (Latin subset)"
            elif record.nameID == 6:
                record.string = rename.replace(" ", "") + "-LatinSubset"
    subset.save_font(font, dst, options)
    check = TTFont(dst)
    names = {r.nameID: r.toUnicode() for r in check["name"].names}
    print(os.path.basename(dst), os.path.getsize(dst), "bytes; family:", names.get(16) or names.get(1),
          "; axes:", [a.axisTag for a in check["fvar"].axes] if "fvar" in check else None,
          "; glyphs:", len(check.getGlyphOrder()))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sans", required=True)
    ap.add_argument("--mono", required=True)
    ap.add_argument("--sans-license", required=True)
    ap.add_argument("--mono-license", required=True)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    make(args.sans, os.path.join(OUT, "site-sans-var.woff2"), RENAME)
    make(args.mono, os.path.join(OUT, "geist-mono-var.woff2"), None)
    shutil.copyfile(args.sans_license, os.path.join(OUT, "LICENSE-Pretendard.txt"))
    shutil.copyfile(args.mono_license, os.path.join(OUT, "LICENSE-Geist.txt"))


if __name__ == "__main__":
    main()
