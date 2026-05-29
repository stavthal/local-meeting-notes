#!/usr/bin/env bash
# End-to-end build: source → .app → .dmg.
# Run from the project root. macOS only.
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

# --- 0. Sanity ---------------------------------------------------------------
[[ "$(uname -s)" == "Darwin" ]] || fail "macOS only (uses iconutil, hdiutil)."

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

VERSION="$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])" 2>/dev/null \
    || python3 -c "import tomli; print(tomli.load(open('pyproject.toml','rb'))['project']['version'])")"
APP_NAME="Meeting Capture"
DMG_NAME="MeetingCapture-${VERSION}.dmg"

ASSETS="meeting_capture/assets"
SRC_ICON="${ASSETS}/app_icon_source.png"
ICONSET="${ASSETS}/AppIcon.iconset"
ICNS="${ASSETS}/AppIcon.icns"

# --- 1. Tooling --------------------------------------------------------------
command -v iconutil  >/dev/null || fail "iconutil not found (should ship with macOS)."
command -v sips      >/dev/null || fail "sips not found (should ship with macOS)."
command -v hdiutil   >/dev/null || fail "hdiutil not found (should ship with macOS)."

if ! command -v create-dmg >/dev/null; then
    say "Installing create-dmg via Homebrew"
    brew install create-dmg
fi

if ! python3 -c "import py2app" 2>/dev/null; then
    say "Installing py2app + build deps into the current Python"
    # py2app 0.28 calls dist.fetch_build_eggs(), removed in setuptools 81+.
    # Pin below 81 until py2app catches up.
    python3 -m pip install --upgrade py2app 'setuptools<81' wheel --break-system-packages
else
    # Even if py2app is already installed, the current setuptools may be too
    # new. Downgrade if needed so the build doesn't fail with
    # 'install_requires is no longer supported'.
    SETUPTOOLS_VER="$(python3 -c 'import setuptools; print(setuptools.__version__)' 2>/dev/null || echo "0")"
    SETUPTOOLS_MAJOR="${SETUPTOOLS_VER%%.*}"
    if [[ "$SETUPTOOLS_MAJOR" =~ ^[0-9]+$ ]] && [[ "$SETUPTOOLS_MAJOR" -ge 81 ]]; then
        say "Downgrading setuptools to <81 for py2app compatibility (was $SETUPTOOLS_VER)"
        python3 -m pip install --upgrade 'setuptools<81' --break-system-packages
    fi
fi

# --- 2. Build the .icns ------------------------------------------------------
[[ -f "$SRC_ICON" ]] || fail "Missing $SRC_ICON. Re-generate it (see scripts in repo)."

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

# --- 3. py2app build ---------------------------------------------------------
say "Cleaning previous build artifacts"
rm -rf build dist

say "Running py2app (this can take a few minutes)"
python3 setup_app.py py2app --no-strip

APP_PATH="dist/${APP_NAME}.app"
[[ -d "$APP_PATH" ]] || fail "py2app did not produce $APP_PATH. Check stderr above."
ok "Built $APP_PATH"

# --- 4. DMG ------------------------------------------------------------------
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

cat <<EOF

────────────────────────────────────────────────────────────────────
Done.

Distribute:  dist/$DMG_NAME

First-launch on a fresh Mac:
  • Double-click the DMG, drag Meeting Capture to Applications.
  • First open: right-click → Open → Open (Gatekeeper warns because
    we're not codesigned. Click Open once; macOS remembers it.)
  • macOS asks for Microphone permission → Allow.
  • The app needs BlackHole + Ollama + ffmpeg installed separately.
    Easiest: clone the repo and run ./setup.sh, or:
        brew install blackhole-2ch ollama ffmpeg
        brew services start ollama
        ollama pull llama3.1:8b

For real distribution (no Gatekeeper warning), you would need:
  • Apple Developer account
  • codesign with a Developer ID Application cert
  • notarytool submit + staple
────────────────────────────────────────────────────────────────────
EOF
