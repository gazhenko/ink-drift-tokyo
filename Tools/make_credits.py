"""Aggregate Docs/credits/*.md into CREDITS.md."""
import pathlib
root = pathlib.Path(__file__).resolve().parents[1]
order = ["cars", "textures", "art", "props", "foliage", "audio"]
parts = ["# Credits\n", "INK DRIFT: TOKYO uses only CC0, CC-BY and SIL OFL third-party assets. Everything not listed here is original work made for this project (procedural/Blender/Python/C#).\n",
         "All car models are de-badged, modified look-alikes; no manufacturer names, logos or trademarks are used in the game.\n"]
files = sorted((root / "Docs/credits").glob("*.md"), key=lambda p: order.index(p.stem) if p.stem in order else 99)
for f in files:
    txt = f.read_text().strip()
    lines = txt.splitlines()
    if lines and lines[0].startswith("# "): lines[0] = "## " + lines[0][2:]
    else: lines.insert(0, f"## {f.stem.title()}")
    parts.append("\n".join(("#" + l) if l.startswith("## ") and i > 0 else l for i, l in enumerate(lines)))
(root / "CREDITS.md").write_text("\n\n".join(parts) + "\n")
print("CREDITS.md:", sum(len(p) for p in parts), "chars from", [f.stem for f in files])
