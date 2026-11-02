"""Create the decorative README animation; it is not a plot of Gaia measurements."""
from __future__ import annotations
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "media" / "research-orbits.gif"
WIDTH, HEIGHT = 1440, 440
FRAMES = 48


def font(size, bold=False):
    names = (["C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if bold else ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    for name in names:
        if Path(name).is_file():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)


def ellipse_point(cx, cy, rx, ry, angle, tilt):
    x, y = rx * math.cos(angle), ry * math.sin(angle)
    return (cx + x * math.cos(tilt) - y * math.sin(tilt), cy + x * math.sin(tilt) + y * math.cos(tilt))


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    base = Image.new("RGB", (WIDTH, HEIGHT), "#08111f")
    draw = ImageDraw.Draw(base)
    for x in range(WIDTH):
        t = x / WIDTH
        draw.line((x, 0, x, HEIGHT), fill=(int(7 + 7*t), int(15 + 19*t), int(29 + 30*t)))
    haze = Image.new("RGBA", base.size)
    h = ImageDraw.Draw(haze)
    h.ellipse((830, -155, 1490, 490), fill=(22, 89, 135, 80))
    h.ellipse((990, 30, 1400, 445), fill=(26, 140, 148, 40))
    haze = haze.filter(ImageFilter.GaussianBlur(110))
    base = Image.alpha_composite(base.convert("RGBA"), haze)
    draw = ImageDraw.Draw(base)
    rng = random.Random(20261102)
    for _ in range(125):
        x, y = rng.randrange(650, WIDTH - 25), rng.randrange(22, HEIGHT - 22)
        radius = rng.choice([1, 1, 1, 2])
        color = rng.choice([(100, 152, 190, 100), (158, 214, 221, 125), (119, 172, 216, 90)])
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=color)
    draw.rounded_rectangle((34, 30, 1406, 410), radius=19, outline=(91, 133, 162, 65), width=1)
    draw.rounded_rectangle((72, 69, 416, 104), radius=17, fill=(24, 63, 81, 220), outline=(74, 153, 169, 120), width=1)
    draw.text((89, 77), "GAIA DR3  /  RESEARCH IN PROGRESS", font=font(15, True), fill=(142, 222, 220, 255), stroke_width=0)
    draw.text((70, 124), "UNIVERSE", font=font(69, True), fill=(244, 249, 253, 255))
    draw.text((70, 201), "SEARCH HARNESS", font=font(57, True), fill=(131, 224, 216, 255))
    draw.text((73, 292), "Real data. Careful review. Open evidence.", font=font(23), fill=(180, 202, 218, 255))
    draw.line((73, 349, 168, 349), fill=(235, 176, 104, 220), width=3)
    draw.text((181, 337), "A FIELD GUIDE TO THE UNKNOWN", font=font(14, True), fill=(133, 166, 187, 255))
    cx, cy, tilt = 1100, 224, -0.25
    orbits = [(270, 110), (210, 78), (150, 49)]
    for rx, ry in orbits:
        points = [ellipse_point(cx, cy, rx, ry, i * 2 * math.pi / 240, tilt) for i in range(241)]
        draw.line(points, fill=(83, 157, 176, 110), width=2)
    draw.line((cx-15, cy, cx+15, cy), fill=(142, 212, 223, 115), width=1)
    draw.line((cx, cy-15, cx, cy+15), fill=(142, 212, 223, 115), width=1)
    for r, col in [(24,(68,170,183,15)),(16,(77,201,205,28)),(8,(120,240,229,85)),(3,(226,255,250,255))]:
        draw.ellipse((cx-r,cy-r,cx+r,cy+r),fill=col)
    frames = []
    for i in range(FRAMES):
        frame = base.copy(); layer = Image.new("RGBA", base.size); d = ImageDraw.Draw(layer)
        t = i * 2 * math.pi / FRAMES
        for rx, ry, phase, direction, color in [(270,110,0.2,1,(120,235,224)),(210,78,2.4,-1,(247,187,112)),(150,49,4.3,1,(139,190,252))]:
            x,y = ellipse_point(cx,cy,rx,ry,direction*t+phase,tilt)
            for r,alpha in [(25,14),(16,25),(10,45),(5,240),(2,255)]:
                d.ellipse((x-r,y-r,x+r,y+r),fill=(*color,alpha))
        frame = Image.alpha_composite(frame,layer).convert("RGB")
        frames.append(frame)
    frames[0].save(OUTPUT, save_all=True, append_images=frames[1:], duration=85, loop=0, optimize=True, disposal=2)
    print(f"Created {OUTPUT.name}: {FRAMES} frames, {OUTPUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
