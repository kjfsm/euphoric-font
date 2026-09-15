#!/usr/bin/env python3
"""sources/ のグリフシートから UFO を作る。

グリフシートは同じ名前の PNG と txt の組である。PNG には文字を横1列に並べ、
txt にはその並び順どおりに文字を1行で書く。文字の区切りは、点のない列で決まる。
"""

import re
import sys
from pathlib import Path

import ufoLib2
import yaml
from fontTools.agl import UV2AGL
from PIL import Image

SOURCES = Path("sources")
CONFIG = SOURCES / "config.yaml"
OUTPUT = SOURCES / "EuphoricPixel-Regular.ufo"

INK = (0, 0, 0, 255)
PAPER = (255, 255, 255)


class SheetError(Exception):
    pass


def read_bitmap(path, height):
    image = Image.open(path).convert("RGBA")
    if image.height != height:
        raise SheetError(f"{path}: 高さが {image.height}px ある。{height}px にする")
    bitmap = []
    for y in range(image.height):
        row = []
        for x in range(image.width):
            pixel = image.getpixel((x, y))
            if pixel == INK:
                row.append(True)
            elif pixel[3] == 0 or pixel[:3] == PAPER:
                row.append(False)
            else:
                raise SheetError(
                    f"{path}: ({x}, {y}) の色 {pixel} は黒でも白でも透明でもない"
                )
        bitmap.append(row)
    return bitmap


def read_chars(path):
    chars = path.read_text(encoding="utf-8").rstrip("\r\n")
    if not chars or any(c.isspace() for c in chars):
        raise SheetError(f"{path}: 空白を入れずに、文字を1行に並べる")
    return chars


def split_columns(bitmap):
    filled = [any(row[x] for row in bitmap) for x in range(len(bitmap[0]))]
    spans, start = [], None
    for x, f in enumerate(filled + [False]):
        if f and start is None:
            start = x
        elif not f and start is not None:
            spans.append((start, x))
            start = None
    return spans


def trace(dots):
    """ドットの集合 {(x, y)}(y は上向き)を、隣り合うドットをつなげた輪郭にする。

    ドットごとの正方形のままだと、アンチエイリアスで継ぎ目が見える。外周は反時計回り、
    穴は時計回り(UFO の向き)になる。
    """
    edges = set()
    for x, y in dots:
        corners = [(x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1)]
        for a, b in zip(corners, corners[1:] + corners[:1]):
            if (b, a) in edges:
                edges.remove((b, a))
            else:
                edges.add((a, b))
    outgoing = {}
    for a, b in sorted(edges):
        outgoing.setdefault(a, []).append(b)

    contours = []
    while outgoing:
        # 最も左下の点は、斜めに接する2つのドットの角にはならない。そのため、
        # 最初の1辺は向きを見ずに選んでよい。
        start = min(outgoing)
        contour, point, direction = [start], start, None
        while True:
            target = take_edge(outgoing, point, direction)
            direction = (target[0] - point[0], target[1] - point[1])
            point = target
            if point == start:
                break
            contour.append(point)
        contours.append(drop_collinear(contour))
    return contours


def take_edge(outgoing, point, direction):
    # 斜めに接する2つのドットの角では出ていく辺が2本ある。左に曲がる辺を選ぶと、
    # 2つのドットが1点で接した8の字の輪郭にならず、別々の輪郭に分かれる。
    targets = outgoing[point]
    target = targets[0]
    if len(targets) > 1 and direction:
        left = (-direction[1], direction[0])
        for t in targets:
            if (t[0] - point[0], t[1] - point[1]) == left:
                target = t
    targets.remove(target)
    if not targets:
        del outgoing[point]
    return target


def drop_collinear(points):
    kept = []
    for i, p in enumerate(points):
        a, b = points[i - 1], points[(i + 1) % len(points)]
        if (p[0] - a[0]) * (b[1] - p[1]) != (p[1] - a[1]) * (b[0] - p[0]):
            kept.append(p)
    return kept


def draw(glyph, dots, unit):
    pen = glyph.getPen()
    for contour in trace(dots):
        pen.moveTo((contour[0][0] * unit, contour[0][1] * unit))
        for x, y in contour[1:]:
            pen.lineTo((x * unit, y * unit))
        pen.closePath()


def glyph_name(char):
    return UV2AGL.get(ord(char), f"uni{ord(char):04X}")


def set_info(info, config, meta):
    # 引用符なしで書くと YAML は数値として読み、0.010 は 0.01 になる。
    m = re.fullmatch(r"(\d+)\.(\d{3})", str(meta["version"]))
    if not m:
        raise SheetError(f'{CONFIG}: version は "0.001" のように小数3桁を引用符で囲んで書く')
    unit = meta["unitsPerDot"]
    ascender = meta["ascender"] * unit
    descender = (meta["ascender"] - meta["dotsPerEm"]) * unit

    info.familyName = config["familyName"]
    info.styleName = meta["styleName"]
    info.versionMajor, info.versionMinor = int(m[1]), int(m[2])
    info.openTypeNameDesigner = meta["designer"]
    info.copyright = meta["copyright"]
    info.openTypeNameLicense = meta["license"]
    info.openTypeNameLicenseURL = meta["licenseURL"]
    info.unitsPerEm = meta["dotsPerEm"] * unit
    info.ascender, info.descender = ascender, descender
    info.capHeight = meta["capHeight"] * unit
    info.xHeight = meta["xHeight"] * unit
    info.openTypeHheaAscender, info.openTypeHheaDescender = ascender, descender
    info.openTypeHheaLineGap = 0
    info.openTypeOS2TypoAscender, info.openTypeOS2TypoDescender = ascender, descender
    info.openTypeOS2TypoLineGap = 0
    info.openTypeOS2WinAscent, info.openTypeOS2WinDescent = ascender, -descender
    # USE_TYPO_METRICS。ブラウザや OS で行の高さを揃える。
    info.openTypeOS2Selection = [7]
    # 下へはみ出す行(g や y)に重ならないよう、その1ドット下に引く。
    info.postscriptUnderlinePosition = -unit
    info.postscriptUnderlineThickness = unit
    info.openTypeOS2Type = []


def build(config):
    meta = config["localMetadata"]
    unit = meta["unitsPerDot"]
    above = meta["rowsAboveBaseline"]
    spacing = meta["letterSpacing"]

    font = ufoLib2.Font()
    set_info(font.info, config, meta)

    # .notdef の幅は、多くの文字と同じ3ドットにする。
    notdef = font.newGlyph(".notdef")
    notdef.width = (3 + spacing) * unit
    top = meta["capHeight"] - 1
    draw(notdef, {(x, y) for x in range(3) for y in range(top + 1) if x != 1 or y in (0, top)}, unit)
    for char in (" ", "\u00a0"):
        glyph = font.newGlyph(glyph_name(char))
        glyph.unicodes = [ord(char)]
        glyph.width = (meta["spaceWidth"] + spacing) * unit

    defined_in = {}
    for sheet in meta["sheets"]:
        png, txt = SOURCES / f"{sheet}.png", SOURCES / f"{sheet}.txt"
        bitmap = read_bitmap(png, above + meta["rowsBelowBaseline"])
        chars = read_chars(txt)
        spans = split_columns(bitmap)
        if len(spans) != len(chars):
            raise SheetError(
                f"{png}: 点のない列で切ると {len(spans)} 文字になるが、"
                f"{txt} には {len(chars)} 文字ある"
            )
        for char, (start, end) in zip(chars, spans):
            if char in defined_in:
                raise SheetError(f"{txt}: {char!r} は {defined_in[char]} にもある")
            defined_in[char] = txt
            glyph = font.newGlyph(glyph_name(char))
            glyph.unicodes = [ord(char)]
            glyph.width = (end - start + spacing) * unit
            dots = {
                (x - start, above - 1 - y)
                for y, row in enumerate(bitmap)
                for x in range(start, end)
                if row[x]
            }
            draw(glyph, dots, unit)

    font.lib["public.glyphOrder"] = list(font.keys())
    return font


def main():
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    try:
        font = build(config)
    except SheetError as e:
        sys.exit(f"png2ufo: {e}")
    font.save(OUTPUT, overwrite=True)
    print(f"png2ufo: {len(font)} グリフを {OUTPUT} に書いた")


if __name__ == "__main__":
    main()
