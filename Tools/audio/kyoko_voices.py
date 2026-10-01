"""Placeholder announcer lines with macOS 'Kyoko' (offline). Overwritten by elevenlabs_voices.py when a key is available."""
import re, subprocess, tempfile, os, pathlib, importlib.util
spec = importlib.util.spec_from_file_location("el", pathlib.Path(__file__).with_name("elevenlabs_voices.py"))
el = importlib.util.module_from_spec(spec); spec.loader.exec_module(el)
OUT = el.OUT; OUT.mkdir(parents=True, exist_ok=True)
for cid, variants in el.LINES.items():
    for n, text in enumerate(variants[:2]):
        t = re.sub(r"\[[^\]]+\]\s*", "", text)
        aiff = tempfile.mktemp(suffix=".aiff")
        subprocess.run(["say", "-v", "Kyoko", "-r", "235", "-o", aiff, t], check=True)
        # brighter + a touch higher, punchy compression, short slap reverb
        af = ("aresample=44100,asetrate=44100*1.10,aresample=44100,atempo=0.97,highpass=f=120,treble=g=4,"
              "acompressor=threshold=-20dB:ratio=5:attack=3:release=60:makeup=5,aecho=0.8:0.45:30|60:0.2|0.1,loudnorm=I=-12:TP=-1")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", aiff, "-af", af, "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(OUT / f"vo_{cid}_{n}.wav")], check=True)
        os.unlink(aiff)
print("ok", len(list(OUT.glob("*.ogg"))))
