# Meeting Capture

Local, private, free meeting notes for macOS. Record your calls, transcribe them with Whisper, summarize them with a local LLM. No cloud, no subscription, no data leaves your machine.

Built for Apple Silicon (M-series). Lives in your menu bar.

## What it does

- One click in the menu bar to start recording any meeting — Teams, Google Meet, Zoom, anything else that produces audio on your Mac.
- Captures **both sides** of the call by mixing your mic with the system audio routed through BlackHole.
- Transcribes locally with MLX Whisper, fully using the Neural Engine.
- Summarizes locally with Ollama (Llama 3.1 8B by default) into structured markdown — TL;DR, decisions, action items, open questions.
- Detects active Teams / Meet / Zoom calls and surfaces that in the status row so you don't forget to hit record.
- Smart device picker that filters out iPhone Continuity inputs, webcam mics, and other noise.

## Why

Every other meeting-notes tool is one of:

- A cloud SaaS that uploads your meetings to someone else's servers.
- A bot that joins your calls and needs explicit consent management.
- A paid Mac app.

This is none of those. Audio capture, transcription, and summarization all happen on your laptop. The only thing that touches the network is the one-time Whisper model download from HuggingFace and Ollama's local server on `127.0.0.1`.

## Get started

1. [Install](installation.md) — one script handles BlackHole, Ollama, ffmpeg, and the CLI.
2. [Set up audio routing](audio-routing.md) — a one-time GUI step in Audio MIDI Setup.
3. [Use it](usage.md) — menu bar app or CLI, your call.

## Requirements

- macOS 13 or newer
- Apple Silicon (M1 or newer) — MLX Whisper requires it
- ~8 GB free disk space (mostly the Whisper + LLM models)
- Homebrew

## Stack

| Component | Library |
|-----------|---------|
| Audio routing | BlackHole 2ch (virtual audio driver) |
| Recording | `sounddevice` (PortAudio bindings) |
| Mixing | `ffmpeg` |
| Transcription | `mlx-whisper` — fastest Whisper on Apple Silicon |
| Summarization | Ollama running `llama3.1:8b` (configurable) |
| Menu bar | `rumps` (PyObjC AppKit wrapper) |
| Call detection | `pyobjc-framework-Quartz` (CGWindowListCopyWindowInfo) |
| CLI | `click` + `questionary` |
| Bundling | PyInstaller + create-dmg |

## License

[MIT](https://github.com/stavthal/local-meeting-notes/blob/main/LICENSE).
