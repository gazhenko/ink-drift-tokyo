#!/usr/bin/env bash
# Capture trailer footage from the macOS build (fixed-timestep frames + game audio per shot).
#   Tools/trailer/capture.sh [shibuya|shuto|okutama|menu|all]
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="$ROOT/Builds/mac/INK DRIFT TOKYO.app/Contents/MacOS/INK DRIFT TOKYO"
OUT="$ROOT/Trailer/capture"; mkdir -p "$OUT"
COMMON=(-screen-width 1920 -screen-height 1080 -screen-fullscreen 0 -w 1920 -h 1080 -fps 60)
cap() { local name=$1; shift; rm -rf "$OUT/$name"; mkdir -p "$OUT/$name"; echo "== $name"; "$BIN" "${COMMON[@]}" -trailer -capture "$OUT/$name" -logFile "$OUT/$name.log" "$@"; ls "$OUT/$name" | head -30; }
what=${1:-all}
if [[ $what == shibuya || $what == all ]]; then
  cap shibuya -scene Track_shibuya -car kaiju -paint 6 -wingmen 2 -startD 180 -warmup 9 -forceCallouts -calloutStart 0 \
    -shots "scenic:6,flyby:4,lowside:5,front:4,wheel:4,orbit_slow:5,chase:6,lowside_l:5,pack:5,heli:4,flyby_l:4"
fi
if [[ $what == shuto || $what == all ]]; then
  cap shuto -scene Track_shuto -car zenkai -paint 0 -wingmen 3 -startD 260 -warmup 9 -forceCallouts -calloutStart 3 \
    -shots "chase:6,lowside:5,front:4,pack:6,heli:5,flyby:4,orbit_slow:5,wheel:4,scenic:6,lowside_l:5"
fi
if [[ $what == okutama || $what == all ]]; then
  cap okutama -scene Track_okutama -car hachi -paint 2 -wingmen 2 -startD 200 -warmup 9 -forceCallouts -calloutStart 5 \
    -shots "scenic:6,lowside:5,flyby:4,front:4,orbit_slow:5,chase:6,heli:5,wheel:4,pack:5,lowside_l:5"
fi
if [[ $what == menu || $what == all ]]; then
  for c in 0 1 2 3 4; do
    rm -rf "$OUT/menu_$c"; mkdir -p "$OUT/menu_$c"
    "$BIN" "${COMMON[@]}" -scene MainMenu -menuScreen car -menuCar $c -record "$OUT/menu_$c" -recordSec 5 -recordDelay 2 -logFile "$OUT/menu_$c.log"
  done
  rm -rf "$OUT/title"; mkdir -p "$OUT/title"
  "$BIN" "${COMMON[@]}" -scene MainMenu -record "$OUT/title" -recordSec 6 -recordDelay 2 -logFile "$OUT/title.log"
fi
du -sh "$OUT"
