"""Detect and report on Meeting Capture's runtime dependencies.

Three things have to be installed on the user's Mac for full functionality:

- **BlackHole** — virtual audio driver. Without it, only the user's
  microphone can be recorded; the other side of the call is silent.
- **ffmpeg** — used to mix mic + system streams and as Whisper's audio loader.
- **Ollama** (server + model) — generates the meeting summary locally.

This module exposes a small status API that the menu bar app polls on
launch and on demand so it can guide the user through fixing anything
that's missing, instead of failing with a cryptic traceback later.

Binary lookup is robust to PATH: even if ``shutil.which`` comes back
empty (some launch contexts strip Homebrew's bin dirs from PATH), we
also probe known Homebrew install locations directly.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Known Homebrew binary locations.  Apple Silicon ships under /opt/homebrew,
# Intel Macs under /usr/local.  Both are checked as a fallback when the
# binary isn't on the inherited PATH.
HOMEBREW_BIN_DIRS = ("/opt/homebrew/bin", "/usr/local/bin")


def _resolve_binary(name: str) -> str | None:
    """Locate an executable.

    First consults ``shutil.which`` (PATH lookup), then falls back to the
    standard Homebrew install dirs. Returns the absolute path or None.
    """
    found = shutil.which(name)
    if found:
        return found
    for prefix in HOMEBREW_BIN_DIRS:
        candidate = Path(prefix) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


@dataclass(frozen=True)
class DependencyStatus:
    """One installable Meeting Capture dependency, plus how to fix it."""

    name: str
    installed: bool
    description: str
    install_command: str  # empty if installed; brew invocation otherwise
    detail: str = ""      # human-readable diagnostic, e.g. resolved path


def _check_ffmpeg() -> DependencyStatus:
    path = _resolve_binary("ffmpeg")
    return DependencyStatus(
        name="ffmpeg",
        installed=path is not None,
        description="Mixes mic + system audio. Required for dual-stream capture and Whisper audio loading.",
        install_command="brew install ffmpeg",
        detail=path or "not found on PATH or in /opt/homebrew/bin or /usr/local/bin",
    )


def _check_blackhole() -> DependencyStatus:
    installed, detail = _blackhole_status()
    return DependencyStatus(
        name="BlackHole 2ch",
        installed=installed,
        description="Virtual audio driver. Required to record the other side of a call.",
        install_command="brew install blackhole-2ch",
        detail=detail,
    )


def _blackhole_status() -> tuple[bool, str]:
    """Return (installed, human-readable detail) for BlackHole.

    Tries the live PortAudio device list first. If that doesn't see BlackHole
    (which happens when PortAudio cached the device list before BlackHole was
    installed), falls back to ``brew list blackhole-2ch`` so we still give
    the right answer for the dep wizard's purposes.
    """
    try:
        from .recorder import find_blackhole_device

        device = find_blackhole_device()
        if device is not None:
            return True, f"PortAudio device #{device.index} ('{device.name}')"
    except Exception as e:  # noqa: BLE001
        # PortAudio unavailable — fall through to brew check.
        portaudio_error = str(e)
    else:
        portaudio_error = "not visible to PortAudio (cached device list?)"

    brew = _resolve_binary("brew")
    if brew is None:
        return False, f"{portaudio_error}; brew CLI not found either"

    result = subprocess.run(
        [brew, "list", "blackhole-2ch"], capture_output=True, check=False
    )
    if result.returncode == 0:
        return True, f"installed via Homebrew ({portaudio_error})"
    return False, f"not installed; {portaudio_error}"


def _check_ollama() -> DependencyStatus:
    binary = _resolve_binary("ollama")
    if binary is None:
        return DependencyStatus(
            name="Ollama",
            installed=False,
            description="Local LLM server. Generates the meeting summary.",
            install_command="brew install ollama && brew services start ollama && ollama pull llama3.1:8b",
            detail="not found on PATH or in /opt/homebrew/bin or /usr/local/bin",
        )

    if not _ollama_server_reachable():
        return DependencyStatus(
            name="Ollama (server not running)",
            installed=False,
            description="Ollama is installed but the server isn't responding on localhost:11434.",
            install_command="brew services start ollama",
            detail=f"binary at {binary} but http://localhost:11434/api/tags not reachable",
        )

    if not _ollama_model_pulled("llama3.1:8b"):
        return DependencyStatus(
            name="Ollama model llama3.1:8b",
            installed=False,
            description="Ollama is running but the summarization model hasn't been downloaded yet (~4.7 GB).",
            install_command="ollama pull llama3.1:8b",
            detail="server up; model llama3.1:8b not in ollama list",
        )

    return DependencyStatus(
        name="Ollama",
        installed=True,
        description="Local LLM server, running and ready.",
        install_command="",
        detail=f"{binary}; server up; model llama3.1:8b present",
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


def format_diagnostic_report(statuses: list[DependencyStatus]) -> str:
    """Render a human-readable status block.  Used by ``meet doctor`` and
    by the menu bar wizard when no deps are missing (sanity check)."""
    lines = ["Dependency check:"]
    for status in statuses:
        marker = "✓" if status.installed else "✗"
        lines.append(f"  {marker} {status.name}")
        if status.detail:
            lines.append(f"        {status.detail}")
    return "\n".join(lines)
