"""Paints the PB-22 cockpit atlas (original art in the stock cockpit style): albedo, normal, metallic/smoothness, AO.
Stock style: neutral dark-grey panels, near-black bezels and dials, white condensed bold legends, yellow/black and red accents."""
import os
CK = os.path.dirname(os.path.abspath(__file__))  # scripts, ctx.obj and tex/ output live next to this file
import sys, math, os, random
sys.path.insert(0, CK)
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pb22_cockpit_model import ATLAS

S = 2048
OUT = os.path.join(CK, 'tex')
os.makedirs(OUT, exist_ok=True)
random.seed(22)

PANEL = (136, 137, 135)     # stock-style light structure grey (EW1/SFB coamings); instrument plates stay dark
DARK = (50, 51, 53)
DIAL = (20, 21, 23)
WHITE = (222, 222, 216)
GREY = (150, 152, 152)
AMBER = (226, 150, 40)
RED = (186, 32, 26)
GREEN = (60, 170, 80)
YEL = (214, 176, 40)

B = Image.new('RGB', (S, S), PANEL)     # albedo
H = Image.new('L', (S, S), 128)         # height for the normal map
G = Image.new('L', (S, S), 110)         # smoothness
db, dh, dg = ImageDraw.Draw(B), ImageDraw.Draw(H), ImageDraw.Draw(G)
FB = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
_fc = {}
def font(px):
    if px not in _fc: _fc[px] = ImageFont.truetype(FB, px)
    return _fc[px]

def R(name): return ATLAS[name]
def rr(x, y, w, h): return (x, y, x + w - 1, y + h - 1)

def text(x, y, s, px, col=WHITE, anchor='mm', squeeze=0.82, rot=0, engrave=True):
    """condensed bold legend centred at x,y (atlas px)."""
    f = font(px)
    bb = f.getbbox(s)
    w, h = bb[2] - bb[0] + 4, bb[3] - bb[1] + 4
    tile = Image.new('L', (w, h), 0)
    ImageDraw.Draw(tile).text((2 - bb[0], 2 - bb[1]), s, font=f, fill=255)
    tile = tile.resize((max(1, int(w*squeeze)), h), Image.LANCZOS)
    if rot: tile = tile.rotate(rot, expand=True, resample=Image.BICUBIC)
    tw, th = tile.size
    ox = int(x - tw/2) if anchor[0] == 'm' else (int(x) if anchor[0] == 'l' else int(x - tw))
    oy = int(y - th/2)
    B.paste(Image.new('RGB', tile.size, col), (ox, oy), tile)
    if engrave:
        H.paste(Image.new('L', tile.size, 120), (ox, oy), tile)

def fill(box, col, h=None, g=None):
    db.rectangle(box, fill=col)
    if h is not None: dh.rectangle(box, fill=h)
    if g is not None: dg.rectangle(box, fill=g)

def rounded(box, r, col, h=None, outline=None, width=1):
    db.rounded_rectangle(box, r, fill=col, outline=outline, width=width)
    if h is not None: dh.rounded_rectangle(box, r, fill=h)

def noise_region(name, base, amp=5, scuff=0):
    x, y, w, h = R(name)
    n = np.random.default_rng(hash(name) & 0xffff).normal(0, amp, (h, w, 1))
    # low-frequency mottling
    low = Image.fromarray(np.uint8(np.clip(128 + np.random.default_rng(7).normal(0, 40, (h//32 + 1, w//32 + 1)), 0, 255))).resize((w, h), Image.BICUBIC)
    low = (np.asarray(low, np.float32)[:, :, None] - 128)/128*amp*0.8
    a = np.clip(np.array(base, np.float32)[None, None, :] + n + low, 0, 255)
    B.paste(Image.fromarray(np.uint8(a)), (x, y))
    d = ImageDraw.Draw(B)
    for _ in range(scuff):   # sparse light scuffs (stock: light, sparse)
        sx, sy = x + random.randint(0, w - 1), y + random.randint(0, h - 1)
        L = random.randint(4, 18); ang = random.uniform(0, math.pi)
        c = tuple(int(v + 14) for v in base)
        d.line((sx, sy, sx + L*math.cos(ang), sy + L*math.sin(ang)), fill=c, width=1)

def bevel_edge(box, light=14, dark=-14, w=2):
    """thin painted edge highlight like the stock worn panel edges."""
    x0, y0, x1, y1 = box
    def shade(b, d):
        reg = B.crop(b); a = np.asarray(reg, np.int16) + d
        B.paste(Image.fromarray(np.uint8(np.clip(a, 0, 255))), b[:2])
    shade((x0, y0, x1 + 1, y0 + w), light); shade((x0, y0, x0 + w, y1 + 1), light)
    shade((x0, y1 - w + 1, x1 + 1, y1 + 1), dark); shade((x1 - w + 1, y0, x1 + 1, y1 + 1), dark)

def screws(box, inset=6, r=2):
    x0, y0, x1, y1 = box
    for cx, cy in ((x0 + inset, y0 + inset), (x1 - inset, y0 + inset), (x0 + inset, y1 - inset), (x1 - inset, y1 - inset)):
        db.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(95, 98, 102)); dh.ellipse((cx - r, cy - r, cx + r, cy + r), fill=150)
        db.line((cx - r + 1, cy, cx + r - 1, cy), fill=(50, 52, 55))

KNOBS = []    # every printed knob / toggle, so the model can put real geometry on top (2026-10-19)
def toggle(cx, cy, s=1.0, guard=False, label=None, lab_px=11):
    KNOBS.append((cx, cy, 'guard' if guard else 'toggle', 7*s))
    r = int(7*s)
    db.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(28, 29, 31)); dh.ellipse((cx - r, cy - r, cx + r, cy + r), fill=100)
    r2 = int(3*s)
    db.ellipse((cx - r2, cy - r2 - 2, cx + r2, cy + r2 - 2), fill=(190, 190, 186)); dh.ellipse((cx - r2, cy - r2 - 2, cx + r2, cy + r2 - 2), fill=200)
    if guard:
        g = int(10*s)
        db.rectangle((cx - g, cy - int(14*s), cx + g, cy + int(12*s)), outline=RED, width=2)
        for k in range(-g, g, 6): db.line((cx + k, cy + int(12*s), cx + k + 4, cy + int(12*s)), fill=YEL, width=2)
    if label: text(cx, cy - int(19*s), label, lab_px)

def lamp(box, col, lit=False, label=None, px=10):
    fill(box, tuple(int(c*(0.95 if lit else 0.35)) for c in col), 150, 200)
    db.rectangle(box, outline=(20, 20, 22), width=1)
    if label: text((box[0] + box[2])/2, (box[1] + box[3])/2, label, px, (25, 22, 18) if lit else (150, 148, 138), engrave=False)

def knob_print(cx, cy, r, label=None):
    KNOBS.append((cx, cy, 'knob', r))
    db.ellipse((cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3), outline=GREY, width=1)
    for k in range(9):
        a = math.radians(-135 + k*270/8)
        db.line((cx + (r + 4)*math.sin(a), cy - (r + 4)*math.cos(a), cx + (r + 8)*math.sin(a), cy - (r + 8)*math.cos(a)), fill=WHITE, width=1)
    if label: text(cx, cy + r + 15, label, 11)

# ================================================================== base paints
noise_region('paint', PANEL, 5, scuff=45)
noise_region('dark', DARK, 3, scuff=40)
dg.rectangle(rr(*R('paint')), fill=105); dg.rectangle(rr(*R('dark')), fill=95)
# faint panel seams and fastener rows on the box-projected paint so large faces aren't flat
x, y, w, h = R('paint')
for k in range(1, 6):
    yy = y + k*h//6
    db.line((x, yy, x + w, yy), fill=(92, 93, 92), width=2); dh.line((x, yy, x + w, yy), fill=110, width=2)
    db.line((x, yy + 2, x + w, yy + 2), fill=(162, 163, 160), width=1)
    for xx in range(x + 20, x + w, 48):
        db.ellipse((xx - 3, yy + 7, xx + 3, yy + 13), fill=(108, 109, 108)); dh.ellipse((xx - 3, yy + 7, xx + 3, yy + 13), fill=140)
        db.point((xx, yy + 10), fill=(70, 70, 70))
for k in range(1, 4):   # vertical seams so the light paint reads as separate panels, not one sheet
    xx = x + k*w//4
    db.line((xx, y, xx, y + h), fill=(98, 99, 98), width=2); dh.line((xx, y, xx, y + h), fill=112, width=2)

# ================================================================== MFD bezels
def mfd(name, labels_top, labels_bot, side_btn=4, pitch=0.156, mx=0.085):
    x, y, w, h = R(name)
    fill(rr(x, y, w, h), DARK, 140, 90)
    noise_region(name, DARK, 3, 6)
    gx0, gy0 = x + int(w*mx), y + int(h*0.105)
    gx1, gy1 = x + w - int(w*mx), y + h - int(h*0.105)
    fill((gx0 - 3, gy0 - 3, gx1 + 3, gy1 + 3), (12, 12, 14), 110, 160)
    for row, labels in ((y + int(h*0.05), labels_top), (y + h - int(h*0.05), labels_bot)):
        for k, lab in enumerate(labels):
            cx = x + int(w*(0.5 + (k - (len(labels) - 1)/2)*pitch))
            rounded((cx - 10, row - 5, cx + 10, row + 5), 2, (24, 25, 28), 150)
    for sx in (x + int(w*mx/2), x + w - int(w*mx/2)):
        for k in range(side_btn):
            cy = gy0 + int((gy1 - gy0)*(k + 0.5)/side_btn)
            rounded((sx - 5, cy - 9, sx + 5, cy + 9), 2, (24, 25, 28), 150)
    bevel_edge(rr(x, y, w, h), 12, -10, 2)
mfd('mfd', 'ABCDE', 'FGHIJ')
mfd('mfd_r', 'ABCDE', 'FGHIJ', 5)
mfd('mfdw', 'ABCDEFGHIJK', 'LMNOPQRSTUV', 4, 0.034/0.459, 0.0175/0.459)     # merged centre display, button pitch 34 mm on a 459 mm bezel

# ================================================================== analog gauges (near-black dials, white markings)
def dial_base(name):
    x, y, w, h = R(name)
    fill(rr(x, y, w, h), DIAL, 128, 170)
    return x + w/2, y + h/2, w/2 - 2

def ticks(cx, cy, r, a0, a1, major, minor_per=4, lw=2):
    n = major*minor_per
    for k in range(n + 1):
        a = math.radians(a0 + (a1 - a0)*k/n)
        big = k % minor_per == 0
        r0 = r*(0.80 if big else 0.88)
        db.line((cx + r0*math.sin(a), cy - r0*math.cos(a), cx + r*0.97*math.sin(a), cy - r*0.97*math.cos(a)), fill=WHITE, width=lw if big else 1)

def needle(cx, cy, r, ang, col=WHITE, w=3):
    a = math.radians(ang)
    db.line((cx - r*0.15*math.sin(a), cy + r*0.15*math.cos(a), cx + r*0.75*math.sin(a), cy - r*0.75*math.cos(a)), fill=col, width=w)
    db.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=(60, 60, 62))

def numbers(cx, cy, r, a0, a1, vals, px):
    for k, v in enumerate(vals):
        a = math.radians(a0 + (a1 - a0)*k/(len(vals) - 1))
        text(cx + r*0.60*math.sin(a), cy - r*0.60*math.cos(a), str(v), px, engrave=False)

# attitude: sky/ground ball, fixed aircraft symbol
x, y, w, h = R('adi'); cx, cy, r = x + w/2, y + h/2, w/2 - 2
fill(rr(x, y, w, h), DIAL, 128, 170)
ball = Image.new('RGB', (w, h), (0, 0, 0)); bd = ImageDraw.Draw(ball)
bd.rectangle((0, 0, w, h*0.54), fill=(70, 110, 150)); bd.rectangle((0, h*0.54, w, h), fill=(92, 66, 44))
bd.line((0, h*0.54, w, h*0.54), fill=WHITE, width=2)
for k in (-2, -1, 1, 2):
    yy = h*0.54 - k*14; L = 18 if k % 2 == 0 else 10
    bd.line((w/2 - L, yy, w/2 + L, yy), fill=WHITE, width=1)
ball = ball.rotate(-8, resample=Image.BICUBIC)
mask = Image.new('L', (w, h), 0); ImageDraw.Draw(mask).ellipse((10, 10, w - 10, h - 10), fill=255)
B.paste(ball, (x, y), mask)
db.ellipse((x + 10, y + 10, x + w - 10, y + h - 10), outline=(30, 30, 32), width=3)
ticks(cx, cy, r*0.93, -60, 60, 4, 1, 2)
db.polygon([(cx, cy - r*0.93 + 2), (cx - 6, cy - r*0.93 + 12), (cx + 6, cy - r*0.93 + 12)], fill=AMBER)
db.line((cx - 34, cy + 2, cx - 12, cy + 2), fill=AMBER, width=4); db.line((cx + 12, cy + 2, cx + 34, cy + 2), fill=AMBER, width=4)
db.line((cx - 12, cy + 2, cx - 6, cy + 9), fill=AMBER, width=4); db.line((cx + 12, cy + 2, cx + 6, cy + 9), fill=AMBER, width=4)
db.ellipse((cx - 3, cy - 1, cx + 3, cy + 5), fill=AMBER)

cx, cy, r = dial_base('asi'); ticks(cx, cy, r, -150, 150, 6); numbers(cx, cy, r, -150, 150, [0, 2, 4, 6, 8, 10, 12], 15)
text(cx, cy + r*0.32, 'KT x100', 10, GREY, engrave=False); needle(cx, cy, r, 40)
cx, cy, r = dial_base('alt'); ticks(cx, cy, r, 0, 324, 9); numbers(cx, cy, r, 0, 324, list(range(0, 10)), 15)
fill((int(cx - 18), int(cy + r*0.18), int(cx + 18), int(cy + r*0.42)), (8, 8, 9)); text(cx, cy + r*0.30, '12.4', 11, engrave=False)
text(cx, cy - r*0.28, 'ALT', 10, GREY, engrave=False); needle(cx, cy, r, 140)
cx, cy, r = dial_base('rpm'); ticks(cx, cy, r, -135, 135, 5); numbers(cx, cy, r, -135, 135, [0, 2, 4, 6, 8, 10], 15)
db.arc((cx - r*0.9, cy - r*0.9, cx + r*0.9, cy + r*0.9), 30, 45, fill=RED, width=4)
text(cx, cy + r*0.38, 'RPM x10', 11, GREY, engrave=False); needle(cx, cy, r, 85)
cx, cy, r = dial_base('egt'); ticks(cx, cy, r, -135, 135, 4); numbers(cx, cy, r, -135, 135, [2, 4, 6, 8, 10], 15)
db.arc((cx - r*0.9, cy - r*0.9, cx + r*0.9, cy + r*0.9), -10, 45, fill=AMBER, width=4)
text(cx, cy + r*0.38, 'TGT x100', 10, GREY, engrave=False); needle(cx, cy, r, 60)
cx, cy, r = dial_base('fuel'); ticks(cx, cy, r, -120, 120, 4); numbers(cx, cy, r, -120, 120, ['E', '1/4', '1/2', '3/4', 'F'], 11)
text(cx, cy + r*0.38, 'FUEL', 10, GREY, engrave=False); needle(cx, cy, r, 70)
cx, cy, r = dial_base('ff'); ticks(cx, cy, r, -135, 135, 5); numbers(cx, cy, r, -135, 135, [0, 2, 4, 6, 8, 10], 15)
text(cx, cy + r*0.38, 'FF T/H', 10, GREY, engrave=False); needle(cx, cy, r, 20)
cx, cy, r = dial_base('hyd'); ticks(cx, cy, r, -135, 135, 4); numbers(cx, cy, r, -135, 135, [0, 1, 2, 3, 4], 15)
db.arc((cx - r*0.9, cy - r*0.9, cx + r*0.9, cy + r*0.9), -225 + 270*0.62, -225 + 270*0.80, fill=GREEN, width=4)
text(cx, cy + r*0.38, 'HYD L R', 10, GREY, engrave=False); needle(cx, cy, r, 55); needle(cx, cy, r*0.8, 62, col=YEL, w=2)
cx, cy, r = dial_base('oil'); ticks(cx, cy, r, -135, 135, 5); numbers(cx, cy, r, -135, 135, [0, 1, 2, 3, 4, 5], 15)
db.arc((cx - r*0.9, cy - r*0.9, cx + r*0.9, cy + r*0.9), -225, -225 + 270*0.12, fill=RED, width=4)
text(cx, cy + r*0.38, 'OIL P', 10, GREY, engrave=False); needle(cx, cy, r, 10)
cx, cy, r = dial_base('nozl'); ticks(cx, cy, r, -135, 135, 5); numbers(cx, cy, r, -135, 135, [0, 20, 40, 60, 80, 100], 13)
db.arc((cx - r*0.9, cy - r*0.9, cx + r*0.9, cy + r*0.9), -225 + 270*0.7, 45, fill=AMBER, width=4)
text(cx, cy + r*0.38, 'NOZ %', 10, GREY, engrave=False); needle(cx, cy, r, -100); needle(cx, cy, r*0.8, -95, col=YEL, w=2)
cx, cy, r = dial_base('brk'); ticks(cx, cy, r, -135, 135, 4); numbers(cx, cy, r, -135, 135, [0, 5, 10, 15, 20], 14)
db.arc((cx - r*0.9, cy - r*0.9, cx + r*0.9, cy + r*0.9), -225 + 270*0.55, -225 + 270*0.85, fill=GREEN, width=4)
text(cx, cy + r*0.38, 'BRAKE L R', 9, GREY, engrave=False); needle(cx, cy, r, 30); needle(cx, cy, r*0.8, 38, col=YEL, w=2)
cx, cy, r = dial_base('volt'); ticks(cx, cy, r, -135, 135, 4); numbers(cx, cy, r, -135, 135, [0, 10, 20, 30, 40], 14)
db.arc((cx - r*0.9, cy - r*0.9, cx + r*0.9, cy + r*0.9), -225 + 270*0.62, -225 + 270*0.75, fill=GREEN, width=4)
text(cx, cy + r*0.38, 'DC VOLTS', 9, GREY, engrave=False); needle(cx, cy, r, 45)
cx, cy, r = dial_base('o2'); ticks(cx, cy, r, -120, 120, 4); numbers(cx, cy, r, -120, 120, ['E', '1/4', '1/2', '3/4', 'F'], 11)
db.arc((cx - r*0.9, cy - r*0.9, cx + r*0.9, cy + r*0.9), -210, -210 + 240*0.15, fill=RED, width=4)
text(cx, cy + r*0.38, 'OXYGEN', 10, GREY, engrave=False); needle(cx, cy, r, 85)
cx, cy, r = dial_base('clock'); ticks(cx, cy, r, 0, 330, 11, 5); numbers(cx, cy, r, 0, 330, [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], 11)
needle(cx, cy, r*0.7, 300); needle(cx, cy, r, 60, w=2)
cx, cy, r = dial_base('cabalt'); ticks(cx, cy, r, -135, 135, 5); numbers(cx, cy, r, -135, 135, [0, 2, 4, 6, 8, 10], 11)
text(cx, cy + r*0.38, 'CABIN ALT', 9, GREY, engrave=False); needle(cx, cy, r, -60)

# ================================================================== keypad / caution / centre stack / gear
def panel_plate(name, col=DARK):
    x, y, w, h = R(name)
    noise_region(name, col, 3, 4)
    dh.rectangle(rr(x, y, w, h), fill=128); dg.rectangle(rr(x, y, w, h), fill=100)
    bevel_edge(rr(x, y, w, h), 34, -18, 2)
    db.rectangle(rr(x, y, w, h), outline=(16, 16, 18), width=1)
    return x, y, w, h

x, y, w, h = panel_plate('keypad')
fill((x + 14, y + 10, x + w - 14, y + 34), (10, 14, 12), 110, 170)
text(x + 30, y + 22, 'WPT 04', 12, GREEN, 'lm', engrave=False)
keys = ['1', '2', '3', 'ENT', '4', '5', '6', 'CLR', '7', '8', '9', 'NAV', 'MRK', '0', 'IFF', 'COM']
for i, k in enumerate(keys):
    cxk = x + 26 + (i % 4)*46; cyk = y + 50 + (i // 4)*20
    rounded((cxk - 19, cyk - 8, cxk + 19, cyk + 8), 3, (28, 29, 32), 160)
    text(cxk, cyk, k, 10, WHITE, engrave=False)

x, y, w, h = panel_plate('caution')
cap = [('FIRE L', RED, False), ('FIRE R', RED, False), ('HYD 1', AMBER, False), ('HYD 2', AMBER, False),
       ('GEN L', AMBER, False), ('GEN R', AMBER, True), ('FUEL LO', AMBER, False), ('OIL', AMBER, False),
       ('ECM', GREEN, True), ('CANOPY', AMBER, False), ('ANTI-SKID', AMBER, False), ('AUTOPLT', GREEN, True),
       ('BAY DOOR', AMBER, False), ('O2', AMBER, False), ('NWS', GREEN, False), ('MASTER', RED, False)]
for i, (lab, col, lit) in enumerate(cap):
    cxk = x + 8 + (i % 4)*44; cyk = y + 8 + (i // 4)*29
    lamp((cxk, cyk, cxk + 40, cyk + 25), col, lit, lab, 8)

x, y, w, h = panel_plate('cswitch')
text(x + w/2, y + 12, 'MASTER', 11)
for k, lab in enumerate(('ARM', 'JETT', 'ECM')):
    cyk = y + 46 + k*52
    toggle(int(x + w*0.70), cyk, 1.0, guard=True)
    text(x + w*0.30, cyk, lab, 11, engrave=True)
lamp((x + 10, y + h - 40, x + 50, y + h - 22), GREEN, True, 'GEAR', 9)
lamp((x + 56, y + h - 40, x + 98, y + h - 22), AMBER, False, 'FLAP', 9)
lamp((x + 10, y + h - 18, x + 98, y + h - 4), RED, False, 'MSL WARN', 9)

x, y, w, h = panel_plate('gear')
text(x + w/2, y + 12, 'LANDING GEAR', 12)
for k, lab in enumerate(('NOSE', 'LEFT', 'RIGHT')):
    lamp((x + 10 + k*44, y + 26, x + 48 + k*44, y + 46), GREEN, True, lab, 9)
db.ellipse((x + w/2 - 24, y + 56, x + w/2 + 24, y + 104), outline=WHITE, width=2)
text(x + 22, y + 66, 'UP', 11); text(x + 22, y + 98, 'DN', 11)
for k in range(0, w, 12):
    db.polygon([(x + k, y + h - 6), (x + k + 6, y + h - 6), (x + k + 12, y + h), (x + k + 6, y + h)], fill=YEL)

# ================================================================== annunciator strip (Backfire-style lamp grid, mostly dark)
x, y, w, h = R('annun')
fill(rr(x, y, w, h), (24, 25, 27), 128, 140)
labels = ['ENG L', 'ENG R', 'HYD', 'ELEC', 'FUEL', 'AP', 'ATHR', 'NAV', 'RADAR', 'ECM', 'IFF', 'LINK', 'BAY', 'GPS', 'INS', 'ICE']
# each pilot gets the full set, two rows of eight, on his half of the lip
cols = 8; cw = w/2/cols; rh = h/2
for half in range(2):
    for k, lab in enumerate(labels):
        lit = lab in ('AP', 'NAV', 'ECM', 'GPS')
        warn = lab in ('FUEL',)
        col = GREEN if lit else (AMBER if warn else (120, 110, 90))
        c, r_ = k % cols, k // cols
        x0 = x + half*w/2 + c*cw
        bx = (int(x0 + 2), int(y + r_*rh + 2), int(x0 + cw - 2), int(y + (r_ + 1)*rh - 2))
        lamp(bx, col, lit or warn, lab, 11)

# ================================================================== throttle quadrant, pedestal panels, consoles
x, y, w, h = panel_plate('quad', DARK)
for k, sx in enumerate((x + w*0.275, x + w*0.725)):
    fill((int(sx - 7), y + 26, int(sx + 7), y + h - 50), (8, 8, 9), 80, 60)
    for j, lab in enumerate(('MAX AB', 'MIL', 'IDLE', 'OFF')):
        yy = y + 30 + j*(h - 90)/3
        db.line((sx - 22, yy, sx - 10, yy), fill=WHITE, width=2)
        if k == 0: text(x + w/2, yy, lab, 10)
    text(sx, y + h - 34, 'ENG ' + ('L' if k == 0 else 'R'), 12)
for k in range(0, w, 12):
    db.polygon([(x + k, y + 8), (x + k + 6, y + 8), (x + k + 12, y + 2), (x + k + 6, y + 2)], fill=YEL)
text(x + w/2, y + h - 14, 'SPD BRK', 11)

def ped(name, title, items):
    x, y, w, h = panel_plate(name)
    text(x + w/2, y + 10, title, 11)
    for k, (kind, lab) in enumerate(items):
        cxk = x + 30 + k*(w - 60)/(len(items) - 1); cyk = y + 54
        if kind == 'k': knob_print(cxk, cyk, 12, lab)
        elif kind == 't': toggle(int(cxk), cyk, 1.1, False, None); text(cxk, cyk + 26, lab, 10)
        elif kind == 'g': toggle(int(cxk), cyk, 1.1, True, None); text(cxk, cyk + 26, lab, 10)
        elif kind == 'd':
            fill((int(cxk - 26), cyk - 10, int(cxk + 26), cyk + 10), (8, 10, 9), 110, 170); text(cxk, cyk, lab, 12, GREEN, engrave=False)
    screws(rr(x, y, w, h))
ped('ped0', 'RADIO', [('k', 'VOL'), ('d', '243.0'), ('k', 'CHAN'), ('t', 'SQL')])
ped('ped1', 'TRIM / AUTOPILOT', [('t', 'PITCH'), ('t', 'ROLL'), ('k', 'HDG'), ('k', 'ALT'), ('g', 'AP DISC')])
ped('ped2', 'FUEL / HYD', [('g', 'XFEED'), ('t', 'PUMP L'), ('t', 'PUMP R'), ('k', 'DUMP')])

def con(name, title, items, rows=2):
    x, y, w, h = panel_plate(name)
    text(x + w/2, y + 12, title, 12)
    per = math.ceil(len(items)/rows)
    for k, (kind, lab) in enumerate(items):
        r_, c_ = divmod(k, per)
        cxk = x + 30 + c_*(w - 60)/max(1, per - 1); cyk = y + 60 + r_*80
        if kind == 'k': knob_print(cxk, cyk, 13, lab)
        elif kind == 't': toggle(int(cxk), cyk, 1.1); text(cxk, cyk + 26, lab, 10)
        elif kind == 'g': toggle(int(cxk), cyk, 1.1, True); text(cxk, cyk + 26, lab, 10)
        elif kind == 'l': lamp((int(cxk - 24), cyk - 9, int(cxk + 24), cyk + 9), AMBER, False, lab, 9)
    screws(rr(x, y, w, h))
con('con0', 'ENGINE START', [('g', 'START L'), ('g', 'START R'), ('t', 'IGN'), ('t', 'APU'), ('l', 'APU RDY'), ('k', 'MODE')])
con('con1', 'ELECTRICAL', [('t', 'BATT'), ('t', 'GEN L'), ('t', 'GEN R'), ('t', 'EXT PWR'), ('l', 'BUS TIE'), ('k', 'INV')])
con('con2', 'LIGHTS', [('k', 'PANEL'), ('k', 'FLOOD'), ('t', 'NAV'), ('t', 'STROBE'), ('t', 'TAXI'), ('t', 'LDG')])
con('con3', 'ENV / OXY', [('k', 'TEMP'), ('k', 'FLOW'), ('t', 'O2'), ('t', 'DEFOG'), ('g', 'RAM AIR'), ('l', 'O2 LOW')])
def placard(x, y, w, h, s):
    fill((x, y, x + w, y + h), (205, 205, 196), 136); db.rectangle((x, y, x + w, y + h), outline=(40, 40, 40))
    text(x + w/2, y + h/2, s, max(8, h - 6), (30, 30, 30), engrave=False)
x0, y0, w0, h0 = R('wall')
placard(x0 + 40, y0 + 12, 160, 22, 'NO STEP ON CONSOLE'); placard(x0 + w0 - 230, y0 + h0 - 40, 190, 22, 'OXYGEN HOSE STOWAGE')
for k in range(0, 300, 16):
    db.polygon([(x0 + 300 + k, y0 + h0 - 14), (x0 + 308 + k, y0 + h0 - 14), (x0 + 316 + k, y0 + h0 - 2), (x0 + 308 + k, y0 + h0 - 2)], fill=YEL)
con('rcon', 'STATION', [('k', 'VOL'), ('k', 'INT'), ('t', 'HOT MIC'), ('g', 'EJECT SEL')])

# rear station panels
x, y, w, h = panel_plate('rctl')
text(x + w/2, y + 12, 'MISSION SYSTEMS', 12)
for k in range(8):
    cxk = x + 30 + k*48
    rounded((cxk - 18, y + 34, cxk + 18, y + 56), 3, (28, 29, 32), 160)
    text(cxk, y + 45, ['RDR', 'ESM', 'ECM', 'IRST', 'LINK', 'NAV', 'TGT', 'WPN'][k], 10, engrave=False)
for k in range(5):
    toggle(int(x + 40 + k*80), y + 92, 1.1, k == 4)
    text(x + 40 + k*80, y + 118, ['JAM', 'CHAFF', 'FLARE', 'RWR', 'RELEASE'][k], 10)
x, y, w, h = panel_plate('rstat')
for k, (lab, col, lit) in enumerate([('ECM ON', GREEN, True), ('JAM', AMBER, False), ('RWR', GREEN, True), ('LINK', GREEN, True),
                                     ('TGT', AMBER, False), ('ARM', RED, False)]):
    cxk = x + 8 + (k % 3)*97; cyk = y + 10 + (k // 3)*44
    lamp((cxk, cyk, cxk + 90, cyk + 36), col, lit, lab, 12)
x, y, w, h = panel_plate('rkbd')
for r_ in range(4):
    for c_ in range(11):
        kx = x + 14 + c_*25 + (r_ % 2)*6; ky = y + 14 + r_*28
        rounded((kx, ky, kx + 21, ky + 22), 3, (30, 31, 34), 170)
x, y, w, h = panel_plate('sw')
for k in range(4): toggle(int(x + 32 + k*58), y + 52, 1.0); text(x + 32 + k*58, y + 20, ['MSTR', 'HUD', 'BRT', 'TEST'][k], 10)

# grip / hub decal: dark rubber with knurling
x, y, w, h = R('grip')
noise_region('grip', (30, 31, 33), 3)
for k in range(0, w, 6): dh.line((x + k, y, x + k, y + h), fill=110)
db.ellipse((x + w/2 - 10, y + h/2 - 10, x + w/2 + 10, y + h/2 + 10), fill=(60, 62, 66))
dg.rectangle(rr(x, y, w, h), fill=60)

# side-wall liner: stock-style panel with lightening holes and a stringer
x, y, w, h = R('wall')
noise_region('wall', (58, 61, 67), 4, 60)
for row in (0.30, 0.70):
    for k in range(9):
        cxk = x + 60 + k*(w - 120)/8; cyk = y + h*row
        db.ellipse((cxk - 20, cyk - 20, cxk + 20, cyk + 20), fill=(22, 23, 26)); dh.ellipse((cxk - 20, cyk - 20, cxk + 20, cyk + 20), fill=60)
        db.ellipse((cxk - 22, cyk - 22, cxk + 22, cyk + 22), outline=(118, 122, 128), width=3)
for k in range(1, 4):
    xx = x + k*w//4
    fill((xx - 5, y, xx + 5, y + h), (70, 74, 80), 150); db.line((xx - 5, y, xx - 5, y + h), fill=(120, 124, 130))
for k in range(0, h, 26):
    for xx in (x + w//4, x + w//2, x + 3*w//4): db.ellipse((xx - 2, y + k + 10, xx + 2, y + k + 14), fill=(110, 114, 118))
fill((x, int(y + h*0.48), x + w, int(y + h*0.52)), (74, 78, 84), 150)
for k in range(0, w, 30):
    db.ellipse((x + k + 10, y + h*0.5 - 3, x + k + 16, y + h*0.5 + 3), fill=(100, 104, 110))
bevel_edge(rr(x, y, w, h), 14, -12, 3)

x, y, w, h = R('red'); fill(rr(x, y, w, h), (176, 28, 22), 150, 150)

# ================================================================== floor: diamond tread plate, heel pads, pedal faces
def tread(name, base=(58, 60, 63), pitch=22):
    x, y, w, h = R(name)
    noise_region(name, base, 4, 3)
    dh.rectangle(rr(x, y, w, h), fill=120); dg.rectangle(rr(x, y, w, h), fill=70)
    # raised lozenges in alternating directions, the usual anti-slip pattern
    for j in range(0, h // pitch + 1):
        for i in range(0, w // pitch + 1):
            cx, cy = x + i*pitch + (pitch//2 if j % 2 else 0), y + j*pitch
            if not (x + 6 < cx < x + w - 6 and y + 6 < cy < y + h - 6): continue
            L, T = 8, 2
            pts = [(cx - L, cy - L + T), (cx - L + T, cy - L), (cx + L, cy + L - T), (cx + L - T, cy + L)] if (i + j) % 2 \
                else [(cx + L, cy - L + T), (cx + L - T, cy - L), (cx - L, cy + L - T), (cx - L + T, cy + L)]
            db.polygon(pts, fill=tuple(min(255, c + 22) for c in base)); dh.polygon(pts, fill=175); dg.polygon(pts, fill=120)
    # worn centre where boots go: lozenges polished lighter
    bevel_edge(rr(x, y, w, h), 20, -24, 3)
    for k in range(4, w - 4, 64):
        for yy in (y + 9, y + h - 10):
            db.ellipse((x + k + 26, yy - 3, x + k + 32, yy + 3), fill=(92, 95, 99)); dh.ellipse((x + k + 26, yy - 3, x + k + 32, yy + 3), fill=150)
    for k in range(4, h - 4, 64):
        for xx in (x + 9, x + w - 10):
            db.ellipse((xx - 3, y + k + 26, xx + 3, y + k + 32), fill=(92, 95, 99)); dh.ellipse((xx - 3, y + k + 26, xx + 3, y + k + 32), fill=150)
tread('tread')
x, y, w, h = R('heelpad')          # ribbed black rubber heel pad
fill(rr(x, y, w, h), (22, 22, 23), 110, 40)
for k in range(6, h - 6, 10):
    db.rectangle((x + 6, y + k, x + w - 7, y + k + 4), fill=(34, 34, 36)); dh.rectangle((x + 6, y + k, x + w - 7, y + k + 4), fill=160)
bevel_edge(rr(x, y, w, h), 10, -10, 2)
x, y, w, h = R('pedal')            # pedal face: ribbed tread with a toe-brake band at the top
fill(rr(x, y, w, h), (44, 45, 47), 120, 80)
for k in range(10, h - 8, 9):
    db.rectangle((x + 8, y + k, x + w - 9, y + k + 3), fill=(70, 72, 75)); dh.rectangle((x + 8, y + k, x + w - 9, y + k + 3), fill=170)
db.rectangle((x + 4, y + 4, x + w - 5, y + int(h*0.28)), outline=(150, 150, 146), width=2)
bevel_edge(rr(x, y, w, h), 18, -18, 2)

x, y, w, h = R('hazard')           # yellow / black ejection-hatch border, four periods across (repeats every 0.10 m on the liner)
fill(rr(x, y, w, h), (20, 20, 20), 130, 90)
_hz = Image.new('RGB', (w, h), (20, 20, 20)); _hd = ImageDraw.Draw(_hz)
for k in range(-2, 6):
    _hd.polygon([(k*64, h), (k*64 + 32, h), (k*64 + 32 + h, 0), (k*64 + h, 0)], fill=(214, 172, 30))
B.paste(_hz, (x, y))
bevel_edge(rr(x, y, w, h), 10, -12, 1)

# ================================================================== write maps
B.save(OUT + '/PB22_cockpit_b.png')
h = np.asarray(H.filter(ImageFilter.GaussianBlur(0.8)), np.float32)/255.0
dx = np.roll(h, -1, 1) - np.roll(h, 1, 1); dy = np.roll(h, -1, 0) - np.roll(h, 1, 0)
k = 4.0
nx, ny, nz = -dx*k, dy*k, np.ones_like(h)
l = np.sqrt(nx*nx + ny*ny + nz*nz)
N = np.stack([(nx/l + 1)*127.5, (ny/l + 1)*127.5, (nz/l + 1)*127.5], -1)
Image.fromarray(np.uint8(N)).save(OUT + '/PB22_cockpit_n.png')
# metallic (R, zero) + smoothness (A), as the stock _MetallicGlossMap
g = np.asarray(G, np.uint8)
M = np.zeros((S, S, 4), np.uint8); M[..., 0] = 10; M[..., 1] = 10; M[..., 2] = 10; M[..., 3] = g
Image.fromarray(M, 'RGBA').save(OUT + '/PB22_cockpit_m.png')
ao = 255 - np.clip((128 - np.asarray(H, np.float32))*1.2, 0, 90)
Image.fromarray(np.uint8(np.asarray(Image.fromarray(np.uint8(ao)).filter(ImageFilter.GaussianBlur(2))))).save(OUT + '/PB22_cockpit_ao.png')

# screen symbology for previews and the in-game lit displays (dim; the tac screen is drawn live by the game)
def screen_img(path, kind):
    im = Image.new('RGB', (512, 400), (6, 9, 12)); d = ImageDraw.Draw(im)
    c = (70, 200, 120)
    if kind == 'pfd':
        d.rectangle((0, 0, 512, 210), fill=(18, 40, 70)); d.rectangle((0, 210, 512, 400), fill=(45, 32, 20))
        d.line((0, 210, 512, 210), fill=(220, 220, 220), width=2)
        for k in (-2, -1, 1, 2): d.line((216, 210 - k*36, 296, 210 - k*36), fill=(220, 220, 220), width=2)
        d.rectangle((10, 120, 80, 300), outline=c, width=2); d.rectangle((432, 120, 502, 300), outline=c, width=2)
        d.line((190, 214, 240, 214), fill=(240, 180, 40), width=5); d.line((272, 214, 322, 214), fill=(240, 180, 40), width=5)
    else:
        for r_ in (60, 120, 180):
            d.ellipse((256 - r_, 230 - r_, 256 + r_, 230 + r_), outline=(40, 110, 70), width=2)
        d.line((256, 30, 256, 400), fill=(40, 110, 70)); d.polygon([(256, 220), (246, 244), (266, 244)], fill=c)
        for k in range(6):
            px_, py_ = random.randint(60, 450), random.randint(40, 380); d.rectangle((px_ - 4, py_ - 4, px_ + 4, py_ + 4), outline=c)
    im.save(path)
def mission_img(path, kind):
    im = Image.new('RGB', (512, 400), (6, 9, 12)); d = ImageDraw.Draw(im)
    c = (70, 200, 120); dim = (40, 110, 70); amb = (230, 160, 40); red = (220, 60, 50)
    fnt = ImageFont.truetype(FB, 18)
    if kind == 'ew':      # threat warning page: rings, own ship, emitter symbols
        cx, cy = 256, 215
        for r_ in (60, 120, 175): d.ellipse((cx - r_, cy - r_, cx + r_, cy + r_), outline=dim, width=2)
        for a in range(0, 360, 30):
            t = math.radians(a); d.line((cx + 175*math.sin(t), cy - 175*math.cos(t), cx + 186*math.sin(t), cy - 186*math.cos(t)), fill=c, width=2)
        d.polygon([(cx, cy - 12), (cx - 9, cy + 10), (cx + 9, cy + 10)], outline=c)
        for (a, r_, sym, col) in ((40, 140, 'S', amb), (300, 95, '10', red), (200, 160, 'A', amb), (120, 70, 'U', c)):
            t = math.radians(a); x_, y_ = cx + r_*math.sin(t), cy - r_*math.cos(t)
            d.text((x_, y_), sym, fill=col, font=fnt, anchor='mm')
            if col == red: d.ellipse((x_ - 18, y_ - 18, x_ + 18, y_ + 18), outline=red, width=2)
        d.text((14, 14), 'EW  AUTO', fill=c, font=fnt); d.text((498, 14), 'JAM RDY', fill=amb, font=fnt, anchor='ra')
        d.text((14, 372), 'CHF 60', fill=c, font=fnt); d.text((498, 372), 'FLR 32', fill=c, font=fnt, anchor='ra')
    else:                 # stores page: planform with the five stations
        d.polygon([(256, 40), (270, 120), (470, 250), (470, 268), (272, 230), (268, 330), (320, 368), (192, 368), (244, 330), (240, 230),
                   (42, 268), (42, 250), (242, 120)], outline=dim, width=2)
        for (x_, y_, lab) in ((256, 160, 'FWD'), (256, 205, 'AFT'), (340, 200, 'L1'), (172, 200, 'R1'), (420, 238, 'L2'), (92, 238, 'R2')):
            d.rectangle((x_ - 26, y_ - 14, x_ + 26, y_ + 14), outline=c, width=2); d.text((x_, y_), lab, fill=c, font=ImageFont.truetype(FB, 15), anchor='mm')
        d.text((14, 14), 'STORES', fill=c, font=fnt); d.text((498, 14), 'MASTER SAFE', fill=amb, font=fnt, anchor='ra')
        d.text((14, 372), 'REL  SGL', fill=c, font=fnt); d.text((498, 372), 'FUZE NT', fill=c, font=fnt, anchor='ra')
    im.save(path)
screen_img(OUT + '/_pfd.png', 'pfd'); screen_img(OUT + '/_nav.png', 'nav')
mission_img(OUT + '/_ew.png', 'ew'); mission_img(OUT + '/_sms.png', 'sms')
# screen sheet 1024x930: left column flight (top) / nav (bottom), right column EW (top) / stores (bottom)
_sc = Image.new('RGB', (1024, 930), (6, 9, 12))     # 512x465 cells fit the taller front glass; the page sits centred in each
for f, pos in (('_pfd', (0, 32)), ('_nav', (0, 497)), ('_ew', (512, 32)), ('_sms', (512, 497))): _sc.paste(Image.open(OUT + '/' + f + '.png'), pos)
_sc.save(OUT + '/screen_PB22_screen.png'); _sc.save(OUT + '/PB22_screen_e.png')
# the tac glass preview comes from the Unity render (tac_preview_text.py)
# knob positions per atlas region (s, t in 0..1 across the region, t = 0 at the bottom; r as a fraction of the region width)
import json
def _region(cx, cy):
    hits = [(w*h, n) for n, (x, y, w, h) in ATLAS.items() if x <= cx < x + w and y <= cy < y + h and n not in ('paint', 'dark')]
    return min(hits)[1] if hits else None
_kn = {}
for cx, cy, kind, r in KNOBS:
    n = _region(cx, cy)
    if n is None: continue
    x, y, w, h = ATLAS[n]
    _kn.setdefault(n, []).append(((cx - x)/w, 1.0 - (cy - y)/h, kind, r/w))
json.dump(_kn, open(os.path.join(CK, 'knobs.json'), 'w'), indent=0)
print('knobs', {k: len(v) for k, v in _kn.items()})
print('atlas written')
