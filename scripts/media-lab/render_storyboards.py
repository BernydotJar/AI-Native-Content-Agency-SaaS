#!/usr/bin/env python3
"""Zero-API-cost animated STORYBOARDS, not generative AI footage.

Requires Pillow 12 and FFmpeg. Generates two fully original vector-animation
concepts so motion/encoding/visual QA are reproducible without a GPU.
"""
from __future__ import annotations

import argparse
import math
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, LENGTH = 720, 1280, 24, 6
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = {size: ImageFont.truetype(FONT_BOLD, size) for size in (18, 20, 22, 26, 30, 38, 50, 64, 78)}
REG = {size: ImageFont.truetype(FONT_REG, size) for size in (16, 18, 20, 22, 26)}
TAU = math.tau


def clamp(n, lo=0., hi=1.):
    return min(hi, max(lo, n))


def ease(n):
    n = clamp(n)
    return n*n*(3-2*n)


def lerp(a, b, p):
    return a + (b - a) * p


def hexblend(c1, c2, p):
    return tuple(round(lerp(c1[i], c2[i], p)) for i in range(3))


def background(top, bottom, accent):
    image = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(image)
    for y in range(H):
        draw.line((0, y, W, y), fill=hexblend(top, bottom, y/H))
    glow = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(glow)
    d.ellipse((80, 170, 860, 1050), fill=(*accent, 88))
    glow = glow.filter(ImageFilter.GaussianBlur(115))
    image = Image.alpha_composite(image.convert("RGBA"), glow)
    grid = ImageDraw.Draw(image, "RGBA")
    for x in range(36, W, 72):
        grid.line((x, 110, x, 1150), fill=(215, 220, 255, 8), width=1)
    for y in range(120, 1150, 72):
        grid.line((36, y, W-36, y), fill=(215, 220, 255, 8), width=1)
    return image


BG_PASTA = background((5, 17, 33), (43, 19, 36), (198, 63, 91))
BG_AGENCY = background((4, 22, 35), (27, 19, 47), (46, 121, 155))


def heading(draw, eyebrow, title1, title2, accent):
    draw.line((50, 98, 670, 98), fill=(*accent, 180), width=2)
    draw.text((52, 135), eyebrow, font=BOLD[20], fill=(*accent, 240))
    draw.text((48, 195), title1, font=BOLD[64], fill=(245, 247, 252, 255))
    draw.text((48, 270), title2, font=BOLD[64], fill=(245, 247, 252, 255))


def particles(draw, t, accent, count=27):
    for k in range(count):
        x = (k * 137 + (t * (11 + k % 5)) * 2) % (W+60) - 30
        y = 370 + ((k * 89 + t * (9 + k % 4)) % 660)
        radius = 1 + k % 3
        draw.ellipse((x-radius, y-radius, x+radius, y+radius),
                     fill=(*accent, 35 + (k % 6)*9))


def badge(draw, text, left, top, accent):
    width = int(draw.textlength(text, font=BOLD[18])) + 42
    draw.rounded_rectangle((left, top, left+width, top+39),
                           radius=19, fill=(9, 23, 36, 228), outline=(*accent, 165), width=2)
    draw.text((left+21, top+8), text, font=BOLD[18], fill=(244, 249, 252, 255))


def footer(draw, main, minor, accent):
    draw.line((50, 1086, 670, 1086), fill=(*accent, 120), width=2)
    draw.text((50, 1122), main, font=BOLD[22], fill=(234, 238, 245, 255))
    draw.text((50, 1167), minor, font=REG[18], fill=(191, 201, 217, 255))


def pasta_frame(t):
    im = BG_PASTA.copy()
    d = ImageDraw.Draw(im, "RGBA")
    accent = (255, 188, 104)
    particles(d, t, accent)
    heading(d, "CAMPAIGNOS / MOTION BENCHMARK", "THE PASTA", "TEST.", accent)
    badge(d, "FICTIONAL ACTOR / ANIMATED", 51, 358, accent)

    # One fictional illustrated character, no public-figure likeness.
    # Face profile and eye use intentionally stable geometry.
    d.ellipse((465, 438, 810, 860), fill=(170, 106, 82, 255))
    d.ellipse((480, 455, 795, 823), fill=(208, 139, 104, 255))
    d.pieslice((477, 431, 809, 755), 178, 345, fill=(32, 31, 48, 255))
    d.ellipse((530, 595, 548, 610), fill=(23, 29, 38, 255))
    d.arc((493, 654, 558, 698), 190, 340, fill=(72, 42, 42, 255), width=5)
    d.line(((481, 650), (459, 671), (489, 681)), fill=(192, 117, 89, 255), width=7)

    # Layered plate and animated spaghetti strands.
    d.ellipse((112, 710, 592, 1042), fill=(7, 14, 28, 110))
    d.ellipse((104, 704, 598, 1025), fill=(234, 230, 219, 255))
    d.ellipse((127, 721, 573, 1005), outline=(180, 170, 168, 255), width=15)
    d.ellipse((160, 752, 543, 972), fill=(134, 43, 45, 255))
    for i in range(19):
        pts = []
        for j in range(28):
            a = TAU * j / 27 + i * 0.48 + t*0.13
            radius = 37 + i*4.8 + 11 * math.sin(3*a + i)
            x = 356 + radius * math.cos(a)
            y = 864 + radius * 0.51 * math.sin(a)
            pts.append((x, y))
        d.line(pts, fill=(243+(i%3)*3, 187+(i%4)*6, 90+(i%5)*5, 240),
               width=4+(i%2), joint="curve")

    progress = ease((t-0.85)/3.6)
    after_bite = ease((t-4.30)/1.20)
    fx = lerp(349, 480, progress) + after_bite*11*math.sin(t*5.0)
    fy = lerp(820, 678, progress) + after_bite*11*math.cos(t*5.0)
    d.line(((fx+10, fy-5), (fx+106, fy-230)), fill=(37, 37, 48, 120), width=21)
    d.line(((fx+10, fy-5), (fx+106, fy-230)), fill=(218, 225, 233, 255), width=14)
    d.ellipse((fx-14, fy-37, fx+24, fy+38), outline=(224, 230, 236, 255), width=8)
    for offset in (-12, -4, 4, 12):
        d.line(((fx+offset, fy-43), (fx+offset, fy-76)),
               fill=(234, 237, 241, 255), width=5)
    for strand in range(5):
        pts = []
        for j in range(27):
            v = j/26
            pts.append((fx + (strand-2)*8 + math.sin(v*TAU*2+strand)*9,
                        fy+10 + v*(38+strand*13)*(1-progress*0.6)))
        d.line(pts, fill=(255, 214, 119, 255), width=4)
    # Hand silhouette follows fork: continuity acceptance target.
    hx, hy = fx+124, fy-226
    d.line(((hx+80, hy+105), (hx, hy)), fill=(185, 119, 88, 255), width=38)
    d.ellipse((hx-26, hy-30, hx+45, hy+27), fill=(208, 145, 109, 255))

    d.rounded_rectangle((49, 1010, 671, 1065), radius=18,
                        fill=(6, 12, 26, 205), outline=(*accent, 75), width=1)
    d.text((75, 1024), "Motion / hand / fork / mouth", font=BOLD[20],
           fill=(255, 235, 204, 255))
    footer(d, "STORYBOARD TEST / NO REAL LIKENESS",
           "Generated locally from original illustration", accent)
    d.line((52, 998, 52 + int(616*t/LENGTH), 998), fill=(*accent, 235), width=6)
    return im


def agency_frame(t):
    im = BG_AGENCY.copy()
    d = ImageDraw.Draw(im, "RGBA")
    accent = (118, 229, 225)
    particles(d, t, accent, 36)
    heading(d, "CAMPAIGNOS / CREATIVE ENGINE", "ONE IDEA.", "EIGHT AGENTS.", accent)
    badge(d, "AI NATIVE / HUMAN GOVERNED", 51, 358, accent)

    cx, cy = 357, 735
    labels = ["CEO", "RESEARCH", "STRATEGY", "GROWTH",
              "WRITER", "MEDIA", "RISK", "PUBLISH"]
    coords = []
    for i, label in enumerate(labels):
        a = (i/8)*TAU - math.pi/2 + math.sin(t*0.35)*0.09
        x = cx + 242*math.cos(a)
        y = cy + 205*math.sin(a)
        coords.append((x, y))
    phase = (t*2.1) % 8
    for idx, (x, y) in enumerate(coords):
        active = idx == int(phase)
        d.line(((cx,cy),(x,y)), fill=(*accent, 160 if active else 42),
               width=4 if active else 2)
    d.ellipse((cx-119, cy-119, cx+119,cy+119), fill=(6, 31, 47, 225),
              outline=(*accent, 175), width=5)
    d.ellipse((cx-96, cy-96, cx+96,cy+96), outline=(*accent, 60), width=3)
    d.text((cx, cy-41), "AI", font=BOLD[78], anchor="mt",
           fill=(248, 255, 255, 255))
    d.text((cx, cy+55), "WAR ROOM", font=BOLD[18], anchor="mm",
           fill=(*accent, 255))

    for idx, (x,y) in enumerate(coords):
        active = idx == int(phase)
        x0, y0 = x-77, y-25
        d.rounded_rectangle((x0+5, y0+7, x0+159, y0+55), radius=17,
                            fill=(2, 12, 25, 75))
        d.rounded_rectangle((x0, y0, x0+154, y0+49), radius=14,
                            fill=(12, 43, 61, 245), outline=(*accent, 210 if active else 62),
                            width=3 if active else 1)
        font = BOLD[18] if len(labels[idx]) > 7 else BOLD[20]
        d.text((x, y), labels[idx], font=font, anchor="mm",
               fill=(248, 255, 255, 255) if active else (196, 226, 230, 255))

    d.rounded_rectangle((50, 1028, 672, 1077), radius=15,
                        fill=(6, 30, 42, 210), outline=(*accent, 100), width=2)
    labels_bottom = ["SCRIPT", "VISUAL", "REVIEW"]
    for i, label in enumerate(labels_bottom):
        d.text((80 + i*196, 1042), label, font=BOLD[18],
               fill=(*accent, 255))
    footer(d, "BRIEF  /  BUILD  /  GREENLIGHT",
           "Visual prototype / no external publishing", accent)
    d.line((52, 1006, 52 + int(616*t/LENGTH), 1006), fill=(*accent, 235), width=7)
    return im


def wav_soundbed(path):
    import struct
    sr = 48000
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        buf = bytearray()
        for i in range(sr*LENGTH):
            t = i/sr
            # Original generated ambient minor chord with gentle rhythm.
            envelope = min(1, t/0.38) * min(1, (LENGTH-t)/0.6)
            pulse = 0.66 + 0.34 * (0.5+0.5*math.cos(TAU*1.7*t))
            sample = sum(math.sin(TAU*hz*t)*v for hz,v in
                         ((110,0.35),(164.81,0.22),(196,0.16),(220.0,0.10)))
            value = int(32767 * 0.49 * envelope * pulse * sample)
            buf.extend(struct.pack("<h", max(-32768, min(32767,value))))
        f.writeframes(buf)


def render(variant, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    audio = out.parent / "original-ambient-bed.wav"
    wav_soundbed(audio)
    command = [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "-", "-i", str(audio), "-t", str(LENGTH), "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "19", "-g", "48", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out),
    ]
    child = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert child.stdin is not None
        for frame in range(FPS*LENGTH):
            t = frame/FPS
            picture = pasta_frame(t) if variant == "spaghetti" else agency_frame(t)
            fade = min(1.0, t/0.23, (LENGTH-t)/0.23)
            if fade < 1:
                picture = Image.blend(Image.new("RGBA",(W,H),(5,9,20,255)),
                                      picture, max(0, fade))
            child.stdin.write(picture.convert("RGB").tobytes())
        child.stdin.close()
        code = child.wait(timeout=180)
    except BaseException:
        child.kill()
        child.wait()
        raise
    if code:
        err = child.stderr.read().decode("utf-8","replace")[-1100:]
        raise RuntimeError(f"ffmpeg failed: {err}")
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--outdir", type=Path, default=Path("artifacts/media-lab/generated"))
    p.add_argument("--preview-only", action="store_true")
    args = p.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    if args.preview_only:
        pasta_frame(3.3).save(args.outdir / "spaghetti-art-preview.png")
        agency_frame(3.3).save(args.outdir / "campaignos-art-preview.png")
    else:
        for variant in ("spaghetti","campaignos"):
            result = render(variant, args.outdir / f"{variant}-illustrated-storyboard.mp4")
            print(result)


if __name__ == "__main__":
    main()
