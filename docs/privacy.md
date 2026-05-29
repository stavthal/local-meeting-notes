# Privacy

## Short version

- All audio stays on your disk in `~/Documents/meeting-capture/recordings/`.
- Transcripts and summaries stay there too.
- Nothing is uploaded.
- Ollama runs entirely on `localhost:11434`.
- The only network traffic is the one-time Whisper model download from HuggingFace (~3 GB). After that, fully offline.

## Data flow audit

Every step, and where the bytes go:

| Step | Where it runs | Network? |
|------|---------------|----------|
| Mic input | Core Audio → sounddevice (local) | No |
| System audio capture | BlackHole loopback → sounddevice (local) | No |
| Mixing | ffmpeg subprocess (local) | No |
| WAV write | filesystem (`~/Documents/meeting-capture/recordings/`) | No |
| Transcription | MLX Whisper (Metal / Neural Engine, local) | Only on first run: HuggingFace model download |
| Transcript write | filesystem (same folder as WAV) | No |
| Summarization | Ollama on `localhost:11434` | No (loopback only) |
| Summary write | filesystem (same folder) | No |
| Notifications | macOS UserNotifications (local) | No |
| Call detection | Quartz `CGWindowListCopyWindowInfo` — reads window titles only | No |

## What's stored on disk

Each recording produces three files in `~/Documents/meeting-capture/recordings/`:

```
20260527_143022.wav         # raw audio, 16 kHz mono PCM
20260527_143022.txt         # timestamped transcript
20260527_143022.summary.md  # structured markdown notes
```

You own these. The app never reads them after creating them. Delete whatever and whenever you want.

## Models cached locally

After first use, these live on disk:

| Model | Location | Size |
|-------|----------|------|
| Whisper large-v3 (MLX) | `~/.cache/huggingface/hub/` | ~3 GB |
| Llama 3.1 8B | `~/.ollama/models/` | ~4.7 GB |

Both are downloaded once and reused forever after. No usage metrics are sent anywhere.

## Call detection is read-only

The call detection feature enumerates on-screen window titles via Quartz to spot Teams / Meet / Zoom meeting windows. It reads **only the window title strings**, not their contents. The data never leaves the running process — it's checked against a fixed list of patterns and discarded.

You can turn detection off entirely via the menu bar's **Detect active calls** toggle.

## What about Ollama?

Ollama runs a local HTTP server on `localhost:11434`. Meeting Capture sends transcripts to that server (over loopback only — not over the network). Ollama itself doesn't phone home. You can verify with:

```bash
lsof -nP -i :11434
```

The only listener should be `ollama` bound to `127.0.0.1`.

## Consent

This is your responsibility. The app records when you tell it to record. Whether you're allowed to record the people on the other side of the call — under your local laws, your company policy, or simple courtesy — is between you and them. Meeting Capture does not handle consent collection.

## Reporting a privacy concern

If you find anything in the codebase that contradicts the above, [open an issue](https://github.com/stavthal/local-meeting-notes/issues/new) and I'll fix it.
