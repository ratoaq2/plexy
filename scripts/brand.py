"""Make the plexy logo, icon, and social preview card.

Run from the repository root:

    uv run --no-project --with fonttools --with resvg-py python scripts/brand.py

It writes these files to docs/images/:

- logo-light.svg, logo-dark.svg, logo-light.png, logo-dark.png: the README header (GitHub light and dark mode)
- icon.svg, icon-32.png ... icon-512.png: favicon and avatar
- social.png: the GitHub social preview. Upload it by hand: Settings, General, Social preview.

The tagline below the word mark is the `description` in pyproject.toml. The README `alt` text has the same
sentence. Change both together.

All text is drawn as paths from scripts/brand/Lexend.ttf (SIL Open Font License, see scripts/brand/OFL.txt).
So the output does not depend on the fonts of the computer.

The colors of the icon are the Plex gray and the Plex orange. plexy is not an official Plex product. Keep the
orange a small accent, and do not use the Plex chevron or the Plex font.

The plexy name, logo, and icon are not covered by the MIT license of this repository.
"""

import tomllib
from pathlib import Path

import resvg_py
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"
FONT = ROOT / "scripts" / "brand" / "Lexend.ttf"
TAGLINE = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["description"]

GRAY, ORANGE, WHITE = "#282a2d", "#e5a00d", "#f4f4f5"
LIGHT, DARK = "#1f2328", "#f0f6fc"  # GitHub text colors
GITHUB_DARK = "#0d1117"


def font(weight: int) -> TTFont:
    f = TTFont(FONT)
    return instantiateVariableFont(f, {a.axisTag: weight if a.axisTag == "wght" else None for a in f["fvar"].axes})


def text_path(f: TTFont, text: str, height: float) -> tuple[str, float]:
    """Text as SVG path data, from x=0 and y=0. The glyph box of 'plexy' in this font is `height` high.

    Returns (d, width)."""
    glyphs, cmap = f.getGlyphSet(), f.getBestCmap()
    bounds, x = BoundsPen(glyphs), 0.0
    for ch in "plexy":
        glyphs[cmap[ord(ch)]].draw(TransformPen(bounds, (1, 0, 0, 1, x, 0)))
        x += glyphs[cmap[ord(ch)]].width
    assert bounds.bounds is not None
    _, y_min, _, y_max = bounds.bounds
    scale = height / (y_max - y_min)
    pen, x = SVGPathPen(glyphs), 0.0
    for ch in text:
        glyph = glyphs[cmap[ord(ch)]]
        glyph.draw(TransformPen(pen, (scale, 0, 0, -scale, x, y_max * scale)))
        x += glyph.width * scale
    return pen.getCommands(), x


def icon() -> str:
    """Two rows: a speaker with the audio track, a subtitle box with the subtitle track (orange)."""
    return (
        f'<rect x="1" y="1" width="98" height="98" rx="21" fill="{GRAY}" stroke="#ffffff" stroke-opacity=".18" '
        'stroke-width="2"/>'
        f'<path d="M14 25 h7 l9 -8 v24 l-9 -8 h-7 Z" fill="{WHITE}"/>'
        f'<rect x="40" y="26" width="48" height="16" rx="8" fill="{WHITE}"/>'
        f'<rect x="12" y="59" width="20" height="16" rx="3.5" fill="none" stroke="{WHITE}" stroke-width="4"/>'
        f'<rect x="40" y="59" width="34" height="16" rx="8" fill="{ORANGE}"/>'
    )


def logo(color: str, word: tuple[str, float], tagline: tuple[str, float]) -> tuple[str, float]:
    """The icon, then the word mark with the tagline below it. Returns (SVG body, width). The height is 100."""
    body = (
        f'<svg width="100" height="100" viewBox="0 0 100 100">{icon()}</svg>'
        f'<path transform="translate(124 0)" d="{word[0]}" fill="{color}"/>'
        f'<path transform="translate(124 79)" d="{tagline[0]}" fill="{color}" fill-opacity=".75"/>'
    )
    return body, 124 + max(word[1], tagline[1])


def svg(body: str, w: float, h: float) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.1f} {h:.1f}" width="{w:.0f}" height="{h:.0f}">'
        f"{body}</svg>"
    )


def png(name: str, content: str, w: float, h: float) -> None:
    data = resvg_py.svg_to_bytes(svg_string=content, width=round(w), height=round(h), skip_system_fonts=True)
    (OUT / name).write_bytes(bytes(data))


def main() -> None:
    word = text_path(font(700), "plexy", 62)
    tagline = text_path(font(400), TAGLINE, 21)

    for name, color in (("logo-light", LIGHT), ("logo-dark", DARK)):
        body, w = logo(color, word, tagline)
        (OUT / f"{name}.svg").write_text(svg(body, w, 100) + "\n", encoding="utf-8")
        png(f"{name}.png", svg(body, w, 100), w * 4, 400)

    (OUT / "icon.svg").write_text(svg(icon(), 100, 100) + "\n", encoding="utf-8")
    for size in (32, 64, 256, 512):
        png(f"icon-{size}.png", svg(icon(), 100, 100), size, size)

    body, w = logo(DARK, word, tagline)
    scale = 2.6
    card = (
        f'<rect width="1280" height="640" fill="{GITHUB_DARK}"/>'
        f'<g transform="translate({(1280 - w * scale) / 2:.1f} {320 - 50 * scale:.1f}) scale({scale})">{body}</g>'
    )
    png("social.png", svg(card, 1280, 640), 1280, 640)


if __name__ == "__main__":
    main()
