#!/usr/bin/env bash
# Package Builds/{mac,win,linux} + trailer and publish a GitHub release.
# Usage: Tools/release.sh v1.0.0 [--draft]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG=${1:?tag like v1.0.0}; shift || true
DRAFT=""; [[ "${1:-}" == "--draft" ]] && DRAFT="--draft"
OUT="$ROOT/Builds/release/$TAG"; rm -rf "$OUT"; mkdir -p "$OUT"
cd "$ROOT/Builds"
[ -d "mac/INK DRIFT TOKYO.app" ] && ditto -c -k --sequesterRsrc --keepParent "mac/INK DRIFT TOKYO.app" "$OUT/InkDriftTokyo-$TAG-macOS-universal.zip"
[ -d win ] && (cd win && zip -qr9 "$OUT/InkDriftTokyo-$TAG-Windows-x64.zip" . -x "*_BurstDebugInformation_DoNotShip/*" -x "*_BackUpThisFolder_ButDontShipItWithYourGame/*")
[ -d linux ] && (cd linux && tar --exclude="*_BurstDebugInformation_DoNotShip" --exclude="*_BackUpThisFolder_ButDontShipItWithYourGame" -czf "$OUT/InkDriftTokyo-$TAG-Linux-x64.tar.gz" .)
[ -f "$ROOT/Trailer/ink_drift_tokyo_trailer.mp4" ] && cp "$ROOT/Trailer/ink_drift_tokyo_trailer.mp4" "$OUT/INK-DRIFT-TOKYO-trailer.mp4"
(cd "$OUT" && shasum -a 256 * > SHA256SUMS.txt)
ls -lh "$OUT"
NOTES="$ROOT/Docs/RELEASE_NOTES.md"
gh release create "$TAG" $DRAFT --title "INK DRIFT: TOKYO $TAG" --notes-file "$NOTES" "$OUT"/*
