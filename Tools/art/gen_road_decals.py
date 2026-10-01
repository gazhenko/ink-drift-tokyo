"""Road-marking decals for INK DRIFT: TOKYO  ->  Game/Assets/InkDrift/Art/Decals/road_*.png

Top-down view, texture "up" (V+) = forward / far along the driving direction.
Japanese road lettering & arrows are designed in "perceived" proportions and then stretched
along the driving direction, exactly like the real thing (so horizontal bars get thicker).
White ~#F2F0EA / yellow ~#F5C400 paint on transparent, worn (wheel-track wear, chips,
aggregate pores, cracks, grime).

Usage:  python gen_road_decals.py            # all
        python gen_road_decals.py tomare     # one (substring match on id)
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decallib import *  # noqa: F401,F403
from inklib import f32

WHITE = hexc("#F2F0EA")
YELLOW = hexc("#F5C400")
SS = 2


def cell_glyph(ch, font, box, mode="fill"):
    return fit_path(text_path(ch, font, 400), box, mode=mode)


def stretched(path: skia.Path, sy: float, cx: float, cy: float) -> skia.Path:
    m = skia.Matrix()
    m.setScale(1.0, sy, cx, cy)
    return xform(path, m)


# --------------------------------------------------------------------------------------
# items: each returns mask (internal res) given canvas
# --------------------------------------------------------------------------------------
def m_tomare(c):
    W, H = c.w, c.h
    chars = "止まれ"  # 止 farthest = top of texture
    top, bot, gap = 34, 34, 44
    ch_h = (H - top - bot - gap * 2) / 3
    ch_w = ch_h / 2.6
    x0 = (W - ch_w) / 2
    ps = []
    for i, ch in enumerate(chars):
        y0 = top + i * (ch_h + gap)
        ps.append(cell_glyph(ch, "noto", (x0, y0, x0 + ch_w, y0 + ch_h)))
    return c.mask(ps), [(W * 0.30, 40), (W * 0.72, 40)]


def m_speed(num):
    def f(c):
        W, H = c.w, c.h
        dw, dh, gap = 380, 1520, 70
        x0 = (W - (dw * 2 + gap)) / 2
        y0 = (H - dh) / 2
        ps = []
        for i, d in enumerate(num):
            ps.append(cell_glyph(d, "noto", (x0 + i * (dw + gap), y0, x0 + i * (dw + gap) + dw, y0 + dh)))
        return c.mask(ps), [(W * 0.27, 70), (W * 0.74, 70)]
    return f


def arrow_head(tipx, tipy, dirx, diry, length, width):
    nx, ny = -diry, dirx
    bx, by = tipx - dirx * length, tipy - diry * length
    return poly([(tipx, tipy), (bx + nx * width / 2, by + ny * width / 2),
                 (bx + dirx * length * 0.18, by + diry * length * 0.18),
                 (bx - nx * width / 2, by - ny * width / 2)])


SY = 3.0  # elongation along driving direction


def arrow_paths(kind, W, H):
    """Arrow in perceived space (y squashed by SY), then stretched. Returns fill path."""
    ph = H / SY  # perceived height
    cx = W / 2 if kind == "straight" else W * 0.66 if kind in ("left", "straight_left") else W * 0.34
    shaft_w = 58
    head_len, head_w = 150, 210
    bottom = ph - 16
    parts = []
    if kind == "straight":
        top = 16
        shaft = poly([(cx - shaft_w / 2, bottom), (cx - shaft_w / 2, top + head_len * 0.95),
                      (cx + shaft_w / 2, top + head_len * 0.95), (cx + shaft_w / 2, bottom)])
        parts += [shaft, arrow_head(cx, top, 0, -1, head_len, head_w)]
    else:
        sgn = -1 if kind in ("left", "straight_left") else 1
        turn_y = ph * 0.48 if kind != "straight_left" else ph * 0.62
        R = 90
        cl = skia.Path()
        cl.moveTo(cx, bottom)
        cl.lineTo(cx, turn_y)
        # quarter turn toward side
        cl.quadTo(cx, turn_y - R, cx + sgn * R, turn_y - R)
        end_x = cx + sgn * (R + 150)
        cl.lineTo(end_x, turn_y - R)
        parts.append(stroke_outline(cl, shaft_w, join="round", cap="butt"))
        parts.append(arrow_head(end_x + sgn * head_len * 0.92, turn_y - R, sgn, 0, head_len, head_w * 0.95))
        if kind == "straight_left":
            top = 16
            shaft = poly([(cx - shaft_w / 2, turn_y + 5), (cx - shaft_w / 2, top + head_len * 0.95),
                          (cx + shaft_w / 2, top + head_len * 0.95), (cx + shaft_w / 2, turn_y + 5)])
            parts += [shaft, arrow_head(cx, top, 0, -1, head_len, head_w)]
    p = union(*parts)
    return stretched(p, SY, 0, 0)


def m_arrow(kind):
    def f(c):
        p = arrow_paths(kind, c.w, c.h)
        return c.mask(p), [(c.w * 0.5, 60)] if kind == "straight" else [(c.w * 0.35, 60), (c.w * 0.7, 60)]
    return f


def m_diamond(c):
    W, H = c.w, c.h
    m, lw = 40, 46
    outer = poly([(W / 2, m), (W - m, H / 2), (W / 2, H - m), (m, H / 2)])
    # inner diamond offset: horizontal line thickness lw (measured horizontally)
    ix = (W / 2 - m) - lw
    k = ix / (W / 2 - m)
    iy = (H / 2 - m) * k
    inner = poly([(W / 2, H / 2 - iy), (W / 2 + ix, H / 2), (W / 2, H / 2 + iy), (W / 2 - ix, H / 2)])
    return mask_sub(c.mask(outer), c.mask(inner)), [(W * 0.3, 40), (W * 0.75, 40)]


def m_crosswalk(c):
    W, H = c.w, c.h
    bw, period = 256, 512
    ps = [rect(x, 56, x + bw, H - 56) for x in (128, 128 + period)]
    return c.mask(ps), [(256, 60), (768, 60)]


def m_school(c):
    """スクールゾーン as painted: two rows across the lane, far row スクール on top, near row
    ゾーン below; every glyph elongated ~2.5x along the driving direction."""
    W, H = c.w, c.h
    m, gap, row_gap = 48, 22, 130
    cw = (W - 2 * m - gap * 3) / 4
    chh = cw * 2.5
    top = (H - (2 * chh + row_gap)) / 2
    ps = []
    for row, chars in enumerate(("スクール", "ゾーン")):
        n = len(chars)
        x_start = (W - (n * cw + (n - 1) * gap)) / 2
        y0 = top + row * (chh + row_gap)
        for i, ch in enumerate(chars):
            x0 = x_start + i * (cw + gap)
            if ch == "ー":  # long vowel: horizontal bar in horizontal writing
                ps.append(rect(x0 + cw * 0.06, y0 + chh * 0.43, x0 + cw * 0.94, y0 + chh * 0.57))
            else:
                ps.append(cell_glyph(ch, "noto", (x0, y0, x0 + cw, y0 + chh)))
    return c.mask(ps), [(W * 0.27, 80), (W * 0.73, 80)]


def m_tsugakuro(c):
    """通学路 across the lane, glyphs elongated ~2.6x along the driving direction."""
    W, H = c.w, c.h
    m, gap = 48, 34
    cw = (W - 2 * m - gap * 2) / 3
    chh = cw * 2.6
    y0 = (H - chh) / 2
    ps = [cell_glyph(ch, "noto", (m + i * (cw + gap), y0, m + i * (cw + gap) + cw, y0 + chh)) for i, ch in enumerate("通学路")]
    return c.mask(ps), [(W * 0.25, 70), (W * 0.75, 70)]


def m_jokou(c):
    W, H = c.w, c.h
    chars = "徐行"
    top, gap = 40, 70
    ch_h = (H - 2 * top - gap) / 2
    ch_w = ch_h / 2.4
    x0 = (W - ch_w) / 2
    ps = [cell_glyph(ch, "noto", (x0, top + i * (ch_h + gap), x0 + ch_w, top + i * (ch_h + gap) + ch_h)) for i, ch in enumerate(chars)]
    return c.mask(ps), [(W * 0.3, 40), (W * 0.72, 40)]


def m_stopline(c):
    W, H = c.w, c.h
    return c.mask(rect(24, 64, W - 24, H - 64)), [(W * 0.25, 120), (W * 0.75, 120)]


def m_chevron(c):
    """導流帯 chevrons, V pointing forward(up); tile both ways (horizontal repeat -> W-zigzag)."""
    Wi, Hi = c.W, c.H
    xx, yy = coords(Hi, Wi)
    s = c.ss
    period = 256 * s
    slope = 1.0  # 45 deg arms
    u = yy - np.abs(xx - Wi / 2) * slope
    # perpendicular stripe width = duty * period / sqrt(1+slope^2)
    duty = 0.42
    f = (u / period) % 1.0
    d = np.minimum(np.abs(f - duty / 2), 1.0)  # distance in period units from stripe centre
    halfw = duty / 2
    dist_px = (d - halfw) * period / math.sqrt(1 + slope * slope)
    # handle wrap of stripe centred at duty/2
    f2 = ((u / period) - duty / 2 + 0.5) % 1.0 - 0.5
    dist_px = (np.abs(f2) - halfw) * period / math.sqrt(1 + slope * slope)
    M = np.clip(0.5 - dist_px, 0, 1).astype(f32)
    # soften the sharp V apex / seam a little (painted chevrons have mitred apex)
    return M, [(256, 70), (768, 70)]


def m_hatch(c):
    Wi, Hi = c.W, c.H
    xx, yy = coords(Hi, Wi)
    s = c.ss
    period = 256 * s
    u = (xx + yy) / period
    f2 = (u - 0.25 + 0.5) % 1.0 - 0.5
    dist_px = (np.abs(f2) - 0.21) * period / math.sqrt(2)
    return np.clip(0.5 - dist_px, 0, 1).astype(f32), [(256, 70), (768, 70)]


def bicycle_path(cx, cy, s):
    """Side-view bicycle pictogram centred at (cx,cy); s = wheel radius."""
    lw = s * 0.22
    rear = (cx - s * 1.25, cy + s * 0.25)
    front = (cx + s * 1.25, cy + s * 0.25)
    bb = (cx - s * 0.1, cy + s * 0.30)            # bottom bracket
    seat_top = (cx - s * 0.45, cy - s * 0.85)     # top of seat tube
    head_top = (cx + s * 0.80, cy - s * 0.80)     # top of head tube
    head_bot = (cx + s * 0.88, cy - s * 0.45)
    parts = []
    for (x, y) in (rear, front):
        ring = skia.Path(); ring.addCircle(x, y, s)
        parts.append(stroke_outline(ring, lw))
        parts.append(circle(x, y, lw * 0.75))
    fr = skia.Path()
    fr.moveTo(*rear); fr.lineTo(*bb); fr.lineTo(*head_bot); fr.lineTo(*head_top)
    fr.moveTo(*rear); fr.lineTo(*seat_top)
    fr.moveTo(*bb); fr.lineTo(*seat_top)
    fr.moveTo(seat_top[0] + s * 0.05, seat_top[1] + s * 0.18); fr.lineTo(head_top[0], head_top[1] + s * 0.12)
    fr.moveTo(*head_bot); fr.lineTo(*front)
    parts.append(stroke_outline(fr, lw * 0.85, join="round", cap="round"))
    hb = skia.Path(); hb.moveTo(head_top[0] - s * 0.05, head_top[1]); hb.lineTo(head_top[0] - s * 0.05, head_top[1] - s * 0.18)
    hb.lineTo(head_top[0] + s * 0.35, head_top[1] - s * 0.22)
    parts.append(stroke_outline(hb, lw * 0.8, join="round", cap="round"))
    sp = skia.Path(); sp.moveTo(seat_top[0] - s * 0.05, seat_top[1]); sp.lineTo(seat_top[0] - s * 0.1, seat_top[1] - s * 0.18)
    parts.append(stroke_outline(sp, lw * 0.7, cap="round"))
    saddle = skia.Path(); saddle.moveTo(seat_top[0] - s * 0.42, seat_top[1] - s * 0.22); saddle.lineTo(seat_top[0] + s * 0.18, seat_top[1] - s * 0.2)
    parts.append(stroke_outline(saddle, lw * 1.1, cap="round"))
    return union(*parts)


def m_bicycle(c):
    W, H = c.w, c.h
    sy = 2.6
    ph = H / sy
    cx = W / 2
    b = bicycle_path(cx, 0, 150)
    l, t, r_, bt = bounds(b)
    bw = r_ - l
    # perceived-space: bike on top, arrow below (arrow tip just under bike), then stretch
    b = fit_path(b, (cx - 330, 20, cx + 330, 20 + 660 * (bt - t) / bw))
    top_y = bounds(b)[3] + 60
    shaft = poly([(cx - 30, ph - 10), (cx - 30, top_y + 120), (cx + 30, top_y + 120), (cx + 30, ph - 10)])
    ar = union(shaft, arrow_head(cx, top_y, 0, -1, 130, 190))
    allp = stretched(union(b, ar), sy, 0, 0)
    return c.mask(allp), [(W * 0.3, 60), (W * 0.7, 60)]


# id: (builder, (w,h), color, seed, opts)
ITEMS = {
    "road_tomare": (m_tomare, (512, 2048), WHITE, 101, {}),
    "road_speed_40_white": (m_speed("40"), (1024, 2048), WHITE, 102, {}),
    "road_speed_60_white": (m_speed("60"), (1024, 2048), WHITE, 103, {}),
    "road_speed_40_yellow": (m_speed("40"), (1024, 2048), YELLOW, 104, {}),
    "road_speed_60_yellow": (m_speed("60"), (1024, 2048), YELLOW, 105, {}),
    "road_arrow_straight": (m_arrow("straight"), (512, 2048), WHITE, 106, {}),
    "road_arrow_left": (m_arrow("left"), (1024, 2048), WHITE, 107, {}),
    "road_arrow_right": (m_arrow("right"), (1024, 2048), WHITE, 108, {}),
    "road_arrow_straight_left": (m_arrow("straight_left"), (1024, 2048), WHITE, 109, {}),
    "road_diamond_crosswalk_ahead": (m_diamond, (512, 2048), WHITE, 110, {}),
    "road_crosswalk_tile": (m_crosswalk, (1024, 2048), WHITE, 111, {"tile": True, "wear": 0.65}),
    "road_school_zone": (m_school, (1024, 2048), WHITE, 112, {}),
    "road_tsugakuro": (m_tsugakuro, (1024, 2048), WHITE, 113, {}),
    "road_jokou": (m_jokou, (512, 2048), WHITE, 114, {}),
    "road_stop_line": (m_stopline, (2048, 256), WHITE, 115, {"wear": 0.7}),
    "road_chevron_tile": (m_chevron, (1024, 1024), WHITE, 116, {"tile": True}),
    "road_chevron_tile_yellow": (m_chevron, (1024, 1024), YELLOW, 117, {"tile": True}),
    "road_hatch_tile": (m_hatch, (1024, 1024), WHITE, 118, {"tile": True}),
    "road_bicycle_lane": (m_bicycle, (1024, 2048), WHITE, 119, {}),
}


def render(name):
    fn, (w, h), col, seed, opts = ITEMS[name]
    c = Canvas(w, h, ss=SS)
    M, tracks = fn(c)
    road_paint(c, M, col, seed, tracks=tracks, wear=opts.get("wear", 0.5), tile=opts.get("tile", False),
               cracks=max(3, int(w * h / 2048 / 2048 * 14)))
    p = out_path("Decals", name + ".png")
    c.save(p)
    print("wrote", p)
    return p


TILES = {"road_crosswalk_tile", "road_chevron_tile", "road_chevron_tile_yellow", "road_hatch_tile"}


def check_margins(min_px=16):
    """Every non-tile decal must keep its alpha bbox >= min_px from each canvas edge."""
    from PIL import Image
    bad = []
    for n in ITEMS:
        if n in TILES:
            continue
        p = os.path.join(ART, "Decals", n + ".png")
        if not os.path.exists(p):
            continue
        a = np.asarray(Image.open(p))[..., 3]
        ys, xs = np.where(a > 2)
        h, w = a.shape
        m = (xs.min(), ys.min(), w - 1 - xs.max(), h - 1 - ys.max())
        ok = min(m) >= min_px
        print(f"margin {'OK ' if ok else 'BAD'} {n:32s} L{m[0]:4d} T{m[1]:4d} R{m[2]:4d} B{m[3]:4d}")
        if not ok:
            bad.append(n)
    return bad


def preview():
    paths = [os.path.join(ART, "Decals", n + ".png") for n in ITEMS]
    paths = [p for p in paths if os.path.exists(p)]

    def bg(w, h, i):
        return asphalt(w, h, seed=7 + i)
    return preview_on(paths, os.path.join(PREVIEWS, "road_decals.png"), bg, cell=(260, 380), cols=7,
                      title="ROAD MARKINGS  (on asphalt)")


if __name__ == "__main__":
    sel = sys.argv[1:]
    for n in ITEMS:
        if not sel or any(s in n for s in sel):
            render(n)
    bad = check_margins()
    preview()
    if bad:
        raise SystemExit(f"margin check failed: {bad}")
