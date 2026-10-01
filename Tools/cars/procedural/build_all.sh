#!/bin/sh
# Rebuild every procedural car (heroes + traffic), the overview contact sheet, and run the contract check.
#   sh Tools/cars/procedural/build_all.sh [car_id ...]
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
BLENDER="${BLENDER:-/opt/homebrew/bin/blender}"
CARS="${*:-hachi kaiju zenkai raijin tsubame traffic_kei traffic_taxi traffic_van traffic_truck}"
for c in $CARS; do
  "$BLENDER" -b -P "$HERE/build.py" -- "$c" 2>&1 | grep -E "^\[build|Error|Traceback" || true
done
cd "$HERE/previews"
"$REPO/Tools/.venv/bin/python" "$REPO/Tools/cars/cartex.py" sheet all_cars_sheet.jpg \
  hachi_front34.png toon_hachi_front34.png kaiju_front34.png toon_kaiju_front34.png \
  zenkai_front34.png toon_zenkai_front34.png raijin_front34.png toon_raijin_front34.png \
  tsubame_front34.png toon_tsubame_front34.png traffic_kei_front34.png traffic_taxi_front34.png \
  traffic_van_front34.png traffic_truck_front34.png
"$BLENDER" -b -P "$REPO/Tools/cars/verify_cars.py" 2>&1 | grep "\[verify\]"
