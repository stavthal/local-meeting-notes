# Meeting Capture (Local, Apple Silicon)

Record mic + system audio, transcribe with **MLX Whisper**, summarize with **Ollama**. 100% local, free, installable as a proper command-line app.

## Install

```bash
cd ~/Documents/meeting-capture
./setup.sh
```

That script:

1. Installs `blackhole-2ch`, `ollama`, and `pipx` via Homebrew (idempotent).
2. Starts the Ollama service and pulls `llama3.1:8b`.
3. Installs this package with `pipx`, so the `meet` command lands on your PATH.

If `pipx` was newly installed, you may need to open a new terminal so the PATH update takes effect.

## One manual step: audio routing

Open **Audio MIDI Setup** (⌘-Space → "Audio MIDI Setup"):

**Multi-Output Device** (so you still HEAR the meeting):
- Click `+` → Create Multi-Output Device
- Check: your speakers/headphones **+** BlackHole 2ch

**Aggregate Device** (this is what you record FROM):
- Click `+` → Create Aggregate Device
- Check: your mic **+** BlackHole 2ch

In **System Settings → Sound**, set Output to **Multi-Output Device** while in a meeting.

## Use

```bash
meet --help                  # all commands
meet devices                 # find your Aggregate Device index
meet record --device <N>     # record until Ctrl+C
meet transcribe <file.wav>   # transcribe an existing recording
meet summarize <file.txt>    # summarize a transcript
meet all --device <N>        # do all three end-to-end
```

Recordings, transcripts, and summaries default to `~/Documents/meeting-capture/recordings/`. Override with the `MEET_DIR` env var.

## Stack

- **Audio routing:** BlackHole 2ch (virtual audio driver) + Aggregate Device
- **Recording:** `sounddevice` → 16 kHz mono WAV
- **Transcription:** `mlx-whisper` (uses the Neural Engine + GPU on M-series)
- **Summarization:** Ollama running `llama3.1:8b`
- **CLI:** Python + Click, packaged via `hatchling`, installed via `pipx`

## Tuning

```bash
# faster, slightly less accurate transcription
meet transcribe foo.wav --model mlx-community/distil-whisper-large-v3

# better summaries (needs 32 GB+ RAM)
meet summarize foo.txt --model qwen2.5:14b

# tiny machine
meet transcribe foo.wav --model mlx-community/whisper-small-mlx
```

## Update

```bash
cd ~/Documents/meeting-capture
pipx install --force .
```

## Uninstall

```bash
pipx uninstall meeting-capture
brew uninstall blackhole-2ch ollama   # optional
```

## Notes

- First Whisper run downloads the model (~3 GB for large-v3) into `~/.cache/huggingface`. Cached afterward.
- Consent capture is your responsibility. Confirm before each recording.
- Speaker diarization ("who said what") is deliberately not in v1 — adds ~50% runtime and a heavy dep tree (pyannote). Swap `transcriber.py` for WhisperX later if you want it.
