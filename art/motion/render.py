#!/usr/bin/env python3
"""Sal title sting — frame-by-frame motion graphic.
Render at 2x (1920x1080), output 960x540 PNG frames."""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1920, 1080          # render size (2x supersample)
OW, OH = 960, 540          # output size
FPS = 30
N = 186                    # 6.2 s

INK    = (58, 42, 90)      # deep purple
MAROON = (107, 31, 43)
GOLD   = (193, 154, 43)
GOLD_HI= (232, 201, 106)
PARCH  = (244, 237, 223)
PARCH_EDGE = (222, 209, 184)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frames")
os.makedirs(OUT, exist_ok=True)

# ---------- easing ----------
def ease_io_cubic(t):  # smooth both ends
    return 4*t*t*t if t < .5 else 1 - pow(-2*t + 2, 3)/2
def ease_out_cubic(t):
    return 1 - pow(1 - t, 3)
def ease_out_back(t, s=1.70158):
    t -= 1
    return 1 + t*t*((s+1)*t + s)
def win(f, a, b):  # 0..1 progress of frame f inside [a,b)
    if f < a: return 0.0
    if f >= b: return 1.0
    return (f - a) / (b - a)

# ---------- static layers ----------
# background: parchment with radial vignette + grain
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
cx, cy = W/2, H/2
d = np.sqrt(((xx-cx)/(W*0.62))**2 + ((yy-cy)/(H*0.62))**2)
v = np.clip(d, 0, 1)**1.8
bg = np.zeros((H, W, 3), np.float32)
for i in range(3):
    bg[..., i] = PARCH[i]*(1-v) + PARCH_EDGE[i]*v
rng = np.random.default_rng(7)
grain = rng.normal(0, 1, (H, W, 1)).astype(np.float32) * 2.6
bg = np.clip(bg + grain, 0, 255)
BG = Image.fromarray(bg.astype(np.uint8), "RGB").convert("RGBA")

# wordmark "Sal"
font_sal = ImageFont.truetype("PlayfairItalic.ttf", 360)
font_sal.set_variation_by_axes([620])
tmp = Image.new("RGBA", (W, H), (0,0,0,0))
td = ImageDraw.Draw(tmp)
bbox = td.textbbox((0,0), "Sal", font=font_sal)
tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
sal_x = (W - tw)//2 - bbox[0]
sal_y = int(H*0.465) - th//2 - bbox[1]
SAL = Image.new("RGBA", (W, H), (0,0,0,0))
ImageDraw.Draw(SAL).text((sal_x, sal_y), "Sal", font=font_sal, fill=INK+(255,))
sal_alpha = np.asarray(SAL.split()[3], np.float32)
# soft shadow of the wordmark
SH = Image.new("RGBA", (W, H), (0,0,0,0))
ImageDraw.Draw(SH).text((sal_x, sal_y+10), "Sal", font=font_sal, fill=(40,30,60,70))
SH = SH.filter(ImageFilter.GaussianBlur(7))
sh_alpha = np.asarray(SH.split()[3], np.float32)
text_l, text_r = bbox[0]+sal_x, bbox[2]+sal_x   # sweep bounds

# caption "TODAY AT"
font_cap = ImageFont.truetype("Playfair.ttf", 66)
font_cap.set_variation_by_axes([560])
CAP_TEXT = "TODAY AT"
def caption_layer(tracking, alpha):
    layer = Image.new("RGBA", (W, H), (0,0,0,0))
    dr = ImageDraw.Draw(layer)
    widths = [dr.textlength(c, font=font_cap) for c in CAP_TEXT]
    total = sum(widths) + tracking*(len(CAP_TEXT)-1)
    x = (W - total)/2
    y = sal_y - 46
    for c, wd in zip(CAP_TEXT, widths):
        dr.text((x, y), c, font=font_cap, fill=MAROON+(int(alpha*255),))
        x += wd + tracking
    return layer

# gold swash under the wordmark (cubic bezier, calligraphic taper)
def bezier(p0, p1, p2, p3, n=420):
    t = np.linspace(0, 1, n)[:, None]
    pts = ((1-t)**3)*p0 + 3*((1-t)**2)*t*p1 + 3*(1-t)*(t**2)*p2 + (t**3)*p3
    return pts
base_y = sal_y + bbox[3] + 44
p0 = np.array([W/2 - tw*0.46, base_y - 6], np.float32)
p1 = np.array([W/2 - tw*0.10, base_y + 40], np.float32)
p2 = np.array([W/2 + tw*0.22, base_y + 34], np.float32)
p3 = np.array([W/2 + tw*0.50, base_y - 26], np.float32)
SWASH_PTS = bezier(p0, p1, p2, p3)
def swash_layer(prog):
    layer = Image.new("RGBA", (W, H), (0,0,0,0))
    dr = ImageDraw.Draw(layer)
    n = max(2, int(len(SWASH_PTS)*prog))
    for i in range(n):
        t = i/(len(SWASH_PTS)-1)
        r = 3.2 + 8.5*math.sin(math.pi*min(t, prog))**0.9
        x, y = SWASH_PTS[i]
        dr.ellipse([x-r, y-r, x+r, y+r], fill=GOLD+(255,))
    return layer

# poppy blossom sprite (gold, flat, 6 petals)
def poppy(scale, alpha, size=120):
    s = Image.new("RGBA", (size, size), (0,0,0,0))
    dr = ImageDraw.Draw(s)
    c = size/2
    pr = 34*scale
    for k in range(6):
        a = k*math.pi/3 + 0.35
        px, py = c + math.cos(a)*pr, c + math.sin(a)*pr
        rr = 15*scale
        dr.ellipse([px-rr, py-rr, px+rr, py+rr], fill=GOLD+(int(alpha*235),))
    dr.ellipse([c-9*scale, c-9*scale, c+9*scale, c+9*scale], fill=(122, 90, 20, int(alpha*255)))
    return s

# glint sprite (soft radial highlight)
GL = Image.new("RGBA", (90, 90), (0,0,0,0))
gd = ImageDraw.Draw(GL)
for r in range(45, 0, -1):
    a = int(150 * (1 - r/45)**2)
    gd.ellipse([45-r, 45-r, 45+r, 45+r], fill=GOLD_HI+(a,))

# ---------- timeline ----------
for f in range(N):
    frame = BG.copy()

    # wordmark ink-sweep reveal (f10-64) with slight rise
    t_rev = ease_io_cubic(win(f, 10, 64))
    if t_rev > 0:
        feather = 190.0
        sweep_x = text_l - feather + (text_r + feather - text_l)*t_rev + feather*0.5
        ramp = np.clip((sweep_x - xx[0]) / feather, 0, 1)  # 1 left of sweep, 0 right
        mask_row = ramp.astype(np.float32)
        rise = int(14*(1 - t_rev))
        # shadow first, then ink — both clipped by the sweep mask
        for src_alpha, src_img in ((sh_alpha, SH), (sal_alpha, SAL)):
            a = (src_alpha * mask_row[None, :].repeat(1, 0)).astype(np.uint8) \
                if False else (src_alpha * mask_row).astype(np.uint8)
            lay = src_img.copy()
            lay.putalpha(Image.fromarray(a, "L"))
            if rise:
                shifted = Image.new("RGBA", (W, H), (0,0,0,0))
                shifted.paste(lay, (0, rise), lay)
                lay = shifted
            frame = Image.alpha_composite(frame, lay)

    # gold swash draws on (f58-100)
    t_sw = ease_out_cubic(win(f, 58, 100))
    if t_sw > 0:
        frame = Image.alpha_composite(frame, swash_layer(t_sw))

    # poppy blooms at swash end (f92-116) + a small floater above (f98-122)
    t_p = win(f, 92, 116)
    if t_p > 0:
        s = ease_out_back(t_p); al = min(1.0, t_p*1.6)
        spr = poppy(max(0.05, s), al)
        px, py = SWASH_PTS[-1]
        frame.alpha_composite(spr, (int(px-60), int(py-60)))
    t_p2 = win(f, 98, 122)
    if t_p2 > 0:
        s = ease_out_back(t_p2)*0.55; al = min(1.0, t_p2*1.6)*0.9
        spr = poppy(max(0.05, s), al)
        frame.alpha_composite(spr, (int(text_r + 40), int(sal_y + 40)))

    # caption tracks in (f100-134)
    t_c = ease_out_cubic(win(f, 100, 134))
    if t_c > 0:
        tracking = 46 - 22*t_c
        frame = Image.alpha_composite(frame, caption_layer(tracking, t_c))

    # glint travels the swash (f128-152)
    t_g = win(f, 128, 152)
    if 0 < t_g < 1:
        idx = int(ease_io_cubic(t_g)*(len(SWASH_PTS)-1))
        gx, gy = SWASH_PTS[idx]
        peak = math.sin(math.pi*t_g)
        g = GL.copy()
        g.putalpha(g.split()[3].point(lambda v: int(v*peak)))
        frame.alpha_composite(g, (int(gx-45), int(gy-45)))

    out = frame.convert("RGB").resize((OW, OH), Image.LANCZOS)
    out.save(f"{OUT}/f{f:04d}.png")

print(f"rendered {N} frames -> {OUT}")
