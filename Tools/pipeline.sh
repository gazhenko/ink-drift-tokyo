#!/usr/bin/env bash
# Headless pipeline: setup -> content -> builds. Usage: Tools/pipeline.sh [setup|content|build|dev|all] [extra unity args]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNITY="${UNITY:-/Applications/Unity/Hub/Editor/6000.3.25f1/Unity.app/Contents/MacOS/Unity}"
PROJ="$ROOT/Game"; LOGS="$ROOT/Builds/logs"; mkdir -p "$LOGS"
run() { local name=$1; shift; echo "== $name"; "$UNITY" -batchmode -nographics -projectPath "$PROJ" -logFile "$LOGS/$name.log" "$@" || { echo "!! $name failed (see $LOGS/$name.log)"; grep -E "error CS|Exception|FAILED|\[Pipeline\]" "$LOGS/$name.log" | head -40; exit 1; }; grep -E "\[Pipeline\]|\[TrackGen|\[Build\]|\[Cars\]" "$LOGS/$name.log" || true; }
runG() { local name=$1; shift; echo "== $name"; "$UNITY" -batchmode -projectPath "$PROJ" -logFile "$LOGS/$name.log" "$@" || { echo "!! $name failed (see $LOGS/$name.log)"; grep -E "error CS|Exception|FAILED|\[Pipeline\]" "$LOGS/$name.log" | head -40; exit 1; }; grep -E "\[Pipeline\]|\[TrackGen|\[Build\]|\[Cars\]|\[Mountain\]" "$LOGS/$name.log" || true; }
step=${1:-all}; shift || true
case $step in
  setup)   run setup -quit -executeMethod InkDrift.EditorTools.ProjectSetup.Run "$@" ;;
  content) runG content -executeMethod InkDrift.EditorTools.Pipeline.Content "$@" ;;
  build)   runG build -executeMethod InkDrift.EditorTools.BuildScript.BuildAll "$@" ;;
  dev)     runG build_dev -executeMethod InkDrift.EditorTools.BuildScript.BuildMacDev "$@" ;;
  all)     "$0" setup && "$0" content && "$0" build ;;
esac
