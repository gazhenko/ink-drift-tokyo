"""Download the OFL fonts used by INK DRIFT: TOKYO from github.com/google/fonts.
Re-runnable: skips files already present."""
import os, sys, requests
from urllib.parse import quote

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "Game", "Assets", "InkDrift", "Art", "Fonts")
BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl/"

FAMILIES = {
    "DelaGothicOne": ("delagothicone", ["DelaGothicOne-Regular.ttf"]),
    "RampartOne": ("rampartone", ["RampartOne-Regular.ttf"]),
    "ReggaeOne": ("reggaeone", ["ReggaeOne-Regular.ttf"]),
    "Bangers": ("bangers", ["Bangers-Regular.ttf"]),
    "ChakraPetch": ("chakrapetch", ["ChakraPetch-Bold.ttf", "ChakraPetch-Regular.ttf"]),
    "NotoSansJP": ("notosansjp", ["NotoSansJP[wght].ttf"]),
}

def get(url, dst):
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        print("skip", os.path.basename(dst)); return
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    with open(dst, "wb") as f:
        f.write(r.content)
    print("got", os.path.basename(dst), len(r.content))

def main():
    os.makedirs(OUT, exist_ok=True)
    for fam, (d, files) in FAMILIES.items():
        for fn in files:
            local = fn.replace("[wght]", "-VariableFont_wght")
            get(BASE + d + "/" + quote(fn), os.path.join(OUT, local))
        get(BASE + d + "/OFL.txt", os.path.join(OUT, f"OFL_{fam}.txt"))

if __name__ == "__main__":
    main()


def make_noto_statics():
    """Instance the Noto Sans JP variable font into static Black (900) and Bold (700) TTFs
    (Unity/TextMeshPro handles static instances more reliably than variable fonts)."""
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    src = os.path.join(OUT, "NotoSansJP-VariableFont_wght.ttf")
    for name, w in (("Black", 900), ("Bold", 700)):
        dst = os.path.join(OUT, f"NotoSansJP-{name}.ttf")
        if os.path.exists(dst):
            print("skip", os.path.basename(dst)); continue
        f = TTFont(src)
        inst = instancer.instantiateVariableFont(f, {"wght": w}, updateFontNames=True)
        inst.save(dst)
        print("made", os.path.basename(dst))


if __name__ == "__main__":
    make_noto_statics()
