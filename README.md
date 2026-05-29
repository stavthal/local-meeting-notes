# Meeting Capture

Local, private, free meeting notes for macOS. Records your calls, transcribes them with Whisper, summarizes them with a local LLM. No cloud, no subscription, no data leaves your machine.

Built for Apple Silicon (M-series). Lives in your menu bar.

## What it does

- One click in the menu bar to start recording any meeting (Teams, Google Meet, Zoom, anything else).
- Captures **both sides** of the call — your mic plus the other party's audio via BlackHole — and mixes them with ffmpeg.
- Transcribes locally with MLX Whisper, taking full advantage of the Neural Engine.
- Summarizes locally with Ollama (Llama 3.1 8B by default), producing structured markdown: TL;DR, decisions, action items, open questions.
- Detects active Teams / Meet / Zoom calls and shows it in the status row so you don't forget to hit record.
- Smart device picker: filters out Continuity iPhones, webcam mics, and other irrelevant inputs. Prefers AirPods, headsets, Aggregate Devices.

## Why

Every meeting-notes tool is one of:
- A cloud SaaS that uploads your meetings to someone else's servers.
- A bot that joins your calls and needs explicit consent management.
- A paid Mac app.

This is none of those. Audio capture, transcription, and summarization all happen on your laptop. The only thing that ever touches the network is HuggingFace (for the one-time Whisper model download) and Ollama's local server on 127.0.0.1.

## Requirements

- macOS 13+
- Apple Silicon (M1 or newer) — MLX Whisper requires it
- ~8 GB free disk space for models
- Homebrew

## Quick start

```bash
git clone <this-repo>
cd meeting-capture
./setup.sh
```

That script installs BlackHole, Ollama, ffmpeg, and pipx via Homebrew, starts the Ollama service, pulls `llama3.1:8b`, downloads the Whisper model, and installs the `meet` CLI on your PATH. Idempotent — safe to re-run.

One manual step is still required: setting up your audio routing in **Audio MIDI Setup**. The script prints exact instructions at the end.

## Usage

### Menu bar app (recommended)

```bash
meet menubar
```

A microphone icon appears in your menu bar:

```
🎙
─────────────────────────
🟢 Ready — Google Meet call detected
─────────────────────────
● Start Recording
■ Stop Recording
Capture mode          ▸
   Mic only
 ✓ Mic + system audio (via BlackHole)
Mic device            ▸
   ✓ Auto-pick
   ...
─────────────────────────
Recent Summaries      ▸
Open last summary
Open recordings folder
─────────────────────────
How to use…
Detect active calls   ✓
─────────────────────────
Quit
```

Click **Start Recording** at the start of a meeting. Click **Stop Recording** at the end. You'll get a macOS notification when the summary is ready.

### CLI

```bash
meet --help                        # all commands
meet devices                       # list audio devices
meet record                        # arrow-key picker, record until Ctrl+C
meet record --include-system-audio # mix mic + BlackHole
meet record --device <N>           # skip the picker
meet all                           # record → transcribe → summarize
meet transcribe <file.wav>         # transcribe an existing recording
meet summarize <file.txt>          # summarize an existing transcript
```

## Build a DMG installer

```bash
./build_dmg.sh
```

That produces `dist/MeetingCapture-<version>.dmg` — a draggable installer that bundles Python + all Python dependencies into a real `.app`. Native dependencies (BlackHole, Ollama, ffmpeg) still need to be installed via `setup.sh` on the target Mac, because they're system-level.

The build is **not codesigned**. First-launch on a fresh Mac requires right-click → Open → Open to get past Gatekeeper. For proper distribution you'd need an Apple Developer account and notarization.

## Architecture

```
Teams / Meet / Zoom ─► macOS Output ─┬─► Speakers (you hear)
                                     └─► BlackHole ──┐
                                                     ├─► ffmpeg amix ─► WAV
Your mic ────────────────────────────────────────────┘                  │
                                                                        ▼
                                                              mlx-whisper (local)
                                                                        │
                                                                        ▼
                                                                  transcript.txt
                                                                        │
                                                                        ▼
                                                                Ollama + Llama 3.1
                                                                        │
                                                                        ▼
                                                                   summary.md
```

Two parallel `sounddevice` InputStreams write to temp WAVs. When you stop, ffmpeg's `amix` filter combines them into a single mono WAV at 16 kHz. That WAV goes through MLX Whisper for transcription, then the resulting timestamped text is piped to a local Ollama server for structured summarization.

### Stack

| Component | Library |
|-----------|---------|
| Audio routing | BlackHole 2ch (virtual audio driver) |
| Recording | `sounddevice` (PortAudio bindings) |
| Mixing | `ffmpeg` (amix filter) |
| Transcription | `mlx-whisper` — fastest Whisper on Apple Silicon |
| Summarization | Ollama running `llama3.1:8b` (configurable) |
| Menu bar | `rumps` (PyObjC AppKit wrapper) |
| Call detection | `pyobjc-framework-Quartz` (CGWindowListCopyWindowInfo) |
| CLI | `click` + `questionary` for the arrow-key picker |
| Bundling | `py2app` + `create-dmg` |

## Tuning

```bash
# faster, slightly less accurate transcription
meet transcribe foo.wav --model mlx-community/distil-whisper-large-v3

# better summaries (needs 32 GB+ RAM)
meet summarize foo.txt --model qwen2.5:14b

# tiny machine
meet transcribe foo.wav --model mlx-community/whisper-small-mlx
```

Recordings, transcripts, and summaries default to `~/Documents/meeting-capture/recordings/`. Override with the `MEET_DIR` environment variable.

## Roadmap

See [docs/audio-capture-roadmap.md](docs/audio-capture-roadmap.md) for the north-star direction (native macOS ScreenCaptureKit capture, killing BlackHole as a dependency).

Other open items:

- Speaker diarization (hybrid mlx-whisper + pyannote — preserves MLX speed)
- Codesigning + notarization for clean Gatekeeper UX
- Per-meeting-type summary templates (1:1 vs standup vs sales call)
- Auto-cleanup of old recordings

## Privacy

- All audio stays on disk in `~/Documents/meeting-capture/recordings/`. Nothing is uploaded.
- The first-run Whisper model download fetches from HuggingFace (~3 GB). After that, no network traffic.
- Ollama runs entirely on `localhost:11434`.
- Recording consent is your responsibility. The app provides the recording mechanism; you provide the legal/ethical justification.

## Contributing

Issues and PRs welcome. The code is structured around four small modules:

```
meeting_capture/
├── recorder.py        # audio capture + device selection
├── transcriber.py     # Whisper wrapper
├── summarizer.py      # Ollama wrapper
├── menubar.py         # rumps menu bar app
├── call_detection.py  # Quartz window enumeration
└── cli.py             # Click entrypoints
```

Tests live in `tests/`. Run them with:

```bash
python3 -m unittest discover -s tests
```

The audio-using tests need PortAudio installed and will be skipped in CI.

## License

MIT. See [LICENSE](LICENSE).
