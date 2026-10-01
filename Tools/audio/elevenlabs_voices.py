"""
Generate the Japanese announcer callouts with ElevenLabs (key from ~/.inkdrift.env, never printed).

  Tools/.venv/bin/python Tools/audio/elevenlabs_voices.py [--list-voices] [--only nice,good] [--sfx] [--music]

Outputs Game/Assets/InkDrift/Audio/Voice/vo_<id>_<n>.ogg (2-3 variants per line, mixed voices).
"""
import argparse, json, os, re, subprocess, sys, time, pathlib, tempfile
import requests

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "Game/Assets/InkDrift/Audio/Voice"
SFX = ROOT / "Game/Assets/InkDrift/Audio/SFX"
MUSIC = ROOT / "Game/Assets/InkDrift/Audio/Music"
API = "https://api.elevenlabs.io/v1"

# id -> list of (text with v3 audio tags) variants. Short, shouted, anime-announcer energy.
LINES = {
    "nice":       ["[excited] ナイス！", "[cheerful] ナイスー！", "[excited] いいね！"],
    "good":       ["[excited] 成功！", "[shouts] せいこう！", "[excited] 成功だよ！"],
    "great":      ["[shouts] グレートドリフト！", "[excited] グレート！ドリフト！", "[shouts] すっごいドリフト！"],
    "awesome":    ["[shouts] すごい！", "[excited] すごーい！", "[shouts] すごいすごい！"],
    "insane":     ["[shouts] やばい！！", "[excited] やっばーい！", "[shouts] マジやばい！"],
    "perfect":    ["[shouts] 完璧！", "[excited] パーフェクト！", "[shouts] かんぺき！"],
    "god":        ["[shouts] 神ドリフト！！", "[shouts] かみドリフトー！！", "[excited] 神！神！神ドリフト！"],
    "fail":       ["[sighs] 失敗…", "[disappointed] あーあ、失敗…", "[sad] ざんねん…"],
    "best_lap":   ["[excited] 最高！", "[shouts] さいこう！ベストラップ！"],
    "new_record": ["[shouts] 新記録！", "[excited] しんきろく！"],
    "start":      ["[excited] スタート！"],
    "count_3":    ["[excited] さん！"],
    "count_2":    ["[excited] に！"],
    "count_1":    ["[excited] いち！"],
    "go":         ["[shouts] ゴー！！", "[shouts] いっけー！ゴー！"],
    "final_lap":  ["[excited] ファイナルラップ！", "[shouts] ラストラップ！"],
    "goal":       ["[shouts] ゴール！", "[excited] ゴーーール！"],
    "drift_king": ["[shouts] ドリフトキング！", "[excited] あなたがドリフトキング！"],
    "ikee":       ["[shouts] いけー！", "[shouts] いけいけー！"],
    "near_miss":  ["[excited] ニアミス！", "[gasps] あぶなーい！"],
    "overtake":   ["[excited] オーバーテイク！", "[shouts] 抜いた！"],
}


def key():
    env = pathlib.Path.home() / ".inkdrift.env"
    for line in env.read_text().splitlines():
        if line.strip().startswith("ELEVENLABS_API_KEY"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("ELEVENLABS_API_KEY missing in ~/.inkdrift.env")


def H(k, extra=None):
    h = {"xi-api-key": k}
    if extra: h.update(extra)
    return h


def pick_voices(k, want=3):
    """Prefer already-added Japanese female voices; otherwise add energetic ones from the shared library."""
    mine = requests.get(f"{API}/voices", headers=H(k), timeout=60).json().get("voices", [])
    chosen = []
    for v in mine:
        labels = {kk: str(vv).lower() for kk, vv in (v.get("labels") or {}).items()}
        if labels.get("gender") == "female" and ("japan" in json.dumps(labels) or "ja" == labels.get("language", "")):
            chosen.append((v["voice_id"], v["name"]))
    if len(chosen) >= want:
        return chosen[:want]
    r = requests.get(f"{API}/shared-voices", headers=H(k), params={"language": "ja", "gender": "female", "page_size": 60, "sort": "trending"}, timeout=60)
    r.raise_for_status()
    pool = r.json().get("voices", [])
    def score(v):
        text = (v.get("description") or "") + " " + (v.get("name") or "") + " " + json.dumps(v.get("descriptive", "")) + " " + (v.get("use_case") or "")
        t = text.lower()
        s = 0
        for w, pts in [("energetic", 3), ("anime", 3), ("excited", 2), ("young", 2), ("cheerful", 2), ("bright", 1), ("game", 2), ("character", 1), ("announcer", 2)]:
            if w in t: s += pts
        s += min(5, (v.get("cloned_by_count") or 0) / 2000)
        return s
    pool.sort(key=score, reverse=True)
    for v in pool:
        if len(chosen) >= want: break
        try:
            add = requests.post(f"{API}/voices/add/{v['public_owner_id']}/{v['voice_id']}", headers=H(k, {"Content-Type": "application/json"}),
                                json={"new_name": f"InkDrift {v.get('name', 'JP')}"[:60]}, timeout=60)
            if add.status_code < 300:
                chosen.append((add.json().get("voice_id", v["voice_id"]), v.get("name")))
            else:
                print("could not add voice:", add.status_code, add.text[:160])
        except Exception as e:
            print("add voice failed", e)
    return chosen


def tts(k, voice_id, text, model):
    body = {"text": text, "model_id": model}
    if model == "eleven_v3":
        body["voice_settings"] = {"stability": 0.0, "similarity_boost": 0.8}
    else:
        body["text"] = re.sub(r"\[[^\]]+\]\s*", "", text)
        body["voice_settings"] = {"stability": 0.25, "similarity_boost": 0.8, "style": 0.85, "use_speaker_boost": True}
    r = requests.post(f"{API}/text-to-speech/{voice_id}", headers=H(k, {"Content-Type": "application/json", "Accept": "audio/mpeg"}),
                      params={"output_format": "mp3_44100_128"}, json=body, timeout=120)
    if r.status_code >= 300:
        raise RuntimeError(f"TTS {r.status_code}: {r.text[:200]}")
    return r.content


def post(mp3_bytes, out_path):
    """Trim silence, punchy compression + short plate reverb, loudness-normalize, export OGG."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(mp3_bytes); src = f.name
    af = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,areverse,"
          "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,"
          "highpass=f=90,acompressor=threshold=-18dB:ratio=4:attack=5:release=80:makeup=4,"
          "aecho=0.8:0.5:35|70:0.18|0.10,loudnorm=I=-12:TP=-1:LRA=7")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", af, "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(out_path)], check=True)
    os.unlink(src)


def sfx(k):
    SFX.mkdir(parents=True, exist_ok=True)
    jobs = {
        "tire_squeal_loop_el": ("Car tires screeching loudly while drifting, continuous sustained tire squeal, no engine, seamless loop", 6),
        "crowd_cheer": ("Small street crowd cheering and whistling at a night car meet", 4),
        "turbo_flutter": ("Turbo blow off valve flutter stututu sound from a tuned car", 2),
        "impact_heavy": ("Heavy car crash into a metal guardrail, crunch and scrape", 2),
    }
    for name, (prompt, dur) in jobs.items():
        r = requests.post(f"{API}/sound-generation", headers=H(k, {"Content-Type": "application/json"}),
                          json={"text": prompt, "duration_seconds": dur, "prompt_influence": 0.6}, timeout=180)
        if r.status_code >= 300:
            print("sfx failed", name, r.status_code, r.text[:200]); continue
        p = SFX / f"{name}.mp3"
        p.write_bytes(r.content)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(p), "-ar", "44100", str(SFX / f"{name}.wav")], check=True)
        p.unlink()
        print("sfx", name)


def music(k):
    MUSIC.mkdir(parents=True, exist_ok=True)
    jobs = {
        "shibuya_el": ("High-energy eurobeat at 155 BPM for a night street drift race in neon Tokyo: driving octave bassline, supersaw chords, "
                       "punchy four-on-the-floor drums, catchy synth lead hook, instrumental, no vocals", 150000),
        "shuto_el": ("Fast eurobeat trance hybrid at 150 BPM, sunset expressway race, euphoric supersaw leads, rolling bass, instrumental, no vocals", 150000),
        "okutama_el": ("Aggressive eurobeat at 160 BPM with distorted rock guitar lead, mountain pass drifting, intense, instrumental, no vocals", 150000),
        "menu_el": ("Stylish neon city-pop synthwave groove at 118 BPM, Tokyo night garage vibe, funky bass, warm pads, instrumental", 90000),
        "trailer_el": ("Cinematic game trailer music, 75 seconds: ominous synth intro, building risers and drum roll, silence, then a massive eurobeat drop "
                       "at 150 BPM with supersaws, breakdown, final huge hit and ring out; instrumental, no vocals", 75000),
    }
    for name, (prompt, ms) in jobs.items():
        r = requests.post(f"{API}/music", headers=H(k, {"Content-Type": "application/json"}),
                          json={"prompt": prompt, "music_length_ms": ms}, timeout=600)
        if r.status_code >= 300:
            print("music failed", name, r.status_code, r.text[:300]); continue
        p = MUSIC / f"{name}.mp3"
        p.write_bytes(r.content)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(p), "-af", "loudnorm=I=-14:TP=-1", "-ar", "44100", "-c:a", "pcm_s16le", str(MUSIC / f"{name}.wav")], check=True)
        p.unlink()
        print("music", name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-voices", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--model", default="eleven_v3")
    ap.add_argument("--sfx", action="store_true")
    ap.add_argument("--music", action="store_true")
    a = ap.parse_args()
    k = key()
    if a.sfx: sfx(k)
    if a.music: music(k)
    if a.sfx or a.music: return
    voices = pick_voices(k)
    print("voices:", [n for _, n in voices])
    if a.list_voices or not voices: return
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(x for x in a.only.split(",") if x)
    for i, (cid, variants) in enumerate(LINES.items()):
        if only and cid not in only: continue
        for n, text in enumerate(variants):
            vid, vname = voices[(i + n) % len(voices)]
            out = OUT / f"vo_{cid}_{n}.wav"
            for attempt in range(3):
                try:
                    post(tts(k, vid, text, a.model), out)
                    print(f"{out.name}  <- {vname}")
                    break
                except Exception as e:
                    print("retry", cid, n, e); time.sleep(2 + attempt * 3)
                    if attempt == 1 and a.model == "eleven_v3": a.model = "eleven_multilingual_v2"


if __name__ == "__main__":
    main()
