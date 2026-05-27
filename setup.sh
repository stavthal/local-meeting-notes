#!/usr/bin/env bash
# One-shot installer for Meeting Capture.
# Safe to re-run — every step is idempotent.

set -euo pipefail

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

say()  { printf "${YELLOW}==> %s${NC}\n" "$*"; }
ok()   { printf "${GREEN}    ✓ %s${NC}\n" "$*"; }
fail() { printf "${RED}    ✗ %s${NC}\n" "$*" >&2; exit 1; }

# --- 0. Sanity ---------------------------------------------------------------
[[ "$(uname -s)" == "Darwin" ]] || fail "macOS only."
[[ "$(uname -m)" == "arm64"  ]] || fail "Apple Silicon required (mlx-whisper)."
command -v brew >/dev/null || fail "Homebrew not installed. See https://brew.sh"

# --- 1. Homebrew deps --------------------------------------------------------
say "Installing system dependencies via Homebrew"

if ! brew list blackhole-2ch >/dev/null 2>&1; then
    brew install blackhole-2ch
else
    ok "blackhole-2ch already installed"
fi

if ! brew list ollama >/dev/null 2>&1; then
    brew install ollama
else
    ok "ollama already installed"
fi

if ! brew list ffmpeg >/dev/null 2>&1; then
    brew install ffmpeg
else
    ok "ffmpeg already installed"
fi

if ! brew list pipx >/dev/null 2>&1; then
    brew install pipx
    pipx ensurepath
else
    ok "pipx already installed"
fi

# --- 2. Start Ollama service -------------------------------------------------
say "Starting Ollama service"
brew services start ollama >/dev/null || true
# Wait for the API to come up (max ~15s)
for _ in {1..15}; do
    if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
        ok "Ollama API is up"
        break
    fi
    sleep 1
done

# --- 3. Install the meet CLI -------------------------------------------------
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
say "Installing 'meet' via pipx from $HERE"
pipx install --force "$HERE"

# Find the meet binary — pipx default location on macOS is ~/.local/bin
MEET_BIN="$HOME/.local/bin/meet"
if [[ ! -x "$MEET_BIN" ]]; then
    MEET_BIN="$(command -v meet || true)"
fi
[[ -x "$MEET_BIN" ]] || fail "Could not locate the 'meet' binary after pipx install."
ok "Installed at: $MEET_BIN"

# --- 4. Pre-download models --------------------------------------------------
say "Pre-downloading Whisper + Ollama models (one-time, a few GB)"
"$MEET_BIN" setup

# --- 5. Audio-routing reminder ----------------------------------------------
cat <<'EOF'

────────────────────────────────────────────────────────────────────
ONE MANUAL STEP LEFT — audio routing
────────────────────────────────────────────────────────────────────
Open  Audio MIDI Setup  (⌘-Space → "Audio MIDI Setup")

  1. Create a Multi-Output Device:
        + → "Create Multi-Output Device"
        Check: your speakers/headphones + BlackHole 2ch
        (this lets you HEAR the meeting)

  2. Create an Aggregate Device:
        + → "Create Aggregate Device"
        Check: your mic + BlackHole 2ch
        (this is what you record FROM)

  In System Settings → Sound, set Output = Multi-Output Device
  while in a meeting.

Then:
  meet all                    # probe inputs, choose one, record → transcribe → summarize
  meet devices                # inspect inputs manually
  meet all --device <N>       # skip the prompt with an input index

If `meet` isn't on PATH yet, open a new terminal (pipx PATH update needs
a fresh shell) or run:  ~/.local/bin/meet --help
EOF
