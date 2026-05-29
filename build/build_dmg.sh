#!/usr/bin/env bash
# End-to-end build: source → .app → .dmg.
# macOS only. Run from anywhere via ./build/build_dmg.sh.
#
# Uses pyinstaller (not py2app — py2app 0.28 is broken on modern setuptools).
# All build tooling lives in an isolated venv at build/.venv-build/.
#
# Outputs:
#   dist/Meeting Capture.app
#   dist/MeetingCapture-<version>.dmg

set -euo pipefail

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

say()  { printf "${YELLOW}==> %s${NC}\n" "$*"; }
ok()   { printf "${GREEN}    ✓ %s${NC}\n" "$*"; }
fail() { printf "${RED}    ✗ %s${NC}\n" "$*" >&2; exit 1; }

# --- 0. Sanity + locations ---------------------------------------------------
[[ "$(uname -s)" == "Darwin" ]] || fail "macOS only (uses iconutil, hdiutil)."

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # build/
ROOT="$(cd "$HERE/.." && pwd)"                          # project root
cd "$ROOT"

ASSETS="meeting_capture/assets"
SRC_ICON="${ASSETS}/app_icon_source.png"
ICONSET="${ASSETS}/AppIcon.iconset"
ICNS="${ASSETS}/AppIcon.icns"
SPEC="build/MeetingCapture.spec"

# --- 1. macOS native tooling -------------------------------------------------
command -v iconutil >/dev/null || fail "iconutil not found (ships with macOS)."
command -v sips     >/dev/null || fail "sips not found (ships with macOS)."
command -v hdiutil  >/dev/null || fail "hdiutil not found (ships with macOS)."

if ! command -v create-dmg >/dev/null; then
    say "Installing create-dmg via Homebrew"
    brew install create-dmg
fi

# --- 2. Pick the build Python ------------------------------------------------
# pyinstaller supports Python 3.8+; any reasonable Python works.
PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3.14 python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PYTHON="$cmd"
        break
    fi
done
[[ -n "$PYTHON" ]] || fail "No python3 on PATH."
PYVER="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
ok "Build Python: $PYTHON ($PYVER)"

# --- 3. Build venv -----------------------------------------------------------
VENV="$HERE/.venv-build"
VPY="$VENV/bin/python"
VPIP="$VENV/bin/pip"

if [[ ! -x "$VPY" ]]; then
    say "Creating isolated build venv at $VENV"
    "$PYTHON" -m venv "$VENV"
else
    ok "Reusing existing build venv at $VENV"
fi

say "Installing build dependencies into the venv (first run is slow — mlx-whisper etc.)"
"$VPIP" install --upgrade pip wheel setuptools --quiet
"$VPIP" install --upgrade pyinstaller pyinstaller-hooks-contrib --quiet
# Editable install of the package + its runtime deps so pyinstaller can find them.
"$VPIP" install -e . --quiet
ok "Venv ready"

# --- 4. Version --------------------------------------------------------------
VERSION="$("$VPY" -c "
import sys
try:
    import tomllib
except ImportError:
    import tomli as tomllib
print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])
")"
APP_NAME="Meeting Capture"
DMG_NAME="MeetingCapture-${VERSION}.dmg"

# --- 5. Icon -----------------------------------------------------------------
[[ -f "$SRC_ICON" ]] || fail "Missing $SRC_ICON."

say "Generating AppIcon.icns from $SRC_ICON"
rm -rf "$ICONSET" "$ICNS"
mkdir -p "$ICONSET"

for spec in \
    "16:icon_16x16.png" \
    "32:icon_16x16@2x.png" \
    "32:icon_32x32.png" \
    "64:icon_32x32@2x.png" \
    "128:icon_128x128.png" \
    "256:icon_128x128@2x.png" \
    "256:icon_256x256.png" \
    "512:icon_256x256@2x.png" \
    "512:icon_512x512.png" \
    "1024:icon_512x512@2x.png"
do
    SIZE="${spec%%:*}"
    NAME="${spec##*:}"
    sips -z "$SIZE" "$SIZE" "$SRC_ICON" --out "$ICONSET/$NAME" >/dev/null
done

iconutil -c icns "$ICONSET" -o "$ICNS"
rm -rf "$ICONSET"
ok "Wrote $ICNS"

# --- 6. pyinstaller build ----------------------------------------------------
say "Cleaning previous build artifacts"
rm -rf dist build_temp

say "Running pyinstaller (this takes a few minutes the first time)"
"$VPY" -m PyInstaller "$SPEC" \
    --noconfirm \
    --clean \
    --workpath build_temp \
    --distpath dist

APP_PATH="dist/${APP_NAME}.app"
[[ -d "$APP_PATH" ]] || fail "pyinstaller did not produce $APP_PATH. Check stderr above."
ok "Built $APP_PATH"

# --- 7. DMG ------------------------------------------------------------------
say "Packaging into $DMG_NAME"
rm -f "dist/$DMG_NAME"

create-dmg \
    --volname "$APP_NAME" \
    --volicon "$ICNS" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "${APP_NAME}.app" 175 190 \
    --hide-extension "${APP_NAME}.app" \
    --app-drop-link 425 190 \
    --no-internet-enable \
    "dist/$DMG_NAME" \
    "$APP_PATH"

ok "DMG ready: dist/$DMG_NAME"

# Clean up pyinstaller's temp build dir.
rm -rf build_temp

cat <<EOF

────────────────────────────────────────────────────────────────────
Done.

Distribute:  dist/$DMG_NAME

First-launch on a fresh Mac:
  • Double-click the DMG, drag Meeting Capture to Applications.
  • First open: right-click → Open → Open (Gatekeeper warns because
    the build is not codesigned).
  • macOS asks for Microphone permission → Allow.
  • The app needs BlackHole + Ollama + ffmpeg installed separately.
    Easiest: clone the repo and run ./setup.sh, or:
        brew install blackhole-2ch ollama ffmpeg
        brew services start ollama
        ollama pull llama3.1:8b

The build venv lives at build/.venv-build/ and is reused on subsequent
runs. Delete it to force a clean rebuild.
────────────────────────────────────────────────────────────────────
EOF
