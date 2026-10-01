"""Contact sheets of all prop previews (each preview contains the 1.7 m reference capsule).
Run:  Tools/.venv/bin/python Tools/blender/props/contact_sheet.py
Writes previews/contact_sheet.png (everything) and previews/contact_sheet_<category>.png."""
import os, json, glob
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PV = os.path.join(HERE, 'previews')
META = os.path.join(PV, 'meta')
FONT = os.path.join(REPO, 'Game', 'Assets', 'InkDrift', 'Art', 'Fonts', 'NotoSansJP-Bold.ttf')
TILE = 360
COLS = 6
ORDER = ['urban', 'expressway', 'mountain']


def load():
    items = []
    for p in sorted(glob.glob(os.path.join(META, '*.json'))):
        m = json.load(open(p))
        img = os.path.join(PV, m['name'] + '.png')
        if os.path.exists(img):
            m['img'] = img
            items.append(m)
    return items


def sheet(items, title, out):
    f_title = ImageFont.truetype(FONT, 34)
    f_name = ImageFont.truetype(FONT, 17)
    f_info = ImageFont.truetype(FONT, 14)
    rows = (len(items) + COLS - 1) // COLS
    lab = 52
    W = COLS * TILE
    H = 70 + rows * (TILE + lab)
    im = Image.new('RGB', (W, H), (24, 24, 30))
    d = ImageDraw.Draw(im)
    d.text((16, 14), title, font=f_title, fill=(255, 248, 231))
    d.text((W - 640, 26), 'blue capsule = 1.7 m human reference   |   size = Unity X x Y x Z (m)', font=f_info,
           fill=(200, 200, 210))
    for i, m in enumerate(items):
        x = (i % COLS) * TILE
        y = 70 + (i // COLS) * (TILE + lab)
        t = Image.open(m['img']).convert('RGB')
        t.thumbnail((TILE - 8, TILE - 8), Image.LANCZOS)
        im.paste(t, (x + 4, y + 4))
        sx, sy, sz = m['size_m']
        d.text((x + 8, y + TILE), m['name'], font=f_name, fill=(255, 230, 0))
        d.text((x + 8, y + TILE + 24), f'{sx:.2f} x {sy:.2f} x {sz:.2f} m   {m["tris"]} tris', font=f_info,
               fill=(220, 220, 225))
    im.save(out, optimize=True)
    print('wrote', out, im.size, len(items), 'props')


def main():
    items = load()
    cats = {}
    for m in items:
        cats.setdefault(m['category'], []).append(m)
    allitems = []
    for c in ORDER + sorted(set(cats) - set(ORDER)):
        if c in cats:
            sheet(cats[c], f'INK DRIFT: TOKYO - props / {c} ({len(cats[c])})', os.path.join(PV, f'contact_sheet_{c}.png'))
            allitems += cats[c]
    sheet(allitems, f'INK DRIFT: TOKYO - street props ({len(allitems)})', os.path.join(PV, 'contact_sheet.png'))
    # combined manifest (sizes, material slots, empties, notes) for the Unity side
    man = {m['name']: {k: v for k, v in m.items() if k != 'img'} for m in allitems}
    with open(os.path.join(HERE, 'props_manifest.json'), 'w') as f:
        json.dump(man, f, indent=1, ensure_ascii=False)
    print('wrote props_manifest.json', len(man))


if __name__ == '__main__':
    main()
