"""Storefront signs for INK DRIFT: TOKYO (all names/brands fictional).

Usage:
  python gen_signs.py            # render all signs + contact sheets
  python gen_signs.py v_ramen_ryuo h_bar_yotaka   # render selected
  python gen_signs.py --sheets   # only rebuild the contact sheets

Outputs: Game/Assets/InkDrift/Art/Signs/<name>_albedo.png / _emission.png
  v_*  vertical tategaki  512x2048
  h_*  horizontal        2048x512
  s_*  square            1024x1024
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from signlib import *  # noqa
from signlib import col, WHITE, STEEL, DARK_STEEL, BOARD_BLACK, WARM_WHITE

REG = {}


def sign(fn):
    REG[fn.__name__] = fn
    return fn


INK = C("ink"); PAPER = C("paper"); MAG = C("magenta"); CYAN = C("cyan"); YEL = C("yellow")
RED = C("red"); IND = C("indigo"); SAK = C("sakura"); LIME = C("lime")
SIGN_RED = hexc("#D8231F"); SIGN_GREEN = hexc("#0E8F4E"); NAVY = hexc("#13235B"); GOLD = hexc("#F2B705")
WHITE_ACRYL = hexc("#FBFAF4")


def V(name):
    return Sign(name, 512, 2048)


def Hs(name):
    return Sign(name, 2048, 512)


def S(name):
    return Sign(name, 1024, 1024)


def txt(s, path, fill, lit=1.0, outline=None, ow=0.0, olit=0.03, outline2=None, ow2=0.0, olit2=0.0):
    return s.outlined(path, fill, outline, ow, lit, olit, outline2, ow2, olit2)


def box_sign(s, face, frame_col=DARK_STEEL, fw=18, bolts=8, radius=6, lit=1.0):
    """Standard projecting box sign: metal frame around an acrylic face."""
    s.fill(rect(0, 0, s.w, s.h), frame_col, lit=0.0)
    s.fill(rect(fw, fw, s.w - fw, s.h - fw), face, lit=lit)
    return (fw, fw, s.w - fw, s.h - fw)


def finish_box(s, fw=18, frame_col=DARK_STEEL, bolts=8, gloss=True, grime=0.8, tubes="v", gain=1.0, warm=0.0):
    if gloss:
        acrylic_gloss(s, (fw, fw, s.w - fw, s.h - fw), 0.07)
    s.frame(0, 0, s.w, s.h, fw, frame_col, bolts=bolts)
    s.bake_backlight(gain=gain, tubes=tubes, warm=warm)
    s.weather(grime, top_band=fw)


def floor_badge(s, cx, cy, r_, text, bg, fg, lit=1.0, font="chakra"):
    s.fill(circle(cx, cy, r_), bg, lit)
    txt(s, T(text, font, (cx - r_ * 0.62, cy - r_ * 0.42, cx + r_ * 0.62, cy + r_ * 0.42)), fg, lit)


def tag_burst(s, cx, cy, rx, ry, fill, outline, text, tcol, font="dela", n=16, seed=1, lit=1.0, rot=0.0):
    p = starburst(cx, cy, rx, ry, n=n, inner=0.78, jitter=0.12, r=rng(seed), rot=rot)
    s.fill(s.A.dilate(s.m(p), 5), outline, 0.05)
    s.fill(p, fill, lit)
    if "\n" in text:
        lines = text.split("\n")
        hh = ry * 1.05 / len(lines)
        for i, ln in enumerate(lines):
            y0 = cy - ry * 0.52 + i * hh
            txt(s, T(ln, font, (cx - rx * 0.62, y0, cx + rx * 0.62, y0 + hh * 0.86)), tcol, lit)
    else:
        txt(s, T(text, font, (cx - rx * 0.6, cy - ry * 0.36, cx + rx * 0.6, cy + ry * 0.36)), tcol, lit)


# ======================================================================================
# VERTICAL 512 x 2048
# ======================================================================================
@sign
def v_ramen_ryuo():
    s = V("v_ramen_ryuo")
    fw = 18
    box_sign(s, SIGN_RED, fw=fw)
    # top black band with bowl
    s.fill(rect(fw, fw, 512 - fw, 360), INK, lit=0.04)
    s.fill(picto_bowl((90, 70, 422, 300)), PAPER, lit=1.0)
    txt(s, T("創業一九八七年", "noto", (70, 312, 442, 348)), YEL, 1.0)
    # yellow stripe
    s.fill(rect(fw, 360, 512 - fw, 374), YEL, lit=1.0)
    # main vertical text
    p = VT("ラーメン", "dela", (86, 420, 426, 1500), spacing=1.02)
    txt(s, p, PAPER, 1.0, INK, 14, 0.03)
    # name badge
    s.fill(circle(256, 1690, 150), INK, 0.04)
    s.fill(circle(256, 1690, 136), YEL, 1.0)
    txt(s, VT("龍王", "dela", (190, 1570, 322, 1810)), INK, 0.05)
    s.fill(rect(fw, 1860, 512 - fw, 2048 - fw), INK, lit=0.04)
    txt(s, T("とんこつ・醤油", "noto", (60, 1884, 452, 1940)), PAPER, 1.0)
    txt(s, T("11:00 - 翌3:00", "chakra", (110, 1952, 402, 2000)), YEL, 1.0)
    finish_box(s, fw)
    return s


@sign
def v_izakaya_sumida():
    s = V("v_izakaya_sumida")
    fw = 16
    box_sign(s, WHITE_ACRYL, frame_col=hexc("#2B2622"), fw=fw)
    s.fill(rect(fw, fw, 512 - fw, 330), hexc("#B3141B"), lit=1.0)
    s.fill(picto_mug((150, 54, 362, 236)), PAPER, 1.0)
    txt(s, T("生ビール", "noto", (90, 252, 422, 310)), PAPER, 1.0)
    # big brush-ish text
    p = VT("居酒屋", "reggae", (60, 400, 370, 1460), spacing=1.0)
    txt(s, p, INK, 0.06)
    # secondary column
    p2 = VT("炭火焼", "noto", (380, 420, 470, 820))
    txt(s, p2, hexc("#B3141B"), 1.0)
    # name in red seal box
    s.fill(rect(120, 1540, 392, 1900, 10), hexc("#B3141B"), 1.0)
    s.stroke(rect(136, 1556, 376, 1884, 6), PAPER, 6, 1.0)
    txt(s, VT("すみだ", "reggae", (170, 1576, 342, 1866)), PAPER, 1.0)
    txt(s, T("03-5912-4410", "chakra", (100, 1940, 412, 1990)), INK, 0.06)
    finish_box(s, fw, frame_col=hexc("#2B2622"), warm=0.25, grime=1.1)
    return s


@sign
def v_karaoke_utahime():
    s = V("v_karaoke_utahime")
    s.fill(rect(0, 0, 512, 2048), hexc("#141018"), lit=0)
    s.fill(rect(14, 14, 498, 2034, 22), hexc("#1E1A26"), lit=0)
    # neon border
    s.neon(rect(40, 40, 472, 2008, 30), MAG, r=4.2, clips=0.6)
    s.neon(rect(58, 58, 454, 1990, 18), CYAN, r=3.0, clips=0.3, halo=0.6)
    # mic picto (outline neon)
    s.neon_text(picto_mic((176, 110, 336, 400)), YEL, r=4.5, mode="outline", inset=4, clips=0.5)
    s.neon(picto_mic_grille((176, 110, 336, 400)), YEL, r=2.0, halo=0.4, shadow=0.2)
    # main
    s.neon_text(VT("カラオケ", "noto_bold", (110, 470, 402, 1420), spacing=1.0), CYAN, r=6.5, mode="skeleton", clips=1.0)
    s.neon_text(VT("歌姫", "noto_bold", (140, 1480, 372, 1860)), MAG, r=6.0, mode="skeleton", clips=1.0)
    # printed small
    txt(s, T("B1F", "chakra", (200, 1900, 312, 1960)), PAPER, 0.0)
    s.neon(T("B1F", "chakra", (200, 1900, 312, 1960)), PAPER, r=1.6, halo=0.4, shadow=0.2)
    s.weather(0.6)
    return s


@sign
def v_yakiniku_homura():
    s = V("v_yakiniku_homura")
    fw = 18
    box_sign(s, hexc("#121014"), fw=fw, lit=0.05)
    # flame motif behind text
    for i, (y, sc) in enumerate([(1080, 1.0), (560, 0.7)]):
        pass
    fl = picto_flame((60, 120, 452, 560))
    grad_fill(s, fl, 120, 560, [(0, YEL), (0.45, hexc("#FF8A00")), (1, RED)], lit=1.0)
    s.fill(picto_flame_inner((60, 120, 452, 560)), hexc("#121014"), 0.05)
    txt(s, VT("炎", "dela", (170, 330, 342, 530)), PAPER, 1.0, INK, 8)
    p = VT("焼肉", "dela", (70, 640, 442, 1500))
    F = s.m(p)
    s.fill(s.A.dilate(F, 18), PAPER, 1.0)
    s.fill(s.A.dilate(F, 10), INK, 0.03)
    grad_fill(s, F, 640, 1500, [(0, YEL), (0.4, hexc("#FF7A00")), (1, RED)], lit=1.0)
    # yellow tag
    s.fill(rect(70, 1580, 442, 1760, 12), YEL, 1.0)
    txt(s, T("食べ放題", "dela", (96, 1600, 416, 1700)), INK, 0.04)
    txt(s, T("90分 ¥3,980", "chakra", (110, 1704, 402, 1748)), INK, 0.04)
    txt(s, VT("国産黒毛和牛", "noto", (20, 0, 0, 0)) if False else T("国産黒毛和牛", "noto", (70, 1800, 442, 1860)), PAPER, 0.9)
    txt(s, T("2F", "chakra", (210, 1890, 302, 1990)), YEL, 1.0)
    finish_box(s, fw, grime=0.9)
    return s


@sign
def v_sushi_hamachidori():
    s = V("v_sushi_hamachidori")
    fw = 16
    box_sign(s, WHITE_ACRYL, frame_col=hexc("#C8C3B6"), fw=fw)
    # seigaiha waves lower part
    clipm = s.m(rect(fw, 1500, 512 - fw, 2048 - fw))
    seigaiha_paint(s, (fw - 40, 1500, 560, 2060), 52, WHITE_ACRYL, hexc("#1D3C8F"), clip=clipm)
    s.fill(rect(fw, 1490, 512 - fw, 1504), hexc("#1D3C8F"), 1.0)
    # fish
    s.fill(picto_fish((110, 80, 402, 250)), hexc("#C8102E"), 1.0)
    p = VT("寿司", "reggae", (70, 330, 400, 1150))
    txt(s, p, hexc("#1D3C8F"), 1.0)
    s.fill(rect(388, 360, 470, 900, 6), hexc("#C8102E"), 1.0)
    txt(s, VT("浜千鳥", "noto", (398, 380, 460, 880)), PAPER, 1.0)
    txt(s, VT("江戸前", "noto", (80, 1180, 430, 1440)), hexc("#C8102E"), 1.0)
    finish_box(s, fw, frame_col=hexc("#C8C3B6"), grime=0.7)
    return s


@sign
def v_drug_midori():
    s = V("v_drug_midori")
    fw = 18
    box_sign(s, YEL, frame_col=hexc("#E7E4DC"), fw=fw)
    s.fill(circle(256, 250, 200), PAPER, 1.0)
    s.stroke(circle(256, 250, 186), hexc("#E0171F"), 16, 1.0)
    txt(s, T("薬", "noto", (120, 110, 392, 390)), hexc("#E0171F"), 1.0)
    p = VT("ドラッグストア", "noto", (110, 500, 402, 1500), spacing=0.98)
    txt(s, p, INK, 0.05)
    s.fill(rect(70, 1560, 442, 1860, 14), SIGN_GREEN, 1.0)
    txt(s, VT("ミドリ", "dela", (170, 1580, 342, 1840)), PAPER, 1.0)
    txt(s, T("化粧品・日用品", "noto", (60, 1900, 452, 1990)), INK, 0.05)
    finish_box(s, fw, frame_col=hexc("#E7E4DC"), grime=0.7)
    return s


@sign
def v_hotel_gekko():
    s = V("v_hotel_gekko")
    s.fill(rect(0, 0, 512, 2048), hexc("#120C1C"), lit=0)
    s.fill(rect(16, 16, 496, 2032, 10), hexc("#2A1640"), lit=0)
    s.stroke(rect(16, 16, 496, 2032, 10), hexc("#8A7CA0"), 4, 0)
    # moon neon
    s.neon_text(picto_moon((150, 80, 362, 300)), YEL, r=5.0, mode="outline", inset=6, clips=0.6)
    for i, (x, y, rr) in enumerate([(380, 110, 26), (120, 260, 18), (400, 300, 14)]):
        s.neon(picto_star((x - rr, y - rr, x + rr, y + rr)), YEL, r=2.2, halo=0.5)
    s.neon_text(VT("ホテル", "noto_bold", (140, 360, 372, 1080)), hexc("#C04BFF"), r=6.0, mode="skeleton", clips=1.0)
    s.neon_text(VT("月光", "dela", (120, 1120, 392, 1600)), CYAN, r=4.0, mode="outline", inset=7, clips=0.8)
    # printed rates panel (backlit small)
    s.fill(rect(70, 1660, 442, 1840, 8), hexc("#F4EEFF"), 0.9)
    txt(s, T("休憩 ¥3,800〜", "noto", (90, 1676, 422, 1744)), hexc("#2A1640"), 0.05)
    txt(s, T("宿泊 ¥7,500〜", "noto", (90, 1760, 422, 1828)), hexc("#2A1640"), 0.05)
    # vacancy indicator
    s.fill(rect(80, 1880, 250, 1990, 8), hexc("#0B3A1E"), 0)
    s.fill(rect(262, 1880, 432, 1990, 8), hexc("#3A0B10"), 0)
    m1 = txt(s, T("空室", "noto", (100, 1896, 230, 1974)), hexc("#9CF3B4"), 0.0)
    txt(s, T("満室", "noto", (282, 1896, 412, 1974)), hexc("#7A3C44"), 0.0)
    s.emit(s.m(rect(80, 1880, 250, 1990, 8)), hexc("#0FA54A"), 0.35)
    s.emit(m1, hexc("#7DFFAF"), 1.2)
    s.emit(s.A.blur(m1, 8), hexc("#2BFF7A"), 0.6)
    s.bake_backlight(0.9)
    s.weather(0.6)
    return s


@sign
def v_pachinko_ginga():
    s = V("v_pachinko_ginga")
    fw = 22
    s.fill(rect(0, 0, 512, 2048), hexc("#B8860B"), lit=0)
    grad_fill(s, rect(fw, fw, 512 - fw, 2048 - fw), fw, 2048, [(0, hexc("#2A0A5E")), (0.5, hexc("#7A0A6A")), (1, hexc("#D0102E"))], lit=1.0)
    # star field
    r = rng("pachi")
    for i in range(26):
        x, y, rr = r.uniform(50, 462), r.uniform(60, 1990), r.uniform(8, 22)
        s.fill(picto_star((x - rr, y - rr, x + rr, y + rr)), YEL, 1.0, opacity=0.85)
    # rainbow text
    p = VT("パチンコ", "dela", (90, 120, 422, 1280), spacing=1.02)
    F = s.m(p)
    s.fill(s.A.dilate(F, 24), INK, 0.03)
    s.fill(s.A.dilate(F, 15), PAPER, 1.0)
    t = s.A.ramp((0, 120), (0, 1280))
    rain = gradient_map(t, [(0, hexc("#FF2D2D")), (0.2, hexc("#FF9A00")), (0.4, YEL), (0.6, hexc("#34E34B")),
                            (0.8, hexc("#00B7FF")), (1, hexc("#B04BFF"))])
    s.fill(F, rain, 1.0)
    # 銀河 gold badge
    tag_burst(s, 256, 1500, 205, 175, YEL, INK, "銀河", hexc("#C8102E"), n=22, seed=3)
    s.fill(rect(60, 1720, 452, 1830, 10), INK, 0.03)
    txt(s, T("新台入替", "dela", (80, 1734, 432, 1818)), YEL, 1.0)
    txt(s, T("10:00 OPEN", "chakra", (100, 1860, 412, 1930)), PAPER, 1.0)
    s.frame(0, 0, 512, 2048, fw, hexc("#C9A227"), bolts=0)
    s.bake_backlight(1.0)
    # chase bulbs along border
    pts = []
    for i in range(48):
        pts.append((fw / 2, 30 + i * (1988 / 47)))
        pts.append((512 - fw / 2, 30 + i * (1988 / 47)))
    for i in range(1, 11):
        pts.append((i * 512 / 11, fw / 2)); pts.append((i * 512 / 11, 2048 - fw / 2))
    s.bulbs(pts, 7.5, hexc("#FFC86A"))
    s.weather(0.6)
    return s


@sign
def v_manga_tengoku():
    s = V("v_manga_tengoku")
    fw = 18
    box_sign(s, hexc("#19C3E6"), frame_col=hexc("#E9E9EC"), fw=fw)
    s.fill(rect(fw, fw, 512 - fw, 300), INK, 0.04)
    txt(s, T("24H", "chakra", (70, 50, 442, 210)), YEL, 1.0)
    txt(s, T("年中無休", "noto", (130, 220, 382, 280)), PAPER, 1.0)
    halftone_fill(s, s.m(rect(fw, 300, 512 - fw, 2048 - fw)), hexc("#0E9CC0"), 16, s.A.ramp((0, 300), (0, 2048)) * 0.5 + 0.08, lit=1.0)
    txt(s, VT("まんが喫茶", "noto", (322, 370, 474, 1180), spacing=0.98), INK, 0.05)
    p = VT("漫画天国", "dela", (40, 360, 280, 1440))
    txt(s, p, MAG, 1.0, PAPER, 9, 1.0, INK, 8)
    s.fill(picto_book((330, 1240, 470, 1380)), PAPER, 1.0)
    s.fill(rect(60, 1520, 452, 1800, 12), PAPER, 1.0)
    for i, w in enumerate(["ネット", "ダーツ", "シャワー"]):
        txt(s, T(w, "noto", (90, 1540 + i * 84, 422, 1606 + i * 84)), hexc("#0E5C78"), 0.95)
    floor_badge(s, 256, 1900, 80, "5F", INK, YEL, 1.0)
    finish_box(s, fw, frame_col=hexc("#E9E9EC"))
    return s


def tenant_stack(name, tenants, frame=hexc("#EDEDEA"), seed=0):
    s = V(name)
    fw = 16
    s.fill(rect(0, 0, 512, 2048), frame, lit=0)
    n = len(tenants)
    gap = 14
    top = fw
    hh = (2048 - 2 * fw - gap * (n - 1)) / n
    for i, tdef in enumerate(tenants):
        y0 = top + i * (hh + gap)
        y1 = y0 + hh
        box = (fw, y0, 512 - fw, y1)
        tdef(s, box)
        # thin divider frame with screws
        s.stroke(rect(*box), darken(frame, 0.35), 3, 0)
    s.frame(0, 0, 512, 2048, fw, frame, bolts=0)
    for i in range(1, n):
        y = top + i * (hh + gap) - gap / 2
        s.fill(rect(0, y - gap / 2, 512, y + gap / 2), frame, 0)
        s.bolts([(40, y), (472, y)], 5, rust=0.4)
    acrylic_gloss(s, (0, 0, 512, 2048), 0.05)
    s.bake_backlight(1.0, tubes="v")
    s.weather(0.9, top_band=16)
    return s


def _ten(fl, bg, fg, name, font="noto", sub=None, subcol=None, badge_bg=INK, badge_fg=YEL, lit=1.0, picto=None,
         picto_col=None, horizontal=False):
    def f(s, box):
        x0, y0, x1, y1 = box
        s.fill(rect(*box), bg, lit)
        h = y1 - y0
        floor_badge(s, x0 + 60, y0 + 62, 44, fl, badge_bg, badge_fg, 1.0 if lit else 0.2)
        if picto is not None:
            s.fill(picto((x0 + 22, y1 - 120, x0 + 112, y1 - 24)), picto_col if picto_col is not None else fg, lit)
        if horizontal:
            txt(s, T(name, font, (x0 + 120, y0 + h * 0.18, x1 - 24, y0 + h * 0.62)), fg, lit)
            if sub:
                txt(s, T(sub, "noto", (x0 + 120, y0 + h * 0.68, x1 - 24, y0 + h * 0.86)), subcol if subcol is not None else fg, lit)
        else:
            txt(s, VT(name, font, (x0 + 140, y0 + 22, x1 - 80, y1 - 22)), fg, lit)
            if sub:
                txt(s, VT(sub, "noto_bold", (x1 - 74, y0 + 30, x1 - 22, y1 - 30)), subcol if subcol is not None else fg, lit)
    return f


@sign
def v_tenants_a():
    return tenant_stack("v_tenants_a", [
        _ten("6F", INK, GOLD, "BAR 夜鷹", font="dela", horizontal=True, sub="Whisky & Cocktail", subcol=PAPER,
             badge_bg=GOLD, badge_fg=INK, picto=picto_cocktail),
        _ten("5F", hexc("#0F7A3C"), PAPER, "麻雀東南荘", font="noto", sub="フリー・セット", subcol=YEL),
        _ten("4F", WHITE_ACRYL, hexc("#147A5C"), "整体ほぐし堂", font="noto", sub="60分¥2980", subcol=hexc("#D02030")),
        _ten("3F", hexc("#1E5BD8"), PAPER, "英会話", font="dela", sub="SPEAK UP", subcol=YEL, badge_bg=PAPER, badge_fg=hexc("#1E5BD8")),
        _ten("2F", hexc("#FF6FAE"), PAPER, "スナック蝶", font="reggae", picto=picto_butterfly, picto_col=PAPER),
        _ten("1F", hexc("#F28C1E"), INK, "立ち飲み角", font="dela", sub="せんべろ", subcol=PAPER, badge_bg=PAPER, badge_fg=INK),
    ])


@sign
def v_tenants_b():
    return tenant_stack("v_tenants_b", [
        _ten("5F", hexc("#5B2A86"), PAPER, "占い星読み", font="reggae", sub="手相・タロット", subcol=SAK,
             picto=lambda b: picto_star(b), picto_col=YEL),
        _ten("4F", WHITE_ACRYL, MAG, "ネイルサロン", font="noto", sub="NAIL ROOM", subcol=INK),
        _ten("3F", hexc("#0B0B12"), CYAN, "ダーツ&BAR", font="dela", sub="DARTS", subcol=MAG, badge_bg=CYAN, badge_fg=INK),
        _ten("2F", hexc("#FFE600"), INK, "金券ショップ", font="noto", sub="高価買取", subcol=hexc("#D02030"), badge_bg=INK, badge_fg=YEL),
        _ten("B1", hexc("#D21F3C"), PAPER, "ライブハウス爆音", font="dela", sub="LIVE", subcol=YEL, picto=picto_note,
             picto_col=YEL),
    ], frame=hexc("#2C2D33"))


@sign
def v_snack_cho():
    s = V("v_snack_cho")
    s.fill(rect(0, 0, 512, 2048), hexc("#1A0B14"), lit=0)
    wood(s, s.m(rect(14, 14, 498, 2034, 16)), hexc("#3A1426"), seed=4, vertical=True)
    s.stroke(rect(14, 14, 498, 2034, 16), GOLD, 5, 0.0)
    s.neon_text(picto_butterfly((90, 120, 422, 520)), SAK, r=4.0, mode="outline", inset=5, clips=0.6)
    s.neon_text(VT("スナック", "noto_bold", (170, 600, 342, 1200)), MAG, r=5.2, mode="skeleton", clips=1)
    s.neon_text(VT("蝶", "noto_bold", (90, 1250, 422, 1650)), hexc("#FF4FB0"), r=5.5, mode="skeleton", clips=1)
    txt(s, T("会員制", "noto", (150, 1730, 362, 1800)), GOLD, 0.9)
    txt(s, T("19:00〜", "chakra", (150, 1820, 362, 1890)), GOLD, 0.9)
    s.neon(rect(60, 1700, 452, 1920, 20), CYAN, r=2.6, halo=0.6, clips=0.4)
    s.bake_backlight(0.9, tubes=None)
    s.weather(0.7)
    return s


@sign
def v_soba_sarashina():
    s = V("v_soba_sarashina")
    s.fill(rect(0, 0, 512, 2048), hexc("#2A1C12"), lit=0)
    m = s.m(rect(20, 60, 492, 1990, 6))
    wood(s, m, hexc("#B98A55"), seed=2, vertical=True, ring=0.35)
    # carved & ink-filled text
    p = VT("そば", "reggae", (70, 200, 442, 1200))
    F = s.m(p)
    s.A.paint(s.A.shift(F, 3, 4), hexc("#5A3A1E"), 0.6)
    s.fill(F, hexc("#121010"))
    p2 = VT("更科", "noto", (170, 1280, 342, 1660))
    s.fill(p2, hexc("#7A1414"))
    s.fill(rect(160, 1720, 352, 1900, 8), hexc("#A11C1C"))
    txt(s, VT("手打", "noto", (205, 1736, 307, 1884)), PAPER, 0.0)
    # hanging hardware
    s.fill(rect(0, 0, 512, 60), hexc("#1E1A16"))
    s.bolts([(80, 30), (432, 30)], 12, rust=0.7)
    # emission: gooseneck lamps pool of light from top
    lamp = np.clip(1 - s.A.radial(256, -120, 1500), 0, 1) ** 1.6
    rgb = s.A.px[..., :3] * (lamp * m)[..., None] * mix(WHITE, WARM_WHITE, 0.8)
    s.emit_rgb(rgb, 0.75)
    s.weather(1.2)
    return s


@sign
def v_dental_sakura():
    s = V("v_dental_sakura")
    fw = 16
    box_sign(s, WHITE_ACRYL, frame_col=hexc("#F2F2F0"), fw=fw)
    # sakura flower
    cx, cy = 256, 230
    for k in range(5):
        a = math.radians(-90 + k * 72)
        petal = ellipse(cx + math.cos(a) * 82, cy + math.sin(a) * 82, 70, 92)
        petal = transformed(petal, rotate=math.degrees(a) + 90, pivot=(cx + math.cos(a) * 82, cy + math.sin(a) * 82))
        notch = circle(cx + math.cos(a) * 168, cy + math.sin(a) * 168, 26)
        s.fill(skia.Op(petal, notch, skia.PathOp.kDifference_PathOp), hexc("#FF8DBB"), 1.0)
    s.fill(circle(cx, cy, 40), hexc("#FFE16B"), 1.0)
    s.fill(picto_tooth((cx - 26, cy - 26, cx + 26, cy + 26)), PAPER, 1.0)
    txt(s, VT("さくら歯科", "noto", (150, 440, 362, 1500), spacing=1.04), hexc("#127C78"), 1.0)
    txt(s, VT("一般・小児・矯正", "noto_bold", (390, 460, 446, 1300)), hexc("#FF6FA3"), 1.0)
    s.fill(rect(80, 1580, 432, 1720, 10), hexc("#127C78"), 1.0)
    txt(s, T("診療中", "noto", (110, 1598, 402, 1700)), PAPER, 1.0)
    floor_badge(s, 256, 1860, 90, "3F", hexc("#FF6FA3"), PAPER, 1.0)
    finish_box(s, fw, frame_col=hexc("#F2F2F0"), grime=0.5)
    return s


@sign
def v_fudosan_marukado():
    s = V("v_fudosan_marukado")
    fw = 16
    box_sign(s, hexc("#1550C8"), frame_col=hexc("#D9DADF"), fw=fw)
    s.fill(picto_house((110, 70, 402, 340)), PAPER, 1.0)
    txt(s, VT("不動産", "noto", (90, 420, 422, 1300), spacing=1.0), PAPER, 1.0)
    s.fill(rect(70, 1380, 442, 1800, 8), PAPER, 1.0)
    s.fill(circle(256, 1470, 64), hexc("#E6301E"), 1.0)
    txt(s, T("角", "noto", (214, 1428, 298, 1512)), PAPER, 1.0)
    txt(s, VT("丸角", "dela", (190, 1550, 322, 1790)), hexc("#1550C8"), 1.0)
    txt(s, T("賃貸・売買", "noto", (70, 1850, 442, 1920)), YEL, 1.0)
    txt(s, T("03-3388-0721", "chakra", (90, 1940, 422, 1996)), PAPER, 1.0)
    finish_box(s, fw, frame_col=hexc("#D9DADF"))
    return s


# ======================================================================================
# HORIZONTAL 2048 x 512
# ======================================================================================
@sign
def h_konbini_yorumart():
    s = Hs("h_konbini_yorumart")
    fw = 14
    box_sign(s, hexc("#F7F7F4"), frame_col=hexc("#E0E0DE"), fw=fw)
    # stripes band across bottom
    s.fill(rect(fw, 330, 2048 - fw, 372), hexc("#2A1F7A"), 1.0)
    s.fill(rect(fw, 372, 2048 - fw, 412), MAG, 1.0)
    s.fill(rect(fw, 412, 2048 - fw, 452), CYAN, 1.0)
    s.fill(rect(fw, 452, 2048 - fw, 512 - fw), hexc("#2A1F7A"), 1.0)
    # logo block
    s.fill(rect(60, 40, 400, 312, 40), hexc("#2A1F7A"), 1.0)
    s.fill(picto_moon((110, 70, 260, 220)), YEL, 1.0)
    s.fill(picto_star((250, 70, 330, 150)), YEL, 1.0)
    txt(s, T("YORU", "chakra", (110, 220, 350, 296)), PAPER, 1.0)
    txt(s, T("ヨルマート", "noto", (440, 60, 1560, 230), tracking=0.02), hexc("#2A1F7A"), 1.0)
    txt(s, T("YORU MART", "chakra", (444, 240, 1180, 312), tracking=0.12), MAG, 1.0)
    # 24H badge
    s.fill(rect(1620, 40, 1990, 312, 30), MAG, 1.0)
    txt(s, T("24", "chakra", (1650, 58, 1880, 260)), PAPER, 1.0)
    txt(s, T("H", "chakra", (1880, 130, 1960, 260)), YEL, 1.0)
    txt(s, T("OPEN", "chakra", (1660, 262, 1950, 300), tracking=0.4), PAPER, 1.0)
    finish_box(s, fw, frame_col=hexc("#E0E0DE"), tubes="h", grime=0.5, bolts=12)
    return s


@sign
def h_gamecenter_neoarcade():
    s = Hs("h_gamecenter_neoarcade")
    s.fill(rect(0, 0, 2048, 512), hexc("#0D0D12"), 0)
    s.fill(rect(10, 10, 2038, 502, 14), hexc("#17161E"), 0)
    # LED matrix panel
    s.fill(rect(40, 40, 1240, 300, 8), hexc("#08080A"), 0)
    led_text = T("ゲームセンター", "noto", (56, 58, 1224, 282))
    F = s.m(led_text)
    # rainbow LED colours across x: draw in 4 colour bands using masks
    xs = s.A.ramp((40, 0), (1240, 0))
    on = s.led_matrix(F, (40, 40, 1240, 300), PAPER, pitch=9, glow=0.0)
    # recolour lit dots in emission with rainbow
    rain = gradient_map(xs, [(0, MAG), (0.33, YEL), (0.66, LIME), (1, CYAN)])
    s.E -= on[..., None] * mix(PAPER, WHITE, 0.15) * 1.1
    s.emit_rgb(rain * on[..., None], 1.25)
    s.emit_rgb(rain * blur(on, 9 * 2 * 0.7)[..., None], 0.6)
    # NEO ARCADE neon
    s.neon_text(T("NEO", "chakra", (1300, 50, 1700, 280)), MAG, r=5.0, mode="outline", inset=7, clips=0.8)
    s.neon_text(T("ARCADE", "chakra", (1300, 300, 2000, 470)), CYAN, r=4.5, mode="outline", inset=6, clips=0.8)
    s.neon_text(picto_gamepad((1730, 60, 2000, 270)), YEL, r=4.0, mode="outline", inset=5, clips=0.6)
    # printed strip
    s.fill(rect(40, 330, 1240, 470, 8), YEL, 0.9)
    txt(s, T("UFOキャッチャー・プリクラ・音ゲー・メダル", "noto", (70, 352, 1210, 446)), INK, 0.05)
    s.bake_backlight(1.0, tubes="h")
    s.weather(0.6)
    return s


@sign
def h_cafe_hoshizora():
    s = Hs("h_cafe_hoshizora")
    fw = 16
    box_sign(s, hexc("#F3E6C8"), frame_col=hexc("#5A3A22"), fw=fw)
    # retro stripes
    for i, c in enumerate([hexc("#E2711D"), hexc("#C4421A"), hexc("#7A3B1A")]):
        s.fill(rect(fw, 380 + i * 34, 2048 - fw, 380 + i * 34 + 24), c, 1.0)
    s.fill(circle(250, 220, 170), hexc("#7A3B1A"), 1.0)
    s.fill(picto_cup((130, 110, 370, 340)), hexc("#F3E6C8"), 1.0)
    txt(s, T("純喫茶", "noto", (480, 44, 800, 120)), hexc("#C4421A"), 1.0)
    p = T("ほしぞら", "reggae", (470, 120, 1560, 360))
    txt(s, p, hexc("#5A2A12"), 0.95, hexc("#F7C873"), 0, 1.0)
    for (x, y, rr) in [(1600, 90, 30), (1680, 170, 18), (1590, 250, 14)]:
        s.fill(picto_star((x - rr, y - rr, x + rr, y + rr)), hexc("#E2711D"), 1.0)
    txt(s, T("COFFEE & NAPOLITAN", "chakra", (1640, 80, 2000, 140)), hexc("#5A2A12"), 0.95)
    txt(s, T("創業 昭和四十八年", "noto", (1660, 170, 2000, 230)), hexc("#7A3B1A"), 0.95)
    txt(s, T("モーニング 7:00〜", "noto", (1660, 260, 2000, 330)), hexc("#C4421A"), 0.95)
    finish_box(s, fw, frame_col=hexc("#5A3A22"), tubes="h", warm=0.4, grime=1.0, bolts=12)
    return s


@sign
def h_pharmacy_hikari():
    s = Hs("h_pharmacy_hikari")
    fw = 14
    box_sign(s, WHITE_ACRYL, frame_col=hexc("#DADBD8"), fw=fw)
    s.fill(rect(fw, fw, 470, 512 - fw), SIGN_GREEN, 1.0)
    s.fill(circle(242, 256, 160), PAPER, 1.0)
    s.fill(picto_capsule((122, 136, 362, 376)), SIGN_GREEN, 1.0)
    txt(s, T("ひかり薬局", "noto", (540, 60, 1560, 300)), SIGN_GREEN, 1.0)
    s.stroke(rect(540, 340, 960, 450, 8), SIGN_GREEN, 6, 1.0)
    txt(s, T("調剤薬局", "noto", (566, 356, 934, 434)), SIGN_GREEN, 1.0)
    txt(s, T("処方せん受付", "noto", (1000, 352, 1560, 438)), INK, 0.05)
    s.fill(rect(1620, 70, 1990, 440, 16), hexc("#F2F7F4"), 1.0)
    s.stroke(rect(1620, 70, 1990, 440, 16), SIGN_GREEN, 5, 1.0)
    txt(s, T("営業時間", "noto", (1660, 96, 1950, 160)), SIGN_GREEN, 1.0)
    txt(s, T("9:00-19:00", "chakra", (1650, 190, 1960, 270)), INK, 0.05)
    txt(s, T("日・祝 休", "noto", (1680, 320, 1930, 400)), hexc("#D02030"), 1.0)
    finish_box(s, fw, frame_col=hexc("#DADBD8"), tubes="h", grime=0.4, bolts=12)
    return s


@sign
def h_ramen_ichibanboshi():
    s = Hs("h_ramen_ichibanboshi")
    fw = 18
    box_sign(s, YEL, frame_col=INK, fw=fw)
    halftone_fill(s, s.m(rect(fw, fw, 2048 - fw, 512 - fw)), hexc("#FFB800"), 18,
                  s.A.ramp((0, 0), (2048, 0)) * 0.45, angle=45, lit=1.0)
    s.fill(picto_star((60, 50, 470, 460)), hexc("#E0171F"), 1.0)
    txt(s, T("一番", "dela", (150, 190, 380, 300)), YEL, 1.0)
    p = T("らーめん", "dela", (520, 50, 1500, 330))
    txt(s, p, hexc("#E0171F"), 1.0, INK, 14, 0.03)
    s.fill(rect(530, 360, 1080, 470, 10), INK, 0.03)
    txt(s, T("一番星", "dela", (560, 372, 1050, 458)), PAPER, 1.0)
    txt(s, T("背脂醤油", "noto", (1110, 372, 1480, 458)), INK, 0.03)
    tag_burst(s, 1780, 256, 230, 210, hexc("#E0171F"), INK, "替玉\n無料", PAPER, n=20, seed=4)
    finish_box(s, fw, frame_col=INK, tubes="h", bolts=12)
    return s


@sign
def h_izakaya_tanuki():
    s = Hs("h_izakaya_tanuki")
    fw = 16
    box_sign(s, hexc("#151214"), frame_col=hexc("#4A2A1A"), fw=fw, lit=0.05)
    # lanterns graphic
    for cx in (150, 1900):
        s.fill(ellipse(cx, 256, 95, 150), hexc("#D8231F"), 1.0)
        for k in range(-4, 5):
            s.stroke(ellipse(cx, 256 + k * 30, 95 * math.sqrt(max(0.05, 1 - (k * 30 / 150) ** 2)), 4), hexc("#8B1010"), 3, 0.6)
        s.fill(rect(cx - 50, 92, cx + 50, 120, 4), INK, 0.0)
        s.fill(rect(cx - 50, 392, cx + 50, 420, 4), INK, 0.0)
        txt(s, VT("酒", "noto", (cx - 50, 200, cx + 50, 312)), INK, 0.05)
    txt(s, T("大衆酒場", "reggae", (330, 50, 900, 170)), PAPER, 1.0)
    p = T("たぬき", "reggae", (320, 170, 1200, 460))
    txt(s, p, YEL, 1.0, hexc("#D8231F"), 10, 1.0)
    s.fill(picto_mug((1260, 70, 1440, 260)), YEL, 1.0)
    txt(s, T("生ビール", "noto", (1450, 80, 1760, 170)), PAPER, 1.0)
    txt(s, T("¥290", "chakra", (1460, 180, 1760, 280)), YEL, 1.0)
    s.fill(rect(1260, 320, 1760, 450, 10), hexc("#D8231F"), 1.0)
    txt(s, T("焼き鳥 一本¥99", "noto", (1280, 340, 1740, 430)), PAPER, 1.0)
    finish_box(s, fw, frame_col=hexc("#4A2A1A"), tubes="h", warm=0.2, grime=1.0, bolts=12)
    return s


def picto_cat(box):
    p = skia.Path()
    p.addPath(ellipse(50, 60, 40, 34))
    p.addPath(poly([(14, 46), (18, 6), (42, 30)]))
    p.addPath(poly([(86, 46), (82, 6), (58, 30)]))
    holes = skia.Path()
    holes.addPath(ellipse(36, 58, 5, 7)); holes.addPath(ellipse(64, 58, 5, 7))
    holes.addPath(poly([(46, 70), (54, 70), (50, 75)]))
    return fit_path(skia.Op(p, holes, skia.PathOp.kDifference_PathOp), box)


@sign
def h_karaoke_nekonokoe():
    s = Hs("h_karaoke_nekonokoe")
    s.fill(rect(0, 0, 2048, 512), hexc("#0E0C14"), 0)
    s.fill(rect(12, 12, 2036, 500, 30), hexc("#1C1530"), 0)
    s.neon(rect(36, 36, 2012, 476, 26), hexc("#B04BFF"), r=3.5, clips=0.5)
    s.neon_text(picto_cat((80, 90, 400, 420)), YEL, r=4.5, mode="outline", inset=5, clips=0.5)
    s.neon_text(T("カラオケ", "noto_bold", (450, 80, 1250, 290)), MAG, r=6.5, mode="skeleton", clips=1)
    s.neon_text(T("ネコの声", "dela", (460, 300, 1100, 450)), CYAN, r=3.6, mode="outline", inset=6, clips=1)
    for (x, y) in [(1560, 150), (1720, 110)]:
        s.neon_text(picto_note((x - 60, y - 50, x + 60, y + 70)), YEL, r=3.4, mode="outline", inset=3, clips=0.4)
    s.fill(rect(1200, 290, 1980, 450, 10), hexc("#F8F3FF"), 0.95)
    txt(s, T("30分 ¥100〜", "noto", (1230, 302, 1950, 380)), hexc("#5A1A8C"), 0.05)
    txt(s, T("フリータイム ¥980", "noto", (1230, 384, 1950, 440)), MAG, 1.0)
    s.bake_backlight(0.95, tubes="h")
    s.weather(0.6)
    return s


@sign
def h_denki_kaminari():
    s = Hs("h_denki_kaminari")
    fw = 14
    box_sign(s, YEL, frame_col=INK, fw=fw)
    # hazard stripes bottom
    stripe = skia.Path()
    for i in range(-2, 40):
        x = i * 70
        stripe.addPath(poly([(x, 430), (x + 35, 430), (x + 35 - 70, 512), (x - 70, 512)]))
    sm = s.m(stripe) * s.m(rect(fw, 430, 2048 - fw, 512 - fw))
    s.fill(sm, INK, 0.03)
    s.fill(circle(240, 215, 175), INK, 0.03)
    s.fill(picto_lightning((150, 60, 330, 370)), YEL, 1.0)
    p = T("カミナリ電機", "dela", (470, 60, 1620, 300))
    txt(s, p, INK, 0.03)
    txt(s, T("家電・パソコン・カメラ", "noto", (480, 320, 1240, 410)), INK, 0.03)
    tag_burst(s, 1860, 200, 170, 160, hexc("#E0171F"), INK, "10%\n還元", PAPER, font="noto", n=18, seed=7)
    txt(s, T("KAMINARI DENKI", "chakra", (1300, 330, 1700, 410), tracking=0.1), hexc("#E0171F"), 1.0)
    finish_box(s, fw, frame_col=INK, tubes="h", bolts=12)
    return s


@sign
def h_mahjong_tonanso():
    s = Hs("h_mahjong_tonanso")
    fw = 16
    box_sign(s, hexc("#0E6B3A"), frame_col=hexc("#C9C9C4"), fw=fw)
    halftone_fill(s, s.m(rect(fw, fw, 2048 - fw, 512 - fw)), hexc("#0A5A30"), 14, 0.35, angle=30, lit=1.0)
    for i, (ch, cc) in enumerate([("東", INK), ("南", INK), ("中", hexc("#D21F1F"))]):
        x = 70 + i * 150
        s.fill(rect(x + 8, 108, x + 138, 412, 16), hexc("#C7A86A"), 0.3)
        s.fill(rect(x, 100, x + 130, 400, 16), PAPER, 1.0)
        s.fill(rect(x, 330, x + 130, 400, 16), hexc("#F2B705"), 0.9)
        txt(s, T(ch, "noto", (x + 18, 150, x + 112, 300)), cc, 1.0)
    txt(s, T("麻雀", "dela", (560, 60, 1060, 300)), PAPER, 1.0, INK, 10)
    p = T("東南荘", "noto", (1100, 70, 1700, 290))
    txt(s, p, YEL, 1.0, INK, 8)
    txt(s, T("フリー・セット・ノーレート", "noto", (580, 340, 1500, 430)), PAPER, 1.0)
    floor_badge(s, 1860, 256, 140, "2F", PAPER, hexc("#0E6B3A"))
    finish_box(s, fw, frame_col=hexc("#C9C9C4"), tubes="h", bolts=12)
    return s


@sign
def h_100yen_hyakkindo():
    s = Hs("h_100yen_hyakkindo")
    fw = 14
    box_sign(s, WHITE_ACRYL, frame_col=hexc("#E5E5E2"), fw=fw)
    s.fill(rect(fw, fw, 2048 - fw, 90), hexc("#FF4F8B"), 1.0)
    s.fill(rect(fw, 422, 2048 - fw, 512 - fw), hexc("#FF4F8B"), 1.0)
    for i in range(30):
        s.fill(circle(40 + i * 70, 90, 20), WHITE_ACRYL, 1.0)
        s.fill(circle(40 + i * 70, 422, 20), WHITE_ACRYL, 1.0)
    s.fill(circle(260, 256, 190), hexc("#FFD400"), 1.0)
    s.stroke(circle(260, 256, 176), hexc("#E0171F"), 8, 1.0)
    txt(s, T("100", "dela", (130, 160, 390, 300)), hexc("#E0171F"), 1.0)
    txt(s, T("円", "noto", (210, 300, 310, 380)), hexc("#E0171F"), 1.0)
    txt(s, T("100円ショップ", "noto", (500, 112, 1180, 210)), hexc("#FF4F8B"), 1.0)
    p = T("ヒャッキン堂", "dela", (500, 200, 1840, 404))
    txt(s, p, hexc("#1F3BB3"), 1.0)
    txt(s, T("税込110円", "noto", (1440, 114, 1990, 194)), INK, 0.05)
    finish_box(s, fw, frame_col=hexc("#E5E5E2"), tubes="h", grime=0.5, bolts=12)
    return s


@sign
def h_bar_yotaka():
    s = Hs("h_bar_yotaka")
    s.fill(rect(0, 0, 2048, 512), hexc("#0A0A0E"), 0)
    # brick wall backing
    m = s.m(rect(0, 0, 2048, 512))
    brick = skia.Path()
    for j in range(9):
        off = 60 if j % 2 else 0
        for i in range(-1, 18):
            x = i * 120 + off; y = j * 60
            brick.addPath(rect(x + 3, y + 3, x + 117, y + 57, 4))
    bm = s.m(brick)
    nb = s.A.noise(30, seed=5)
    s.A.paint(bm, hexc("#4A2A24")[None, None, :] * (0.7 + 0.5 * nb)[..., None])
    s.fill(rect(140, 40, 1900, 472, 24), hexc("#121016"), 0)
    s.neon_text(picto_cocktail((200, 90, 470, 420)), CYAN, r=4.0, mode="outline", inset=5, clips=0.6)
    s.neon(circle(330, 150, 18), LIME, r=3.0, halo=0.5)
    s.neon_text(T("Bar", "bangers", (520, 70, 1000, 430)), MAG, r=4.6, mode="outline", inset=8, clips=1.0)
    s.neon_text(T("夜鷹", "noto_bold", (1060, 90, 1560, 400)), CYAN, r=6.0, mode="skeleton", clips=1.0)
    s.neon_text(T("B1F", "chakra", (1620, 110, 1840, 240)), YEL, r=3.0, mode="outline", inset=4)
    s.neon(picto_arrow((1640, 280, 1830, 400), "down"), YEL, r=3.2, halo=0.7)
    s.weather(0.8, streak=0.5)
    return s


@sign
def h_coinlaundry_awaawa():
    s = Hs("h_coinlaundry_awaawa")
    fw = 14
    box_sign(s, hexc("#BDE9FF"), frame_col=hexc("#F4F4F2"), fw=fw)
    halftone_fill(s, s.m(rect(fw, fw, 2048 - fw, 512 - fw)), hexc("#8AD4FA"), 22, s.A.ramp((0, 0), (0, 512)) * 0.5, lit=1.0)
    s.fill(circle(256, 256, 190), hexc("#123A8C"), 1.0)
    txt(s, T("泡々", "dela", (130, 160, 382, 350)), PAPER, 1.0)
    s.fill(picto_bubbles((1680, 60, 2000, 380)), PAPER, 1.0)
    txt(s, T("コインランドリー", "noto", (500, 60, 1640, 270)), hexc("#123A8C"), 1.0)
    s.fill(rect(500, 310, 1080, 440, 10), hexc("#123A8C"), 1.0)
    txt(s, T("24時間営業", "noto", (530, 330, 1050, 420)), PAPER, 1.0)
    txt(s, T("乾燥機 10分 ¥100", "noto", (1110, 330, 1640, 420)), hexc("#D02030"), 1.0)
    finish_box(s, fw, frame_col=hexc("#F4F4F2"), tubes="h", grime=0.5, bolts=12)
    return s


@sign
def h_shoten_fumizuki():
    s = Hs("h_shoten_fumizuki")
    s.fill(rect(0, 0, 2048, 512), hexc("#0E1A3A"), lit=0)
    brushed_metal(s, s.m(rect(0, 0, 2048, 512)), hexc("#15244F"), seed=3)
    s.stroke(rect(24, 24, 2024, 488, 8), GOLD, 6, 0)
    s.fill(picto_book((90, 120, 380, 400)), GOLD, 0.0)
    # front-lit channel letters (gold faces, lit)
    p = T("文月堂書店", "noto", (460, 70, 1640, 330))
    F = s.m(p)
    s.A.paint(s.A.shift(F, 6, 8), hexc("#05080F"), 0.8)
    s.A.paint(F, s.A.vgrad(70, 330, [(0, hexc("#FFE29A")), (0.5, GOLD), (1, hexc("#B07A00"))]))
    s.emit(F, hexc("#FFD36A"), 1.0)
    s.emit(s.A.blur(F, 10), hexc("#FFB020"), 0.35)
    txt(s, T("本・雑誌・コミック・文具", "noto", (470, 370, 1400, 450)), PAPER, 0.0)
    s.emit(s.m(T("本・雑誌・コミック・文具", "noto", (470, 370, 1400, 450))), PAPER, 0.7)
    txt(s, T("SINCE 1952", "chakra", (1700, 200, 1980, 280), tracking=0.15), GOLD, 0.0)
    s.weather(0.7)
    return s


@sign
def h_yakitori_torikichi():
    s = Hs("h_yakitori_torikichi")
    fw = 16
    box_sign(s, hexc("#C8161D"), frame_col=hexc("#222222"), fw=fw)
    s.fill(circle(250, 256, 180), INK, 0.04)
    txt(s, T("炭火", "noto", (130, 180, 370, 330)), YEL, 1.0)
    for i in range(3):
        s.fill(picto_skewer((1680 + i * 90, 60, 1880 + i * 90, 460)), PAPER, 1.0)
    p = T("焼鳥", "reggae", (480, 40, 1080, 330))
    txt(s, p, PAPER, 1.0, INK, 10)
    s.fill(rect(1100, 70, 1640, 300, 10), PAPER, 1.0)
    txt(s, T("とり吉", "reggae", (1130, 90, 1610, 280)), hexc("#C8161D"), 1.0)
    txt(s, T("テイクアウト・持ち帰り歓迎", "noto", (490, 360, 1400, 450)), YEL, 1.0)
    txt(s, T("17:00〜24:00", "chakra", (1430, 360, 1660, 450)), PAPER, 1.0)
    finish_box(s, fw, frame_col=hexc("#222222"), tubes="h", warm=0.2, grime=1.0, bolts=12)
    return s


@sign
def h_massage_iyashi():
    s = Hs("h_massage_iyashi")
    fw = 14
    box_sign(s, hexc("#F4EFD9"), frame_col=hexc("#3D5A3A"), fw=fw)
    s.fill(rect(fw, fw, 520, 512 - fw), hexc("#3D7A4A"), 1.0)
    s.fill(picto_leaf((90, 60, 440, 410)), hexc("#A9E07E"), 1.0)
    txt(s, T("癒", "noto", (180, 150, 360, 330)), PAPER, 1.0)
    txt(s, T("もみほぐし", "noto", (580, 60, 1520, 270)), hexc("#2C4F2A"), 1.0)
    txt(s, T("全身・足つぼ・ヘッドスパ", "noto", (590, 310, 1500, 400)), hexc("#3D7A4A"), 1.0)
    s.fill(rect(1560, 60, 1990, 450, 20), hexc("#D0302C"), 1.0)
    txt(s, T("60分", "noto", (1600, 90, 1950, 190)), PAPER, 1.0)
    txt(s, T("¥2,980", "chakra", (1590, 210, 1960, 360)), YEL, 1.0)
    txt(s, T("予約優先", "noto", (1640, 370, 1910, 430)), PAPER, 1.0)
    finish_box(s, fw, frame_col=hexc("#3D5A3A"), tubes="h", grime=0.6, bolts=12, warm=0.15)
    return s


# ======================================================================================
# SQUARE 1024
# ======================================================================================
@sign
def s_kusuri():
    s = S("s_kusuri")
    fw = 20
    box_sign(s, WHITE_ACRYL, frame_col=hexc("#DCDCD8"), fw=fw)
    s.fill(circle(512, 470, 380), hexc("#E0171F"), 1.0)
    s.fill(circle(512, 470, 340), WHITE_ACRYL, 1.0)
    txt(s, T("薬", "noto", (260, 220, 764, 720)), hexc("#E0171F"), 1.0)
    txt(s, T("くすり", "noto", (330, 870, 694, 980)), INK, 0.05)
    finish_box(s, fw, frame_col=hexc("#DCDCD8"), tubes="v", bolts=4, grime=0.6)
    return s


@sign
def s_sento_matsunoyu():
    s = S("s_sento_matsunoyu")
    fw = 20
    box_sign(s, hexc("#1B2C6B"), frame_col=hexc("#2B2A2A"), fw=fw)
    s.fill(circle(512, 400, 300), PAPER, 1.0)
    s.fill(picto_onsen((330, 170, 694, 620)), hexc("#E2401C"), 1.0)
    s.fill(circle(150, 150, 95), hexc("#E2401C"), 1.0)
    s.stroke(circle(150, 150, 82), PAPER, 6, 1.0)
    txt(s, T("ゆ", "noto", (95, 92, 205, 205)), PAPER, 1.0)
    txt(s, T("松の湯", "reggae", (230, 740, 794, 900)), PAPER, 1.0)
    txt(s, T("銭湯 15:00〜25:00", "noto", (260, 920, 764, 980)), YEL, 1.0)
    finish_box(s, fw, frame_col=hexc("#2B2A2A"), bolts=4, grime=0.9, warm=0.2)
    return s


@sign
def s_shichi():
    s = S("s_shichi")
    fw = 22
    box_sign(s, hexc("#0F1F17"), frame_col=hexc("#3B3B3B"), fw=fw, lit=0.06)
    s.stroke(circle(512, 440, 340), PAPER, 26, 1.0)
    txt(s, T("質", "noto", (272, 200, 752, 680)), PAPER, 1.0)
    s.fill(rect(150, 820, 874, 960, 10), hexc("#B3141B"), 1.0)
    txt(s, T("質・買取 マルヤ", "noto", (190, 846, 834, 936)), PAPER, 1.0)
    finish_box(s, fw, frame_col=hexc("#3B3B3B"), bolts=4, grime=1.0)
    return s


@sign
def s_parking():
    s = S("s_parking")
    fw = 18
    box_sign(s, hexc("#1446C8"), frame_col=hexc("#E1E1E1"), fw=fw)
    s.fill(rect(60, 60, 964, 640, 30), PAPER, 1.0)
    txt(s, T("P", "chakra", (430, 100, 900, 600)), hexc("#1446C8"), 1.0)
    txt(s, T("24H", "chakra", (100, 470, 360, 600)), hexc("#1446C8"), 1.0)
    # 空 / 満 indicators
    s.fill(rect(60, 680, 500, 860, 16), hexc("#0A0A0E"), 0)
    s.fill(rect(524, 680, 964, 860, 16), hexc("#0A0A0E"), 0)
    k = txt(s, T("空", "noto", (210, 700, 350, 840)), hexc("#7FE89A"), 0)
    m_ = txt(s, T("満", "noto", (674, 700, 814, 840)), hexc("#5E2A30"), 0)
    s.emit(k, hexc("#4CFF7A"), 1.3)
    s.emit(s.A.blur(k, 12), hexc("#22FF66"), 0.6)
    txt(s, T("¥300 / 30分", "noto", (190, 890, 834, 980)), PAPER, 1.0)
    finish_box(s, fw, frame_col=hexc("#E1E1E1"), bolts=4, grime=0.7)
    return s


def lantern(name, paper, band, text, text_col, glow, ribs=26, text2=None):
    s = S(name)
    s.fill(rect(0, 0, 1024, 1024), paper, lit=1.0)
    # paper fibre + rib ridges
    nb = s.A.noise(8, seed=11, beta=1.2, aniso=(0.2, 1.0))
    s.A.multiply(np.ones((s.H, s.W), f32), (0.86 + 0.14 * nb)[..., None] * WHITE)
    ys = np.linspace(0, 1, s.H, dtype=f32)[:, None]
    rib = (0.5 + 0.5 * np.cos(ys * ribs * 2 * math.pi)) ** 6
    s.A.multiply(np.broadcast_to(rib, (s.H, s.W)).copy(), darken(paper, 0.35), 0.55)
    s.L *= (1 - 0.35 * np.broadcast_to(rib, (s.H, s.W)))
    # top/bottom black bands (wood caps)
    s.fill(rect(0, 0, 1024, 90), INK, 0)
    s.fill(rect(0, 934, 1024, 1024), INK, 0)
    s.fill(rect(0, 90, 1024, 130), band, 0.8)
    s.fill(rect(0, 894, 1024, 934), band, 0.8)
    for cx in (256, 768):
        p = VT(text, "reggae", (cx - 150, 190, cx + 150, 850), spacing=1.0)
        s.fill(p, text_col, lit=0.02)
    if text2:
        for cx in (0, 512, 1024):
            s.fill(VT(text2, "noto", (cx - 30, 320, cx + 30, 720)), text_col, lit=0.02)
    # emission: warm paper glow brighter at the lantern belly (v centre)
    belly = np.exp(-((ys - 0.5) / 0.32) ** 2)
    rgb = s.A.px[..., :3] * 0 + col(glow)[None, None, :]
    s.emit_rgb(rgb * (s.L * (0.55 + 0.6 * belly))[..., None], 1.0)
    s.weather(0.7, streak=0.4)
    return s


@sign
def s_chochin_yakitori():
    return lantern("s_chochin_yakitori", hexc("#D8231F"), INK, "焼鳥", INK, hexc("#FF5A2A"), text2="炭火")


@sign
def s_chochin_sake():
    return lantern("s_chochin_sake", hexc("#F3EEE0"), hexc("#C8161D"), "酒", INK, hexc("#FFD9A0"), text2="居酒屋")


@sign
def s_yorumart_pole():
    s = S("s_yorumart_pole")
    fw = 18
    box_sign(s, hexc("#F7F7F4"), frame_col=hexc("#E0E0DE"), fw=fw)
    s.fill(rect(fw, 700, 1024 - fw, 750), MAG, 1.0)
    s.fill(rect(fw, 750, 1024 - fw, 800), CYAN, 1.0)
    s.fill(rect(fw, 800, 1024 - fw, 1024 - fw), hexc("#2A1F7A"), 1.0)
    s.fill(rect(250, 60, 774, 520, 70), hexc("#2A1F7A"), 1.0)
    s.fill(picto_moon((330, 110, 600, 380)), YEL, 1.0)
    s.fill(picto_star((590, 120, 700, 230)), YEL, 1.0)
    txt(s, T("YORU", "chakra", (330, 390, 694, 490)), PAPER, 1.0)
    txt(s, T("ヨルマート", "noto", (120, 560, 904, 680)), hexc("#2A1F7A"), 1.0)
    txt(s, T("24H", "chakra", (300, 830, 724, 980)), YEL, 1.0)
    finish_box(s, fw, frame_col=hexc("#E0E0DE"), bolts=4, grime=0.5)
    return s


@sign
def s_bar_cocktail():
    s = S("s_bar_cocktail")
    s.fill(rect(0, 0, 1024, 1024), hexc("#0C0B10"), 0)
    s.fill(rect(20, 20, 1004, 1004, 40), hexc("#16141C"), 0)
    s.neon(circle(512, 512, 450), MAG, r=4.0, clips=0.5)
    s.neon_text(picto_cocktail((300, 110, 724, 600)), CYAN, r=5.0, mode="outline", inset=6, clips=0.6)
    s.neon(circle(560, 220, 30), LIME, r=4, halo=0.6)
    s.neon_text(T("BAR", "chakra", (300, 640, 724, 800)), YEL, r=5.0, mode="outline", inset=6, clips=0.6)
    s.neon_text(T("OPEN", "chakra", (390, 830, 634, 910)), hexc("#FF3B30"), r=3.4, mode="outline", inset=4, clips=0.5)
    s.weather(0.5)
    return s


@sign
def s_takarakuji():
    s = S("s_takarakuji")
    fw = 18
    box_sign(s, hexc("#D21F1F"), frame_col=GOLD, fw=fw)
    r_ = rng("kuji")
    burst = starburst(512, 400, 470, 360, n=28, inner=0.82, jitter=0.1, r=r_)
    s.fill(burst, YEL, 1.0)
    txt(s, VT("宝", "dela", (360, 160, 664, 460)) if False else T("宝くじ", "dela", (150, 260, 874, 520)), hexc("#D21F1F"), 1.0, PAPER, 12, 1.0, INK, 8)
    s.fill(rect(120, 760, 904, 960, 14), INK, 0.03)
    txt(s, T("1等 前後賞合わせて", "noto", (160, 780, 864, 850)), PAPER, 1.0)
    txt(s, T("7億円!!", "dela", (300, 856, 724, 950)), YEL, 1.0)
    txt(s, T("大当たり続出", "noto", (220, 590, 804, 690)), PAPER, 1.0, INK, 6)
    finish_box(s, fw, frame_col=GOLD, bolts=4)
    return s


@sign
def s_slot_777():
    s = S("s_slot_777")
    s.fill(rect(0, 0, 1024, 1024), hexc("#120A1A"), 0)
    s.fill(rect(24, 24, 1000, 1000, 30), hexc("#2A0C2E"), 0)
    pts = []
    for i in range(21):
        t = i / 20
        pts += [(60 + t * 904, 60), (60 + t * 904, 964), (60, 60 + t * 904), (964, 60 + t * 904)]
    s.bulbs(pts, 10, hexc("#FFC86A"))
    s.neon_text(T("777", "dela", (130, 160, 894, 600)), hexc("#FF3B30"), r=5.5, mode="outline", inset=9, clips=0.6)
    s.neon_text(T("スロット", "noto_bold", (200, 650, 824, 880)), YEL, r=6.0, mode="skeleton", clips=0.8)
    s.weather(0.5)
    return s


@sign
def s_noren_ramen():
    s = S("s_noren_ramen")
    s.fill(rect(0, 0, 1024, 1024), hexc("#2B1E16"), 0)
    # pole
    wood(s, s.m(rect(0, 20, 1024, 70, 20)), hexc("#8A5A30"), seed=7, vertical=False)
    cloth = hexc("#1E2D5C")
    panels = [(30, 70, 340, 1000), (357, 70, 667, 1000), (684, 70, 994, 1000)]
    allm = np.zeros((s.H, s.W), f32)
    for b in panels:
        m = s.m(rect(*b))
        allm = np.maximum(allm, m)
        s.A.paint(m, cloth)
    # fabric weave & folds
    nb = s.A.noise(2.5, seed=21, beta=0.8)
    xs = np.linspace(0, 1, s.W, dtype=f32)[None, :]
    fold = 0.85 + 0.15 * np.sin(xs * 2 * math.pi * 12) ** 2
    s.A.multiply(allm, ((0.9 + 0.1 * nb) * fold)[..., None] * WHITE)
    # white text spans the three panels
    p = T("らーめん", "reggae", (60, 260, 964, 600))
    F = s.m(p) * allm
    s.fill(F, PAPER)
    s.fill(s.m(T("中華そば 松葉", "noto", (220, 690, 804, 790))) * allm, PAPER)
    # wave hem
    seigaiha_paint(s, (0, 860, 1024, 1010), 36, cloth, hexc("#C8D2EC"), clip=allm * s.m(rect(0, 870, 1024, 1000)), lit=None)
    # emission: lamp above the doorway washes the cloth
    lamp = np.clip(1 - s.A.radial(512, -150, 1300), 0, 1) ** 2
    s.emit_rgb(s.A.px[..., :3] * (lamp * allm)[..., None] * WARM_WHITE, 0.85)
    s.weather(0.6, streak=0.3)
    return s


@sign
def s_dental_tooth():
    s = S("s_dental_tooth")
    fw = 18
    box_sign(s, hexc("#127C78"), frame_col=hexc("#F2F2F0"), fw=fw)
    s.fill(circle(512, 400, 300), WHITE_ACRYL, 1.0)
    s.fill(picto_tooth((332, 220, 692, 580)), hexc("#5FD0C8"), 1.0)
    s.fill(picto_tooth((360, 240, 664, 560)), WHITE_ACRYL, 1.0)
    txt(s, T("歯科", "noto", (300, 740, 724, 900)), PAPER, 1.0)
    txt(s, T("DENTAL", "chakra", (380, 910, 644, 970), tracking=0.3), hexc("#BFF3EE"), 1.0)
    finish_box(s, fw, frame_col=hexc("#F2F2F0"), bolts=4, grime=0.4)
    return s


# ======================================================================================
def render(names=None):
    names = names or list(REG.keys())
    out = []
    for n in names:
        s = REG[n]()
        pa, pe = s.save()
        print("wrote", os.path.basename(pa), os.path.basename(pe), flush=True)
        out.append((pa, pe))
    return out


def sheets():
    d = SIGN_DIR
    names = sorted(k for k in REG)
    for kind in ("v", "h", "s"):
        group = [n for n in names if n.startswith(kind + "_")]
        paths = []
        for n in group:
            paths += [os.path.join(d, f"{n}_albedo.png"), os.path.join(d, f"{n}_emission.png")]
        paths = [p for p in paths if os.path.exists(p)]
        if kind == "v":
            cell, cols = (150, 600), 10
        elif kind == "h":
            cell, cols = (520, 130), 4
        else:
            cell, cols = (300, 300), 6
        contact_sheet(paths, os.path.join(PREVIEWS, f"signs_{kind}.png"), cell=cell, cols=cols, bg="dark",
                      title=f"SIGNS {kind.upper()}  (albedo | emission)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--sheets"]:
        sheets()
    else:
        render(args or None)
        sheets()
