"""Vending-machine front faces for INK DRIFT: TOKYO (1024x2048, albedo + emission). All brands fictional.

  vending_front_drinks   — drink machine: lit header ad, 3 shelves of dummies, price LEDs, つめた〜い/あったか〜い
  vending_front_icecream — ice-cream machine: photo-panel grid of treats
  vending_front_gacha    — two stacked capsule-toy (gacha) machines

Usage: python gen_vending.py [drinks|icecream|gacha ...]
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from signlib import *  # noqa
from signlib import col, WHITE, _h

INK = C("ink"); PAPER = C("paper"); MAG = C("magenta"); CYAN = C("cyan"); YEL = C("yellow")
RED = C("red"); IND = C("indigo"); SAK = C("sakura"); LIME = C("lime")
COLD = hexc("#1E6BFF"); HOT = hexc("#E8231E")


def outline_paint(s, mask, fillc, w=3.0, ink=INK, lit=None):
    s.fill(s.A.dilate(mask, w), ink, None if lit is None else 0.02)
    s.fill(mask, fillc, lit)


# --------------------------------------------------------------------------------------
# drink dummies
# --------------------------------------------------------------------------------------
def dummy_can(s, cx, base, w, h, body, band, label, lc=PAPER, tall=False):
    x0, x1 = cx - w / 2, cx + w / 2
    y0 = base - h
    body_p = rect(x0, y0 + h * 0.05, x1, base, w * 0.12)
    m = s.m(body_p)
    s.A.paint(s.A.dilate(m, 2.5), INK)
    cylinder_shade_s(s, m, x0, x1, body)
    bm = s.m(rect(x0, y0 + h * 0.38, x1, y0 + h * 0.66)) * m
    cylinder_shade_s(s, bm, x0, x1, band, hl=0.3)
    tp = T(label, "noto", (x0 + w * 0.1, y0 + h * 0.41, x1 - w * 0.1, y0 + h * 0.63))
    s.A.paint(s.m(tp) * m, col(lc))
    top = s.m(rect(x0 + w * 0.06, y0, x1 - w * 0.06, y0 + h * 0.08, w * 0.05))
    s.A.paint(top, hexc("#C9CED6"))
    s.A.paint(s.m(rect(x0 + w * 0.06, y0 + h * 0.06, x1 - w * 0.06, y0 + h * 0.08)), hexc("#80868F"))
    return m


def dummy_pet(s, cx, base, w, h, liquid, label_col, label, cap=WHITE, lc=INK):
    x0, x1 = cx - w / 2, cx + w / 2
    top = base - h
    p = skia.Path()
    nw = w * 0.36
    p.moveTo(cx - nw / 2, top + h * 0.06)
    p.lineTo(cx + nw / 2, top + h * 0.06)
    p.lineTo(cx + nw / 2, top + h * 0.12)
    p.cubicTo(cx + nw / 2, top + h * 0.2, x1, top + h * 0.22, x1, top + h * 0.32)
    p.lineTo(x1, base - w * 0.12)
    p.quadTo(x1, base, x1 - w * 0.12, base)
    p.lineTo(x0 + w * 0.12, base)
    p.quadTo(x0, base, x0, base - w * 0.12)
    p.lineTo(x0, top + h * 0.32)
    p.cubicTo(x0, top + h * 0.22, cx - nw / 2, top + h * 0.2, cx - nw / 2, top + h * 0.12)
    p.close()
    m = s.m(p)
    s.A.paint(s.A.dilate(m, 2.5), INK)
    cylinder_shade_s(s, m, x0, x1, liquid, hl=0.5, dark=0.35)
    lm = s.m(rect(x0, top + h * 0.45, x1, top + h * 0.78)) * m
    cylinder_shade_s(s, lm, x0, x1, label_col, hl=0.25)
    tp = VT(label, "noto", (x0 + w * 0.15, top + h * 0.47, x1 - w * 0.15, top + h * 0.76)) if len(label) <= 3 and not label.isascii() else \
        T(label, "noto", (x0 + w * 0.08, top + h * 0.53, x1 - w * 0.08, top + h * 0.7))
    s.A.paint(s.m(tp) * lm, col(lc))
    capm = s.m(rect(cx - nw * 0.62, top, cx + nw * 0.62, top + h * 0.075, 3))
    s.A.paint(s.A.dilate(capm, 2), INK)
    s.A.paint(capm, col(cap))
    return m


def cylinder_shade_s(s, mask, x0, x1, base, hl=0.45, dark=0.5):
    t = s.A.ramp((x0, 0), (x1, 0))
    k = 1 - dark * (np.abs(t - 0.42) / 0.58) ** 1.6
    s.A.paint(mask, col(base)[None, None, :] * k[..., None])
    hlm = np.clip(1 - np.abs(t - 0.28) / 0.06, 0, 1)
    s.A.paint(mask * hlm, WHITE, hl)


def led_price(s, box, value, color=hexc("#FF3B30")):
    x0, y0, x1, y1 = box
    s.fill(rect(*box, 3), hexc("#141416"), 0)
    tp = T(value, "chakra", (x0 + 4, y0 + 3, x1 - 4, y1 - 3))
    tm = s.m(tp)
    s.A.paint(tm, mix(color, hexc("#3A1A1A"), 0.55))
    s.emit(tm, color, 1.2)
    s.emit(s.A.blur(tm, 3), color, 0.5)


def cabinet(s, body, x0=0, y0=0, x1=1024, y1=2048, r_=36):
    s.fill(rect(0, 0, 1024, 2048), hexc("#101014"), 0)
    m = s.m(rect(x0, y0, x1, y1, r_))
    t = s.A.ramp((x0, 0), (x1, 0))
    s.A.paint(m, col(body)[None, None, :] * (1.04 - 0.12 * np.abs(t - 0.4))[..., None])
    # edge bevel
    s.A.paint(m * (1 - s.A.shift(m, 6, 6)), WHITE, 0.25)
    s.A.paint(m * (1 - s.A.shift(m, -6, -6)), INK, 0.35)
    return m


def glass(s, box, r_=10, tint=hexc("#DDEFF5"), refl=0.18):
    x0, y0, x1, y1 = box
    m = s.m(rect(*box, r_))
    rr = s.A.ramp((x0, y0), (x1, y1))
    band = np.clip(1 - np.abs(rr - 0.3) / 0.08, 0, 1) + 0.6 * np.clip(1 - np.abs(rr - 0.42) / 0.02, 0, 1)
    s.A.paint(m * band, WHITE, refl)
    s.A.paint(m, tint, 0.05)
    return m


def frame_rect(s, box, w, c, r_=10):
    m = s.m(rect(*box, r_), stroke=w, fill=False)
    s.fill(m, c, 0)
    s.A.paint(m * (1 - s.A.shift(m, 2, 2)), WHITE, 0.3)


def coin_panel(s, x0, y0, x1, y1, body):
    """coin slot, bill acceptor, IC reader, return lever, credit display."""
    s.fill(rect(x0, y0, x1, y1, 16), darken(body, 0.25), 0)
    s.A.paint(s.m(rect(x0, y0, x1, y1, 16), stroke=4, fill=False), INK, 0.6)
    # credit LED
    led_price(s, (x0 + 30, y0 + 30, x0 + 230, y0 + 100), "000", hexc("#3BFF6A"))
    # coin slot with glowing ring
    cx, cy = x0 + 330, y0 + 70
    s.fill(rect(cx - 50, cy - 50, cx + 50, cy + 50, 14), hexc("#B8BCC4"), 0)
    s.fill(rect(cx - 6, cy - 34, cx + 6, cy + 34, 4), INK, 0)
    ring = s.m(rect(cx - 50, cy - 50, cx + 50, cy + 50, 14), stroke=5, fill=False)
    s.A.paint(ring, hexc("#FFB347"))
    s.emit(ring, hexc("#FF9A1E"), 1.0)
    s.emit(s.A.blur(ring, 6), hexc("#FF9A1E"), 0.5)
    s.fill(T("COIN", "chakra", (cx - 40, cy + 58, cx + 40, cy + 80)), PAPER, 0)
    s.fill(T("10・50・100・500円", "noto", (cx - 80, cy + 92, cx + 80, cy + 112)), PAPER, 0)
    # bill acceptor
    bx = x0 + 450
    s.fill(rect(bx, y0 + 26, bx + 220, y0 + 116, 10), hexc("#2A2C33"), 0)
    s.fill(rect(bx + 20, y0 + 64, bx + 200, y0 + 76, 3), INK, 0)
    for k in range(3):
        g = s.m(circle(bx + 30 + k * 22, y0 + 44, 5))
        s.A.paint(g, hexc("#5AFF8A")); s.emit(g, hexc("#3BFF6A"), 1.2)
    s.fill(T("1000円札のみ", "noto", (bx + 20, y0 + 86, bx + 200, y0 + 108)), PAPER, 0)
    # IC reader
    ix = x1 - 190
    s.fill(rect(ix, y0 + 20, ix + 160, y0 + 180, 20), hexc("#1C1E26"), 0)
    icm = s.m(circle(ix + 80, y0 + 90, 52), stroke=6, fill=False)
    s.A.paint(icm, CYAN); s.emit(icm, CYAN, 1.2); s.emit(s.A.blur(icm, 8), CYAN, 0.5)
    for k in range(3):
        arc = skia.Path(); arc.addArc(skia.Rect.MakeLTRB(ix + 60 - k * 12, y0 + 70 - k * 12, ix + 100 + k * 12, y0 + 110 + k * 12), -50, 100)
        am = s.m(arc, stroke=4, fill=False)
        s.A.paint(am, PAPER); s.emit(am, PAPER, 0.7)
    s.fill(T("交通系IC", "noto", (ix + 10, y0 + 148, ix + 150, y0 + 172)), PAPER, 0)
    # return lever + change cup
    rx = x0 + 60
    s.fill(rect(rx, y0 + 160, rx + 170, y0 + 230, 30), hexc("#C9CED6"), 0)
    s.fill(T("おつり", "noto", (rx + 24, y0 + 172, rx + 146, y0 + 218)), INK, 0)
    s.fill(rect(bx, y0 + 150, bx + 220, y0 + 236, 10), hexc("#1A1A1E"), 0)
    s.fill(rect(bx + 10, y0 + 200, bx + 210, y0 + 228, 6), hexc("#2C2C32"), 0)
    s.fill(T("返却口", "noto", (bx + 50, y0 + 240, bx + 170, y0 + 266)), PAPER, 0)


def dispenser(s, x0, y0, x1, y1, body, label="とりだしぐち"):
    s.fill(rect(x0 - 16, y0 - 16, x1 + 16, y1 + 16, 18), darken(body, 0.3), 0)
    s.fill(rect(x0, y0, x1, y1, 12), hexc("#0C0C10"), 0)
    # translucent flap
    fl = s.m(rect(x0 + 10, y0 + 10, x1 - 10, y1 - 30, 8))
    s.A.paint(fl, hexc("#3A3E48"), 0.85)
    s.A.paint(fl * s.A.ramp((0, y0), (0, y1)), WHITE, 0.12)
    for k in range(6):
        y = y0 + 20 + k * (y1 - y0 - 50) / 6
        s.A.paint(s.m(rect(x0 + 14, y, x1 - 14, y + 2)), WHITE, 0.15)
    s.fill(T(label, "noto", (x0 + (x1 - x0) * 0.3, y1 - 26, x1 - (x1 - x0) * 0.3, y1 - 4)), PAPER, 0)
    s.A.paint(s.m(rect(x0 + (x1 - x0) * 0.42, y0 + 30, x0 + (x1 - x0) * 0.58, y0 + 50, 8)), hexc("#9AA0AA"))


# ======================================================================================
def vending_drinks():
    s = Sign("vending_front_drinks", 1024, 2048, bg=hexc("#101014"))
    body = hexc("#1D4ED8")
    cabinet(s, body)
    # --- header ad (backlit)
    hx0, hy0, hx1, hy1 = 50, 50, 974, 430
    s.fill(rect(hx0, hy0, hx1, hy1, 18), hexc("#0B1E5A"), 1.0)
    hm = s.m(rect(hx0, hy0, hx1, hy1, 18))
    s.fill(s.A.halftone(s.A.ramp((0, hy0), (0, hy1)) * 0.55, 12, 45) * hm, hexc("#1E6BFF"), 1.0)
    p = action_lines(760, 250, 140, 700, 90, 14, r=rng(5))
    s.fill(s.m(p) * hm, hexc("#2A86FF"), 1.0, opacity=0.8)
    # big can illustration in header
    dummy_can(s.sub((660, 50, 920, 430)), 790, 400, 210, 330, hexc("#E7ECF5"), CYAN, "のむのむ", lc=hexc("#0B1E5A"))
    for (x, y, rr) in [(640, 120, 16), (700, 90, 10), (930, 130, 14), (900, 330, 9), (650, 330, 12)]:
        c = skia.Path(); c.addCircle(x, y, rr)
        s.fill(stroke_path(c, 4), PAPER, 1.0)
    tt = transformed(T("のむのむ", "dela", (90, 90, 600, 230)), rotate=-4)
    tm = s.m(tt)
    s.fill(s.A.dilate(tm, 14), INK, 0.02)
    s.fill(s.A.dilate(tm, 8), PAPER, 1.0)
    s.fill(tm, s.A.vgrad(90, 230, [(0, YEL), (1, hexc("#FF9A00"))]), 1.0)
    s.fill(T("NOMU-NOMU DRINKS", "chakra", (100, 250, 560, 300)), CYAN, 1.0)
    s.fill(rect(100, 320, 560, 400, 12), MAG, 1.0)
    s.fill(T("冷たいの、あります。", "noto", (120, 332, 540, 388)), PAPER, 1.0)
    frame_rect(s, (hx0, hy0, hx1, hy1), 8, hexc("#C9CED6"), 18)
    # --- display window
    wx0, wy0, wx1, wy1 = 50, 460, 974, 1300
    s.fill(rect(wx0, wy0, wx1, wy1, 12), hexc("#E9F1F6"), 0.95)
    # white backlight inside window
    rows = 3
    rh = (wy1 - wy0) / rows
    cols = 7
    cw = (wx1 - wx0 - 40) / cols
    products = [
        ("can", hexc("#2B0A5E"), MAG, "VOLTZ", PAPER), ("pet", hexc("#7FD36A"), hexc("#0E7A3C"), "緑茶", PAPER),
        ("can", hexc("#121212"), hexc("#C8A04A"), "珈琲", INK), ("pet", hexc("#CFEFFF"), hexc("#1E88E5"), "天然水", PAPER),
        ("can", hexc("#7FF0FF"), hexc("#B6FF3B"), "PUCHI", INK), ("pet", hexc("#E8C79A"), hexc("#8A5A2A"), "ミルクティー", PAPER),
        ("can", hexc("#4A1A6A"), hexc("#FF2D7A"), "KOLA", PAPER),
        ("pet", hexc("#D8A04A"), hexc("#7A4A1A"), "麦茶", PAPER), ("can", hexc("#F2F2F2"), hexc("#00A8E8"), "SODA", PAPER),
        ("pet", hexc("#A8E6FF"), hexc("#2A6AE8"), "SPORTS", PAPER), ("can", hexc("#5A3A1A"), hexc("#F2B705"), "微糖", INK),
        ("pet", hexc("#FFE08A"), hexc("#FF8A00"), "ORANGE", PAPER), ("can", hexc("#0E6B3A"), hexc("#B6FF3B"), "抹茶", INK),
        ("pet", hexc("#F5E6C8"), hexc("#C8102E"), "LEMON", PAPER),
        ("can", hexc("#C8102E"), hexc("#FFE600"), "おしるこ", INK), ("can", hexc("#F2C200"), hexc("#FF8A00"), "コーン", INK),
        ("can", hexc("#121212"), hexc("#C8A04A"), "BLACK", PAPER), ("pet", hexc("#B07A3A"), hexc("#5A2A0A"), "ほうじ茶", PAPER),
        ("can", hexc("#E8E0D0"), hexc("#8A5A2A"), "カフェオレ", PAPER), ("pet", hexc("#CFEFFF"), hexc("#1E88E5"), "天然水", PAPER),
        ("can", hexc("#FF6FAE"), hexc("#FFFFFF"), "MOMO", INK),
    ]
    prices = ["160", "150", "130", "110", "140", "160", "140", "150", "130", "160", "130", "150", "140", "160",
              "130", "130", "130", "150", "130", "110", "140"]
    btn_lit = []
    for j in range(rows):
        y_top = wy0 + j * rh
        shelf_y = y_top + rh * 0.55
        # shelf
        s.fill(rect(wx0 + 10, shelf_y, wx1 - 10, shelf_y + 10), hexc("#B9C2CC"), 0.6)
        for i in range(cols):
            k = j * cols + i
            kind, c1, c2, lab, lc = products[k]
            cx = wx0 + 20 + cw * (i + 0.5)
            s0 = s
            s = s0.sub((cx - cw * 0.5 - 2, y_top, cx + cw * 0.5 + 2, y_top + rh))
            if kind == "can":
                dummy_can(s, cx, shelf_y, cw * 0.62, rh * 0.42, c1, c2, lab, lc)
            else:
                dummy_pet(s, cx, shelf_y, cw * 0.6, rh * 0.5, c1, c2, lab, lc=lc)
            # price LED
            led_price(s, (cx - cw * 0.36, shelf_y + 18, cx + cw * 0.36, shelf_y + 52), prices[k])
            # hot / cold strip
            hot = (j == 2 and i < 2) or (j == 2 and i == 4)
            sc = HOT if hot else COLD
            s.fill(rect(cx - cw * 0.44, shelf_y + 58, cx + cw * 0.44, shelf_y + 82, 4), sc, 1.0)
            s.fill(T("あったか〜い" if hot else "つめた〜い", "noto", (cx - cw * 0.4, shelf_y + 61, cx + cw * 0.4, shelf_y + 79)), PAPER, 1.0)
            # selection button
            bm = s.m(rect(cx - cw * 0.3, shelf_y + 92, cx + cw * 0.3, shelf_y + 122, 8))
            s.A.paint(s.A.dilate(bm, 2), INK)
            s.fill(bm, hexc("#F4F4F2"), 0)
            ind = s.m(rect(cx - cw * 0.12, shelf_y + 100, cx + cw * 0.12, shelf_y + 114, 4))
            soldout = k in (6, 15)
            s.A.paint(ind, hexc("#FF5A4A") if soldout else hexc("#7DFF9A"))
            s.emit(ind, hexc("#FF3B30") if soldout else hexc("#3BFF6A"), 1.1)
            s.emit(s.A.blur(ind, 4), hexc("#FF3B30") if soldout else hexc("#3BFF6A"), 0.5)
            if soldout:
                s.fill(T("売切", "noto", (cx - cw * 0.3, shelf_y - 30, cx + cw * 0.3, shelf_y - 4)), hexc("#FF3B30"), 0.0)
                s.fill(rect(cx - cw * 0.32, shelf_y - 34, cx + cw * 0.32, shelf_y), hexc("#FF3B30"), 0.0, opacity=0.0)
            s = s0
    gl = glass(s, (wx0, wy0, wx1, wy1), 12)
    s.L *= 1.0
    frame_rect(s, (wx0, wy0, wx1, wy1), 12, hexc("#C9CED6"), 12)
    # --- side stickers / brand stripe
    s.fill(rect(50, 1320, 974, 1360, 8), CYAN, 0.0)
    s.fill(T("のむのむ ドリンク  ・  24時間  ・  お釣りはお忘れなく", "noto", (70, 1324, 954, 1356)), INK, 0)
    coin_panel(s.sub((40, 1370, 984, 1670)), 50, 1380, 974, 1660, body)
    # instruction sticker
    s.fill(rect(60, 1680, 520, 1760, 8), PAPER, 0)
    s.fill(T("お金を入れて ボタンを押してね", "noto", (76, 1692, 504, 1748)), INK, 0)
    s.fill(rect(560, 1680, 964, 1760, 8), YEL, 0)
    s.fill(T("ゴミはゴミ箱へ", "noto", (580, 1692, 944, 1748)), INK, 0)
    dispenser(s.sub((100, 1770, 924, 1980)), 120, 1790, 904, 1960, body)
    # kick plate + vents
    s.fill(rect(30, 1990, 994, 2030, 8), hexc("#16161A"), 0)
    for i in range(24):
        s.fill(rect(60 + i * 38, 1998, 84 + i * 38, 2022, 3), hexc("#2A2A30"), 0)
    s.bolts([(30, 30), (994, 30), (30, 1970), (994, 1970)], 9, rust=0.3)
    s.bake_backlight(1.05, tubes="v", tube_count=2, warm=0.05)
    s.weather(0.7, streak=0.5)
    return s


# ======================================================================================
def ice_tile(s, box, kind, bg, name, price, seed):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    s.fill(rect(*box, 10), bg, 1.0)
    rr = s.m(rect(*box, 10))
    s.fill(s.A.halftone(s.A.radial((x0 + x1) / 2, y0 + h * 0.4, w * 0.8) * 0.45, 8, 45) * rr, darken(bg, 0.15), 1.0)
    cx, cy = (x0 + x1) / 2, y0 + h * 0.42
    r = rng(seed)
    def O(p, c):
        m = s.m(p)
        s.fill(s.A.dilate(m, 3), INK, 0.05)
        s.fill(m, c, 1.0)
        return m
    if kind == "cone":
        O(poly([(cx - w * 0.2, cy - h * 0.02), (cx + w * 0.2, cy - h * 0.02), (cx, cy + h * 0.36)]), hexc("#E8A85A"))
        grid = skia.Path()
        for k in range(-4, 5):
            grid.addPath(poly([(cx + k * w * 0.06 - 1, cy), (cx + k * w * 0.06 + 1, cy), (cx + k * w * 0.02 + 1, cy + h * 0.34), (cx + k * w * 0.02 - 1, cy + h * 0.34)]))
        s.fill(s.m(grid) * s.m(poly([(cx - w * 0.2, cy - h * 0.02), (cx + w * 0.2, cy - h * 0.02), (cx, cy + h * 0.36)])), hexc("#B0702A"), 1.0)
        O(union(circle(cx - w * 0.1, cy - h * 0.06, w * 0.14), circle(cx + w * 0.1, cy - h * 0.06, w * 0.14), circle(cx, cy - h * 0.2, w * 0.16)), hexc("#FFB7D5"))
        O(ellipse(cx, cy - h * 0.34, w * 0.04, w * 0.04), hexc("#E8231E"))
    elif kind == "bar":
        O(rect(cx - w * 0.05, cy + h * 0.16, cx + w * 0.05, cy + h * 0.38, 6), hexc("#E8D2A0"))
        m = O(rect(cx - w * 0.2, cy - h * 0.3, cx + w * 0.2, cy + h * 0.2, w * 0.12), hexc("#7FD3FF"))
        s.fill(s.m(rect(cx - w * 0.2, cy - h * 0.3, cx + w * 0.2, cy - h * 0.12, w * 0.12)) * m, hexc("#B9ECFF"), 1.0)
    elif kind == "choco":
        O(rect(cx - w * 0.05, cy + h * 0.16, cx + w * 0.05, cy + h * 0.38, 6), hexc("#E8D2A0"))
        m = O(rect(cx - w * 0.2, cy - h * 0.3, cx + w * 0.2, cy + h * 0.2, w * 0.12), hexc("#5A3018"))
        s.fill(s.m(rect(cx - w * 0.2, cy - h * 0.3, cx + w * 0.2, cy - h * 0.18, w * 0.1)) * m, hexc("#F5E6C8"), 1.0)
        nuts = skia.Path()
        for _ in range(10):
            nuts.addCircle(cx + r.uniform(-0.16, 0.16) * w, cy + r.uniform(-0.15, 0.15) * h, w * 0.02)
        s.fill(s.m(nuts) * m, hexc("#E8C07A"), 1.0)
    elif kind == "cup":
        O(poly([(cx - w * 0.24, cy - h * 0.05), (cx + w * 0.24, cy - h * 0.05), (cx + w * 0.17, cy + h * 0.32), (cx - w * 0.17, cy + h * 0.32)]), PAPER)
        s.fill(T("VANILLA", "chakra", (cx - w * 0.17, cy + h * 0.06, cx + w * 0.17, cy + h * 0.16)), hexc("#C8102E"), 1.0)
        O(ellipse(cx, cy - h * 0.08, w * 0.25, h * 0.08), hexc("#FFF4D6"))
    elif kind == "mochi":
        for k, c in enumerate([hexc("#FFFFFF"), hexc("#FFB7D5"), hexc("#B6E07A")]):
            O(ellipse(cx + (k - 1) * w * 0.17, cy + h * 0.06 - (k == 1) * h * 0.08, w * 0.15, h * 0.13), c)
    elif kind == "melon":
        m = O(ellipse(cx, cy, w * 0.26, h * 0.26), hexc("#9BE05A"))
        net = skia.Path()
        for k in range(-3, 4):
            net.addPath(rect(cx - w * 0.3, cy + k * h * 0.07, cx + w * 0.3, cy + k * h * 0.07 + 2))
            net.addPath(rect(cx + k * w * 0.07, cy - h * 0.3, cx + k * w * 0.07 + 2, cy + h * 0.3))
        s.fill(s.m(net) * m, hexc("#E8F7C8"), 1.0)
    elif kind == "sandwich":
        O(rect(cx - w * 0.28, cy - h * 0.18, cx + w * 0.28, cy - h * 0.06, 8), hexc("#4A2A14"))
        O(rect(cx - w * 0.26, cy - h * 0.06, cx + w * 0.26, cy + h * 0.06, 4), hexc("#FFF4D6"))
        O(rect(cx - w * 0.28, cy + h * 0.06, cx + w * 0.28, cy + h * 0.18, 8), hexc("#4A2A14"))
    else:  # popsicle soda
        O(rect(cx - w * 0.05, cy + h * 0.16, cx + w * 0.05, cy + h * 0.38, 6), hexc("#E8D2A0"))
        m = O(rect(cx - w * 0.2, cy - h * 0.3, cx + w * 0.2, cy + h * 0.2, w * 0.12), hexc("#FF7AB6"))
        s.fill(s.m(rect(cx - w * 0.2, cy - h * 0.06, cx + w * 0.2, cy + h * 0.2)) * m, hexc("#FFE600"), 1.0)
    # name + price
    s.fill(rect(x0 + 6, y1 - h * 0.2, x1 - 6, y1 - 6, 6), PAPER, 1.0)
    s.fill(T(name, "noto", (x0 + 14, y1 - h * 0.19, x1 - 14, y1 - h * 0.1)), INK, 0.05)
    s.fill(T(price, "chakra", (x0 + 14, y1 - h * 0.1, x1 - 14, y1 - 10)), hexc("#C8102E"), 1.0)


def vending_icecream():
    s = Sign("vending_front_icecream", 1024, 2048, bg=hexc("#101014"))
    body = hexc("#F4F2EE")
    cabinet(s, body)
    # top header
    s.fill(rect(50, 50, 974, 360, 20), hexc("#FF4F8B"), 1.0)
    hm = s.m(rect(50, 50, 974, 360, 20))
    s.fill(s.A.halftone(s.A.ramp((0, 50), (0, 360)) * 0.5, 14, 45) * hm, hexc("#FF2D7A"), 1.0)
    for (x, y, rr) in [(110, 100, 26), (930, 110, 20), (900, 300, 16), (130, 300, 14)]:
        s.fill(picto_star((x - rr, y - rr, x + rr, y + rr)), YEL, 1.0)
    tt = T("アイスクリーム", "dela", (110, 90, 914, 240))
    tm = s.m(tt)
    s.fill(s.A.dilate(tm, 14), INK, 0.02)
    s.fill(s.A.dilate(tm, 8), PAPER, 1.0)
    s.fill(tm, s.A.vgrad(90, 240, [(0, hexc("#7FF0FF")), (1, hexc("#00A8E8"))]), 1.0)
    s.fill(T("ICE KOORI HIME  氷姫", "chakra", (200, 262, 824, 330)), PAPER, 1.0)
    frame_rect(s, (50, 50, 974, 360), 8, hexc("#C9CED6"), 20)
    # tile grid
    kinds = ["cone", "bar", "choco", "cup", "mochi", "melon", "sandwich", "soda"]
    names = ["いちごコーン", "ソーダバー", "チョコナッツ", "バニラカップ", "雪見もち風", "メロンボール", "モナカサンド", "ピーチソーダ"]
    bgs = [hexc("#FFE3EE"), hexc("#DDF4FF"), hexc("#F5E6D6"), hexc("#FFF6D6"), hexc("#EFFFE3"), hexc("#E8FFD6"), hexc("#F2E6DA"), hexc("#FFE6F2")]
    gx0, gy0, gx1, gy1 = 60, 390, 964, 1330
    s.fill(rect(gx0 - 10, gy0 - 10, gx1 + 10, gy1 + 10, 14), hexc("#1A1A20"), 0)
    ncol, nrow = 4, 4
    tw = (gx1 - gx0) / ncol; th = (gy1 - gy0) / nrow
    for j in range(nrow):
        for i in range(ncol):
            k = (j * ncol + i) % 8
            b = (gx0 + i * tw + 6, gy0 + j * th + 6, gx0 + (i + 1) * tw - 6, gy0 + (j + 1) * th - 52)
            ss_ = s.sub((b[0] - 4, b[1] - 4, b[2] + 4, b[3] + 46))
            ice_tile(ss_, b, kinds[(k + j) % 8], bgs[(k + j) % 8], names[(k + j) % 8], ["¥160", "¥130", "¥180", "¥150"][(i + j) % 4], seed=j * 10 + i)
            cx = (b[0] + b[2]) / 2
            bm = ss_.m(rect(cx - 40, b[3] + 10, cx + 40, b[3] + 38, 8))
            ss_.A.paint(ss_.A.dilate(bm, 2), INK); ss_.fill(bm, hexc("#F4F4F2"), 0)
            ind = ss_.m(circle(cx, b[3] + 24, 7))
            ss_.A.paint(ind, hexc("#7DD8FF")); ss_.emit(ind, CYAN, 1.2); ss_.emit(ss_.A.blur(ind, 4), CYAN, 0.5)
    glass(s, (gx0 - 10, gy0 - 10, gx1 + 10, gy1 + 10), 14, refl=0.14)
    frame_rect(s, (gx0 - 10, gy0 - 10, gx1 + 10, gy1 + 10), 10, hexc("#C9CED6"), 14)
    s.fill(rect(50, 1350, 974, 1390, 8), hexc("#FF4F8B"), 0.0)
    s.fill(T("−18℃ でお届け  ・  ひとつずつ出てきます", "noto", (70, 1354, 954, 1386)), PAPER, 0)
    coin_panel(s.sub((40, 1400, 984, 1690)), 50, 1410, 974, 1680, body)
    s.fill(rect(60, 1700, 964, 1770, 8), hexc("#DDF4FF"), 0)
    s.fill(T("商品はすぐにお取り出しください", "noto", (80, 1710, 944, 1760)), hexc("#0B4A8A"), 0)
    dispenser(s.sub((200, 1780, 824, 1980)), 220, 1800, 804, 1960, body, "とりだしぐち")
    s.fill(rect(30, 1990, 994, 2030, 8), hexc("#16161A"), 0)
    s.bolts([(30, 30), (994, 30), (30, 1970), (994, 1970)], 9, rust=0.2)
    s.bake_backlight(1.05, tubes="v", tube_count=2)
    s.weather(0.6, streak=0.5)
    return s


# ======================================================================================
def cat_ninja(cx, cy, r_):
    head = ellipse(cx, cy, r_, r_ * 0.86)
    ears = union(poly([(cx - r_ * 0.9, cy - r_ * 0.3), (cx - r_ * 0.75, cy - r_ * 1.1), (cx - r_ * 0.2, cy - r_ * 0.75)]),
                 poly([(cx + r_ * 0.9, cy - r_ * 0.3), (cx + r_ * 0.75, cy - r_ * 1.1), (cx + r_ * 0.2, cy - r_ * 0.75)]))
    mask = rect(cx - r_ * 1.02, cy - r_ * 0.28, cx + r_ * 1.02, cy + r_ * 0.12, r_ * 0.1)
    eyes = union(ellipse(cx - r_ * 0.38, cy - r_ * 0.08, r_ * 0.16, r_ * 0.12), ellipse(cx + r_ * 0.38, cy - r_ * 0.08, r_ * 0.16, r_ * 0.12))
    return union(head, ears), mask, eyes


def gacha_unit(s, y0, name_jp, name_en, price, theme, seed, figures="cat"):
    x0, x1 = 40, 984
    y1 = y0 + 980
    s = s.sub((x0 - 4, y0 - 4, x1 + 4, y1 + 4))
    r = rng(seed)
    # body frame
    s.fill(rect(x0, y0, x1, y1, 30), theme, 0)
    t = s.A.ramp((x0, 0), (x1, 0))
    bm = s.m(rect(x0, y0, x1, y1, 30))
    s.A.paint(bm, col(theme)[None, None, :] * (1.06 - 0.16 * np.abs(t - 0.4))[..., None])
    s.A.paint(bm * (1 - s.A.shift(bm, 6, 6)), WHITE, 0.3)
    # display card (backlit)
    cx0, cy0, cx1, cy1 = x0 + 40, y0 + 36, x1 - 40, y0 + 330
    s.fill(rect(cx0, cy0, cx1, cy1, 12), PAPER, 1.0)
    cm = s.m(rect(cx0, cy0, cx1, cy1, 12))
    s.fill(s.A.halftone(s.A.ramp((cx0, 0), (cx1, 0)) * 0.4, 12, 45) * cm, lighten(theme, 0.4), 1.0)
    p = action_lines((cx0 + cx1) / 2, (cy0 + cy1) / 2, 120, 600, 70, 10, r=rng(seed + 1))
    s.fill(s.m(p) * cm, lighten(theme, 0.55), 1.0)
    tt = transformed(T(name_jp, "dela", (cx0 + 30, cy0 + 24, cx0 + 500, cy0 + 150), align=(0, 0.5)), rotate=-3)
    tm = s.m(tt)
    s.fill(s.A.dilate(tm, 10), INK, 0.03); s.fill(s.A.dilate(tm, 5), PAPER, 1.0); s.fill(tm, theme, 1.0)
    s.fill(T(name_en, "bangers", (cx0 + 30, cy0 + 160, cx0 + 460, cy0 + 220), align=(0, 0.5)), INK, 0.05)
    s.fill(rect(cx0 + 30, cy0 + 236, cx0 + 230, cy0 + 284, 8), INK, 0.03)
    s.fill(T("全6種", "noto", (cx0 + 40, cy0 + 240, cx0 + 220, cy0 + 280)), YEL, 1.0)
    # figures lineup
    cols_ = [MAG, CYAN, YEL, LIME, hexc("#B04BFF"), hexc("#FF7A2E")]
    for i in range(6):
        fx = cx0 + 600 + (i % 3) * 100
        fy = cy0 + 85 + (i // 3) * 130
        if figures == "cat":
            head, mask, eyes = cat_ninja(fx, fy, 42)
            hm_ = s.m(head)
            s.fill(s.A.dilate(hm_, 4), INK, 0.03); s.fill(hm_, [hexc("#F2F2F2"), hexc("#F2B060"), hexc("#3A3A3A"), hexc("#E8D0A8"), hexc("#9A9AA6"), hexc("#F2F2F2")][i], 1.0)
            s.fill(s.m(mask) * hm_, cols_[i], 1.0)
            s.fill(s.m(eyes) * hm_, PAPER, 1.0)
        else:
            # sushi racers: rice block + topping + wheels
            body = rect(fx - 40, fy - 8, fx + 40, fy + 24, 11)
            top = rect(fx - 44, fy - 32, fx + 44, fy - 2, 13)
            bm_ = s.m(union(body, top))
            s.fill(s.A.dilate(bm_, 4), INK, 0.03)
            s.fill(s.m(body), PAPER, 1.0)
            s.fill(s.m(top), [hexc("#FF7A5A"), hexc("#FFB347"), hexc("#E8231E"), hexc("#F2E6C8"), hexc("#FF9AB0"), hexc("#3A2A1A")][i], 1.0)
            for wx in (-24, 24):
                s.fill(circle(fx + wx, fy + 28, 13), INK, 0.03)
            s.fill(rect(fx - 44, fy - 42, fx - 22, fy - 32, 3), cols_[i], 1.0)
    frame_rect(s, (cx0, cy0, cx1, cy1), 6, hexc("#C9CED6"), 12)
    # capsule window
    wx0, wy0, wx1, wy1 = x0 + 60, y0 + 360, x1 - 60, y0 + 720
    s.fill(rect(wx0, wy0, wx1, wy1, 24), hexc("#DCEAF0"), 0.85)
    wm = s.m(rect(wx0, wy0, wx1, wy1, 24))
    caps = []
    for _ in range(140):
        rr_ = r.uniform(34, 44)
        x = r.uniform(wx0 + rr_, wx1 - rr_)
        y = wy1 - rr_ - (r.random() ** 0.7) * (wy1 - wy0 - 60)
        caps.append((y, x, rr_))
    caps.sort()
    ccols = [MAG, CYAN, YEL, LIME, hexc("#FF7A2E"), hexc("#B04BFF"), hexc("#FF3B30"), hexc("#3A7BFF")]
    for (y, x, rr_) in caps:
        c = ccols[int(r.integers(0, len(ccols)))]
        ang = r.uniform(0, 360)
        s0 = s
        s = s0.sub((x - rr_ - 4, y - rr_ - 4, x + rr_ + 4, y + rr_ + 4))
        wm = s.m(rect(wx0, wy0, wx1, wy1, 24))
        cm_ = s.m(circle(x, y, rr_)) * wm
        s.A.paint(s.A.dilate(cm_, 1.5) * wm, darken(c, 0.6))
        s.A.paint(cm_, mix(c, PAPER, 0.75))  # clear half
        half = s.m(transformed(rect(x - rr_ - 2, y, x + rr_ + 2, y + rr_ + 2), rotate=ang, pivot=(x, y))) * cm_
        s.A.paint(half, c)
        s.A.paint(s.m(ellipse(x - rr_ * 0.35, y - rr_ * 0.4, rr_ * 0.28, rr_ * 0.16)) * cm_, WHITE, 0.8)
        s.A.paint(s.m(circle(x, y, rr_), stroke=2.5, fill=False) * wm, darken(c, 0.4), 0.7)
        s = s0
    wm = s.m(rect(wx0, wy0, wx1, wy1, 24))
    glass(s, (wx0, wy0, wx1, wy1), 24, refl=0.22)
    frame_rect(s, (wx0, wy0, wx1, wy1), 10, hexc("#D8DCE2"), 24)
    # coin mechanism plate
    px0, py0, px1, py1 = x0 + 140, y0 + 745, x1 - 140, y0 + 950
    pm = s.m(rect(px0, py0, px1, py1, 16))
    brushed_metal(s, pm, hexc("#B9BEC6"), seed=seed)
    s.A.paint(pm * (1 - s.A.shift(pm, 4, 4)), WHITE, 0.4)
    s.A.paint(pm * (1 - s.A.shift(pm, -4, -4)), INK, 0.4)
    # price + coin slots
    s.fill(rect(px0 + 24, py0 + 24, px0 + 220, py0 + 92, 8), hexc("#E8231E"), 0)
    s.fill(T(price, "chakra", (px0 + 34, py0 + 30, px0 + 210, py0 + 86)), PAPER, 0)
    for k in range(int(price.strip("¥")) // 100):
        sx = px0 + 40 + k * 60
        s.fill(rect(sx, py0 + 110, sx + 40, py0 + 180, 6), hexc("#2A2C33"), 0)
        s.fill(rect(sx + 16, py0 + 118, sx + 24, py0 + 172, 3), INK, 0)
    # big turn knob
    kx, ky = px1 - 150, (py0 + py1) / 2
    km = s.m(circle(kx, ky, 82))
    s.A.paint(s.A.shift(s.A.dilate(km, 4), 6, 8), INK, 0.5)
    s.fill(km, hexc("#D8DCE2"), 0)
    s.A.paint(km * s.A.ramp((kx - 82, ky - 82), (kx + 82, ky + 82)), INK, 0.35)
    bar = s.m(transformed(rect(kx - 74, ky - 16, kx + 74, ky + 16, 14), rotate=30, pivot=(kx, ky)))
    s.fill(s.A.dilate(bar, 3), INK, 0); s.fill(bar, theme, 0)
    s.fill(T("まわす", "noto", (kx - 60, py1 - 34, kx + 60, py1 - 8)), INK, 0)
    s.fill(T("→", "noto", (kx + 86, ky - 30, kx + 120, ky + 30)), INK, 0)
    # exit flap
    s.fill(rect(x0 + 40, y0 + 760, x0 + 120, y0 + 940, 10), hexc("#16161A"), 0)
    s.fill(rect(x1 - 120, y0 + 760, x1 - 40, y0 + 940, 10), hexc("#16161A"), 0)
    s.fill(VT("とりだしぐち", "noto", (x0 + 62, y0 + 770, x0 + 98, y0 + 930)), PAPER, 0)
    s.fill(VT("ガチャ", "dela", (x1 - 100, y0 + 780, x1 - 60, y0 + 920)), YEL, 0)
    s.bolts([(x0 + 24, y0 + 24), (x1 - 24, y0 + 24), (x0 + 24, y1 - 24), (x1 - 24, y1 - 24)], 8, rust=0.3)


def vending_gacha():
    s = Sign("vending_front_gacha", 1024, 2048, bg=hexc("#121216"))
    s.fill(rect(0, 0, 1024, 2048), hexc("#1A1A20"), 0)
    gacha_unit(s, 30, "ねこ忍者", "NEKO NINJA mini figures", "¥300", hexc("#1E2A6A"), 41, "cat")
    gacha_unit(s, 1040, "すしドリフト", "SUSHI DRIFTERS pull-back", "¥200", hexc("#C8161D"), 42, "sushi")
    s.bake_backlight(1.0, tubes="h", tube_count=2)
    s.weather(0.6, streak=0.4)
    return s


REG = {"drinks": vending_drinks, "icecream": vending_icecream, "gacha": vending_gacha}


def sheets():
    paths = []
    for k in REG:
        n = f"vending_front_{k}"
        paths += [os.path.join(SIGN_DIR, f"{n}_albedo.png"), os.path.join(SIGN_DIR, f"{n}_emission.png")]
    paths = [p for p in paths if os.path.exists(p)]
    contact_sheet(paths, os.path.join(PREVIEWS, "vending.png"), cell=(300, 600), cols=6, bg="dark",
                  title="VENDING FRONTS  (albedo | emission)")


if __name__ == "__main__":
    args = sys.argv[1:] or list(REG)
    if args != ["--sheets"]:
        for a in args:
            s = REG[a]()
            pa, pe = s.save()
            print("wrote", os.path.basename(pa), os.path.basename(pe), flush=True)
    sheets()
