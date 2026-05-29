"""Meeting Capture CLI: record → transcribe → summarize, all local."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click

DEFAULT_WHISPER = "mlx-community/whisper-large-v3-mlx"
DEFAULT_LLM = "llama3.1:8b"


def _recordings_dir() -> Path:
    """Where recordings live. Override with MEET_DIR env var; defaults to ~/Documents/meeting-capture/recordings."""
    import os

    base = os.environ.get("MEET_DIR")
    if base:
        d = Path(base).expanduser()
    else:
        d = Path.home() / "Documents" / "meeting-capture" / "recordings"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _timestamped_wav() -> Path:
    return _recordings_dir() / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"


@click.group()
@click.version_option(package_name="meeting-capture")
def cli() -> None:
    """Record meetings, transcribe with Whisper, summarize with Ollama — all local."""


@cli.command()
def devices() -> None:
    """List audio devices."""
    from .recorder import list_devices

    list_devices()


@cli.command()
def menubar() -> None:
    """Launch the macOS menu bar app (rumps)."""
    from .menubar import run

    run()


@cli.command()
@click.option("--whisper-model", default=DEFAULT_WHISPER, show_default=True)
@click.option("--llm-model", default=DEFAULT_LLM, show_default=True)
def setup(whisper_model: str, llm_model: str) -> None:
    """Pre-download Whisper + Ollama models so the first real run is instant."""
    import shutil
    import subprocess

    # --- Whisper -------------------------------------------------------------
    click.echo(f"==> Downloading Whisper model: {whisper_model}")
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        raise SystemExit(
            "huggingface_hub not installed. Re-run the install: `pipx install --force .`"
        )
    path = snapshot_download(repo_id=whisper_model)
    click.echo(f"    Cached at: {path}")

    # --- Ollama --------------------------------------------------------------
    click.echo(f"\n==> Checking Ollama model: {llm_model}")
    if shutil.which("ollama") is None:
        click.echo("    ollama CLI not found on PATH. Install with: brew install ollama")
        raise SystemExit(1)

    # Is the model already pulled?
    listed = subprocess.run(
        ["ollama", "list"], capture_output=True, text=True, check=False
    )
    if llm_model.split(":")[0] in listed.stdout and llm_model in listed.stdout:
        click.echo("    Already pulled.")
    else:
        click.echo("    Pulling (this can take a few minutes)...")
        subprocess.run(["ollama", "pull", llm_model], check=True)

    # --- Reachability sanity check -------------------------------------------
    click.echo("\n==> Verifying Ollama server is reachable")
    try:
        import requests

        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        r.raise_for_status()
        click.echo("    OK — http://localhost:11434 is up.")
    except Exception as e:  # noqa: BLE001
        click.echo(f"    ⚠  Could not reach Ollama: {e}")
        click.echo("       Start it with: brew services start ollama")

    click.echo("\nAll set. Try: meet devices")


@cli.command()
@click.option(
    "--device",
    type=int,
    default=None,
    help="Skip the prompt with an input device index (see `devices`).",
)
@click.option("--output", type=click.Path(path_type=Path), default=None, help="Output WAV path.")
@click.option(
    "--include-system-audio/--mic-only",
    default=False,
    help="Mix mic + system audio (BlackHole). Default: mic only.",
)
def record(device: int | None, output: Path | None, include_system_audio: bool) -> None:
    """Record from a device until Ctrl+C."""
    from .recorder import DeviceSelectionError, record_audio, record_audio_mixed

    if output is None:
        output = _timestamped_wav()
    try:
        if include_system_audio:
            record_audio_mixed(output, mic_device=device)
        else:
            record_audio(output, device)
    except DeviceSelectionError as e:
        raise click.ClickException(str(e)) from e


@cli.command()
@click.argument("audio", type=click.Path(exists=True, path_type=Path))
@click.option("--model", default=DEFAULT_WHISPER, show_default=True, help="Whisper model.")
def transcribe(audio: Path, model: str) -> None:
    """Transcribe an audio file. Saves <audio>.txt."""
    from .transcriber import transcribe as do_transcribe

    txt = audio.with_suffix(".txt")
    do_transcribe(audio, txt, model=model)


@cli.command()
@click.argument("transcript", type=click.Path(exists=True, path_type=Path))
@click.option("--model", default=DEFAULT_LLM, show_default=True, help="Ollama model.")
def summarize(transcript: Path, model: str) -> None:
    """Summarize a transcript. Saves <transcript>.summary.md."""
    from .summarizer import summarize as do_summarize

    out = transcript.with_suffix(".summary.md")
    do_summarize(transcript, out, model=model)


@cli.command(name="all")
@click.option(
    "--device",
    type=int,
    default=None,
    help="Skip the prompt with an input device index.",
)
@click.option("--whisper-model", default=DEFAULT_WHISPER, show_default=True)
@click.option("--llm-model", default=DEFAULT_LLM, show_default=True)
@click.option(
    "--include-system-audio/--mic-only",
    default=False,
    help="Mix mic + system audio (BlackHole). Default: mic only.",
)
def do_all(
    device: int | None,
    whisper_model: str,
    llm_model: str,
    include_system_audio: bool,
) -> None:
    """Record → transcribe → summarize in one shot."""
    from .recorder import DeviceSelectionError, record_audio, record_audio_mixed
    from .summarizer import summarize as do_summarize
    from .transcriber import transcribe as do_transcribe

    audio = _timestamped_wav()
    try:
        if include_system_audio:
            record_audio_mixed(audio, mic_device=device)
        else:
            record_audio(audio, device)
    except DeviceSelectionError as e:
        raise click.ClickException(str(e)) from e

    txt = audio.with_suffix(".txt")
    do_transcribe(audio, txt, model=whisper_model)

    summary = audio.with_suffix(".summary.md")
    do_summarize(txt, summary, model=llm_model)

    click.echo("\nDone.")
    click.echo(f"  Audio:    {audio}")
    click.echo(f"  Text:     {txt}")
    click.echo(f"  Summary:  {summary}")


if __name__ == "__main__":
    cli()
