"""Generate tileable building facade texture sets for INK DRIFT: TOKYO.

Usage:  Tools/.venv/bin/python Tools/art/gen_facades.py [set ...]   (no args = all sets)

Each set writes  Game/Assets/InkDrift/Art/Facades/<set>_{albedo,normal,emission,mask,height}.png
  albedo  : sRGB RGB, no strong baked lighting (light AO only)
  normal  : OpenGL (+Y up) tangent space, derived from the height map
  emission: night interiors (black elsewhere)
  mask    : R=metallic, G=AO, B=0, A=smoothness
Previews: Tools/art/previews/facade_<set>_tiled.png (2x2 albedo | 2x2 emission) + facades.png
All randomness is seeded; outputs are deterministic.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inklib import (C, mix, rng, drip_paths, flecks, sfx_text_path, transformed, union, rect, poly, circle, ellipse, text_path, vtext_path, fit_path,  # noqa: E402
                    bounds, smooth_closed, combine, f32, PREVIEWS, ART, contact_sheet, tile_preview,
                    noise, halftone)
from facadelib import (Facade, Region, K, rgb, window_state, paint_window, streak_field,  # noqa: E402
                       wrap_fade_rows, wrap_band_cols, person_path, plant_path, assign_lit,
                       tile_field, ac_unit, pipe_v, text_region, sheen_field, ring as ring_reg,
                       WARM, WARM2, NEUTRAL, COOL, COOLER, TV_BLUE, BAR_PINK, BAR_PURPLE, CURTAINS)
import skia  # noqa: E402

OUT = os.path.join(ART, "Facades")
SETS = {}


def register(fn):
    SETS[fn.__name__] = fn
    return fn


def _lit_rooms(r, n_modules, lit_target, kinds=("office",), min_w=1, max_w=3):
    """Partition n_modules into rooms; return list of (start, width, state)."""
    rooms = []
    i = 0
    while i < n_modules:
        wdt = int(r.integers(min_w, max_w + 1))
        wdt = min(wdt, n_modules - i)
        st = window_state(r, kind=r.choice(kinds), lit_p=lit_target)
        rooms.append((i, wdt, st))
        i += wdt
    return rooms


# ======================================================================================
# 1. GLASS OFFICE — unitised curtain wall
# ======================================================================================
@register
def glass_office():
    """4 floors x 3.8 m = 15.2 m tall, 8 modules x 1.9 m = 15.2 m wide (134.7 px/m)."""
    S = 2048
    F = Facade("glass_office", S, S, ss=2, seed=101)
    r = rng(101)
    floors, mods = 4, 8
    fh, mw = S / floors, S / mods
    span_h = 74            # half-height of spandrel band (centred on slab line y = i*fh)
    mull = 9               # half-width of vertical mullion
    tr = 7                 # half-height of transom

    # ---- glass reflection field (periodic): diagonal sheen bands + soft cloud noise + pane jitter
    xx, yy = F._xx, F._yy
    diag = ((xx / S) * 2 + (yy / S) * 1) % 1.0
    sheen = (np.clip(1 - np.abs(diag - 0.32) / 0.07, 0, 1) ** 2 * 0.10 +
             np.clip(1 - np.abs(diag - 0.47) / 0.025, 0, 1) ** 2 * 0.07 +
             np.clip(1 - np.abs(diag - 0.81) / 0.05, 0, 1) ** 2 * 0.06).astype(f32)
    clouds = F.noise(420, 11, beta=2.2)
    refl = (sheen * 1.25 + (clouds - 0.5) * 0.14).astype(f32)   # scalar field, tinted in paint_window
    del diag, sheen, clouds

    # ---- base wall (everything is covered later, but give sane defaults)
    F.put(F.full(), alb=rgb("#2B3540"), h=0.3, smooth=0.9)

    glass = rgb("#46606F")
    plan = [_lit_rooms(r, mods, 0.5, kinds=("office",), min_w=1, max_w=3) for _ in range(floors)]
    frac = assign_lit(plan, 0.46, r)
    print("  glass_office lit fraction", round(frac, 2))
    for fl in range(floors):
        y_top = fl * fh + span_h + tr
        y_bot = (fl + 1) * fh - span_h - tr
        rooms = plan[fl]
        for (m0, wdt, st) in rooms:
            for m in range(m0, m0 + wdt):
                x0 = m * mw + mull
                x1 = (m + 1) * mw - mull
                tint = (r.uniform(-0.025, 0.025))
                g = glass * (1 + tint) + np.array([0, 0.01, 0.015], f32) * r.uniform(-1, 1)
                # vision pane: some modules split with a low operable vent
                st2 = dict(st); st2["seed"] = int(r.integers(1 << 30))
                paint_window(F, x0, y_top, x1, y_bot, st2, g, glass_reflect=refl, smooth=0.95, h=0.28,
                             interior_vis=0.5)
                if r.random() < 0.25:
                    # top-hung vent: thin frame line + slightly different reflection
                    vy = y_top + (y_bot - y_top) * 0.78
                    F.put(F.R(x0, vy - 2.5, x1, vy + 2.5), alb=rgb("#9CA3A8"), h=0.55, metal=0.9, smooth=0.6)

    # ---- spandrel bands (fritted dark glass) centred on slab lines, wrap vertically
    for fl in range(floors + 1):
        yc = fl * fh
        reg = F.R(0, yc - span_h, S, yc + span_h)
        if reg is None:
            continue
        t = np.clip(F.ly(reg, yc - span_h, 2 * span_h) / (2 * span_h), 0, 1)
        # ceramic frit: dot screen growing toward the band centre
        cov = (0.55 - 0.5 * np.abs(t - 0.5) * 2) ** 1.5
        cov = np.broadcast_to(cov, reg.m.shape)
        dots = halftone(reg.m.shape[0], reg.m.shape[1], cov, F.tile_period(9), 45,
                        offset=(reg.xs.start, reg.ys.start))
        base = rgb("#1F2A33") + (refl[reg.ys, reg.xs] * 0.6)[..., None] * np.array([0.85, 0.95, 1.0], f32)
        alb = base * (1 - dots[..., None]) + rgb("#7F8B92") * dots[..., None]
        F.put(reg, alb=alb, h=0.36, metal=0.0, smooth=0.9)
        # back-pan shadow lines at slab edge (hidden structure) -> subtle darker line
        F.put(F.R(0, yc - 3, S, yc + 3), alb=rgb("#141B22"), h=0.34, smooth=0.85)

    # ---- transoms (horizontal mullions) at spandrel edges
    alu = rgb("#A9B0B6")
    for fl in range(floors + 1):
        yc = fl * fh
        for yy0 in (yc - span_h, yc + span_h):
            reg = F.R(0, yy0 - tr, S, yy0 + tr)
            if reg is None:
                continue
            t = F.ly(reg, yy0 - tr, 2 * tr) / (2 * tr)
            prof = 0.6 + 0.12 * np.sin(np.clip(t, 0, 1) * math.pi)
            shade = (1.0 - 0.10 * t)[..., None]
            F.put(reg, alb=alu * shade, h=prof, metal=0.9, smooth=0.55)

    # ---- vertical mullions with pressure-plate caps (continuous -> seamless)
    for m in range(mods + 1):
        xc = m * mw
        reg = F.R(xc - mull, 0, xc + mull, S)
        if reg is None:
            continue
        t = F.lx(reg, xc - mull, 2 * mull) / (2 * mull)
        prof = 0.64 + 0.14 * np.sin(np.clip(t, 0, 1) * math.pi)
        groove = (np.abs(t - 0.5) < 0.06).astype(f32)
        col = alu * (1.02 - 0.08 * t)[..., None] * (1 - 0.35 * groove[..., None])
        F.put(reg, alb=col, h=prof - groove * 0.05, metal=0.92, smooth=0.6)
        # caps cast a tiny AO on glass beside them
        F.put(F.R(xc - mull - 6, 0, xc + mull + 6, S), ao=0.8, opacity=0.6)

    # ---- maintenance: subtle vertical grime streaks below transoms
    st = streak_field(F, 77, scale=5, aniso=20)
    for fl in range(floors):
        fade = wrap_fade_rows(F, fl * fh + span_h + tr, 120, 1.6)
        grime = np.clip((st - 0.48) * 3, 0, 1) * fade
        F.tint(F.from_mask(grime.astype(f32)), rgb("#8E8F86"), 0.35)
    del st
    del refl
    return F.finalize(OUT, normal_strength=5.0, height_blur=0.7, albedo_ao=0.25)


# ======================================================================================
# 2. ZAKKYO TILE — white/beige 45二丁 mosaic-tile mixed-use building (雑居ビル)
# ======================================================================================
def sash_window(F, x0, y0, x1, y1, st, r, n_sash=2, ranma=True, frame_col=None, glass=None,
                interior_vis=0.55, emis_scale=1.0, sill=True, depth_h=0.30, refl=None, screen=False):
    """Aluminium sash window: outer frame, optional fixed transom (欄間), sliding sashes."""
    frame_col = rgb("#B9BDBF") if frame_col is None else frame_col
    glass = rgb("#6F818C") if glass is None else glass
    fw = 9  # frame width
    # reveal shadow (AO) around opening
    F.put(F.R(x0 - 4, y0 - 4, x1 + 4, y1 + 4), alb=rgb("#9A968C"), h=0.42)
    F.put(ring_reg(F, x0 - 4, y0 - 4, x1 + 4, y1 + 4, 22), ao=0.75)
    gx0, gy0, gx1, gy1 = x0 + fw, y0 + fw, x1 - fw, y1 - fw
    paint_window(F, gx0, gy0, gx1, gy1, st, glass, smooth=0.92, h=depth_h, interior_vis=interior_vis,
                 emis_scale=emis_scale, glass_reflect=refl)
    # outer frame (ring)
    ring = skia.Path()
    ring.addRect(skia.Rect.MakeLTRB(x0, y0, x1, y1))
    ring.addRect(skia.Rect.MakeLTRB(gx0, gy0, gx1, gy1))
    reg = F.region(ring, evenodd=True)
    F.put(reg, alb=frame_col, h=0.5, metal=0.85, smooth=0.55)
    rows = []
    if ranma:
        ry = gy0 + (gy1 - gy0) * 0.24
        F.put(F.R(gx0, ry - 5, gx1, ry + 5), alb=frame_col * 0.95, h=0.48, metal=0.85, smooth=0.55)
        sy0 = ry + 5
    else:
        sy0 = gy0
    # sliding sash stiles (meeting rails overlap: draw double stile)
    for i in range(1, n_sash):
        sx = gx0 + (gx1 - gx0) * i / n_sash
        F.put(F.R(sx - 9, sy0, sx + 9, gy1), alb=frame_col * 0.97, h=0.47, metal=0.85, smooth=0.55)
        F.put(F.R(sx - 1, sy0, sx + 1, gy1), alb=frame_col * 0.6, h=0.44)
        # crescent lock
        F.put(F.R(sx - 6, sy0 + (gy1 - sy0) * 0.5 - 8, sx + 6, sy0 + (gy1 - sy0) * 0.5 + 8, 3),
              alb=rgb("#8E9296"), h=0.53, metal=0.9)
    if screen and n_sash >= 2:
        # insect screen (網戸) over one sash: grey veil + frame
        side = r.integers(n_sash)
        sx0 = gx0 + (gx1 - gx0) * side / n_sash + 9
        sx1 = gx0 + (gx1 - gx0) * (side + 1) / n_sash - 9
        F.put(F.R(sx0, sy0, sx1, gy1), alb=rgb("#3E4448"), opacity=0.35, smooth=0.3)
        F.put(F.R(sx0, sy0, sx1, gy1), emis=np.array([0.7, 0.7, 0.7], f32), emode="mul")
        ring = skia.Path(); ring.addRect(skia.Rect.MakeLTRB(sx0, sy0, sx1, gy1))
        ring.addRect(skia.Rect.MakeLTRB(sx0 + 5, sy0 + 5, sx1 - 5, gy1 - 5))
        F.put(F.region(ring, evenodd=True), alb=frame_col * 0.9, h=0.49, metal=0.8)
    if sill:
        F.put(F.R(x0 - 10, y1, x1 + 10, y1 + 11), alb=frame_col * 1.03, h=0.62, metal=0.85, smooth=0.5)
        F.put(F.R(x0 - 10, y1 + 11, x1 + 10, y1 + 26), ao=0.75)


@register
def zakkyo_tile():
    """4 floors x 3.2 m = 12.8 m tall, 3 bays x 4.27 m = 12.8 m wide (160 px/m).
    45x95 mm mosaic tile (馬目地 running bond, 128 x 256 tiles per texture)."""
    S = 2048
    F = Facade("zakkyo_tile", S, S, ss=2, seed=202)
    r = rng(202)
    floors, bays = 4, 3
    fh, bw = S / floors, S / bays

    # ---- tile cladding over everything
    tf = tile_field(F, 128, 256, grout=1.6, bond="running", seed=5)
    base = rgb("#E6DDCD")
    var = (tf["rnd"] - 0.5)[..., None] * np.array([0.045, 0.045, 0.04], f32) + \
          ((tf["rnd2"] > 0.93) * 0.05)[..., None] * np.array([0.6, 0.4, -0.2], f32) * -1
    big = F.noise(300, 21, beta=2.0)
    col = base + var + ((big - 0.5) * 0.08)[..., None]
    # slight glaze dome per tile
    dome = np.sin(np.clip(tf["u"], 0, 1) * math.pi) * np.sin(np.clip(tf["v"], 0, 1) * math.pi)
    grout_col = rgb("#C3BCAF")
    gm = tf["grout"][..., None]
    alb = col * (1 - gm) + grout_col * gm
    F.alb[:] = alb
    F.hgt[:] = 0.5 + 0.03 * dome - 0.07 * tf["grout"]
    F.smooth[:] = 0.5 * (1 - tf["grout"]) + 0.15 * tf["grout"]
    del tf, var, big, col, dome, gm, alb

    # ---- window + tenant plan
    tenants = [
        dict(kind="bar", txt="スナック 蘭", tcol=rgb("#FF5FA2"), lit=True, font="reggae", cover="curtain",
             curtain=rgb("#B0446E"), temp=BAR_PINK),
        dict(kind="office", txt="麻雀 東風荘", tcol=rgb("#F2F0E8"), lit=True, font="noto", cover="none",
             temp=COOLER),
        dict(kind="home", txt="英会話 ENGLISH", tcol=rgb("#FFD23A"), lit=True, font="noto", cover="blinds",
             temp=NEUTRAL),
        dict(kind="home", txt="整体 ほぐし処", tcol=rgb("#F4F1E9"), lit=False, font="noto", cover="curtain",
             curtain=rgb("#E9DCC4"), temp=WARM2),
        dict(kind="vacant", txt=None, lit=False),
        dict(kind="office", txt=None, lit=True, cover="blinds", temp=COOL),
        dict(kind="office", txt=None, lit=False, cover="blinds", temp=COOL),
        dict(kind="home", txt="鍼灸院", tcol=rgb("#E8362F"), lit=False, font="noto", cover="lace", temp=WARM),
        dict(kind="home", txt=None, lit=True, cover="curtain", curtain=rgb("#D8C49A"), temp=WARM),
        dict(kind="bar", txt="カラオケ 歌", tcol=rgb("#B47CFF"), lit=True, font="reggae", cover="none",
             temp=BAR_PURPLE),
        dict(kind="office", txt=None, lit=False, cover="none", temp=COOL),
        dict(kind="home", txt=None, lit=False, cover="curtain", curtain=rgb("#9DB4C8"), temp=WARM),
    ]
    order = r.permutation(len(tenants))
    win_head, win_sill = 84, 372
    refl = sheen_field(F, 9, 0.8, clouds=0.1)
    ac_slots = {(0, 1), (1, 0), (2, 2), (3, 1), (2, 0)}
    for fl in range(floors):
        for b in range(bays):
            t = tenants[order[fl * bays + b]]
            x0 = b * bw + bw / 2 - 296
            x1 = b * bw + bw / 2 + 296
            y0 = fl * fh + win_head
            y1 = fl * fh + win_sill
            st = window_state(r, kind="office" if t["kind"] in ("office", "vacant") else "home")
            st["lit"] = t.get("lit", False)
            st["cover"] = t.get("cover", "none")
            if "curtain" in t:
                st["curtain"] = t["curtain"]
            if "temp" in t:
                st["temp"] = t["temp"]
            if t["kind"] == "bar":
                st["kind"] = "home"; st["tv"] = False
            if t["kind"] == "vacant":
                st["cover"] = "none"
            n_sash = 2 if r.random() < 0.6 else 4
            sash_window(F, x0, y0, x1, y1, st, r, n_sash=n_sash, ranma=r.random() < 0.7, refl=refl,
                        screen=(t['kind'] == 'home' and n_sash == 2))
            gx0, gy0, gx1, gy1 = x0 + 9, y0 + 9, x1 - 9, y1 - 9
            if t["kind"] == "vacant":
                # paper "for lease" board taped inside the glass
                bx0, by0 = gx0 + (gx1 - gx0) * 0.30, gy0 + (gy1 - gy0) * 0.30
                bx1, by1 = gx0 + (gx1 - gx0) * 0.70, gy0 + (gy1 - gy0) * 0.88
                F.put(F.R(bx0, by0, bx1, by1), alb=rgb("#F3F1EA"), smooth=0.3, emis=0)
                F.put(text_region(F, "テナント募集", (bx0 + 14, by0 + 14, bx1 - 14, by0 + (by1 - by0) * 0.42)),
                      alb=rgb("#D7262B"))
                F.put(text_region(F, "TENANT", (bx0 + 30, by0 + (by1 - by0) * 0.55, bx1 - 30, by1 - 40), font="chakra"),
                      alb=rgb("#1F3A93"))
                F.put(F.R(bx0 + 20, by1 - 28, bx1 - 20, by1 - 18), alb=rgb("#1F3A93"))
            if t.get("txt"):
                # vinyl lettering across the upper sash area
                ty0 = gy0 + (gy1 - gy0) * (0.30 if True else 0.1)
                box = (gx0 + 40, ty0, gx1 - 40, ty0 + (gy1 - gy0) * 0.30)
                reg = text_region(F, t["txt"], box, font=t["font"])
                F.put(reg, alb=t["tcol"], smooth=0.6, metal=0.0)
                F.put(reg, emis=np.array([0.08, 0.06, 0.05], f32), emode="mul")
            # AC outdoor unit on a bracket beneath the window
            if (fl, b) in ac_slots:
                aw, ah = 118, 80
                ax = x0 + (40 if r.random() < 0.5 else (x1 - x0) - 40 - aw)
                ay = fl * fh + win_sill + 24
                # bracket
                F.put(F.R(ax + 8, ay + ah, ax + aw - 8, ay + ah + 6), alb=rgb("#6E6F70"), h=0.7, metal=0.8)
                F.put(F.R(ax + 10, ay + ah, ax + 16, ay + ah + 26), alb=rgb("#6E6F70"), h=0.68, metal=0.8)
                F.put(F.R(ax + aw - 16, ay + ah, ax + aw - 10, ay + ah + 26), alb=rgb("#6E6F70"), h=0.68, metal=0.8)
                ac_unit(F, ax, ay, aw, ah, r)
                F.put(F.R(ax + 6, ay + ah + 6, ax + aw - 6, ay + ah + 40), ao=0.8, opacity=0.8)

    # ---- small wall-mounted tenant panels (backlit acrylic)
    panels = [(0, 0, "整体", rgb("#2E7D4F")), (2, 1, "麻雀", rgb("#C8102E")), (1, 2, "ENGLISH", rgb("#1F3A93"))]
    for (fl, b, txt, colr) in panels:
        px0 = b * bw + bw / 2 + 120
        py0 = fl * fh + win_sill + 28
        pw, ph = 146, 66
        F.put(F.R(px0 - 4, py0 - 4, px0 + pw + 4, py0 + ph + 4, 4), alb=rgb("#9EA2A6"), h=0.72, metal=0.8, smooth=0.5)
        F.put(F.R(px0, py0, px0 + pw, py0 + ph, 2), alb=rgb("#F7F5EE"), h=0.74, smooth=0.7,
              emis=rgb("#FFF6E2") * 0.85)
        reg = text_region(F, txt, (px0 + 12, py0 + 10, px0 + pw - 12, py0 + ph - 10),
                          font="noto" if txt != "ENGLISH" else "chakra")
        F.put(reg, alb=colr, emis=colr * 0.9)

    # ---- projecting concrete floor bands (centred on slab lines -> wrap vertically)
    for fl in range(floors + 1):
        yc = fl * fh
        reg = F.R(0, yc - 22, S, yc + 22)
        if reg is None:
            continue
        t = np.clip(F.ly(reg, yc - 22, 44) / 44, 0, 1)
        F.put(reg, alb=rgb("#D6D0C4") * (1.02 - 0.06 * t)[..., None], h=0.7 + 0.02 * (1 - t), smooth=0.2)
        F.put(F.R(0, yc + 22, S, yc + 46), ao=0.72)
        F.put(F.R(0, yc + 22, S, yc + 26), alb=rgb("#9C968B"), h=0.6)

    # ---- drain pipe on the bay boundary (continuous -> tiles vertically)
    pipe_v(F, bw, -10, S + 10, 12, color=rgb("#B8B4AA"), brackets=fh / 2)
    # electrical conduit
    pipe_v(F, bw * 2 + 30, -10, S + 10, 4, color=rgb("#CFCBC1"), brackets=fh / 3, hgt=0.7)

    # ---- grime: streaks from sill ends and below bands (periodic)
    st = streak_field(F, 303, scale=7, aniso=9)
    for fl in range(floors):
        for b in range(bays):
            x0 = b * bw + bw / 2 - 296
            x1 = b * bw + bw / 2 + 296
            fade = wrap_fade_rows(F, fl * fh + win_sill + 12, 150, 1.4)
            cols = wrap_band_cols(F, x0 - 14, x0 + 26, 8) + wrap_band_cols(F, x1 - 26, x1 + 14, 8) + \
                wrap_band_cols(F, x0 + 40, x1 - 40, 30) * 0.35
            m = np.clip((st - 0.42) * 2.2, 0, 1) * fade * np.clip(cols, 0, 1)
            F.tint(F.from_mask(m.astype(f32)), rgb("#A39A8A"), 0.4)
        fade = wrap_fade_rows(F, fl * fh + 22, 70, 2.0)
        m = np.clip((st - 0.45) * 2.0, 0, 1) * fade
        F.tint(F.from_mask(m.astype(f32)), rgb("#A49B8C"), 0.35)
    del st
    return F.finalize(OUT, normal_strength=6.0, height_blur=0.6, albedo_ao=0.3)


# ======================================================================================
# 3. CONCRETE APARTMENT — balconies, frosted parapets, AC units, laundry
# ======================================================================================
def stipple_concrete(F, base, seed, amt=0.05, scale=2.0):
    """Painted spray-textured concrete (吹付) albedo + height field (full canvas)."""
    n1 = F.noise(scale, seed, beta=1.0)
    n2 = F.noise(140, seed + 1, beta=2.0)
    col = base * (1 + (n1 - 0.5)[..., None] * amt * 2 + (n2 - 0.5)[..., None] * 0.07)
    return col.astype(f32), (n1 - 0.5).astype(f32) * 0.04


def laundry(F, x0, x1, y_pole, r, max_drop=150):
    """Laundry pole with hanging items (towels, shirts, socks) between x0..x1."""
    F.put(F.R(x0, y_pole - 3, x1, y_pole + 3), alb=rgb("#C8CCCF"), h=0.42, metal=0.8, smooth=0.6)
    for xh in (x0 + 6, x1 - 6):
        F.put(F.R(xh - 3, y_pole - 60, xh + 3, y_pole + 4), alb=rgb("#AEB2B5"), h=0.4, metal=0.8)
    x = x0 + r.uniform(10, 40)
    cols = [rgb("#F2F0EA"), rgb("#9EC3E6"), rgb("#F5C9C9"), rgb("#F7E08F"), rgb("#B6D7A8"),
            rgb("#E9E6DF"), rgb("#7FA1C9"), rgb("#D9A0B8"), rgb("#4E5D73")]
    while x < x1 - 40:
        kind = r.choice(["towel", "shirt", "shirt", "sock", "towel", "pants"])
        c = cols[int(r.integers(len(cols)))]
        if kind == "towel":
            w = r.uniform(50, 80); hgt = r.uniform(90, 130)
            p = poly([(x, y_pole), (x + w, y_pole), (x + w + 2, y_pole + hgt), (x - 2, y_pole + hgt)])
        elif kind == "shirt":
            w = r.uniform(70, 95); hgt = r.uniform(85, 110)
            sl = w * 0.28
            p = poly([(x + w * 0.3, y_pole + 4), (x + w * 0.7, y_pole + 4), (x + w + sl * 0.6, y_pole + 18),
                      (x + w + sl * 0.3, y_pole + 45), (x + w * 0.88, y_pole + 40), (x + w * 0.9, y_pole + hgt),
                      (x + w * 0.1, y_pole + hgt), (x + w * 0.12, y_pole + 40), (x - sl * 0.3, y_pole + 45),
                      (x - sl * 0.6, y_pole + 18)])
            # hanger hook
            F.put(F.R(x + w * 0.5 - 2, y_pole - 8, x + w * 0.5 + 2, y_pole + 4), alb=rgb("#777777"), h=0.42)
        elif kind == "pants":
            w = r.uniform(55, 70); hgt = r.uniform(120, 150)
            p = poly([(x, y_pole), (x + w, y_pole), (x + w + 4, y_pole + hgt), (x + w * 0.56, y_pole + hgt),
                      (x + w * 0.5, y_pole + hgt * 0.35), (x + w * 0.44, y_pole + hgt), (x - 4, y_pole + hgt)])
        else:
            w = r.uniform(16, 22); hgt = r.uniform(40, 55)
            p = poly([(x, y_pole), (x + w, y_pole), (x + w, y_pole + hgt), (x + w + 8, y_pole + hgt + 10),
                      (x - 2, y_pole + hgt + 10)])
        reg = F.region(p)
        if reg is not None:
            ty = np.clip(F.ly(reg, y_pole, max_drop) / max_drop, 0, 1)
            F.put(reg, alb=c * (1 - 0.15 * ty)[..., None], h=0.4, metal=0.0, smooth=0.1, emis=0)
        x += w + r.uniform(12, 40)


@register
def concrete_apartment():
    """4 floors x 2.9 m = 11.6 m tall, 2 units x 5.8 m = 11.6 m wide (176.6 px/m)."""
    S = 2048
    F = Facade("concrete_apartment", S, S, ss=2, seed=303)
    r = rng(303)
    floors, units = 4, 2
    fh, uw = S / floors, S / units
    slab = 24        # half thickness of slab edge band
    fin = 34         # half width of the concrete fin walls between units
    par_h = 196      # parapet height above slab top (1.1 m)
    door_h = 360     # 2.0 m

    wall_col, wall_h = stipple_concrete(F, rgb("#D8D2C6"), 31)
    F.alb[:] = wall_col
    F.hgt[:] = 0.25 + wall_h
    F.smooth[:] = 0.18
    del wall_col, wall_h

    refl = sheen_field(F, 33, 0.7, clouds=0.1)
    plan = []
    for fl in range(floors):
        row = []
        for u in range(units):
            for d in range(2):
                st = window_state(r, kind="home", lit_p=0.5)
                st["cover"] = r.choice(["curtain", "curtain", "lace", "curtain_open", "blinds"])
                row.append((u * 2 + d, 1, st))
        plan.append(row)
    frac = assign_lit(plan, 0.45, r)
    print("  concrete_apartment lit fraction", round(frac, 2))

    futon_unit = (1, 0)
    dish_unit = (2, 1)
    for fl in range(floors):
        Yf = (fl + 1) * fh - slab           # balcony floor (top of slab) for this storey
        Yc = fl * fh + slab                  # ceiling (underside of slab above)
        for u in range(units):
            ux0 = u * uw + fin
            ux1 = (u + 1) * uw - fin
            # ---- doors: big LD door + bedroom door
            specs = [(ux0 + 60, ux0 + 60 + 400), (ux1 - 60 - 330, ux1 - 60)]
            for d, (dx0, dx1) in enumerate(specs):
                st = plan[fl][u * 2 + d][2]
                dy0, dy1 = Yf - door_h, Yf
                fw = 10
                F.put(F.R(dx0 - 5, dy0 - 5, dx1 + 5, dy1), alb=rgb("#A9A398"), h=0.22)
                F.put(ring_reg(F, dx0 - 5, dy0 - 5, dx1 + 5, dy1 + 5, 24), ao=0.75)
                paint_window(F, dx0 + fw, dy0 + fw, dx1 - fw, dy1 - 6, st, rgb("#6B7C86"), glass_reflect=refl,
                             smooth=0.92, h=0.16, interior_vis=0.62)
                ring = skia.Path(); ring.addRect(skia.Rect.MakeLTRB(dx0, dy0, dx1, dy1))
                ring.addRect(skia.Rect.MakeLTRB(dx0 + fw, dy0 + fw, dx1 - fw, dy1 - 6))
                F.put(F.region(ring, evenodd=True), alb=rgb("#BFC2C2"), h=0.24, metal=0.85, smooth=0.5)
                mx = (dx0 + dx1) / 2
                F.put(F.R(mx - 9, dy0 + fw, mx + 9, dy1 - 6), alb=rgb("#B5B8B9"), h=0.23, metal=0.85, smooth=0.5)
                F.put(F.R(mx - 1, dy0 + fw, mx + 1, dy1 - 6), alb=rgb("#6D7072"), h=0.2)
            # ---- AC outdoor unit on the balcony floor (mostly behind the frosted parapet)
            ax = ux0 + 60 + 400 + 30 if (fl + u) % 2 == 0 else ux1 - 60 - 330 - 30 - 150
            ac_unit(F, ax, Yf - 112, 150, 104, r, hgt=0.4)
            # ---- laundry on some balconies
            if r.random() < 0.42:
                lx0 = ux0 + r.uniform(30, 120)
                laundry(F, lx0, lx0 + r.uniform(300, 520), Yc + 120, r)
            # ---- tall plant peeking above the parapet
            if r.random() < 0.45:
                px = r.uniform(ux0 + 40, ux1 - 40)
                F.put(F.region(plant_path(px, Yf, r.uniform(240, 300), r)), alb=rgb("#3F6B3A"), h=0.42,
                      smooth=0.3, emis=0)
            # ---- ceiling shadow on the recessed wall (balcony soffit above)
            reg = F.R(ux0, Yc, ux1, Yc + 170)
            if reg is not None:
                t = np.clip(F.ly(reg, Yc, 170) / 170, 0, 1)
                F.put(reg, ao=(0.45 + 0.55 * t ** 0.7))
                F.tint(reg, rgb("#E6E1DA") * 0 + (0.86 + 0.14 * t)[..., None], 1.0)
            # balcony ceiling light (small bracket lamp) above the LD door
            lx = ux0 + 260
            F.put(F.R(lx - 14, Yc + 18, lx + 14, Yc + 40, 6), alb=rgb("#F1EFE6"), h=0.33, smooth=0.6)
            if plan[fl][u * 2][2]["lit"] or r.random() < 0.3:
                F.put(F.R(lx - 14, Yc + 18, lx + 14, Yc + 40, 6), emis=K(3000) * 0.95)
                reg = F.region(ellipse(lx, Yc + 50, 140, 90))
                if reg is not None:
                    d = np.sqrt((F.lx(reg, lx - 140, 280) - 140) ** 2 / 140 ** 2 +
                                (F.ly(reg, Yc - 40, 180) - 90) ** 2 / 90 ** 2)
                    F.put(reg, emis=K(3000) * (np.clip(1 - d, 0, 1) ** 2 * 0.25)[..., None], emode="add")

            # ---- frosted-glass parapet: blur what is behind, veil it
            py0, py1 = Yf - par_h, Yf + slab * 0  # panel spans down to slab top
            s = F.ss
            ys = slice(int(py0 * s), int(py1 * s)); xs = slice(int(ux0 * s), int(ux1 * s))
            import cv2
            sig = 9 * s
            k = int(sig * 3) * 2 + 1
            F.alb[ys, xs] = cv2.GaussianBlur(F.alb[ys, xs], (k, k), sig)
            F.emis[ys, xs] = cv2.GaussianBlur(F.emis[ys, xs], (k, k), sig * 1.6)
            reg = F.R(ux0, py0, ux1, py1)
            ty = np.clip(F.ly(reg, py0, par_h) / par_h, 0, 1)
            frost = rgb("#D9E2E4") * (1.0 - 0.06 * ty)[..., None]
            F.put(reg, alb=frost, opacity=0.68, h=0.7, metal=0.0, smooth=0.75)
            F.put(reg, emis=np.array([0.72, 0.72, 0.72], f32), emode="mul")
            # frames: top rail / handrail, posts, bottom rail
            alu = rgb("#C4C6C3")
            F.put(F.R(ux0, py0 - 16, ux1, py0 + 6, 4), alb=alu * 1.03, h=0.84, metal=0.88, smooth=0.55)
            F.put(F.R(ux0, py0 + 6, ux1, py0 + 9), ao=0.7)
            npost = 4
            for i in range(npost + 1):
                px = ux0 + (ux1 - ux0) * i / npost
                F.put(F.R(px - 7, py0, px + 7, py1), alb=alu, h=0.78, metal=0.88, smooth=0.5)
            F.put(F.R(ux0, py1 - 10, ux1, py1), alb=alu * 0.95, h=0.76, metal=0.88, smooth=0.5)
            # futon airing over the handrail
            if (fl, u) == futon_unit:
                fx0 = ux0 + 150; fx1 = fx0 + 330
                fp = rect(fx0, py0 - 22, fx1, py0 + 140, 10)
                reg = F.region(fp)
                ty = np.clip(F.ly(reg, py0 - 22, 162) / 162, 0, 1)
                tx = np.clip(F.lx(reg, fx0, fx1 - fx0) / (fx1 - fx0), 0, 1)
                # floral-ish pattern: soft dots on pink cotton
                patt = halftone(reg.m.shape[0], reg.m.shape[1], 0.18, 26 * s, 30,
                                offset=(reg.xs.start, reg.ys.start))
                col = rgb("#F2B8C6") * (1 - patt[..., None]) + rgb("#FFFFFF") * patt[..., None]
                col = col * (0.82 + 0.18 * np.sin(ty * math.pi * 0.9 + 0.3))[..., None]
                F.put(reg, alb=col, h=0.9, smooth=0.1, metal=0.0, emis=0)
                F.put(F.R(fx0, py0 + 140, fx1, py0 + 168), ao=0.6)
                # clips
                for cx_ in (fx0 + 40, fx1 - 40):
                    F.put(F.R(cx_ - 9, py0 - 26, cx_ + 9, py0 - 8, 3), alb=rgb("#3D7BD9"), h=0.93)
            # BS satellite dish on the handrail
            if (fl, u) == (dish_unit[0] % floors, dish_unit[1]):
                dx = ux1 - 140
                F.put(F.R(dx - 3, py0 - 90, dx + 3, py0), alb=rgb("#8F9295"), h=0.86, metal=0.8)
                F.put(F.region(ellipse(dx - 18, py0 - 120, 46, 52)), alb=rgb("#ECEBE6"), h=0.92, smooth=0.5)
                F.put(F.R(dx - 30, py0 - 126, dx + 22, py0 - 118), alb=rgb("#5B5E61"), h=0.95, metal=0.6)

    # ---- slab edges (centred on the tile's horizontal lines -> seamless)
    ed_col, ed_h = stipple_concrete(F, rgb("#D9D4CA"), 41)
    for k in range(floors + 1):
        yc = k * fh
        reg = F.R(0, yc - slab, S, yc + slab)
        if reg is None:
            continue
        t = np.clip(F.ly(reg, yc - slab, 2 * slab) / (2 * slab), 0, 1)
        F.put(reg, alb=F._fit(ed_col, reg) * (1.02 - 0.06 * t)[..., None], h=0.82 + F._fit(ed_h, reg),
              smooth=0.2, metal=0.0)
        # drip groove under the slab edge
        F.put(F.R(0, yc + slab - 5, S, yc + slab - 2), alb=rgb("#A7A196"), h=0.76)
    # ---- fin walls between units (vertical, continuous)
    for u in range(units + 1):
        xc = u * uw
        reg = F.R(xc - fin, 0, xc + fin, S)
        if reg is None:
            continue
        t = np.clip(F.lx(reg, xc - fin, 2 * fin) / (2 * fin), 0, 1)
        F.put(reg, alb=F._fit(ed_col, reg) * (1.0 - 0.04 * t)[..., None], h=0.86 + F._fit(ed_h, reg),
              smooth=0.2, metal=0.0, emis=0)
        F.put(F.R(xc - fin - 10, 0, xc - fin, S), ao=0.75)
        F.put(F.R(xc + fin, 0, xc + fin + 10, S), ao=0.75)
        # expansion joint line
        F.put(F.R(xc - 1.2, 0, xc + 1.2, S), alb=rgb("#A7A196"), h=0.8)
    del ed_col, ed_h
    # ---- rain-water down pipe on fin face
    pipe_v(F, uw + fin - 16, -10, S + 10, 11, color=rgb("#CFCCC3"), brackets=fh / 2, hgt=0.95)

    # ---- water stains below every slab edge and handrail (periodic streaks)
    st = streak_field(F, 313, scale=10, aniso=7)
    front = np.clip((F.hgt - 0.62) * 8, 0, 1)
    for k in range(floors):
        yc = k * fh
        fade = wrap_fade_rows(F, yc + slab, 300, 1.3)
        m = np.clip((st - 0.45) * 2.0, 0, 1) * fade * front
        F.tint(F.from_mask(m.astype(f32)), rgb("#A0998D"), 0.5)
    # fin walls: long rain streaks from the top of each storey
    for k in range(floors):
        fade = wrap_fade_rows(F, k * fh + slab, 480, 0.8)
        m = np.clip((st - 0.5) * 2.0, 0, 1) * fade * front * 0.6
        F.tint(F.from_mask(m.astype(f32)), rgb("#A39C90"), 0.4)
    del front
    del st, refl
    return F.finalize(OUT, normal_strength=6.0, height_blur=0.7, albedo_ao=0.3)


# ======================================================================================
# 4. BRICK MANSION — 二丁掛 brick-tile mansion, recessed windows, French balconies
# ======================================================================================
def brick_albedo(F, tf, palette, mortar, seed):
    pal = np.stack(palette).astype(f32)
    idx = np.minimum((tf["rnd"] * len(palette)).astype(np.int32), len(palette) - 1)
    col = pal[idx]
    # flashed ends + per-brick speckle + large-scale weathering
    flash = (np.abs(tf["u"] - 0.5) * 2) ** 3 * (tf["rnd2"] > 0.5)
    col = col * (1 - 0.18 * flash)[..., None]
    sp = F.noise(1.6, seed, beta=0.8)
    col = col * (0.93 + 0.14 * sp)[..., None]
    big = F.noise(380, seed + 1, beta=2.0)
    col = col * (0.94 + 0.12 * big)[..., None]
    gm = tf["grout"][..., None]
    return (col * (1 - gm) + mortar * gm).astype(f32)


@register
def brick_mansion():
    """4 floors x 3.0 m = 12 m tall, 3 bays x 4.0 m = 12 m wide (170.7 px/m).
    227x60 mm brick tiles (51 x 172 per texture, running bond)."""
    S = 2048
    F = Facade("brick_mansion", S, S, ss=2, seed=404)
    r = rng(404)
    floors, bays = 4, 3
    fh, bw = S / floors, S / bays

    tf = tile_field(F, 51, 172, grout=2.0, bond="running", seed=17)
    palette = [rgb("#8E4C38"), rgb("#7B4231"), rgb("#9C5B42"), rgb("#6F3B2D"), rgb("#A6694F"), rgb("#86503D")]
    F.alb[:] = brick_albedo(F, tf, palette, rgb("#B9B2A6"), 51)
    dome = np.sin(np.clip(tf["u"], 0, 1) * math.pi) ** 0.3 * np.sin(np.clip(tf["v"], 0, 1) * math.pi) ** 0.3
    F.hgt[:] = 0.48 + 0.05 * dome - 0.09 * tf["grout"]
    F.smooth[:] = 0.32 * (1 - tf["grout"]) + 0.1 * tf["grout"]
    del tf, dome

    refl = sheen_field(F, 44, 0.7, clouds=0.1)
    stone = rgb("#D9D1C1")
    iron = rgb("#24262A")

    # plan: per floor [window, door, window]
    plan = []
    for fl in range(floors):
        row = []
        for b in range(bays):
            st = window_state(r, kind="home", lit_p=0.5)
            st["cover"] = r.choice(["curtain", "lace", "curtain", "blinds", "curtain_open"])
            row.append((b, 1, st))
        plan.append(row)
    frac = assign_lit(plan, 0.5, r)
    print("  brick_mansion lit fraction", round(frac, 2))

    for fl in range(floors):
        Yf = (fl + 1) * fh - 18      # finished floor level of this storey (just above string course)
        for b in range(bays):
            bc = b * bw + bw / 2
            st = plan[fl][b][2]
            if b == 1:
                # ---- French door + shallow balcony
                x0, x1 = bc - 200, bc + 200
                y0, y1 = Yf - 372, Yf - 6
            else:
                x0, x1 = bc - 175, bc + 175
                y0, y1 = Yf - 408, Yf - 158
            rev = 16  # visible reveal depth (side jamb)
            # reveal (recess) - darker brick returns
            F.put(F.R(x0 - rev, y0 - rev, x1 + rev, y1), alb=rgb("#5E3528"), h=0.3)
            F.put(ring_reg(F, x0 - rev, y0 - rev, x1 + rev, y1 + rev, rev + 14), ao=0.6)
            fw = 11
            frame = rgb("#3B3A39") if b != 1 else rgb("#E9E6DF")
            gx0, gy0, gx1, gy1 = x0 + fw, y0 + fw, x1 - fw, y1 - fw
            paint_window(F, gx0, gy0, gx1, gy1, st, rgb("#62737E"), glass_reflect=refl, smooth=0.93, h=0.18,
                         interior_vis=0.6)
            ring = skia.Path(); ring.addRect(skia.Rect.MakeLTRB(x0, y0, x1, y1))
            ring.addRect(skia.Rect.MakeLTRB(gx0, gy0, gx1, gy1))
            F.put(F.region(ring, evenodd=True), alb=frame, h=0.24, metal=0.6 if b != 1 else 0.0, smooth=0.5)
            mx = (x0 + x1) / 2
            F.put(F.R(mx - 8, gy0, mx + 8, gy1), alb=frame, h=0.23, metal=0.6 if b != 1 else 0.0, smooth=0.5)
            if b == 1:
                # door transom bar + handles
                F.put(F.R(gx0, gy0 + 70, gx1, gy0 + 80), alb=frame, h=0.23)
                for hx in (mx - 22, mx + 16):
                    F.put(F.R(hx, y0 + 190, hx + 6, y0 + 232, 3), alb=rgb("#B49A62"), h=0.3, metal=1.0, smooth=0.7)
            # reveal shadow gradient from top-left (soft AO, not baked sun)
            F.put(F.R(x0, y0, x1, y0 + 26), ao=0.7)
            # ---- soldier-course header (vertical bricks)
            hy0, hy1 = y0 - rev - 30, y0 - rev
            reg = F.R(x0 - rev - 8, hy0, x1 + rev + 8, hy1)
            lx = F.lx(reg, x0 - rev - 8, (x1 + rev + 8) - (x0 - rev - 8))
            u = (lx / 13.0) % 1.0
            jm = np.clip((1.0 - np.minimum(u, 1 - u) * 13.0) * F.ss * 0.5, 0, 1)
            seed_b = np.floor(lx / 13.0)
            tone = (np.sin(seed_b * 12.9898) * 43758.5453) % 1.0
            colh = np.stack(palette)[np.minimum((tone * len(palette)).astype(int), len(palette) - 1)] * 0.92
            ty = F.ly(reg, hy0, 30)
            jm = np.maximum(jm, np.clip((1.0 - np.minimum(ty, 30 - ty)) * F.ss * 0.5, 0, 1))
            F.put(reg, alb=colh * (1 - jm[..., None]) + rgb("#B9B2A6") * jm[..., None], h=0.5 - 0.08 * jm)
            # ---- precast sill / balcony slab
            if b == 1:
                F.put(F.R(x0 - 50, y1, x1 + 50, y1 + 26), alb=stone, h=0.8, smooth=0.3)
                F.put(F.R(x0 - 50, y1 + 26, x1 + 50, y1 + 52), ao=0.6)
                # AC unit standing on the balcony behind the railing
                if fl % 2 == 0:
                    ac_unit(F, x1 - 170, y1 - 108, 150, 102, r, hgt=0.42)
                # wrought-iron railing: top rail, bottom rail, balusters + scroll band
                ry0, ry1 = y1 - 196, y1
                F.put(F.R(x0 - 46, ry0 - 9, x1 + 46, ry0 + 5, 3), alb=iron, h=0.9, metal=0.75, smooth=0.45, emis=0)
                F.put(F.R(x0 - 46, ry1 - 22, x1 + 46, ry1 - 14), alb=iron, h=0.88, metal=0.75, smooth=0.45, emis=0)
                F.put(F.R(x0 - 46, ry0 + 30, x1 + 46, ry0 + 36), alb=iron, h=0.88, metal=0.75, smooth=0.45, emis=0)
                n = 22
                for i in range(n + 1):
                    bx = x0 - 40 + (x1 - x0 + 80) * i / n
                    F.put(F.R(bx - 3, ry0, bx + 3, ry1 - 14), alb=iron, h=0.88, metal=0.75, smooth=0.45, emis=0)
                for i in range(n // 2):
                    cx_ = x0 - 40 + (x1 - x0 + 80) * (2 * i + 1) / n
                    reg = F.region(circle(cx_, ry0 + 18, 9), stroke=3.2, fill=False)
                    F.put(reg, alb=iron, h=0.88, metal=0.75, emis=0)
            else:
                F.put(F.R(x0 - 30, y1, x1 + 30, y1 + 20), alb=stone, h=0.74, smooth=0.3)
                F.put(F.R(x0 - 30, y1 + 20, x1 + 30, y1 + 38), ao=0.65)
                # window grille (面格子) on some side windows
                if (fl + b) % 3 == 0:
                    gc = rgb("#B6B8B6")
                    F.put(F.R(x0 + 4, y0 + 4, x1 - 4, y0 + 14), alb=gc, h=0.7, metal=0.85, emis=0)
                    F.put(F.R(x0 + 4, y1 - 14, x1 - 4, y1 - 4), alb=gc, h=0.7, metal=0.85, emis=0)
                    for i in range(12):
                        gx = x0 + 20 + (x1 - x0 - 40) * i / 11
                        F.put(F.R(gx - 4, y0 + 4, gx + 4, y1 - 4), alb=gc, h=0.7, metal=0.85, smooth=0.5,
                              emis=np.zeros(3, f32))
            # grime streaks below sill
        # ---- sills drip grime (per floor, periodic)
    # ---- precast string course centred on slab lines
    for k in range(floors + 1):
        yc = k * fh
        reg = F.R(0, yc - 18, S, yc + 18)
        if reg is None:
            continue
        t = np.clip(F.ly(reg, yc - 18, 36) / 36, 0, 1)
        nz = F.noise(3, 61, beta=1.0)
        F.put(reg, alb=stone * (1.0 - 0.07 * t)[..., None] * (0.95 + 0.1 * F._fit(nz, reg))[..., None],
              h=0.76 + 0.03 * (1 - t), smooth=0.3, emis=0)
        F.put(F.R(0, yc + 18, S, yc + 40), ao=0.7)
        del nz
    # ---- downpipe on pier
    pipe_v(F, 2 * bw, -10, S + 10, 12, color=rgb("#6A5F55"), brackets=fh / 2, hgt=0.9, metal=0.4)
    # ---- grime streaks under sills / string courses
    st = streak_field(F, 414, scale=8, aniso=8)
    for fl in range(floors):
        Yf = (fl + 1) * fh - 18
        for b in range(bays):
            bc = b * bw + bw / 2
            x0, x1 = (bc - 200, bc + 200) if b == 1 else (bc - 175, bc + 175)
            ys = (Yf - 6 + 26) if b == 1 else (Yf - 158 + 20)
            fade = wrap_fade_rows(F, ys + 6, 150, 1.6)
            cols = np.clip(wrap_band_cols(F, x0 - 30, x1 + 30, 30), 0, 1)
            m = np.clip((st - 0.47) * 2.0, 0, 1) * fade * cols * (F.hgt < 0.7)
            F.tint(F.from_mask(m.astype(f32)), rgb("#7E7468"), 0.3)
    del st, refl
    return F.finalize(OUT, normal_strength=6.0, height_blur=0.6, albedo_ao=0.3)


# ======================================================================================
# 5. DARK GLASS TOWER — black glass, bronze fins, LED accent lines
# ======================================================================================
@register
def dark_glass_tower():
    """4 floors x 4.0 m = 16 m tall, 10 modules x 1.6 m = 16 m wide (128 px/m)."""
    S = 2048
    F = Facade("dark_glass_tower", S, S, ss=2, seed=505)
    r = rng(505)
    floors, mods = 4, 10
    fh, mw = S / floors, S / mods
    span = 56
    refl = sheen_field(F, 55, 1.3, clouds=0.07)
    F.put(F.full(), alb=rgb("#10161D"), h=0.3, smooth=0.95)

    plan = [_lit_rooms(r, mods, 0.5, kinds=("office",), min_w=2, max_w=4) for _ in range(floors)]
    frac = assign_lit(plan, 0.38, r)
    print("  dark_glass_tower lit fraction", round(frac, 2))
    for fl in range(floors):
        y0 = fl * fh + span
        y1 = (fl + 1) * fh - span
        for (m0, wdt, st) in plan[fl]:
            if r.random() < 0.25:
                st["temp"] = WARM2   # lounge / reception
            for m in range(m0, m0 + wdt):
                x0 = m * mw + 6
                x1 = (m + 1) * mw - 6
                st2 = dict(st); st2["seed"] = int(r.integers(1 << 30))
                st2["bright"] = st["bright"] * 0.9
                paint_window(F, x0, y0, x1, y1, st2, rgb("#1A2530"), glass_reflect=refl, smooth=0.96,
                             h=0.28, interior_vis=0.14)
    # spandrels: opaque black glass with fine horizontal reeding + LED reveal line
    for k in range(floors + 1):
        yc = k * fh
        reg = F.R(0, yc - span, S, yc + span)
        if reg is None:
            continue
        ly = F.ly(reg, yc - span, 2 * span)
        reed = 0.5 + 0.5 * np.sin(ly / 4.0 * math.pi)
        base = rgb("#0B0F14") + (F._fit(refl, reg) * 0.7)[..., None] * np.array([0.7, 0.85, 1.0], f32)
        F.put(reg, alb=base * (0.92 + 0.08 * reed)[..., None], h=0.34 + 0.01 * reed, smooth=0.9, metal=0.0, emis=0)
        # slim transoms
        for yy in (yc - span, yc + span):
            F.put(F.R(0, yy - 4, S, yy + 4), alb=rgb("#2E2A26"), h=0.6, metal=0.9, smooth=0.6)
        # LED accent line (horizontal) recessed in the spandrel bottom reveal
        reg = F.R(0, yc + span - 18, S, yc + span - 13)
        F.put(reg, alb=rgb("#CAD3D8"), h=0.32, metal=0.0, smooth=0.8,
              emis=np.array([0.80, 0.92, 1.0], f32) * 0.85)
        # soft LED wash onto the reeded spandrel above it
        reg = F.R(0, yc + span - 60, S, yc + span - 18)
        if reg is not None:
            t = np.clip(F.ly(reg, yc + span - 60, 42) / 42, 0, 1)
            F.put(reg, emis=(np.array([0.5, 0.7, 0.9], f32) * (t ** 3 * 0.25)[..., None]), emode="add")
    # vertical fins (alternating depth) + cyan LED on every 5th fin
    for m in range(mods + 1):
        xc = m * mw
        deep = (m % 2 == 0)
        hw = 10 if deep else 6
        reg = F.R(xc - hw, 0, xc + hw, S)
        t = np.clip(F.lx(reg, xc - hw, 2 * hw) / (2 * hw), 0, 1)
        prof = (0.9 if deep else 0.7) + 0.05 * np.sin(t * math.pi)
        col = rgb("#4A4037") * (1.1 - 0.25 * t)[..., None]
        F.put(reg, alb=col, h=prof, metal=0.9, smooth=0.55, emis=0)
        F.put(F.R(xc - hw - 8, 0, xc + hw + 8, S), ao=0.82, opacity=0.7)
        if m % 5 == 0:
            reg = F.R(xc - 2, 0, xc + 2, S)
            F.put(reg, alb=rgb("#BFEFF5"), h=(0.96 if deep else 0.76), smooth=0.8, metal=0.0, emis=C("cyan") * 0.95)
            # halo on fin faces
            reg = F.R(xc - hw - 14, 0, xc + hw + 14, S)
            d = np.abs(F.lx(reg, xc - hw - 14, 2 * hw + 28) - (hw + 14))
            F.put(reg, emis=C("cyan")[None, None, :] * (np.clip(1 - d / (hw + 14), 0, 1) ** 2 * 0.35)[..., None],
                  emode="add")
    del refl
    return F.finalize(OUT, normal_strength=6.0, height_blur=0.6, albedo_ao=0.2)


# ======================================================================================
# 6. SHOPFRONT STRIP — ground floor shops (tiles horizontally only), 2048 x 1024
# ======================================================================================
def shutter(F, x0, y0, x1, y1, r, color=None, painted=False, grime=0.5):
    """Roll-down shutter curtain from y0 (top) to y1 (bottom bar)."""
    color = rgb("#A9ADAE") if color is None else color
    reg = F.R(x0, y0, x1, y1)
    if reg is None:
        return
    ly = F.ly(reg, y0, y1 - y0)
    lx = F.lx(reg, x0, x1 - x0)
    per = 17.0
    ph = (ly / per) % 1.0
    corr = np.sin(ph * math.pi * 2)
    groove = np.clip(1 - np.abs(ph - 0.02) * 25, 0, 1) + np.clip(1 - np.abs(ph - 1.0) * 25, 0, 1)
    shade = 0.95 + 0.06 * corr - 0.25 * groove
    t = np.clip(ly / (y1 - y0), 0, 1)
    dirt = F._fit(F._shutter_noise, reg) if hasattr(F, "_shutter_noise") else 0.5
    col = color * shade[..., None]
    col = col * (1 - grime * 0.35 * np.clip(t - 0.45, 0, 1)[..., None] * (0.6 + 0.8 * dirt)[..., None])
    F.put(reg, alb=col, h=0.5 + 0.035 * corr - 0.05 * groove, metal=0.0 if painted else 0.65,
          smooth=0.35 if painted else 0.4, emis=0)
    # bottom bar + lock
    F.put(F.R(x0, y1 - 22, x1, y1), alb=color * 0.8, h=0.56, metal=0.0 if painted else 0.7, smooth=0.4)
    cx = (x0 + x1) / 2
    F.put(F.R(cx - 26, y1 - 19, cx + 26, y1 - 4, 3), alb=rgb("#56595B"), h=0.6, metal=0.85)
    F.put(F.region(circle(cx, y1 - 11, 4)), alb=rgb("#1C1D1E"), h=0.55)


def guide_rails(F, x0, x1, y0, y1):
    for gx in (x0, x1):
        F.put(F.R(gx - 9, y0, gx + 9, y1), alb=rgb("#8D9193"), h=0.62, metal=0.75, smooth=0.4, emis=0)
        F.put(F.R(gx - 3, y0, gx + 3, y1), alb=rgb("#4A4D4F"), h=0.55)


def shutter_box(F, x0, x1, y0, y1, color=None):
    color = rgb("#B4B7B6") if color is None else color
    reg = F.R(x0 - 12, y0, x1 + 12, y1)
    t = np.clip(F.ly(reg, y0, y1 - y0) / (y1 - y0), 0, 1)
    F.put(reg, alb=color * (1.03 - 0.1 * t)[..., None], h=0.72 + 0.03 * (1 - t), metal=0.55, smooth=0.45, emis=0)
    F.put(F.R(x0 - 12, y1, x1 + 12, y1 + 14), ao=0.65)


def graffiti_throwup(F, text, box, fill_top, fill_bot, outline, shadow, r, font="bangers", rot=-4,
                     drips=5):
    p = fit_path(text_path(text, font, 200, -0.02), box)
    p = transformed(p, rotate=rot, skew_x=-0.12)
    l, t, rr, b = bounds(p)
    # shadow block
    sp = skia.Path(p); sp.offset(10, 9)
    reg = F.region(sp, stroke=16, join="round")
    F.put(reg, alb=shadow, smooth=0.45)
    # outline
    reg = F.region(p, stroke=16, join="round")
    F.put(reg, alb=outline, smooth=0.45)
    # drips from the outline bottom
    for i in range(drips):
        dx = r.uniform(l + 20, rr - 20)
        for dp in drip_paths(dx, b - 6, r.uniform(5, 8), r.uniform(25, 70), r):
            F.put(F.region(dp), alb=outline, smooth=0.45)
    # fill with vertical gradient + highlight band
    reg = F.region(p)
    ty = np.clip((F.Y(reg) - t) / max(1, b - t), 0, 1)
    col = fill_top * (1 - ty[..., None]) + fill_bot * ty[..., None]
    band = (np.abs(ty - 0.3) < 0.06).astype(f32)
    col = col * (1 - band[..., None]) + rgb("#FFFFFF") * band[..., None]
    F.put(reg, alb=np.broadcast_to(col, reg.m.shape + (3,)), smooth=0.45)
    # little shine sparkles
    for _ in range(3):
        sx, sy = r.uniform(l, rr), r.uniform(t, t + (b - t) * 0.5)
        star = poly([(sx, sy - 14), (sx + 3, sy - 3), (sx + 14, sy), (sx + 3, sy + 3), (sx, sy + 14),
                     (sx - 3, sy + 3), (sx - 14, sy), (sx - 3, sy - 3)])
        F.put(F.region(star), alb=rgb("#FFFFFF"))


def graffiti_tag(F, text, box, color, r, font="reggae", rot=-8, width=3.5):
    p = fit_path(text_path(text, font, 200), box)
    p = transformed(p, rotate=rot, skew_x=-0.25)
    reg = F.region(p, stroke=width, fill=False, join="round", cap="round")
    F.put(reg, alb=color, smooth=0.4)
    # underline swoosh
    l, t, rr, b = bounds(p)
    sw = skia.Path(); sw.moveTo(l, b + 8); sw.quadTo((l + rr) / 2, b + 22, rr + 20, b - 4)
    F.put(F.region(sw, stroke=width, fill=False, cap="round"), alb=color, smooth=0.4)


def vending_machine(F, x0, y0, x1, y1, r, body=None, header=None):
    body = rgb("#F1F1EC") if body is None else body
    header = rgb("#D8342B") if header is None else header
    w, h = x1 - x0, y1 - y0
    F.put(F.R(x0 - 8, y0 - 6, x0 + 2, y1), ao=0.55)
    F.put(F.R(x1 - 2, y0 - 6, x1 + 8, y1), ao=0.55)
    F.put(F.R(x0, y0, x1, y1, 5), alb=body, h=0.92, metal=0.1, smooth=0.55, emis=0)
    # header band
    F.put(F.R(x0 + 8, y0 + 8, x1 - 8, y0 + h * 0.08), alb=header, h=0.93, smooth=0.6, emis=header * 0.9)
    F.put(text_region(F, "DRINK", (x0 + 30, y0 + 14, x1 - 30, y0 + h * 0.08 - 6), font="chakra"),
          alb=rgb("#FFFFFF"), emis=np.array([1, 1, 1], f32))
    # display window with 3 rows of drinks
    wx0, wy0, wx1, wy1 = x0 + 12, y0 + h * 0.1, x1 - 12, y0 + h * 0.56
    F.put(F.R(wx0, wy0, wx1, wy1, 3), alb=rgb("#DCE6EA"), h=0.86, smooth=0.95,
          emis=np.array([0.85, 0.93, 1.0], f32) * 0.95)
    rows, cols = 3, 6
    can_cols = [rgb("#E83A3A"), rgb("#2D6FD6"), rgb("#F2C230"), rgb("#2DA44E"), rgb("#F07F2F"),
                rgb("#7A4BC8"), rgb("#FFFFFF"), rgb("#1E1E1E"), rgb("#47B8D8"), rgb("#C8A06A")]
    for i in range(rows):
        ry0 = wy0 + (wy1 - wy0) * i / rows
        ry1 = wy0 + (wy1 - wy0) * (i + 1) / rows
        for j in range(cols):
            cx = wx0 + (wx1 - wx0) * (j + 0.5) / cols
            cw = (wx1 - wx0) / cols * 0.55
            ch = (ry1 - ry0) * 0.58
            col = can_cols[int(r.integers(len(can_cols)))]
            if r.random() < 0.5:   # can
                pth = rect(cx - cw / 2, ry0 + (ry1 - ry0) * 0.12, cx + cw / 2, ry0 + (ry1 - ry0) * 0.12 + ch, 3)
            else:                  # PET bottle
                bt = ry0 + (ry1 - ry0) * 0.08
                pth = combine(rect(cx - cw / 2, bt + ch * 0.3, cx + cw / 2, bt + ch * 1.05, 5),
                              poly([(cx - cw / 2, bt + ch * 0.32), (cx - cw * 0.18, bt + ch * 0.08),
                                    (cx + cw * 0.18, bt + ch * 0.08), (cx + cw / 2, bt + ch * 0.32)]),
                              rect(cx - cw * 0.16, bt, cx + cw * 0.16, bt + ch * 0.1, 2))
            F.put(F.region(pth), alb=col, emis=col * 0.9 + 0.08)
            # label stripe
            F.put(F.R(cx - cw / 2, ry0 + (ry1 - ry0) * 0.38, cx + cw / 2, ry0 + (ry1 - ry0) * 0.48),
                  alb=rgb("#F7F7F2"), emis=np.array([0.95, 0.95, 0.95], f32))
            # price tag + button
            by = ry1 - (ry1 - ry0) * 0.2
            F.put(F.R(cx - cw * 0.6, by - 6, cx + cw * 0.6, by + 4), alb=rgb("#1C1C1C"),
                  emis=np.array([0.0, 0.0, 0.0], f32))
            lit_red = r.random() < 0.15
            bcol = rgb("#FF3B30") if lit_red else rgb("#34C1F0")
            F.put(F.R(cx - cw * 0.35, by + 6, cx + cw * 0.35, by + 14, 4), alb=bcol, emis=bcol)
    # lower panel: coin slot, bill slot, return lever, dispenser
    F.put(F.R(x1 - 70, y0 + h * 0.6, x1 - 30, y0 + h * 0.66, 3), alb=rgb("#8C9093"), h=0.94, metal=0.9)
    F.put(F.R(x1 - 56, y0 + h * 0.615, x1 - 44, y0 + h * 0.645), alb=rgb("#111111"))
    F.put(F.R(x0 + 30, y0 + h * 0.6, x0 + 110, y0 + h * 0.64, 3), alb=rgb("#2B2E31"), h=0.94,
          emis=np.array([0.2, 0.9, 0.4], f32) * 0.6)
    F.put(F.R(x0 + 20, y0 + h * 0.78, x1 - 20, y0 + h * 0.9, 6), alb=rgb("#222426"), h=0.84, ao=0.6)
    F.put(F.R(x0 + 24, y0 + h * 0.78 + 4, x1 - 24, y0 + h * 0.83, 4), alb=rgb("#3B3F43"), h=0.86)
    F.put(F.R(x0 + 4, y1 - 14, x1 - 4, y1), alb=rgb("#4C4F52"), h=0.9)


def red_lantern(F, cx, cy, rw, rh, r):
    """Akachōchin: ribbed red paper lantern with black caps and 酒 calligraphy."""
    reg = F.region(ellipse(cx, cy, rw, rh))
    ly = F.ly(reg, cy - rh, 2 * rh) - rh
    lx = F.lx(reg, cx - rw, 2 * rw) - rw
    rib = 0.5 + 0.5 * np.sin(ly / (rh / 9) * math.pi)
    rad = np.clip(1 - (lx / rw) ** 2, 0, 1)
    col = rgb("#D9241E") * (0.75 + 0.25 * rad ** 0.5)[..., None] * (0.92 + 0.08 * rib)[..., None]
    emi = np.array([1.0, 0.22, 0.12], f32) * (0.55 + 0.45 * rad)[..., None]
    F.put(reg, alb=col, h=0.9 + 0.05 * rad, smooth=0.3, emis=emi)
    F.put(F.R(cx - rw * 0.55, cy - rh - 14, cx + rw * 0.55, cy - rh + 8, 3), alb=rgb("#16130F"), h=0.95, emis=0)
    F.put(F.R(cx - rw * 0.55, cy + rh - 8, cx + rw * 0.55, cy + rh + 14, 3), alb=rgb("#16130F"), h=0.95, emis=0)
    F.put(F.R(cx - 2, cy - rh - 40, cx + 2, cy - rh - 14), alb=rgb("#16130F"), h=0.9)
    reg = text_region(F, "酒", (cx - rw * 0.55, cy - rh * 0.5, cx + rw * 0.55, cy + rh * 0.5), font="reggae")
    F.put(reg, alb=rgb("#141010"), emis=np.array([0.12, 0.02, 0.01], f32))
    # glow halo on the wall around it
    reg = F.region(ellipse(cx, cy, rw * 2.6, rh * 2.0))
    d = np.sqrt(((F.lx(reg, cx - rw * 2.6, rw * 5.2) - rw * 2.6) / (rw * 2.6)) ** 2 +
                ((F.ly(reg, cy - rh * 2.0, rh * 4.0) - rh * 2.0) / (rh * 2.0)) ** 2)
    F.put(reg, emis=np.array([1.0, 0.25, 0.12], f32) * (np.clip(1 - d, 0, 1) ** 2 * 0.35)[..., None], emode="add")


@register
def shopfront_strip():
    """Ground floor only: 2048 x 1024 = 9 m wide x 4.5 m tall (227.6 px/m), 3 shops x 3 m.
    Tiles horizontally only."""
    W, H = 2048, 1024
    F = Facade("shopfront_strip", W, H, ss=2, wrap_x=True, wrap_y=False, seed=606)
    r = rng(606)
    sw = W / 3
    pier = 30
    F._shutter_noise = F.noise(60, 66, beta=1.6)
    # ---- base wall: painted concrete
    wall, wall_h = stipple_concrete(F, rgb("#CFC8BB"), 61)
    F.alb[:] = wall; F.hgt[:] = 0.5 + wall_h; F.smooth[:] = 0.2
    del wall, wall_h
    # top slab band
    reg = F.R(0, 0, W, 64)
    t = np.clip(F.ly(reg, 0, 64) / 64, 0, 1)
    F.put(reg, alb=rgb("#D8D2C6") * (1.02 - 0.06 * t)[..., None], h=0.75, smooth=0.2)
    F.put(F.R(0, 64, W, 84), ao=0.6)
    # granite plinth
    gr = F.noise(1.5, 67, beta=0.6)
    reg = F.R(0, 990, W, H)
    F.put(reg, alb=rgb("#5E5D5B") * (0.85 + 0.3 * F._fit(gr, reg))[..., None], h=0.62, smooth=0.55)
    del gr

    # ===================== shop A: closed shutter w/ graffiti + vending machine
    ax0, ax1 = pier, sw - pier
    F.put(F.R(ax0 + 8, 76, ax1 - 8, 224, 4), alb=rgb("#E8E1CF"), h=0.78, smooth=0.3, emis=0)  # old fascia
    F.put(text_region(F, "金物 山田商店", (ax0 + 50, 104, ax1 - 50, 200), font="noto"),
          alb=rgb("#3E5C8A") * 0.9 + 0.08)
    fade = F.noise(30, 68, beta=1.4)
    reg = F.R(ax0 + 8, 76, ax1 - 8, 224)
    F.tint(reg, rgb("#BFB49C"), 0.5)  # sun-faded
    del fade
    shutter_box(F, ax0, ax1, 238, 300)
    shutter(F, ax0 + 10, 300, ax1 - 10, 990, r, grime=0.8)
    guide_rails(F, ax0 + 4, ax1 - 4, 300, 990)
    # graffiti
    graffiti_throwup(F, "SUMI", (ax0 + 36, 470, ax0 + 380, 720), rgb("#F4FBFF"), rgb("#9FDDF0"),
                     rgb("#0B0B12"), C("magenta"), r, rot=-5)
    graffiti_tag(F, "KZK", (ax0 + 60, 790, ax0 + 230, 880), rgb("#111111"), r, rot=-6, width=4)
    graffiti_tag(F, "ink!", (ax0 + 250, 350, ax0 + 400, 420), C("magenta"), r, font="bangers", rot=-10, width=4)
    graffiti_tag(F, "墨", (ax0 + 60, 340, ax0 + 150, 430), rgb("#1A1A1A"), r, font="reggae", rot=4, width=4)
    # closing notice paper (閉店のお知らせ)
    F.put(F.R(ax0 + 470, 360, ax0 + 560, 470), alb=rgb("#F6F3EA"), h=0.53, smooth=0.2)
    F.put(text_region(F, "お知らせ", (ax0 + 478, 368, ax0 + 552, 392), font="noto_bold"), alb=rgb("#C8262B"))
    for i in range(4):
        F.put(F.R(ax0 + 480, 404 + i * 14, ax0 + 550 - (i % 2) * 16, 407 + i * 14), alb=rgb("#3A3A3A"))
    # vending machine standing against the right of the shutter
    vending_machine(F, ax1 - 236, 570, ax1 - 30, 988, r)

    # ===================== shop B: izakaya
    bx0, bx1 = sw + pier, 2 * sw - pier
    # dark stained wood cladding over the whole bay
    reg = F.R(bx0, 76, bx1, 990)
    lx = F.lx(reg, bx0, bx1 - bx0)
    board = (lx / 22.0) % 1.0
    wn = F._fit(F.noise(6, 69, beta=1.2, aniso=(1.0, 10.0)), reg)
    col = rgb("#3A2A20") * (0.85 + 0.25 * wn)[..., None] * (1 - 0.35 * (board < 0.06))[..., None]
    F.put(reg, alb=col, h=0.58 - 0.04 * (board < 0.06), smooth=0.25, emis=0)
    # fascia board with lettering + gooseneck lamps
    F.put(F.R(bx0 + 20, 92, bx1 - 20, 216, 3), alb=rgb("#2A1E17"), h=0.7, smooth=0.3)
    F.put(F.R(bx0 + 26, 98, bx1 - 26, 210, 2), alb=rgb("#4A3426"), h=0.72, smooth=0.3)
    reg = text_region(F, "大衆酒場 たぬき", (bx0 + 50, 114, bx1 - 50, 196), font="reggae")
    F.put(reg, alb=rgb("#F3E9D2"), emis=K(3000) * 0.9)
    for lxp in (bx0 + 140, (bx0 + bx1) / 2, bx1 - 140):
        F.put(F.R(lxp - 3, 64, lxp + 3, 92), alb=rgb("#202020"), h=0.85, metal=0.8)
        F.put(F.R(lxp - 14, 84, lxp + 14, 96, 4), alb=rgb("#202020"), h=0.88, metal=0.8, emis=K(3000))
        reg = F.region(ellipse(lxp, 150, 110, 70))
        d = np.sqrt(((F.lx(reg, lxp - 110, 220) - 110) / 110) ** 2 + ((F.ly(reg, 80, 140) - 70) / 70) ** 2)
        F.put(reg, emis=K(3000)[None, None, :] * (np.clip(1 - d, 0, 1) ** 1.5 * 0.35)[..., None], emode="add")
    # entrance: lattice sliding doors
    ex0, ex1, ey0, ey1 = bx0 + 70, bx0 + 400, 330, 988
    st = window_state(r, "home"); st.update(lit=True, temp=WARM, cover="none", tv=False, bright=1.0)
    paint_window(F, ex0, ey0, ex1, ey1, st, rgb("#4B5258"), smooth=0.9, h=0.4, interior_vis=0.3)
    reg = F.R(ex0, ey0, ex1, ey1)
    lx = F.lx(reg, ex0, ex1 - ex0); ly = F.ly(reg, ey0, ey1 - ey0)
    lat = (((lx % 26.0) < 6) | ((ly % 120.0) < 6)).astype(f32)
    F.put(F.from_mask(np.zeros((F.H, F.W), f32)))  # no-op keeps API symmetrical
    F.put(Region(reg.m * lat, reg.ys, reg.xs), alb=rgb("#5A3E2A"), h=0.5, smooth=0.3, emis=np.zeros(3, f32))
    for fx in (ex0, (ex0 + ex1) / 2, ex1):
        F.put(F.R(fx - 9, ey0, fx + 9, ey1), alb=rgb("#4A3322"), h=0.52, emis=np.zeros(3, f32))
    F.put(F.R(ex0 - 9, ey0 - 12, ex1 + 9, ey0 + 6), alb=rgb("#4A3322"), h=0.55, emis=np.zeros(3, f32))
    # noren (3 panels) with 居酒屋
    nx0, nx1, ny0, ny1 = ex0 + 6, ex1 - 6, ey0 + 4, ey0 + 250
    F.put(F.R(nx0 - 20, ny0 - 8, nx1 + 20, ny0 + 4, 4), alb=rgb("#7A6A55"), h=0.75, metal=0.0)
    gap = 8
    pw = (nx1 - nx0 - 2 * gap) / 3
    for i, ch in enumerate("居酒屋"):
        px0 = nx0 + i * (pw + gap)
        pth = smooth_closed([(px0, ny0), (px0 + pw, ny0), (px0 + pw + 2, ny1 - 6), (px0 + pw / 2, ny1 + 4),
                             (px0 - 2, ny1 - 6)], 0.2)
        reg = F.region(pth)
        ly = np.clip(F.ly(reg, ny0, ny1 - ny0) / (ny1 - ny0), 0, 1)
        F.put(reg, alb=rgb("#1E2B4F") * (1 - 0.15 * ly)[..., None], h=0.7, smooth=0.12,
              emis=np.array([0.10, 0.06, 0.03], f32))
        F.put(text_region(F, ch, (px0 + 14, ny0 + 60, px0 + pw - 14, ny0 + 60 + pw - 28), font="reggae"),
              alb=rgb("#F2EEE4"), emis=np.array([0.25, 0.2, 0.15], f32))
    # side window with bamboo sudare blind
    wx0, wx1, wy0, wy1 = bx0 + 450, bx1 - 40, 360, 720
    st2 = window_state(r, "home"); st2.update(lit=True, temp=WARM2, cover="none", bright=0.95)
    paint_window(F, wx0, wy0, wx1, wy1, st2, rgb("#4B5258"), smooth=0.9, h=0.42, interior_vis=0.3)
    reg = F.R(wx0, wy0, wx1, wy0 + (wy1 - wy0) * 0.75)
    ly = F.ly(reg, wy0, wy1 - wy0)
    sl = 0.6 + 0.4 * (np.sin(ly / 3.0 * math.pi) > 0)
    F.put(reg, alb=rgb("#B89A62") * sl[..., None], h=0.52, smooth=0.2)
    F.put(reg, emis=np.array([0.55, 0.45, 0.3], f32) * sl[..., None], emode="mul")
    ring = skia.Path(); ring.addRect(skia.Rect.MakeLTRB(wx0 - 10, wy0 - 10, wx1 + 10, wy1 + 10))
    ring.addRect(skia.Rect.MakeLTRB(wx0, wy0, wx1, wy1))
    F.put(F.region(ring, evenodd=True), alb=rgb("#4A3322"), h=0.6, emis=np.zeros(3, f32))
    # menu blackboard (tategaki chalk menu)
    mx0, mx1, my0, my1 = bx0 + 450, bx1 - 40, 750, 970
    F.put(F.R(mx0, my0, mx1, my1, 4), alb=rgb("#5A3E2A"), h=0.65)
    F.put(F.R(mx0 + 10, my0 + 10, mx1 - 10, my1 - 10, 2), alb=rgb("#26302B"), h=0.66, smooth=0.2)
    items = [("おすすめ", "#F2F0E6"), ("焼鳥", "#F7E08F"), ("生ビール", "#F2F0E6"), ("枝豆", "#B6FF9B"),
             ("刺身", "#FFB7D5")]
    colw = (mx1 - mx0 - 30) / len(items)
    for i, (txt, c) in enumerate(items):
        cx_ = mx1 - 20 - colw * (i + 0.5)
        F.put(text_region(F, txt, (cx_ - colw * 0.38, my0 + 22, cx_ + colw * 0.38, my1 - 22), font="noto_bold",
                          vertical=True, align=(0.5, 0.0)), alb=rgb(c), smooth=0.2)
    # red lantern beside the entrance
    red_lantern(F, ex1 + 40, 420, 34, 56, r)

    # ===================== shop C: cleaners, shutter half down
    cx0, cx1 = 2 * sw + pier, W - pier
    F.put(F.R(cx0 + 8, 80, cx1 - 8, 220, 4), alb=rgb("#F7F8F6"), h=0.78, smooth=0.6,
          emis=np.array([0.95, 0.97, 1.0], f32) * 0.9)
    F.put(F.R(cx0 + 8, 196, cx1 - 8, 220), alb=rgb("#1F63C6"), emis=rgb("#1F63C6") * 0.9)
    F.put(text_region(F, "クリーニング 白鳥", (cx0 + 40, 100, cx1 - 40, 186), font="noto"),
          alb=rgb("#1F63C6"), emis=rgb("#1F63C6") * 0.95)
    shutter_box(F, cx0, cx1, 238, 300)
    # storefront glass + door (interior lit, garment racks)
    gx0, gx1, gy0, gy1 = cx0 + 10, cx1 - 10, 300, 988
    st3 = window_state(r, "office"); st3.update(lit=True, temp=COOL, cover="none", bright=1.0)
    paint_window(F, gx0, gy0, gx1, gy1, st3, rgb("#5C6C76"), smooth=0.92, h=0.4, interior_vis=0.4)
    # garments in plastic on a rail
    F.put(F.R(gx0 + 40, 560, gx1 - 220, 566), alb=rgb("#9EA4A8"), h=0.43, metal=0.9, emis=np.zeros(3, f32))
    gxp = gx0 + 50
    while gxp < gx1 - 260:
        gw = r.uniform(26, 40)
        gc = [rgb("#F2F2F0"), rgb("#2F3B52"), rgb("#B9C3CF"), rgb("#6D5A4E"), rgb("#E6D6C3")][int(r.integers(5))]
        F.put(F.R(gxp, 568, gxp + gw, 568 + r.uniform(200, 330), 4), alb=gc * 0.8, h=0.44,
              emis=gc * 0.55)
        gxp += gw + r.uniform(2, 8)
    # aluminium door frame on the right + counter
    F.put(F.R(gx1 - 200, gy0 + 300, gx1 - 192, gy1), alb=rgb("#BFC3C5"), h=0.5, metal=0.85, emis=np.zeros(3, f32))
    F.put(F.R(gx0, gy1 - 120, gx1 - 210, gy1 - 112), alb=rgb("#BFC3C5"), h=0.5, metal=0.85, emis=np.zeros(3, f32))
    F.put(text_region(F, "Yシャツ ¥180", (gx1 - 186, gy0 + 380, gx1 - 30, gy0 + 420), font="noto"),
          alb=rgb("#D8262B"), emis=np.array([0.3, 0.05, 0.05], f32))
    # shutter half down (covers to y=600) + glow spill under it
    shutter(F, cx0 + 10, 300, cx1 - 10, 600, r, color=rgb("#9FB8AE"), painted=True, grime=0.4)
    guide_rails(F, cx0 + 4, cx1 - 4, 300, 990)
    reg = F.R(cx0 + 10, 600, cx1 - 10, 640)
    t = np.clip(F.ly(reg, 600, 40) / 40, 0, 1)
    F.put(reg, emis=np.array([0.6, 0.7, 0.8], f32) * (0.4 + 0.6 * t)[..., None], emode="mul")
    # striped awning above (projects; drawn over the shutter box)
    ay0, ay1 = 236, 330
    reg = F.R(cx0 - 6, ay0, cx1 + 6, ay1)
    lx = F.lx(reg, cx0 - 6, cx1 - cx0 + 12)
    stripe = ((lx // 44) % 2).astype(f32)
    ty = np.clip(F.ly(reg, ay0, ay1 - ay0) / (ay1 - ay0), 0, 1)
    col = (rgb("#F4F2EC") * (1 - stripe[..., None]) + rgb("#2366C8") * stripe[..., None]) * (1.0 - 0.18 * ty)[..., None]
    F.put(reg, alb=col, h=0.95, smooth=0.15, metal=0.0, emis=np.zeros(3, f32))
    # scalloped valance
    xs = cx0 - 6
    while xs < cx1 + 6:
        reg = F.region(ellipse(xs + 22, ay1, 22, 18))
        lx = F.lx(reg, xs, 44)
        stripe = ((((xs - cx0 + 6) // 44) % 2))
        F.put(reg, alb=rgb("#2366C8") if stripe else rgb("#F4F2EC"), h=0.95, emis=np.zeros(3, f32))
        xs += 44
    F.put(F.R(cx0 - 6, ay1 + 14, cx1 + 6, ay1 + 50), ao=0.55)

    # ===================== piers (mosaic tile), pipes, meters
    tf = tile_field(F, 256, 128, grout=1.2, bond="stack", seed=71)
    pcol = rgb("#8D8278") * (0.9 + 0.2 * tf["rnd"])[..., None]
    pcol = pcol * (1 - tf["grout"][..., None]) + rgb("#C9C2B6") * tf["grout"][..., None]
    ph = 0.68 - 0.05 * tf["grout"]
    for k in range(4):
        xc = k * sw
        reg = F.R(xc - pier, 70, xc + pier, 990)
        if reg is None:
            continue
        F.put(reg, alb=F._fit(pcol, reg), h=F._fit(ph, reg), smooth=0.45, metal=0.0, emis=np.zeros(3, f32))
        F.put(F.R(xc - pier - 8, 70, xc - pier, 990), ao=0.7)
        F.put(F.R(xc + pier, 70, xc + pier + 8, 990), ao=0.7)
    del tf, pcol, ph
    pipe_v(F, 0, 64, 990, 12, color=rgb("#9A9C96"), brackets=230, hgt=0.85)
    # electric meter on pier A/B, gas meter on pier B/C
    F.put(F.R(sw - 26, 520, sw + 26, 600, 4), alb=rgb("#D9D9D2"), h=0.82, smooth=0.5)
    F.put(F.R(sw - 18, 530, sw + 18, 560, 2), alb=rgb("#30373D"), h=0.83, smooth=0.9)
    F.put(F.R(2 * sw - 26, 760, 2 * sw + 26, 850, 6), alb=rgb("#C9C4B4"), h=0.82, smooth=0.4)
    F.put(F.R(2 * sw - 5, 850, 2 * sw + 5, 990), alb=rgb("#B9A64A"), h=0.8, metal=0.6)

    # ===================== grime: streaks from top band + splash zone near the ground
    st = streak_field(F, 616, scale=8, aniso=8)
    fade = wrap_fade_rows(F, 84, 260, 1.4)
    m = np.clip((st - 0.47) * 2, 0, 1) * fade
    F.tint(F.from_mask(m.astype(f32)), rgb("#968F83"), 0.4)
    ground = np.clip((F._yy - 900) / 90, 0, 1) * (0.4 + 0.6 * F.noise(25, 617, beta=1.5))
    F.tint(F.from_mask(ground.astype(f32) * np.ones((1, F.W), f32)), rgb("#8B8478"), 0.45)
    del st, fade, m, ground, F._shutter_noise
    return F.finalize(OUT, normal_strength=6.0, height_blur=0.6, albedo_ao=0.3)


# ======================================================================================
# 7. PARKING GARAGE — open-deck multi-storey car park (立体駐車場)
# ======================================================================================
def car_front(F, cx, base_y, w, h, body, r, lights_on=False, rear=False):
    """Simplified car seen head-on / from behind: body, glasshouse, lamps, grille, plate, tyres."""
    Z = np.zeros(3, f32)
    tyre = rgb("#151617")
    for sx in (-1, 1):
        F.put(F.R(cx + sx * w * 0.38 - w * 0.08, base_y - h * 0.2, cx + sx * w * 0.38 + w * 0.08, base_y, 8),
              alb=tyre, h=0.36, emis=Z)
    # cabin (roof pillars) + windshield
    cab = poly([(cx - w * 0.42, base_y - h * 0.5), (cx - w * 0.31, base_y - h * 0.95),
                (cx + w * 0.31, base_y - h * 0.95), (cx + w * 0.42, base_y - h * 0.5)])
    F.put(F.region(cab), alb=body * 0.92, h=0.4, metal=0.5, smooth=0.75, emis=Z)
    ws = poly([(cx - w * 0.37, base_y - h * 0.53), (cx - w * 0.28, base_y - h * 0.89),
               (cx + w * 0.28, base_y - h * 0.89), (cx + w * 0.37, base_y - h * 0.53)])
    reg = F.region(ws)
    ty = np.clip(F.ly(reg, base_y - h * 0.89, h * 0.36) / (h * 0.36), 0, 1)
    F.put(reg, alb=rgb("#2A3640") * (1.25 - 0.45 * ty)[..., None], h=0.39, metal=0.0, smooth=0.95)
    # mirrors
    for sx in (-1, 1):
        F.put(F.region(ellipse(cx + sx * w * 0.47, base_y - h * 0.55, w * 0.05, h * 0.035)), alb=body * 0.85,
              h=0.42, emis=Z)
    # lower body
    reg = F.R(cx - w * 0.5, base_y - h * 0.55, cx + w * 0.5, base_y - h * 0.08, w * 0.06)
    ty = np.clip(F.ly(reg, base_y - h * 0.55, h * 0.47) / (h * 0.47), 0, 1)
    F.put(reg, alb=body * (1.08 - 0.3 * ty)[..., None], h=0.42, metal=0.5, smooth=0.75, emis=Z)
    # hood highlight line
    F.put(F.R(cx - w * 0.42, base_y - h * 0.54, cx + w * 0.42, base_y - h * 0.52), alb=body * 1.2 + 0.05, h=0.43)
    # grille / rear garnish
    F.put(F.R(cx - w * 0.22, base_y - h * 0.4, cx + w * 0.22, base_y - h * 0.27, 4),
          alb=rgb("#1B1D1F") if not rear else body * 0.6, h=0.41)
    # lamps
    lc = rgb("#B81F18") if rear else rgb("#DDE6EA")
    em = (np.array([1.0, 0.1, 0.06], f32) * 0.95 if rear else np.array([0.95, 0.97, 1.0], f32)) if lights_on else Z
    for sx in (-1, 1):
        lp = poly([(cx + sx * w * 0.47, base_y - h * 0.47), (cx + sx * w * 0.25, base_y - h * 0.45),
                   (cx + sx * w * 0.26, base_y - h * 0.38), (cx + sx * w * 0.47, base_y - h * 0.4)])
        F.put(F.region(lp), alb=lc, h=0.44, smooth=0.9, emis=em)
    # bumper + plate
    F.put(F.R(cx - w * 0.48, base_y - h * 0.16, cx + w * 0.48, base_y - h * 0.08, 4), alb=body * 0.55, h=0.43)
    F.put(F.R(cx - w * 0.1, base_y - h * 0.25, cx + w * 0.1, base_y - h * 0.16, 2), alb=rgb("#F2F2EA"), h=0.44)


@register
def parking_garage():
    """4 decks x 2.8 m = 11.2 m tall, 4 bays x 2.8 m = 11.2 m wide (182.9 px/m)."""
    S = 2048
    F = Facade("parking_garage", S, S, ss=2, seed=707)
    r = rng(707)
    decks, bays = 4, 4
    dh, bwid = S / decks, S / bays
    slab = 36
    col_hw = 24
    # deep interior (back wall + ceiling) as base
    F.put(F.full(), alb=rgb("#3E4143"), h=0.12, smooth=0.25)
    car_cols = [rgb("#E9E9E6"), rgb("#1C1C1F"), rgb("#9DA3A8"), rgb("#B3262A"), rgb("#2C4E8A"),
                rgb("#F0F0EE"), rgb("#4A5A3E"), rgb("#D7C7A0"), rgb("#6A6E73")]
    for d in range(decks):
        ytop = d * dh + slab
        ybot = (d + 1) * dh - slab
        # ceiling soffit + beams (lighter concrete, gradient)
        reg = F.R(0, ytop, S, ytop + 120)
        t = np.clip(F.ly(reg, ytop, 120) / 120, 0, 1)
        F.put(reg, alb=rgb("#6B6E70") * (1.0 - 0.25 * t)[..., None], h=0.16)
        # back wall gets darker toward the floor
        reg = F.R(0, ytop + 120, S, ybot)
        t = np.clip(F.ly(reg, ytop + 120, ybot - ytop - 120) / (ybot - ytop - 120), 0, 1)
        F.put(reg, alb=rgb("#3D4042") * (1.0 - 0.3 * t)[..., None], h=0.1)
        # far structure: back columns, beams, exit sign
        for b in range(bays):
            fxc = b * bwid + bwid / 2 + r.uniform(-60, 60)
            F.put(F.R(fxc - 16, ytop + 60, fxc + 16, ybot), alb=rgb("#55585A"), h=0.13)
        F.put(F.R(0, ytop + 52, S, ytop + 66), alb=rgb("#4E5153"), h=0.15)
        lit_deck = d != 2 or r.random() < 0.3
        if d == 1:
            ex = bwid * 2.5 + 120
            F.put(F.R(ex - 46, ytop + 80, ex + 46, ytop + 112, 3), alb=rgb("#1E9A4A"), h=0.16,
                  emis=rgb("#2BD46A") * 0.9)
            F.put(text_region(F, "出口 EXIT", (ex - 40, ytop + 84, ex + 40, ytop + 108), font="noto_bold"),
                  alb=rgb("#FFFFFF"), emis=np.array([0.95, 1.0, 0.95], f32))
        # emission: ambient interior glow (cool fluorescent) w/ falloff
        if lit_deck:
            reg = F.R(0, ytop, S, ybot)
            t = np.clip(F.ly(reg, ytop, ybot - ytop) / (ybot - ytop), 0, 1)
            F.put(reg, emis=COOLER[None, None, :] * (0.22 * (1 - t) ** 1.8 + 0.05)[..., None])
        # fluorescent fixtures on the ceiling
        nfx = 8
        for i in range(nfx):
            fx = (i + 0.5) * S / nfx
            on = lit_deck and r.random() < 0.85
            F.put(F.R(fx - 70, ytop + 14, fx + 70, ytop + 26, 3), alb=rgb("#E8ECEA"), h=0.2, smooth=0.6,
                  emis=COOLER * 1.0 if on else np.zeros(3, f32))
            if on:
                reg = F.region(ellipse(fx, ytop + 30, 190, 110))
                dd = np.sqrt(((F.lx(reg, fx - 190, 380) - 190) / 190) ** 2 + ((F.ly(reg, ytop - 80, 220) - 110) / 110) ** 2)
                F.put(reg, emis=COOLER[None, None, :] * (np.clip(1 - dd, 0, 1) ** 2 * 0.5)[..., None], emode="add")
        # parked cars (seen head-on / rear) in each bay
        for b in range(bays):
            if r.random() < 0.2:
                continue
            cx = b * bwid + bwid * 0.5 + r.uniform(-40, 40)
            w = r.uniform(300, 335); hgt = r.uniform(250, 290)
            car_front(F, cx, ybot - 4, w, hgt, car_cols[int(r.integers(len(car_cols)))], r,
                      lights_on=(r.random() < 0.12), rear=r.random() < 0.5)
        # expanded-metal mesh parapet panel (1.0 m) with top rail
        py0 = ybot - 183
        reg = F.R(0, py0, S, ybot)
        lx = F.lx(reg, 0, S); ly = F.ly(reg, py0, 183)
        u = (lx / 14.0 + ly / 9.0); v = (lx / 14.0 - ly / 9.0)
        du = np.abs((u % 1.0) - 0.5); dv = np.abs((v % 1.0) - 0.5)
        strand = (np.minimum(du, dv) < 0.13).astype(f32)
        mesh = rgb("#8F9496")
        F.put(Region(reg.m * strand, reg.ys, reg.xs), alb=mesh, h=0.62, metal=0.85, smooth=0.4,
              emis=np.zeros(3, f32))
        F.put(Region(reg.m * (1 - strand), reg.ys, reg.xs), alb=rgb("#2A2C2E"), opacity=0.35,
              emis=np.array([0.55, 0.55, 0.55], f32), emode="mul")
        F.put(F.R(0, py0 - 10, S, py0 + 4), alb=rgb("#A6ABAD"), h=0.7, metal=0.85, smooth=0.5, emis=np.zeros(3, f32))
        for b in range(bays * 2 + 1):
            px = b * S / (bays * 2)
            F.put(F.R(px - 5, py0, px + 5, ybot), alb=rgb("#9EA3A5"), h=0.66, metal=0.85, emis=np.zeros(3, f32))
    # slab edges with painted yellow/black safety stripe on the lower lip
    for k in range(decks + 1):
        yc = k * dh
        reg = F.R(0, yc - slab, S, yc + slab)
        if reg is None:
            continue
        t = np.clip(F.ly(reg, yc - slab, 2 * slab) / (2 * slab), 0, 1)
        F.put(reg, alb=rgb("#C9C5BC") * (1.03 - 0.08 * t)[..., None], h=0.78, smooth=0.2, emis=np.zeros(3, f32))
        F.put(F.R(0, yc + slab, S, yc + slab + 30), ao=0.55)
        reg = F.R(0, yc - slab + 4, S, yc - slab + 16)
        lx = F.lx(reg, 0, S)
        hz = (((lx + F.ly(reg, 0, S)) / 22.0) % 2.0 < 1.0).astype(f32)
        F.put(reg, alb=rgb("#E8C21E") * (1 - hz[..., None]) + rgb("#1B1B1B") * hz[..., None], h=0.79, smooth=0.35)
    # columns
    for b in range(bays + 1):
        xc = b * bwid
        reg = F.R(xc - col_hw, 0, xc + col_hw, S)
        if reg is None:
            continue
        t = np.clip(F.lx(reg, xc - col_hw, 2 * col_hw) / (2 * col_hw), 0, 1)
        F.put(reg, alb=rgb("#CDC9C0") * (1.02 - 0.06 * t)[..., None], h=0.82, smooth=0.2, emis=np.zeros(3, f32))
        F.put(F.R(xc - col_hw - 10, 0, xc - col_hw, S), ao=0.7)
        F.put(F.R(xc + col_hw, 0, xc + col_hw + 10, S), ao=0.7)
    # blue "P" level markers on alternating columns
    for d in range(decks):
        xc = (d % 2) * bwid * 2 + bwid
        y0 = d * dh + slab + 60
        F.put(F.R(xc - 20, y0, xc + 20, y0 + 40, 4), alb=rgb("#1F5FBF"), h=0.84, emis=rgb("#1F5FBF") * 0.7)
        F.put(text_region(F, "P", (xc - 14, y0 + 5, xc + 14, y0 + 35), font="chakra"), alb=rgb("#FFFFFF"),
              emis=np.array([0.95, 0.95, 0.95], f32))
    # rust/water streaks below slabs
    st = streak_field(F, 717, scale=8, aniso=8)
    front = np.clip((F.hgt - 0.7) * 8, 0, 1)
    for k in range(decks):
        fade = wrap_fade_rows(F, k * dh + slab, 300, 1.2)
        m = np.clip((st - 0.46) * 2, 0, 1) * fade * front
        F.tint(F.from_mask(m.astype(f32)), rgb("#958C7E"), 0.5)
    del st, front
    return F.finalize(OUT, normal_strength=6.0, height_blur=0.6, albedo_ao=0.3)


# ======================================================================================
# preview helpers
# ======================================================================================
def previews(name, paths, wrap_y=True):
    os.makedirs(PREVIEWS, exist_ok=True)
    a = Image.open(paths["albedo"]).convert("RGB")
    e = Image.open(paths["emission"]).convert("RGB")
    ny = 2 if wrap_y else 2
    ta = tile_preview(a, 2, ny, 1200)
    te = tile_preview(e, 2, ny, 1200)
    out = Image.new("RGB", (ta.width + te.width + 16, max(ta.height, te.height)), (20, 18, 28))
    out.paste(ta, (0, 0)); out.paste(te, (ta.width + 16, 0))
    p = os.path.join(PREVIEWS, f"facade_{name}_tiled.png")
    out.save(p)
    return p


def mask_viz(n):
    """Preview of the packed mask: metallic | AO | smoothness as greyscale strips."""
    p = os.path.join(OUT, f"{n}_mask.png")
    a = np.asarray(Image.open(p).convert("RGBA"))
    w, h = a.shape[1], a.shape[0]
    s = 512 / max(w, h)
    tiles = [Image.fromarray(a[..., c]).resize((int(w * s), int(h * s)), Image.LANCZOS) for c in (0, 1, 3)]
    out = Image.new("L", (tiles[0].width * 3 + 16, tiles[0].height), 40)
    for i, t in enumerate(tiles):
        out.paste(t, (i * (t.width + 8), 0))
    q = os.path.join(PREVIEWS, f"facade_{n}_maskviz.png")
    out.save(q)
    return q


def sheet():
    paths = []
    for n in SETS:
        for ch in ("albedo", "normal", "emission", "mask"):
            p = os.path.join(OUT, f"{n}_{ch}.png")
            if os.path.exists(p):
                paths.append(mask_viz(n) if ch == "mask" else p)
    if paths:
        contact_sheet(paths, os.path.join(PREVIEWS, "facades.png"), cell=(300, 300), cols=4,
                      bg="dark", title="FACADES  albedo / normal / emission / mask (metal | AO | smooth)")


def check_seams(names=None):
    """Compare the wrap-around edge difference to typical neighbouring-pixel differences.
    A ratio near 1.0 means the seam is statistically invisible."""
    names = names or list(SETS)
    for n in names:
        for ch in ("albedo", "normal", "emission", "mask"):
            p = os.path.join(OUT, f"{n}_{ch}.png")
            if not os.path.exists(p):
                continue
            a = np.asarray(Image.open(p)).astype(np.float32)
            inner_x = np.abs(np.diff(a, axis=1)).mean()
            seam_x = np.abs(a[:, 0] - a[:, -1]).mean()
            msg = f"{n:20s} {ch:9s} x-seam {seam_x / max(inner_x, 1e-6):5.2f}"
            if n != "shopfront_strip":
                inner_y = np.abs(np.diff(a, axis=0)).mean()
                seam_y = np.abs(a[0] - a[-1]).mean()
                msg += f"   y-seam {seam_y / max(inner_y, 1e-6):5.2f}"
            print(msg)


def lit_report(names=None):
    """Measure the lit-window fraction from the emission maps (count of openings whose mean
    emission is clearly non-zero), using the window rectangles recorded at paint time."""
    import json
    names = names or list(SETS)
    out = {}
    for n in names:
        jp = os.path.join(PREVIEWS, f"facade_{n}_windows.json")
        ep = os.path.join(OUT, f"{n}_emission.png")
        if not (os.path.exists(jp) and os.path.exists(ep)):
            continue
        e = np.asarray(Image.open(ep).convert("RGB")).astype(np.float32).max(-1) / 255.0
        wins = json.load(open(jp))
        lit = 0
        for x0, y0, x1, y1, _flag in wins:
            xs = np.arange(int(x0), int(x1)) % e.shape[1]
            ys = np.clip(np.arange(int(y0), int(y1)), 0, e.shape[0] - 1)
            if e[np.ix_(ys, xs)].mean() > 0.06:
                lit += 1
        frac = lit / max(1, len(wins))
        out[n] = (lit, len(wins), frac)
        print(f"{n:20s} lit windows {lit:3d}/{len(wins):3d} = {frac * 100:4.0f}%")
    return out


def main(argv):
    if argv and argv[0] == "--check":
        check_seams(argv[1:] or None)
        lit_report(argv[1:] or None)
        return
    names = argv or list(SETS)
    for n in names:
        print("rendering", n, flush=True)
        F_paths = SETS[n]()
        previews(n, F_paths)
    sheet()
    lit_report(names)


if __name__ == "__main__":
    main(sys.argv[1:])
