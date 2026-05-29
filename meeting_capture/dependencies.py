"""Detect and report on Meeting Capture's runtime dependencies.

Three things have to be installed on the user's Mac for full functionality:

- **BlackHole** — virtual audio driver. Without it, only the user's
  microphone can be recorded; the other side of the call is silent.
- **ffmpeg** — used to mix mic + system streams and as Whisper's audio loader.
- **Ollama** (server + model) — generates the meeting summary locally.

This module exposes a small status API that the menu bar app polls on
launch and on demand so it can guide the user through fixing anything
that's missing, instead of failing with a cryptic traceback later.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class DependencyStatus:
    """One installable Meeting Capture dependency, plus how to fix it."""

    name: str
    installed: bool
    description: str
    install_command: str  # empty if installed; brew invocation otherwise


def _check_blackhole() -> DependencyStatus:
    # We avoid importing recorder here because it pulls in PortAudio at module
    # load time, which fails in test/CI environments. The menu bar wires its
    # own BlackHole check by calling find_blackhole_device when it has rumps.
    return DependencyStatus(
        name="BlackHole 2ch",
        installed=_blackhole_installed(),
        description="Virtual audio driver. Required to record the other side of a call.",
        install_command="brew install blackhole-2ch",
    )


def _blackhole_installed() -> bool:
    # Prefer the audio-device probe so this works whether the user installed
    # via brew or via the official BlackHole .pkg.
    try:
        from .recorder import find_blackhole_device

        return find_blackhole_device() is not None
    except Exception:  # noqa: BLE001
        # Fall back to checking Homebrew so we still give useful guidance even
        # when PortAudio is unavailable.
        result = subprocess.run(
            ["brew", "list", "blackhole-2ch"], capture_output=True, check=False
        )
        return result.returncode == 0


def _check_ffmpeg() -> DependencyStatus:
    return DependencyStatus(
        name="ffmpeg",
        installed=shutil.which("ffmpeg") is not None,
        description="Mixes mic + system audio. Required for dual-stream capture and Whisper audio loading.",
        install_command="brew install ffmpeg",
    )


def _check_ollama() -> DependencyStatus:
    if shutil.which("ollama") is None:
        return DependencyStatus(
            name="Ollama",
            installed=False,
            description="Local LLM server. Generates the meeting summary.",
            install_command="brew install ollama && brew services start ollama && ollama pull llama3.1:8b",
        )

    if not _ollama_server_reachable():
        return DependencyStatus(
            name="Ollama (server not running)",
            installed=False,
            description="Ollama is installed but the server isn't responding on localhost:11434.",
            install_command="brew services start ollama",
        )

    if not _ollama_model_pulled("llama3.1:8b"):
        return DependencyStatus(
            name="Ollama model llama3.1:8b",
            installed=False,
            description="Ollama is running but the summarization model hasn't been downloaded yet (~4.7 GB).",
            install_command="ollama pull llama3.1:8b",
        )

    return DependencyStatus(
        name="Ollama",
        installed=True,
        description="Local LLM server, running and ready.",
        install_command="",
    )


def _ollama_server_reachable() -> bool:
    try:
        import requests
    except ImportError:
        return False
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def _ollama_model_pulled(model: str) -> bool:
    try:
        import requests
    except ImportError:
        return False
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code != 200:
            return False
        models = response.json().get("models", [])
        names = {m.get("name", "") for m in models}
        return any(model in name for name in names)
    except Exception:  # noqa: BLE001
        return False


def check_all() -> list[DependencyStatus]:
    """Run every dependency check. Order matters — easier-to-install first."""
    return [
        _check_ffmpeg(),
        _check_blackhole(),
        _check_ollama(),
    ]


def missing_dependencies(statuses: list[DependencyStatus]) -> list[DependencyStatus]:
    return [s for s in statuses if not s.installed]


def combined_install_command(statuses: list[DependencyStatus]) -> str:
    """Join brew install commands for the missing deps into a single shell line."""
    commands = [s.install_command for s in missing_dependencies(statuses) if s.install_command]
    return " && ".join(commands)
