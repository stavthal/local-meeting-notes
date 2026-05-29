"""Audio recorder. Streams from a chosen input device to a 16 kHz mono WAV."""

from __future__ import annotations

from dataclasses import dataclass
import queue
import sys
import threading
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import sounddevice as sd
import soundfile as sf

DEFAULT_SIGNAL_THRESHOLD = 0.01
DEFAULT_PROBE_SECONDS = 1.0

# Input devices to skip entirely. These appear via macOS Continuity or as
# camera-mounted mics and are never the right capture source for a meeting.
EXCLUDED_DEVICE_PATTERNS = (
    # macOS Continuity devices
    "iphone",
    "ipad",
    "apple watch",
    "continuity",
    # built-in camera mics
    "facetime",
    # external webcam mics — typically low quality, never the right call source
    "webcam",
    "cam sync",
    "obs virtual",
)


class DeviceSelectionError(RuntimeError):
    """Raised when no usable recording input can be selected."""


@dataclass(frozen=True)
class InputDeviceCandidate:
    index: int
    name: str
    max_input_channels: int
    default_samplerate: float | None
    priority: int


@dataclass(frozen=True)
class SelectedInputDevice:
    index: int
    name: str
    max_input_channels: int
    rms: float | None
    auto_selected: bool


@dataclass(frozen=True)
class InputDeviceProbe:
    candidate: InputDeviceCandidate
    rms: float | None
    error: str | None = None


def list_devices() -> None:
    """Print all audio devices. Look for your Aggregate Device in the input list."""
    print(sd.query_devices())
    default_in, default_out = sd.default.device
    print(f"\nDefault input:  {default_in}")
    print(f"Default output: {default_out}")
    print(
        "\nTip: `meet record` probes active inputs and prompts you to choose. "
        "Pass --device to skip the prompt."
    )


def _should_exclude_device(name: str) -> bool:
    """True if a device should never be considered for meeting capture."""
    normalized = name.lower()
    return any(pattern in normalized for pattern in EXCLUDED_DEVICE_PATTERNS)


def _device_priority(name: str) -> int:
    """Score input devices by how likely they are to capture the meeting.

    Tier 1 (100):  aggregate / meeting capture device — both sides of the call.
    Tier 2 (80-90): system-audio loopbacks (BlackHole, generic virtual / loopback).
    Tier 3 (70):   meeting-app virtual devices (Zoom, Teams).
    Tier 4 (50-60): personal headset / earbuds — captures the user's voice cleanly.
    Tier 5 (30):   MacBook built-in microphone.
    Tier 6 (10):   anything else with input channels.
    """
    normalized = name.lower()

    if "aggregate" in normalized or "meeting capture" in normalized:
        return 100
    if "blackhole" in normalized:
        return 90
    if "loopback" in normalized or "virtual" in normalized:
        return 80
    if "zoom" in normalized or "teams" in normalized:
        return 70

    if any(p in normalized for p in ("airpods", "beats", "bose", "sony", "jabra", "sennheiser")):
        return 60
    if "headset" in normalized or "headphone" in normalized or "earbud" in normalized:
        return 55

    if "macbook" in normalized and ("microphone" in normalized or "mic" in normalized):
        return 30

    return 10


def input_device_candidates(devices: Iterable[dict] | None = None) -> list[InputDeviceCandidate]:
    """Return input-capable devices with their PortAudio indexes.

    Devices matching EXCLUDED_DEVICE_PATTERNS (iPhone via Continuity, camera mics, etc.)
    are skipped entirely — they are never probed or shown to the user.
    """
    if devices is None:
        devices = sd.query_devices()

    candidates = []
    for index, device in enumerate(devices):
        max_input_channels = int(device.get("max_input_channels", 0) or 0)
        if max_input_channels <= 0:
            continue

        name = str(device.get("name", f"Device {index}"))
        if _should_exclude_device(name):
            continue

        candidates.append(
            InputDeviceCandidate(
                index=index,
                name=name,
                max_input_channels=max_input_channels,
                default_samplerate=device.get("default_samplerate"),
                priority=_device_priority(name),
            )
        )
    return candidates


def _device_rms(samples: np.ndarray) -> float:
    """Return the loudest channel RMS for a recorded sample buffer."""
    if samples.size == 0:
        return 0.0
    if samples.ndim == 1:
        samples = samples.reshape(-1, 1)
    channel_rms = np.sqrt(np.mean(np.square(samples), axis=0))
    return float(np.max(channel_rms))


def _probe_device_rms(
    candidate: InputDeviceCandidate,
    samplerate: int,
    probe_seconds: float,
) -> float:
    frames = max(1, int(samplerate * probe_seconds))
    samples = sd.rec(
        frames,
        samplerate=samplerate,
        channels=candidate.max_input_channels,
        device=candidate.index,
        blocking=True,
    )
    return _device_rms(samples)


def probe_input_devices(
    devices: Iterable[dict] | None = None,
    rms_probe: Callable[[InputDeviceCandidate], float] | None = None,
    samplerate: int = 16_000,
    probe_seconds: float = DEFAULT_PROBE_SECONDS,
) -> list[InputDeviceProbe]:
    """Record a short sample from every visible input device and return signal levels."""
    candidates = input_device_candidates(devices)
    if not candidates:
        raise DeviceSelectionError("No input devices are visible to PortAudio.")

    if rms_probe is None:
        rms_probe = lambda candidate: _probe_device_rms(candidate, samplerate, probe_seconds)

    probes = []
    for candidate in candidates:
        try:
            rms = rms_probe(candidate)
        except Exception as e:  # noqa: BLE001 - bad devices should not block probing others.
            probes.append(InputDeviceProbe(candidate=candidate, rms=None, error=str(e)))
            continue
        probes.append(InputDeviceProbe(candidate=candidate, rms=rms))

    return probes


def _recommended_probe(
    probes: list[InputDeviceProbe],
    threshold: float,
) -> InputDeviceProbe | None:
    """Return the best probe with active signal, or None if nothing meets the threshold."""
    active = [
        probe
        for probe in probes
        if probe.error is None and probe.rms is not None and probe.rms >= threshold
    ]
    if not active:
        return None
    return max(active, key=lambda probe: (probe.candidate.priority, probe.rms or 0.0))


def _fallback_default_probe(probes: list[InputDeviceProbe]) -> InputDeviceProbe | None:
    """Highest-priority working probe, used when nothing shows signal."""
    eligible = [p for p in probes if p.error is None]
    if not eligible:
        return None
    return max(eligible, key=lambda probe: (probe.candidate.priority, probe.rms or 0.0))


def _print_probe_results(
    probes: list[InputDeviceProbe],
    recommended: InputDeviceProbe,
) -> None:
    print("\nInput probe results:")
    for probe in probes:
        marker = "*" if probe.candidate.index == recommended.candidate.index else " "
        if probe.error:
            signal = f"error: {probe.error}"
        else:
            signal = f"rms {probe.rms:.4f}"
        print(
            f"{marker} {probe.candidate.index:>2} — {probe.candidate.name} "
            f"({probe.candidate.max_input_channels} ch, {signal})"
        )


def _format_probe_label(probe: InputDeviceProbe) -> str:
    if probe.error:
        signal = f"error: {probe.error}"
    else:
        signal = f"rms {probe.rms:.4f}"
    return (
        f"{probe.candidate.index:>2} — {probe.candidate.name} "
        f"({probe.candidate.max_input_channels} ch, {signal})"
    )


def _arrow_key_picker(
    probes: list[InputDeviceProbe],
    recommended: InputDeviceProbe,
) -> int:
    """Interactive arrow-key/Enter picker. Raises ImportError if questionary is missing."""
    import questionary

    choices = []
    default_choice = None
    for probe in probes:
        label = _format_probe_label(probe)
        if probe.candidate.index == recommended.candidate.index:
            label = f"{label}  ← recommended"
        choice = questionary.Choice(
            title=label,
            value=probe.candidate.index,
            disabled="probe failed" if probe.error else False,
        )
        choices.append(choice)
        if probe.candidate.index == recommended.candidate.index and not probe.error:
            default_choice = choice

    answer = questionary.select(
        "Choose input device:",
        choices=choices,
        default=default_choice,
        instruction="(↑/↓ to move, Enter to confirm)",
    ).ask()

    if answer is None:
        # User pressed Ctrl+C / ESC inside the picker.
        raise DeviceSelectionError("Device selection cancelled.")
    return int(answer)


def _number_prompt(
    probes: list[InputDeviceProbe],
    recommended: InputDeviceProbe,
) -> int:
    """Fallback prompt when questionary is not installed."""
    available = {probe.candidate.index for probe in probes}
    while True:
        raw = input(f"Choose input device [{recommended.candidate.index}]: ").strip()
        if raw == "":
            return recommended.candidate.index
        try:
            selected = int(raw)
        except ValueError:
            print("Enter one of the listed device indexes.")
            continue
        if selected in available:
            return selected
        print("Enter one of the listed device indexes.")


def _prompt_for_device(
    probes: list[InputDeviceProbe],
    recommended: InputDeviceProbe,
) -> int:
    if not sys.stdin.isatty():
        return recommended.candidate.index

    try:
        return _arrow_key_picker(probes, recommended)
    except ImportError:
        # questionary not installed — degrade gracefully to the typed prompt.
        return _number_prompt(probes, recommended)


def choose_input_device(
    probes: list[InputDeviceProbe],
    threshold: float = DEFAULT_SIGNAL_THRESHOLD,
    chooser: Callable[[list[InputDeviceProbe], InputDeviceProbe], int] | None = None,
) -> SelectedInputDevice:
    """Choose a device from probe results, using a prompt by default.

    Always shows the picker as long as there is at least one working probe.
    When no probe shows signal above ``threshold``, the highest-priority
    candidate becomes the default so the user can pick before any audio flows.
    """
    recommended = _recommended_probe(probes, threshold)
    default = recommended or _fallback_default_probe(probes)

    if default is None:
        errors = [
            f"{probe.candidate.index}: {probe.candidate.name} ({probe.error})"
            for probe in probes
            if probe.error
        ]
        detail = f" Probe errors: {'; '.join(errors)}" if errors else ""
        raise DeviceSelectionError(
            f"No usable input devices to choose from.{detail}"
        )

    if recommended is None:
        print(
            "\n⚠  No input device shows active audio yet. "
            "Pick one — signal will flow once your call starts or you talk."
        )

    _print_probe_results(probes, default)

    if chooser is None:
        chooser = _prompt_for_device

    selected_index = chooser(probes, default)
    for probe in probes:
        if probe.candidate.index != selected_index:
            continue
        if probe.error:
            raise DeviceSelectionError(
                f"Device {selected_index} could not be probed: {probe.error}"
            )
        return SelectedInputDevice(
            index=probe.candidate.index,
            name=probe.candidate.name,
            max_input_channels=probe.candidate.max_input_channels,
            rms=probe.rms,
            auto_selected=True,
        )

    raise DeviceSelectionError(f"Device {selected_index} is not one of the probed inputs.")


def select_active_input_device(
    devices: Iterable[dict] | None = None,
    rms_probe: Callable[[InputDeviceCandidate], float] | None = None,
    samplerate: int = 16_000,
    probe_seconds: float = DEFAULT_PROBE_SECONDS,
    threshold: float = DEFAULT_SIGNAL_THRESHOLD,
) -> SelectedInputDevice:
    """Probe inputs and pick the recommended active device without prompting.

    Strict: raises ``DeviceSelectionError`` when nothing meets the threshold.
    For an interactive fallback that tolerates silence, use ``choose_input_device``.
    """
    probes = probe_input_devices(
        devices=devices,
        rms_probe=rms_probe,
        samplerate=samplerate,
        probe_seconds=probe_seconds,
    )
    recommended = _recommended_probe(probes, threshold)
    if recommended is None:
        raise DeviceSelectionError(
            "No input device with audio signal was detected. "
            "Start or unmute the call, then try again; or pass --device explicitly."
        )
    candidate = recommended.candidate
    return SelectedInputDevice(
        index=candidate.index,
        name=candidate.name,
        max_input_channels=candidate.max_input_channels,
        rms=recommended.rms,
        auto_selected=True,
    )


def _resolve_input_device(
    device: int | None,
    samplerate: int,
    probe_seconds: float,
    threshold: float,
) -> SelectedInputDevice:
    if device is None:
        print(f"Probing input devices for {probe_seconds:.1f}s each...")
        probes = probe_input_devices(
            samplerate=samplerate,
            probe_seconds=probe_seconds,
        )
        return choose_input_device(probes, threshold=threshold)

    info = sd.query_devices(device)
    max_input_channels = int(info.get("max_input_channels", 0) or 0)
    if max_input_channels <= 0:
        raise DeviceSelectionError(f"Device {device} has no input channels.")
    return SelectedInputDevice(
        index=device,
        name=str(info["name"]),
        max_input_channels=max_input_channels,
        rms=None,
        auto_selected=False,
    )


def record_audio(
    output_path: Path,
    device: int | None = None,
    samplerate: int = 16_000,
    channels: int = 1,
    probe_seconds: float = DEFAULT_PROBE_SECONDS,
    signal_threshold: float = DEFAULT_SIGNAL_THRESHOLD,
    stop_event: threading.Event | None = None,
    quiet: bool = False,
) -> Path:
    """Record until Ctrl+C (or ``stop_event`` is set), writing PCM_16 WAV.

    The optional ``stop_event`` lets non-CLI callers (e.g. the menu bar app)
    stop recording cleanly from another thread. ``quiet`` suppresses print
    output, useful when the caller renders its own UI.

    Returns the output path on success.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    selected = _resolve_input_device(
        device=device,
        samplerate=samplerate,
        probe_seconds=probe_seconds,
        threshold=signal_threshold,
    )
    stream_channels = selected.max_input_channels if channels == 1 else channels

    q: queue.Queue = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status and not quiet:
            print(status, file=sys.stderr)
        data = indata.copy()
        if channels == 1 and data.ndim == 2 and data.shape[1] > 1:
            data = data.mean(axis=1, keepdims=True)
        q.put(data)

    if not quiet:
        if selected.auto_selected:
            print(f"Selected input: {selected.index} — {selected.name} (rms {selected.rms:.4f})")
        print(f"Recording from '{selected.name}' → {output_path}")
        if stop_event is None:
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
                device=selected.index,
                channels=stream_channels,
                callback=callback,
            ):
                while True:
                    if stop_event is not None and stop_event.is_set():
                        # Drain any remaining buffered audio before closing.
                        while True:
                            try:
                                f.write(q.get_nowait())
                            except queue.Empty:
                                break
                        break
                    try:
                        f.write(q.get(timeout=0.1))
                    except queue.Empty:
                        continue
    except KeyboardInterrupt:
        pass

    if not quiet:
        print(f"\nStopped. Saved: {output_path}")
    return output_path
