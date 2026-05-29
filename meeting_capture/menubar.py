"""macOS menu bar interface for Meeting Capture.

This module wraps the existing CLI pipeline (record → transcribe → summarize)
in a rumps-based menu bar app so the user does not have to live in the terminal
during meetings.

Heavy GUI dependencies (rumps, AppKit via PyObjC) are imported lazily inside
``run()`` so the rest of the package stays importable on Linux/CI.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .recorder import (
    DeviceSelectionError,
    InputDeviceCandidate,
    input_device_candidates,
    record_audio,
)
from .summarizer import summarize
from .transcriber import transcribe

ASSETS_DIR = Path(__file__).parent / "assets"
ICON_PATH = ASSETS_DIR / "tray_icon.png"

DEFAULT_WHISPER_MODEL = "mlx-community/whisper-large-v3-mlx"
DEFAULT_LLM_MODEL = "llama3.1:8b"


def _recordings_dir() -> Path:
    """Where outputs land. Same convention as the CLI."""
    base = os.environ.get("MEET_DIR")
    if base:
        d = Path(base).expanduser()
    else:
        d = Path.home() / "Documents" / "meeting-capture" / "recordings"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _timestamped_wav() -> Path:
    return _recordings_dir() / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"


def _format_duration(seconds: float) -> str:
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _recent_summaries(limit: int = 8) -> list[Path]:
    return sorted(
        _recordings_dir().glob("*.summary.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]


HOW_TO_USE_TEXT = """\
Meeting Capture — quick guide

1. Pick an input device from "Device" submenu.
   Auto-pick probes inputs and chooses the best one.
   Set up an Aggregate Device (mic + BlackHole) in Audio MIDI Setup
   if you want to capture BOTH sides of the call.

2. Click "Start Recording" before or during the meeting.
   The icon shows "● REC" with elapsed time.

3. Click "Stop Recording" when the meeting ends.
   Transcription (mlx-whisper) and summarization (Ollama) run automatically.
   You'll get a macOS notification when the summary is ready.

4. Open recent summaries from "Recent" submenu, or browse the
   recordings folder.

System Settings → Sound → Output should be set to your
Multi-Output Device (your headphones + BlackHole) when you want
to capture the OTHER side of the call. Otherwise you only capture
your own microphone.

Ollama must be running. brew services start ollama if not.
"""


def run() -> None:
    """Launch the menu bar app. Blocks until Quit."""
    try:
        import rumps  # noqa: F401
    except ImportError as e:
        raise SystemExit(
            "rumps is not installed. Install with:\n"
            "  pipx inject meeting-capture rumps\n"
            "or reinstall: pipx install --force ~/Documents/meeting-capture"
        ) from e

    app = _build_app(rumps)
    app.run()


def _build_app(rumps: Any) -> Any:
    """Construct the rumps app. ``rumps`` injected so tests can mock it."""

    class MeetingCaptureApp(rumps.App):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__(
                name="MeetingCapture",
                title="",
                icon=str(ICON_PATH) if ICON_PATH.exists() else None,
                template=True,
                quit_button=None,
            )

            # State
            self.is_recording = False
            self.is_processing = False
            self.stop_event: threading.Event | None = None
            self.worker_thread: threading.Thread | None = None
            self.current_audio_path: Path | None = None
            self.last_summary_path: Path | None = None
            self.recording_started_at: float | None = None
            self.selected_device_index: int | None = None  # None = auto-pick

            # Menu items kept as instance attrs so we can mutate them.
            self.status_item = rumps.MenuItem("🟢 Ready", callback=None)
            self.start_item = rumps.MenuItem("● Start Recording", callback=self.on_start)
            self.stop_item = rumps.MenuItem("■ Stop Recording", callback=self.on_stop)
            self.device_menu = rumps.MenuItem("Device")
            self.recent_menu = rumps.MenuItem("Recent Summaries")
            self.open_folder_item = rumps.MenuItem(
                "Open recordings folder", callback=self.on_open_folder
            )
            self.open_last_item = rumps.MenuItem(
                "Open last summary", callback=self.on_open_last_summary
            )
            self.how_to_item = rumps.MenuItem("How to use…", callback=self.on_how_to_use)
            self.rescan_item = rumps.MenuItem(
                "Re-scan devices", callback=self.on_rescan_devices
            )
            self.quit_item = rumps.MenuItem("Quit", callback=self.on_quit)

            self.menu = [
                self.status_item,
                None,
                self.start_item,
                self.stop_item,
                self.device_menu,
                None,
                self.recent_menu,
                self.open_last_item,
                self.open_folder_item,
                None,
                self.how_to_item,
                self.rescan_item,
                None,
                self.quit_item,
            ]

            self._populate_device_menu()
            self._populate_recent_menu()
            self._refresh_buttons()

            # Tick the elapsed timer every second while recording.
            self.elapsed_timer = rumps.Timer(self._on_tick, 1)

        # ----- menu construction -------------------------------------------

        def _populate_device_menu(self) -> None:
            self.device_menu.clear()
            auto_item = rumps.MenuItem(
                "Auto-pick (probe and choose best)",
                callback=self._make_device_setter(None),
            )
            auto_item.state = self.selected_device_index is None
            self.device_menu.add(auto_item)
            self.device_menu.add(rumps.separator)

            try:
                candidates = input_device_candidates()
            except Exception as e:  # noqa: BLE001 - keep the UI alive on bad audio state
                err = rumps.MenuItem(f"Error listing devices: {e}", callback=None)
                self.device_menu.add(err)
                return

            if not candidates:
                self.device_menu.add(
                    rumps.MenuItem("No input devices visible", callback=None)
                )
                return

            for cand in sorted(candidates, key=lambda c: -c.priority):
                label = f"{cand.index} — {cand.name}"
                item = rumps.MenuItem(label, callback=self._make_device_setter(cand.index))
                item.state = cand.index == self.selected_device_index
                self.device_menu.add(item)

        def _make_device_setter(self, index: int | None):
            def setter(_: Any) -> None:
                self.selected_device_index = index
                self._populate_device_menu()
            return setter

        def _populate_recent_menu(self) -> None:
            self.recent_menu.clear()
            recents = _recent_summaries()
            if not recents:
                self.recent_menu.add(rumps.MenuItem("(none yet)", callback=None))
                return
            for path in recents:
                label = path.stem.replace(".summary", "")
                item = rumps.MenuItem(label, callback=self._make_opener(path))
                self.recent_menu.add(item)

        def _make_opener(self, path: Path):
            def opener(_: Any) -> None:
                _open_in_finder(path)
            return opener

        # ----- state rendering ---------------------------------------------

        def _refresh_buttons(self) -> None:
            self.start_item.set_callback(None if self.is_recording or self.is_processing else self.on_start)
            self.stop_item.set_callback(self.on_stop if self.is_recording else None)
            self.device_menu.set_callback(None)
            if self.is_recording:
                self.status_item.title = "🔴 Recording — 00:00"
                self.title = "● REC"
            elif self.is_processing:
                self.status_item.title = "⏳ Transcribing + summarizing…"
                self.title = "⏳"
            else:
                self.status_item.title = "🟢 Ready"
                self.title = ""

        def _on_tick(self, _: Any) -> None:
            if not self.is_recording or self.recording_started_at is None:
                return
            elapsed = time.time() - self.recording_started_at
            label = _format_duration(elapsed)
            self.status_item.title = f"🔴 Recording — {label}"
            self.title = f"● {label}"

        # ----- actions ------------------------------------------------------

        def on_start(self, _: Any) -> None:
            if self.is_recording or self.is_processing:
                return
            self.current_audio_path = _timestamped_wav()
            self.stop_event = threading.Event()
            self.recording_started_at = time.time()
            self.is_recording = True
            self._refresh_buttons()
            self.elapsed_timer.start()

            self.worker_thread = threading.Thread(
                target=self._run_pipeline,
                args=(self.current_audio_path, self.selected_device_index, self.stop_event),
                daemon=True,
            )
            self.worker_thread.start()

        def on_stop(self, _: Any) -> None:
            if not self.is_recording or self.stop_event is None:
                return
            self.stop_event.set()
            self.elapsed_timer.stop()

        def on_open_folder(self, _: Any) -> None:
            _open_in_finder(_recordings_dir())

        def on_open_last_summary(self, _: Any) -> None:
            if self.last_summary_path and self.last_summary_path.exists():
                _open_in_finder(self.last_summary_path)
                return
            recents = _recent_summaries(limit=1)
            if recents:
                _open_in_finder(recents[0])
            else:
                rumps.alert(title="No summaries yet", message="Record a meeting first.")

        def on_how_to_use(self, _: Any) -> None:
            rumps.alert(title="Meeting Capture", message=HOW_TO_USE_TEXT)

        def on_rescan_devices(self, _: Any) -> None:
            self._populate_device_menu()

        def on_quit(self, _: Any) -> None:
            if self.is_recording and self.stop_event is not None:
                self.stop_event.set()
            rumps.quit_application()

        # ----- worker pipeline ---------------------------------------------

        def _run_pipeline(
            self,
            audio_path: Path,
            device_index: int | None,
            stop_event: threading.Event,
        ) -> None:
            try:
                record_audio(
                    audio_path,
                    device=device_index,
                    stop_event=stop_event,
                    quiet=True,
                )
            except DeviceSelectionError as e:
                self._finalize_with_error(f"Device error: {e}")
                return
            except Exception as e:  # noqa: BLE001
                self._finalize_with_error(f"Recording failed: {e}")
                return

            self.is_recording = False
            self.is_processing = True
            self._refresh_buttons()

            try:
                txt_path = audio_path.with_suffix(".txt")
                transcribe(audio_path, txt_path, model=DEFAULT_WHISPER_MODEL)
                summary_path = audio_path.with_suffix(".summary.md")
                summarize(txt_path, summary_path, model=DEFAULT_LLM_MODEL)
            except Exception as e:  # noqa: BLE001
                self._finalize_with_error(f"Processing failed: {e}")
                return

            self.last_summary_path = summary_path
            self.is_processing = False
            self._refresh_buttons()
            self._populate_recent_menu()

            try:
                rumps.notification(
                    title="Meeting summary ready",
                    subtitle=summary_path.stem,
                    message="Click 'Open last summary' to view.",
                    sound=True,
                )
            except Exception:  # noqa: BLE001 - notifications need bundled .app on newer macOS
                pass

        def _finalize_with_error(self, message: str) -> None:
            self.is_recording = False
            self.is_processing = False
            self._refresh_buttons()
            self.elapsed_timer.stop()
            try:
                rumps.alert(title="Meeting Capture", message=message)
            except Exception:  # noqa: BLE001
                pass

    return MeetingCaptureApp()


def _open_in_finder(path: Path) -> None:
    """macOS-friendly open. Falls back silently elsewhere."""
    try:
        subprocess.run(["open", str(path)], check=False)
    except FileNotFoundError:
        pass
