"""Dessine le logo (broutille.png) et l'icône (broutille.ico) : une carapace vue de dessus, avec un brin d'herbe."""

import math

from PIL import Image, ImageDraw

T = 1024
VERT, CARAPACE, ECAILLE, TRAIT, PEAU = (127, 185, 80), (92, 74, 42), (217, 164, 65), (42, 32, 16), (150, 165, 95)


def hexagone(cx, cy, r, angle=0.0):
    return [(cx + r * math.cos(angle + i * math.pi / 3), cy + r * math.sin(angle + i * math.pi / 3)) for i in range(6)]


def main():
    img = Image.new("RGBA", (T * 2, T * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    e = 2
    # fond rond
    d.ellipse([20 * e, 20 * e, (T - 20) * e, (T - 20) * e], fill=(27, 33, 25, 255))
    cx, cy = T // 2 * e, 545 * e
    # tête et pattes, sous la carapace
    d.ellipse([cx - 80 * e, cy - 395 * e, cx + 80 * e, cy - 205 * e], fill=PEAU)
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        x, y = cx + sx * 245 * e, cy + sy * 210 * e
        d.ellipse([x - 75 * e, y - 60 * e, x + 75 * e, y + 60 * e], fill=PEAU)
    d.ellipse([cx - 28 * e, cy + 300 * e, cx + 28 * e, cy + 360 * e], fill=PEAU)
    # carapace
    d.ellipse([cx - 265 * e, cy - 310 * e, cx + 265 * e, cy + 310 * e], fill=CARAPACE, outline=TRAIT, width=16 * e)
    # écailles : motif rayonné d'une tortue radiée
    centres = [(0, 0), (0, -185), (0, 185), (-155, -92), (155, -92), (-155, 92), (155, 92)]
    for x, y in centres:
        px, py = cx + x * e, cy + y * e
        d.polygon(hexagone(px, py, 88 * e, math.pi / 6), fill=TRAIT)
        d.polygon(hexagone(px, py, 72 * e, math.pi / 6), fill=(70, 55, 30))
        for i in range(6):
            a = i * math.pi / 3 + math.pi / 6
            d.line([px, py, px + 62 * e * math.cos(a), py + 62 * e * math.sin(a)], fill=ECAILLE, width=11 * e)
        d.ellipse([px - 15 * e, py - 15 * e, px + 15 * e, py + 15 * e], fill=ECAILLE)
    # brin d'herbe à la bouche
    bx, by = cx + 42 * e, cy - 375 * e
    d.polygon([(bx, by), (bx + 150 * e, by - 120 * e), (bx + 40 * e, by + 12 * e)], fill=VERT)
    img = img.resize((T, T), Image.LANCZOS)
    img.save("broutille.png")
    img.save("broutille.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()
