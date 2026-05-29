# Installation

## Quick path

```bash
git clone https://github.com/stavthal/local-meeting-notes.git
cd local-meeting-notes
./setup.sh
```

That installs everything: BlackHole 2ch, Ollama, ffmpeg, pipx, the `meet` CLI on your PATH, the Whisper large-v3 model (~3 GB), and the Llama 3.1 8B summarization model (~4.7 GB). Idempotent — safe to re-run.

After it finishes there is still **one manual step** — setting up your audio routing in Audio MIDI Setup. See [Audio routing](audio-routing.md).

## What it installs

| Tool | Source | Purpose |
|------|--------|---------|
| BlackHole 2ch | `brew install blackhole-2ch` | Virtual audio driver. Routes system audio to a recordable input. |
| Ollama | `brew install ollama` | Local LLM server. Generates the meeting summary. |
| ffmpeg | `brew install ffmpeg` | Audio mixing + Whisper audio loading. |
| pipx | `brew install pipx` | Installs the `meet` CLI in its own isolated venv. |
| meeting-capture | `pipx install .` | The Python package that wires everything together. |
| `mlx-community/whisper-large-v3-mlx` | HuggingFace | Speech-to-text model. |
| `llama3.1:8b` | Ollama registry | Summarization LLM. |

## Manual install

If you'd rather install each piece yourself:

```bash
# 1. System tooling
brew install blackhole-2ch ollama ffmpeg pipx
brew services start ollama
ollama pull llama3.1:8b

# 2. Python CLI
git clone https://github.com/stavthal/local-meeting-notes.git
cd local-meeting-notes
pipx install .

# 3. Pre-download the Whisper model (otherwise first transcription will pull it)
meet setup
```

## DMG installer

If you'd rather distribute (or use) the app as a real macOS `.app` bundle:

```bash
./build/build_dmg.sh
```

That produces `dist/MeetingCapture-<version>.dmg`. Drag the app to Applications. Native dependencies (BlackHole, Ollama, ffmpeg) still need to be installed separately — the app surfaces a dependency wizard on first launch that copies the right brew command to your clipboard.

The build is not codesigned, so the first launch on a Mac that didn't build it requires right-click → Open → Open to dismiss Gatekeeper.

## Updating

```bash
cd ~/local-meeting-notes
git pull
pipx install --force .
```

## Uninstall

```bash
pipx uninstall meeting-capture
brew uninstall blackhole-2ch ollama ffmpeg   # optional, keeps the brew installs
rm -rf ~/Documents/meeting-capture/recordings/   # your recordings
```
