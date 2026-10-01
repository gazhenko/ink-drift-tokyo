"""
Assemble the trailer from in-engine captures (TrailerDirector) + title cards + music, driven by an EDL.

  Tools/.venv/bin/python Tools/trailer/edit.py --edl Tools/trailer/edl.json --out Trailer/ink_drift_tokyo_trailer.mp4

EDL (JSON list), times in seconds:
  {"type":"clip","src":"shibuya/shot_02_lowside","in":0.4,"dur":1.6,"speed":1.0,"flash":false,"game_audio":0.35}
  {"type":"card","png":"c1_tokyo","dur":1.4,"zoom":0.06,"over":"okutama/shot_05_scenic","over_in":0.0}
  {"type":"black","dur":0.5}
Top-level object form also allowed: {"fps":60,"music":"...","music_offset":0.0,"segments":[...]}
"""
import argparse, json, os, pathlib, shutil, subprocess, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
CAP = ROOT / "Trailer/capture"
CARDS = ROOT / "Tools/trailer/cards"
W, H = 1920, 1080


def ff(*args):
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *map(str, args)]
    subprocess.run(cmd, check=True)


def clip_segment(seg, fps, out):
    src = CAP / seg["src"]
    frames = sorted(src.glob("f_*.jpg"))
    if not frames:
        raise SystemExit(f"no frames in {src}")
    speed = float(seg.get("speed", 1.0))
    start = int(round(float(seg.get("in", 0.0)) * fps))
    need = int(round(float(seg["dur"]) * fps * speed))
    start = min(start, max(0, len(frames) - need))
    vf = [f"setpts=PTS/{speed}", f"scale={W}:{H}:flags=lanczos"]
    if seg.get("flash"):
        vf.append("fade=t=in:st=0:d=0.12:color=white")
    if seg.get("punch"):
        # quick zoom punch-in over the first 0.25 s
        vf.append(f"zoompan=z='if(lte(on,{int(0.25 * fps)}),1.12-0.12*on/{int(0.25 * fps)},1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={fps}")
    ff("-framerate", fps, "-start_number", start, "-i", src / "f_%05d.jpg", "-frames:v", need, "-vf", ",".join(vf),
       "-r", fps, "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", out)


def card_segment(seg, fps, out):
    png = CARDS / f"{seg['png']}.png"
    dur = float(seg["dur"])
    n = int(round(dur * fps))
    z = float(seg.get("zoom", 0.05))
    if seg.get("over"):
        # card over a (darkened) clip
        tmp = out.with_suffix(".bg.mp4")
        clip_segment({"src": seg["over"], "in": seg.get("over_in", 0.0), "dur": dur, "speed": seg.get("over_speed", 1.0)}, fps, tmp)
        ff("-i", tmp, "-loop", "1", "-i", png, "-filter_complex",
           f"[0:v]eq=brightness=-0.18:saturation=0.8[bg];[1:v]scale={W}:{H},zoompan=z='1+{z}*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={fps}[fg];[bg][fg]overlay=0:0:shortest=1,format=yuv420p",
           "-frames:v", n, "-r", fps, "-c:v", "libx264", "-preset", "slow", "-crf", "14", out)
        tmp.unlink()
    else:
        ff("-loop", "1", "-i", png, "-f", "lavfi", "-i", f"color=c=0x0B0B12:s={W}x{H}:r={fps}", "-filter_complex",
           f"[0:v]scale={W}:{H},zoompan=z='1+{z}*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={fps}[fg];[1:v][fg]overlay=0:0,format=yuv420p",
           "-frames:v", n, "-r", fps, "-c:v", "libx264", "-preset", "slow", "-crf", "14", out)


def black_segment(seg, fps, out):
    ff("-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={fps}", "-frames:v", int(round(float(seg["dur"]) * fps)),
       "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edl", default=str(ROOT / "Tools/trailer/edl.json"))
    ap.add_argument("--out", default=str(ROOT / "Trailer/ink_drift_tokyo_trailer.mp4"))
    ap.add_argument("--gif", default=str(ROOT / "Docs/media/teaser.gif"))
    a = ap.parse_args()
    edl = json.loads(pathlib.Path(a.edl).read_text())
    if isinstance(edl, list):
        edl = {"segments": edl}
    fps = int(edl.get("fps", 60))
    music = edl.get("music") or str(ROOT / "Game/Assets/InkDrift/Audio/Music/trailer.mp3")
    work = pathlib.Path(tempfile.mkdtemp(prefix="trailer_"))
    parts, t, audio_events = [], 0.0, []
    for i, seg in enumerate(edl["segments"]):
        out = work / f"seg_{i:03d}.mp4"
        kind = seg["type"]
        if kind == "clip":
            clip_segment(seg, fps, out)
            if seg.get("game_audio", 0) > 0:
                wav = CAP / seg["src"] / "audio.wav"
                if wav.exists():
                    audio_events.append((t, wav, float(seg.get("in", 0.0)), float(seg["dur"]) * float(seg.get("speed", 1.0)), float(seg["game_audio"]), float(seg.get("speed", 1.0))))
        elif kind == "card":
            card_segment(seg, fps, out)
        else:
            black_segment(seg, fps, out)
        parts.append(out)
        t += float(seg["dur"])
        print(f"[{i:02d}] {kind:5s} {seg.get('src', seg.get('png', ''))}  ends at {t:6.2f}s")
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    video = work / "video.mp4"
    ff("-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", video)

    # audio: music bed + game audio stingers (engine/tires/voice) placed at their segment times
    inputs = ["-i", music]
    filt = [f"[1:a]atrim=0:{t},afade=t=out:st={max(0, t - 2.5)}:d=2.5,volume=1.0[m]"]
    labels = ["[m]"]
    for k, (st, wav, tin, dur, gain, speed) in enumerate(audio_events):
        inputs += ["-i", wav]
        tempo = f",atempo={max(0.5, min(2.0, speed))}" if abs(speed - 1.0) > 1e-3 else ""
        filt.append(f"[{k + 2}:a]atrim={tin}:{tin + dur}{tempo},asetpts=PTS-STARTPTS,volume={gain},adelay={int(st * 1000)}|{int(st * 1000)}[g{k}]")
        labels.append(f"[g{k}]")
    filt.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,alimiter=limit=0.95[a]")
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    ff("-i", video, *inputs, "-filter_complex", ";".join(filt), "-map", "0:v", "-map", "[a]",
       "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", "-t", t, a.out)
    print("trailer:", a.out, f"{t:.1f}s")

    # GIF teaser for the README (first drop section if marked, else 24.5s..33s)
    gs = float(edl.get("gif_start", 24.5)); gd = float(edl.get("gif_dur", 8.0))
    pathlib.Path(a.gif).parent.mkdir(parents=True, exist_ok=True)
    pal = work / "pal.png"
    ff("-ss", gs, "-t", gd, "-i", a.out, "-vf", "fps=15,scale=640:-1:flags=lanczos,palettegen=max_colors=128:stats_mode=diff", pal)
    ff("-ss", gs, "-t", gd, "-i", a.out, "-i", pal, "-lavfi", "fps=15,scale=640:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle", a.gif)
    shutil.rmtree(work)
    print("gif:", a.gif)


if __name__ == "__main__":
    main()
