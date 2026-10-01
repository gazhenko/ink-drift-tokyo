#!/usr/bin/env bash
# Run the Unity pipeline on the licensed Linux build VM (kiki-unity) and sync results back.
#   Tools/remote.sh push | pull | setup | content [args] | build [args] | method <Class.Method> [args] | log <name>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${INK_HOST:-kiki-unity}"
RDIR="${INK_RDIR:-Projects/ink-drift-tokyo}"
RUNITY="${INK_RUNITY:-\$HOME/Unity/6000.3.20f1/Editor/Unity}"
EXCL=(--exclude Library/ --exclude Temp/ --exclude Logs/ --exclude UserSettings/ --exclude Obj/ --exclude Build/ --exclude '*.csproj' --exclude '*.sln' --exclude .DS_Store)

push() {
  ssh "$HOST" "mkdir -p $RDIR/Game $RDIR/Tools/tracks $RDIR/logs $RDIR/Builds"
  rsync -az "${EXCL[@]}" "$ROOT/Game/" "$HOST:$RDIR/Game/"
  rsync -az "$ROOT/Tools/tracks/" "$HOST:$RDIR/Tools/tracks/"
}
pull() {
  # Unity-authored files (meta, scenes, generated assets, settings) come back; code stays local-first.
  rsync -azu "${EXCL[@]}" --exclude 'InkDrift/Scripts/***' --exclude 'InkDrift/Shaders/***' --include '*/' --exclude 'InkDrift/Scripts/*.cs' \
        "$HOST:$RDIR/Game/Assets/" "$ROOT/Game/Assets/"
  # metas for code files are Unity-authored; bring them back only if missing locally
  rsync -azu --ignore-existing --include '*/' --include '*.meta' --exclude '*' "$HOST:$RDIR/Game/Assets/InkDrift/Scripts/" "$ROOT/Game/Assets/InkDrift/Scripts/"
  rsync -azu --ignore-existing --include '*/' --include '*.meta' --exclude '*' "$HOST:$RDIR/Game/Assets/InkDrift/Shaders/" "$ROOT/Game/Assets/InkDrift/Shaders/"
  rsync -azu "$HOST:$RDIR/Game/ProjectSettings/" "$ROOT/Game/ProjectSettings/"
  rsync -azu --exclude manifest.json "$HOST:$RDIR/Game/Packages/" "$ROOT/Game/Packages/"
}
run() {
  local name=$1; shift
  echo "== remote $name: $*"
  set +e
  ssh "$HOST" "cd $RDIR && $RUNITY -batchmode -nographics -projectPath \$HOME/$RDIR/Game -logFile \$HOME/$RDIR/logs/$name.log $* ; echo EXIT=\$?" | tail -1
  set -e
  ssh "$HOST" "grep -E 'error CS|Exception|\\[Pipeline\\]|\\[TrackGen|\\[Build\\]|\\[Cars\\]|\\[Mountain\\]|\\[Resources\\]|\\[PrefabBuilder\\]|\\[InkDrift\\]|Compilation failed|Scripts have compiler errors' $RDIR/logs/$name.log | grep -v 'UnityEngine.Debug' | head -60" || true
}
cmd=${1:-help}; shift || true
case $cmd in
  push) push ;;
  pull) pull ;;
  setup) push; run setup -quit -executeMethod InkDrift.EditorTools.ProjectSetup.Run "$@"; pull ;;
  content) push; run content -executeMethod InkDrift.EditorTools.Pipeline.Content "$@"; pull ;;
  build) push; run build -executeMethod InkDrift.EditorTools.BuildScript.BuildAll -out \$HOME/$RDIR/Builds "$@"
         mkdir -p "$ROOT/Builds"; rsync -az --delete --exclude shots/ --exclude logs/ --exclude release/ "$HOST:$RDIR/Builds/" "$ROOT/Builds/" ;;
  method) m=$1; shift; push; run "${m##*.}" -executeMethod "$m" "$@"; pull ;;
  log) ssh "$HOST" "tail -n ${2:-80} $RDIR/logs/$1.log" ;;
  *) echo "usage: $0 push|pull|setup|content|build|method|log" ;;
esac
