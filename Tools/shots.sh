#!/usr/bin/env bash
# Run the macOS player headless-ish for verification.
#   Tools/shots.sh <scene> [times=4,8,12] [extra player args...]      -> Builds/shots/<scene>/*.png
#   Tools/shots.sh physics [cars]                                      -> Builds/shots/physics.txt
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/Builds/mac/INK DRIFT TOKYO.app/Contents/MacOS"
BIN="$APP/$(ls "$APP" | head -1)"
OUT="$ROOT/Builds/shots"; mkdir -p "$OUT"
scene=${1:?scene}; shift || true
if [[ $scene == physics ]]; then
  cars=${1:-hachi,kaiju,zenkai,raijin,tsubame}
  "$BIN" -screen-width 1280 -screen-height 720 -screen-fullscreen 0 -scene TestPad -physicsTest "$OUT/physics.txt" -car "$cars" -logFile "$OUT/physics.log" || true
  cat "$OUT/physics.txt"; exit 0
fi
times=${1:-4,8,12}; shift || true
mkdir -p "$OUT/$scene"; rm -f "$OUT/$scene"/*.png
"$BIN" -screen-width 1920 -screen-height 1080 -screen-fullscreen 0 -scene "$scene" -autopilot -shots "$OUT/$scene" -shotTimes "$times" -logFile "$OUT/$scene.log" "$@" || true
ls "$OUT/$scene"
