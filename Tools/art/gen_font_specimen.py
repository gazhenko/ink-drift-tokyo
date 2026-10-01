"""Font specimen sheet -> Tools/art/previews/fonts.png (checks every downloaded font renders)."""
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inklib import FONT_FILES, PREVIEWS, pil_font  # noqa

SAMPLES = {
    "dela": "神ドリフト！！ INK DRIFT 0123",
    "rampart": "首都高C1 ファイナルラップ！",
    "reggae": "渋谷ネオン 焼肉 らーめん 墨",
    "bangers": "GOD DRIFT!! NEW RECORD! 0123456789",
    "chakra": "SPEED 287 KM/H  LAP 2/3  01:23.456",
    "chakra_reg": "TELEMETRY  RPM 7800  BOOST 1.2 BAR",
    "noto": "奥多摩峠 ヨルマート 24時間営業 薬",
    "noto_bold": "インクドリフト東京 不動産 歯科",
}


def main():
    W, row = 1800, 120
    im = Image.new("RGB", (W, row * len(SAMPLES) + 20), (255, 248, 231))
    d = ImageDraw.Draw(im)
    label = pil_font("chakra", 18)
    for i, (k, txt) in enumerate(SAMPLES.items()):
        y = 10 + i * row
        d.text((16, y + 4), f"{k}  ({FONT_FILES[k]})", fill=(27, 19, 64), font=label)
        d.text((16, y + 30), txt, fill=(11, 11, 18), font=pil_font(k, 64))
    out = os.path.join(PREVIEWS, "fonts.png")
    im.save(out)
    print(out)


if __name__ == "__main__":
    main()
