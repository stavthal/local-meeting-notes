# Architecture

## End-to-end flow

```text
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

## Modules

```
meeting_capture/
├── __init__.py
├── __main__.py            # python -m meeting_capture
├── cli.py                 # Click entrypoints
├── menubar.py             # rumps menu bar app
├── recorder.py            # audio capture + device probing/selection
├── transcriber.py         # MLX Whisper wrapper
├── summarizer.py          # Ollama wrapper
├── call_detection.py      # Quartz window enumeration
├── dependencies.py        # BlackHole / Ollama / ffmpeg detection
└── assets/                # tray icon, app icon source
```

## Recording: two streams, one mixed WAV

When the user picks "Mic + system audio", `recorder.record_audio_mixed` opens **two parallel** `sounddevice.InputStream`s:

- Stream A: the user's chosen mic (AirPods, built-in mic, headset, etc.)
- Stream B: BlackHole 2ch (carrying the call audio routed via the Multi-Output Device)

Each stream is written to a temporary WAV via its own thread + queue. When the user clicks Stop (or sends Ctrl+C in CLI mode), both streams stop and ffmpeg's `amix` filter combines them into the final single-channel 16 kHz WAV. The temp files are deleted.

This is simpler and more reliable than real-time mixing inside Python (no clock drift to manage; ffmpeg handles it offline).

## Device selection

`input_device_candidates()` walks every PortAudio input device and applies:

**Exclusion** (`EXCLUDED_DEVICE_PATTERNS`):

- iPhone / iPad / Apple Watch (Continuity devices)
- FaceTime HD Camera (built-in webcam mic)
- Generic webcams (Cam Sync, OBS Virtual Camera)

**Priority** (`_device_priority`), higher = preferred:

| Tier | Score | Match |
|------|-------|-------|
| Aggregate / "meeting capture" | 100 | combines mic + system audio |
| BlackHole | 90 | system audio loopback |
| Loopback / virtual | 80 | generic |
| Zoom / Teams virtual devices | 70 | meeting-app shims |
| AirPods / Beats / Bose / Sony / Jabra / Sennheiser | 60 | personal headsets |
| `headset` / `headphone` / `earbud` | 55 | generic personal mics |
| MacBook built-in mic | 30 | fallback |
| Everything else | 10 | last resort |

In interactive mode (`meet record` without `--device`), the recorder probes each candidate by recording a 1-second sample, computes RMS, and presents a picker with the highest-priority active device pre-selected. When nothing has signal yet (e.g. before the call starts), the highest-priority candidate is still the default — the picker doesn't block, with a warning.

## Call detection

`call_detection.detect_active_call()` calls Quartz's `CGWindowListCopyWindowInfo` (no special permission required) and matches each window against three signatures:

| App | Owner contains | Title contains |
|-----|----------------|----------------|
| Microsoft Teams | `teams` | `meeting`, `calling`, `call with`, or ` \| ` |
| Google Meet | one of: `chrome`, `arc`, `safari`, `edge`, `brave`, `vivaldi`, `firefox` | starts with `meet -` or contains `meet.google.com` + `meet -` |
| Zoom | `zoom` | `meeting`, `webinar` |

False positives are guarded explicitly — the Teams main window alone (`"Microsoft Teams"`), the Meet landing page (`"Google Meet"`), and an idle Zoom (`"Zoom"`) are all ignored.

The menu bar app polls every 5 seconds via `rumps.Timer` and updates the status row. Detection is **never** used to auto-start recording — consent stays with the user.

## Dependency detection

`dependencies.check_all()` runs three independent checks:

- **ffmpeg** — `shutil.which("ffmpeg")` on PATH.
- **BlackHole** — `find_blackhole_device()` against PortAudio, with `brew list blackhole-2ch` as a fallback when PortAudio isn't available.
- **Ollama** — three layers: (1) binary on PATH, (2) server reachable at `localhost:11434`, (3) `llama3.1:8b` model in the registry. Each failed layer surfaces its own targeted brew command.

The menu bar app calls this at end of `__init__` and on every Re-scan, showing a wizard alert with a single composite install command if anything is missing.

## Local-only

Once the Whisper model is cached on disk (first run downloads ~3 GB from HuggingFace) and Ollama has its model pulled (~4.7 GB), the entire pipeline runs offline:

- Recording: macOS Core Audio + sounddevice + soundfile, local I/O only.
- Mixing: ffmpeg, local process.
- Transcription: MLX Whisper, Apple Silicon Metal / Neural Engine.
- Summarization: Ollama on `127.0.0.1:11434`.

Nothing is uploaded. See [Privacy](privacy.md) for the full data-flow audit.

## Tests

```
tests/
├── test_recorder_device_selection.py    # device probing + exclusion + priority
├── test_call_detection.py               # window pattern matching
├── test_dependencies.py                 # ffmpeg / Ollama layered detection
├── test_menubar_lazy_import.py          # menu bar app constructs without rumps
├── test_cli_imports.py                  # CLI doesn't pull mlx_whisper into import path
├── test_transcriber_dependencies.py     # ffmpeg dep check fires before mlx import
└── test_setup_dependencies.py           # setup.sh still installs ffmpeg
```

Run them with:

```bash
python3 -m unittest discover -s tests
```

The audio-using tests need PortAudio installed locally and skip in CI Linux runners.
