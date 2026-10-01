"""Shared atlas layout for INK DRIFT foliage textures.

Imported by both the texture generator (Tools/.venv python) and the Blender builders.
Each atlas lists named cells as pixel rects (x0, y0, x1, y1) in IMAGE space (y down),
plus the image size. `cell_uv()` converts to Blender UV space (v up).
"""

# (name) -> dict(size=(W, H), cells={cell_name: (x0, y0, x1, y1)})
ATLASES = {
    # hero-tree leaf atlases: 2x2 cells. round_a/round_b = puffy clusters (centre-pivot),
    # spray_a/spray_b = elongated twig sprays (pivot bottom-centre, twig grows "up" the cell)
    "Leaves_Sakura": dict(size=(2048, 2048)),
    "Leaves_Keyaki": dict(size=(2048, 2048)),
    "Leaves_Ginkgo": dict(size=(2048, 2048)),
    "Leaves_Momiji": dict(size=(2048, 2048)),
    "Leaves_Bamboo": dict(size=(2048, 2048)),
    # small atlases 1024, 2x2 cells
    "Leaves_Pine": dict(size=(1024, 1024)),
    "Leaves_Azalea": dict(size=(1024, 1024)),
    "Leaves_Boxwood": dict(size=(1024, 1024)),
    "Leaves_Bush": dict(size=(1024, 1024)),
    # sugi: two wide sprays stacked (each 1024x512), branch base at left edge centre
    "Leaves_Sugi": dict(size=(1024, 1024), cells={
        "spray_a": (0, 0, 1024, 512),
        "spray_b": (0, 512, 1024, 1024),
    }),
    # grass: 2x2 clumps, base at bottom edge
    "Grass": dict(size=(1024, 1024), cells={
        "clump_a": (0, 0, 512, 512),
        "clump_b": (512, 0, 1024, 512),
        "tall": (0, 512, 512, 1024),
        "flowers": (512, 512, 1024, 1024),
    }),
    # fern: two portrait fronds, base at bottom centre
    "Fern": dict(size=(1024, 1024), cells={
        "frond_a": (0, 0, 512, 1024),
        "frond_b": (512, 0, 1024, 1024),
    }),
    # tall autumn weeds: susuki (pampas) clump + plume, goldenrod weeds
    "Weeds": dict(size=(1024, 1024), cells={
        "susuki": (0, 0, 512, 1024),
        "weeds": (512, 0, 1024, 1024),
    }),
    # ground litter patches, 2:1
    "Litter": dict(size=(1024, 1024), cells={
        "autumn": (0, 0, 1024, 512),
        "petals": (0, 512, 1024, 1024),
    }),
}

_QUAD = {
    "round_a": (0, 0, 1, 1),
    "round_b": (1, 0, 2, 1),
    "spray_a": (0, 1, 1, 2),
    "spray_b": (1, 1, 2, 2),
}

for _name, _a in ATLASES.items():
    if "cells" not in _a:
        W, H = _a["size"]
        cw, ch = W // 2, H // 2
        _a["cells"] = {k: (c0 * cw, r0 * ch, c1 * cw, r1 * ch) for k, (c0, r0, c1, r1) in _QUAD.items()}


def cell_px(atlas, cell):
    return ATLASES[atlas]["cells"][cell]


def cell_uv(atlas, cell):
    """Return (u0, v0, u1, v1) in Blender UV space (v=0 at image bottom)."""
    W, H = ATLASES[atlas]["size"]
    x0, y0, x1, y1 = ATLASES[atlas]["cells"][cell]
    return (x0 / W, 1.0 - y1 / H, x1 / W, 1.0 - y0 / H)


def cells(atlas):
    return list(ATLASES[atlas]["cells"].keys())
