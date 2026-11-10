#!/usr/bin/env python3
"""Draw the plugin icon: a stick figure beating a dead horse.

Writes .claude-plugin/icon.png, a 1024 px square PNG. Flat line art, thick
black strokes on an off-white square. Needs Pillow. The output is
deterministic, so rerunning this script reproduces the committed PNG.

Run: python scripts/draw-icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
SCALE = 2  # draw at twice the size, then downsample for smooth edges
INK = (17, 17, 17)
PAPER = (247, 244, 236)
STROKE = 34

OUT = Path(__file__).resolve().parent.parent / ".claude-plugin" / "icon.png"


def s(*xy):
    """Scale icon coordinates to the drawing canvas."""
    return [v * SCALE for v in xy]


def line(draw, *points, width=STROKE):
    draw.line(s(*points), fill=INK, width=width * SCALE, joint="curve")
    r = width * SCALE / 2
    for x, y in (points[0:2], points[-2:]):
        draw.ellipse([x * SCALE - r, y * SCALE - r, x * SCALE + r, y * SCALE + r], fill=INK)


def stick_figure(draw):
    # Head.
    draw.ellipse(s(170, 210, 300, 340), outline=INK, width=STROKE * SCALE)
    # Body.
    line(draw, 235, 340, 250, 620)
    # Legs.
    line(draw, 250, 620, 170, 860)
    line(draw, 250, 620, 320, 860)
    # Back arm.
    line(draw, 240, 420, 140, 540)
    # Raised arm, hand above the head.
    line(draw, 240, 410, 340, 300, 370, 170)
    # The stick, raised over the head and angled toward the horse.
    line(draw, 330, 184, 620, 83, width=30)
    # Motion lines by the stick.
    line(draw, 470, 210, 560, 190, width=22)
    line(draw, 440, 270, 530, 270, width=22)
    line(draw, 600, 140, 650, 200, width=22)


def dead_horse(draw):
    # Body, lying on its side.
    draw.ellipse(s(580, 650, 960, 860), outline=INK, width=STROKE * SCALE)
    # Head, resting on the ground against the body.
    draw.ellipse(s(345, 690, 605, 880), outline=INK, width=STROKE * SCALE)
    # X for an eye.
    line(draw, 490, 745, 540, 795, width=22)
    line(draw, 540, 745, 490, 795, width=22)
    # Nostril.
    draw.ellipse(s(385, 800, 413, 828), fill=INK)
    # Ear.
    line(draw, 455, 695, 420, 640, width=26)
    # Stiff legs, sticking straight up.
    for x in (650, 720, 830, 900):
        line(draw, x, 670, x + 10, 450)
    # Tail.
    line(draw, 955, 730, 990, 770, 985, 840, width=26)
    # Ground.
    line(draw, 60, 905, 990, 905, width=24)


def main():
    canvas = Image.new("RGB", (SIZE * SCALE, SIZE * SCALE), PAPER)
    draw = ImageDraw.Draw(canvas)
    stick_figure(draw)
    dead_horse(draw)
    icon = canvas.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    icon.save(OUT, format="PNG", optimize=True)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
