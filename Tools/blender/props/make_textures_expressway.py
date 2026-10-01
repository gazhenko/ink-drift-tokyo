"""Procedural decal textures for the expressway / roadside-device props.
Run:  Tools/.venv/bin/python Tools/blender/props/make_textures_expressway.py
Writes prop_*_albedo.png into Game/Assets/InkDrift/Models/Props/Textures/ (original artwork, OFL fonts)."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from make_textures import font, save, text_center, grime


def chevron_single():
    """Yellow chevron curve-alignment panel (0.45 x 0.6 m) -> 256x512, black chevron pointing right."""
    W, H = 512, 1024
    im = Image.new('RGB', (W, H), (246, 196, 0))
    d = ImageDraw.Draw(im)
    # black border
    d.rectangle((0, 0, W - 1, H - 1), outline=(18, 18, 20), width=26)
    # chevron '>' : two slanted bars
    cx, cy = W / 2, H / 2
    t = 120      # stroke thickness (horizontal)
    hw = 150     # half width of chevron
    hh = 330     # half height
    pts = [(cx - hw, cy - hh), (cx - hw + t, cy - hh), (cx + hw + t / 2, cy), (cx - hw + t, cy + hh),
           (cx - hw, cy + hh), (cx + hw - t / 2, cy)]
    d.polygon(pts, fill=(18, 18, 20))
    im = im.filter(ImageFilter.GaussianBlur(0.7)).resize((256, 512), Image.LANCZOS)
    save(grime(im, 6, 11), 'prop_chevron_albedo.png')


def chevron_wide():
    """Wide chevron board (1.2 x 0.45 m) with three chevrons -> 1024x512 (stretched on the board)."""
    W, H = 2048, 768
    im = Image.new('RGB', (W, H), (246, 196, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W - 1, H - 1), outline=(18, 18, 20), width=30)
    t = 150; hw = 170; hh = 270
    for k in range(3):
        cx = W * (k + 0.5) / 3 - 20; cy = H / 2
        pts = [(cx - hw, cy - hh), (cx - hw + t, cy - hh), (cx + hw + t / 2, cy), (cx - hw + t, cy + hh),
               (cx - hw, cy + hh), (cx + hw - t / 2, cy)]
        d.polygon(pts, fill=(18, 18, 20))
    im = im.filter(ImageFilter.GaussianBlur(0.7)).resize((1024, 512), Image.LANCZOS)
    save(grime(im, 6, 12), 'prop_chevron_wide_albedo.png')


def emergency_phone():
    """Emergency telephone sign plate (0.6 x 0.3 m): white 非常電話 + SOS on expressway green, 512x256."""
    W, H = 1024, 512
    green = (0, 112, 72)
    im = Image.new('RGB', (W, H), green)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((16, 16, W - 16, H - 16), radius=36, outline=(255, 255, 255), width=12)
    # handset pictogram (tilted classic receiver) in a white rounded square
    d.rounded_rectangle((60, 96, 340, 376), radius=40, fill=(255, 255, 255))
    ic = Image.new('RGBA', (280, 280), (0, 0, 0, 0))
    di = ImageDraw.Draw(ic)
    di.arc((40, 40, 240, 240), 200, 340, fill=green, width=44)          # handle
    di.rounded_rectangle((22, 112, 92, 172), radius=18, fill=green)      # ear piece
    di.rounded_rectangle((188, 112, 258, 172), radius=18, fill=green)    # mouth piece
    di.rectangle((60, 100, 80, 120), fill=green)
    di.rectangle((200, 100, 220, 120), fill=green)
    ic = ic.rotate(-35, resample=Image.BICUBIC, center=(140, 140))
    im.paste(ic, (60, 110), ic)
    text_center(d, (680, 210), '非常電話', font(size=150), (255, 255, 255))
    text_center(d, (680, 380), 'SOS  EMERGENCY TEL', font('NotoSansJP-Bold.ttf', 58), (255, 255, 255))
    im = im.resize((512, 256), Image.LANCZOS)
    save(im, 'prop_emergency_phone_albedo.png')


if __name__ == '__main__':
    chevron_single()
    chevron_wide()
    emergency_phone()
