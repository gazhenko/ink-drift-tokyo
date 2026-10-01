"""Build Tools/trailer/edl.json from the captured shots, cut on the trailer music's bar grid (150 BPM, 1.6 s bars)."""
import glob, json, os, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
CAP = ROOT / "Trailer/capture"


def shot(track, rig, nth=0):
    ds = sorted(glob.glob(str(CAP / track / f"shot_*_{rig}")))
    if not ds:
        ds = sorted(glob.glob(str(CAP / track / "shot_*")))
    d = ds[min(nth, len(ds) - 1)]
    n = len(glob.glob(d + "/f_*.jpg"))
    return os.path.relpath(d, CAP), n / 60.0


def clip(track, rig, dur, nth=0, at=None, flash=False, punch=False, ga=0.0, speed=1.0):
    src, length = shot(track, rig, nth)
    callout_t = 0.35 * length
    # put the scheduled callout ~0.4 s into the clip (if it fits), otherwise use the requested in-point
    tin = at if at is not None else max(0.0, callout_t - 0.4)
    tin = min(tin, max(0.0, length - dur * speed - 0.05))
    return {"type": "clip", "src": src, "in": round(tin, 3), "dur": dur, "speed": speed, "flash": flash, "punch": punch, "game_audio": ga}


def card(png, dur, over=None, over_in=0.0, zoom=0.06):
    seg = {"type": "card", "png": png, "dur": dur, "zoom": zoom}
    if over:
        src, _ = shot(*over)
        seg.update(over=src, over_in=over_in)
    return seg


B, H = 1.6, 0.8
segs = [
    # ---- intro 0-8
    card("c1_tokyo", 3.2),
    clip("shibuya", "Scenic", B, at=2.5, flash=True),
    clip("shibuya", "Flyby", B, at=1.0, flash=True),
    clip("okutama", "Heli", B, at=0.6),
    # ---- build 8-24
    card("c2_never_sleeps", 3.2, over=("shuto", "Scenic"), over_in=1.0),
    clip("shibuya", "LowSide", B, ga=0.25),
    clip("shuto", "Front", B, ga=0.25),
    card("c3_neither", B),
    clip("okutama", "LowSide", B, ga=0.3),
    clip("shibuya", "Wheel", H, at=0.5),
    clip("shuto", "Chase", H, at=2.0),
    clip("okutama", "Front", H, at=0.6),
    clip("shibuya", "Orbit", H, at=1.0),
    clip("shuto", "LowSide", H, at=1.2),
    clip("okutama", "Wheel", H, at=1.0),
    clip("shibuya", "Front", H, at=1.6),
    clip("shuto", "Heli", H, at=1.0),
    {"type": "black", "dur": 0.5},
    # ---- drop 24.5-56.5 (20 bars)
    clip("shibuya", "LowSide", B, flash=True, punch=True, ga=0.55),
    clip("shibuya", "Chase", B, ga=0.5),
    clip("shuto", "Chase", B, at=0.8, ga=0.45),
    clip("okutama", "Flyby", B, ga=0.5),
    clip("shuto", "LowSide", B, nth=1, flash=True, ga=0.55),
    clip("okutama", "Chase", B, ga=0.5),
    clip("shibuya", "Heli", B, at=1.0, ga=0.3),
    card("c4_counts", B, over=("shuto", "Chase"), over_in=3.0, zoom=0.1),
    clip("okutama", "LowSide", B, nth=1, flash=True, punch=True, ga=0.55),
    clip("shuto", "Front", B, ga=0.5),
    clip("shibuya", "Flyby", B, nth=1, ga=0.45),
    clip("okutama", "Chase", B, at=3.5, ga=0.45),
    clip("shuto", "Wheel", B, flash=True, ga=0.5),
    clip("shibuya", "LowSide", B, nth=1, ga=0.55),
    clip("okutama", "Heli", B, at=1.5, ga=0.3),
    card("c5_drift", B, over=("okutama", "Chase"), over_in=3.5, zoom=0.1),
    clip("shuto", "Orbit", B, flash=True, punch=True, ga=0.55),
    clip("shibuya", "Front", B, ga=0.5),
    clip("okutama", "Wheel", B, ga=0.45),
    clip("shuto", "LowSide", B, nth=1, at=2.6, ga=0.45),
]
# ---- breakdown: the five machines on the turntable (56.5-62.9)
for i in range(5):
    d = CAP / f"menu_{i}"
    if d.exists():
        segs.append({"type": "clip", "src": f"menu_{i}", "in": 0.6, "dur": 1.28, "speed": 1.0, "flash": i == 0, "punch": False, "game_audio": 0.0})
    else:
        segs.append(clip("shibuya", "Orbit", 1.28, at=0.5 + i * 0.6))
# ---- breath + final card
if (CAP / "title").exists():
    segs.append({"type": "clip", "src": "title", "in": 1.0, "dur": 1.1, "speed": 1.0, "flash": False, "punch": False, "game_audio": 0.0})
else:
    segs.append({"type": "black", "dur": 1.1})
segs.append(card("c9_end", 11.0, zoom=0.04))

total = sum(s["dur"] for s in segs)
edl = {"fps": 60, "music": str(ROOT / "Game/Assets/InkDrift/Audio/Music/trailer.mp3"), "gif_start": 24.5, "gif_dur": 6.4, "segments": segs}
(ROOT / "Tools/trailer/edl.json").write_text(json.dumps(edl, indent=1))
print(f"{len(segs)} segments, total {total:.2f} s")
