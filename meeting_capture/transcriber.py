"""Transcribe a WAV with MLX Whisper. Writes a timestamped .txt next to it."""

from __future__ import annotations

from pathlib import Path

import mlx_whisper


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def transcribe(
    audio_path: Path,
    output_path: Path,
    model: str = "mlx-community/whisper-large-v3-mlx",
) -> Path:
    """Run Whisper and write a timestamped transcript. Returns the output path."""
    audio_path = Path(audio_path)
    output_path = Path(output_path)

    print(f"Transcribing {audio_path.name} with {model}...")
    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=model,
        verbose=False,
    )

    lines = []
    for seg in result["segments"]:
        start = _fmt_time(seg["start"])
        end = _fmt_time(seg["end"])
        text = seg["text"].strip()
        lines.append(f"[{start} --> {end}] {text}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved transcript: {output_path}")
    return output_path
