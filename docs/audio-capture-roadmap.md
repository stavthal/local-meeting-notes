# Audio Capture Roadmap

This project should move toward "just record the meeting" while keeping the current CLI small and local-first.

## Current Path: Probe and Prompt

Status: implemented as the near-term default.

When no `--device` is provided, `meet record` probes visible input devices for a short audio sample. It prints the measured signal levels, marks the recommended device, and prompts the user to choose the input.

The recommendation prioritizes names that are likely to represent call audio capture:

- Aggregate devices, especially a user-created meeting capture device.
- BlackHole devices.
- Loopback or virtual devices.
- Generic microphones only when no preferred call-capture device is active.

For selected devices with multiple input channels, recording opens all input channels and downmixes them to the mono WAV written for transcription. This matters for Aggregate Devices because mic and BlackHole channels can be exposed separately.

Manual override remains available:

```bash
meet record --device <N>
meet all --device <N>
```

Limitations:

- This is signal detection, not call detection. It can tell that an input has audio, but it cannot prove the signal is Zoom, Google Meet, Teams, Slack, or another meeting app.
- It depends on PortAudio seeing the device. In sandboxed/headless shells, no devices may be visible.
- It still depends on BlackHole/Aggregate Device routing for combined mic + system audio.
- It cannot automatically know whether macOS Sound output is routed to the Multi-Output Device.

## Roadmap Option 2: Native macOS Capture Helper

Status: future candidate.

Add a small native macOS helper binary, likely Swift, dedicated to capturing system/app audio through Apple APIs. The Python CLI would launch this helper, receive a WAV/PCM stream or file, then keep using the existing Whisper and Ollama pipeline.

Potential API directions:

- ScreenCaptureKit with audio capture enabled for screen/window/app streams.
- Core Audio process taps on supported macOS versions for process-level system audio capture.

Expected advantages:

- Less dependency on user-created BlackHole/Aggregate devices.
- Better path toward capturing a specific meeting app or browser tab.
- More app-like first-run setup with explicit macOS permission prompts.

Expected costs:

- Requires native macOS code and signing/notarization considerations if distributed broadly.
- Requires permission handling for microphone, screen/system audio capture, and possibly screen recording.
- Requires version-aware behavior because macOS audio capture APIs differ across releases.
- Adds a second runtime artifact alongside the Python package.

Open design questions:

- Should the helper stream PCM to Python over stdout, write a temp WAV, or expose a local socket?
- Should the helper capture only system audio, only a selected app, or system audio plus microphone?
- What is the minimum supported macOS version?
- How should failures fall back to the current BlackHole/Aggregate Device path?

Reference starting points:

- ScreenCaptureKit: `SCStreamConfiguration.capturesAudio`
- Core Audio: process taps / system audio capture

## Roadmap Option 3: Product-Grade Capture UX

Status: long-term direction.

Build a hybrid capture layer that behaves more like commercial meeting recorders:

- First-run setup checks permissions and explains missing capabilities.
- `meet record` detects active call contexts such as Zoom, Teams, Slack, Chrome, Arc, or Safari.
- Native capture records system/app audio.
- Microphone capture runs separately.
- The recorder mixes both sources into a single 16 kHz mono WAV for Whisper.
- The current probe-and-prompt PortAudio/BlackHole path remains as a fallback.

Expected user experience:

```bash
meet record
```

The command should choose the best available capture route, print what it is using, and start recording without requiring a device index.

Expected architecture:

- Python CLI remains the orchestration layer.
- A capture strategy selector chooses between native helper and PortAudio fallback.
- Each strategy exposes the same output contract: a WAV file suitable for transcription.
- Transcription and summarization stay unchanged.

Suggested milestones:

1. Keep improving PortAudio probing, prompting, and diagnostics.
2. Prototype a native helper that captures system audio to a WAV file.
3. Add microphone + system audio mixing in the native path.
4. Add call-app/process targeting.
5. Add first-run permission checks and clear fallback messages.

This should stay alive as the north-star direction, but the current implementation should remain useful without waiting for native capture work.
