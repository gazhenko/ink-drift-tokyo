#!/usr/bin/env bash
# Ad-hoc sign the macOS player built on Linux so Apple Silicon will run it, and strip quarantine.
set -euo pipefail
APP="${1:-$(cd "$(dirname "$0")/.." && pwd)/Builds/mac/INK DRIFT TOKYO.app}"
chmod +x "$APP/Contents/MacOS/"* || true
xattr -cr "$APP" || true
codesign --force --deep --sign - --timestamp=none "$APP"
codesign --verify --deep --strict "$APP" && echo "signed: $APP"
