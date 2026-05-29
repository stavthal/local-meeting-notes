# Usage

## Menu bar app (recommended)

```bash
meet menubar
```

The app detaches into the background and returns your terminal immediately. Logs go to `~/Library/Logs/MeetingCapture/menubar.log`. A microphone icon appears in your menu bar. Click it to see the menu:

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
   ✓ Auto-pick (probe and choose best)
   ────
   3 — MacBook Pro Microphone
   5 — Stavros's AirPods
   7 — Microsoft Teams Audio
─────────────────────────
Recent Summaries      ▸
Open last summary
Open recordings folder
─────────────────────────
How to use…
Install missing dependencies…
Re-scan devices
✓ Detect active calls
─────────────────────────
Quit
```

Quit the app from its menu bar icon when you're done. If you want to debug a crash, run in the foreground instead:

```bash
meet menubar --foreground
```

### Per-meeting flow

1. Pick a **Capture mode**:
    - **Mic only** — records just your microphone.
    - **Mic + system audio (via BlackHole)** — records you AND the other side. The default if BlackHole is installed.
2. Pick a **Mic device** (or leave it on Auto-pick).
3. Click **Start Recording**. The icon turns into `● 12:34` showing live elapsed time.
4. When the meeting ends, click **Stop Recording**.
5. Wait for the summary. The icon shows `⏳` while transcribing and summarizing. You'll get a macOS notification when it's done.
6. Click **Open last summary** to read it.

### Call detection

If "Detect active calls" is on (default), the status row will surface when Teams / Google Meet / Zoom has an active meeting window — e.g. "🟢 Ready — Google Meet call detected". It's a hint, never auto-start. You still click Start Recording yourself.

### Dependency wizard

If anything Meeting Capture needs is missing, you'll see an alert on launch with a single composite brew command to fix everything. Click **Copy install command**, paste in Terminal, hit Enter. You can re-open this wizard anytime via **Install missing dependencies…**.

## CLI

```bash
meet --help                        # all commands
meet devices                       # raw device list
meet record                        # arrow-key picker, record until Ctrl+C
meet record --include-system-audio # mix mic + BlackHole
meet record --device <N>           # skip the picker
meet all                           # record → transcribe → summarize
meet all --include-system-audio    # same, with dual-stream
meet transcribe <file.wav>         # transcribe an existing recording
meet summarize <file.txt>          # summarize a transcript
meet setup                         # pre-download Whisper + Ollama models
```

## Tuning

```bash
# faster, slightly less accurate transcription
meet transcribe foo.wav --model mlx-community/distil-whisper-large-v3

# better summaries (needs 32 GB+ RAM)
meet summarize foo.txt --model qwen2.5:14b

# tiny machine
meet transcribe foo.wav --model mlx-community/whisper-small-mlx
```

## Where files end up

Recordings, transcripts, and summaries default to:

```
~/Documents/meeting-capture/recordings/
├── 20260527_143022.wav        # raw audio
├── 20260527_143022.txt        # timestamped transcript
└── 20260527_143022.summary.md # structured notes
```

Override the location with the `MEET_DIR` environment variable:

```bash
MEET_DIR=~/Notes/Meetings meet menubar
```
