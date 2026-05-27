"""Audio recorder. Streams from a chosen input device to a 16 kHz mono WAV."""

from __future__ import annotations

import queue
import sys
from pathlib import Path

import sounddevice as sd
import soundfile as sf


def list_devices() -> None:
    """Print all audio devices. Look for your Aggregate Device in the input list."""
    print(sd.query_devices())
    default_in, default_out = sd.default.device
    print(f"\nDefault input:  {default_in}")
    print(f"Default output: {default_out}")
    print(
        "\nTip: pick the *index* of your Aggregate Device (mic + BlackHole) "
        "and pass it with --device."
    )


def record_audio(
    output_path: Path,
    device: int | None = None,
    samplerate: int = 16_000,
    channels: int = 1,
) -> None:
    """Record until Ctrl+C, writing PCM_16 WAV to ``output_path``."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    q: queue.Queue = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        q.put(indata.copy())

    dev_label = sd.query_devices(device)["name"] if device is not None else "default"
    print(f"Recording from '{dev_label}' → {output_path}")
    print("Press Ctrl+C to stop.\n")

    try:
        with sf.SoundFile(
            str(output_path),
            mode="x",
            samplerate=samplerate,
            channels=channels,
            subtype="PCM_16",
        ) as f:
            with sd.InputStream(
                samplerate=samplerate,
                device=device,
                channels=channels,
                callback=callback,
            ):
                while True:
                    f.write(q.get())
    except KeyboardInterrupt:
        print(f"\nStopped. Saved: {output_path}")
