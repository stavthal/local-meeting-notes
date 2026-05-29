"""Detect whether the user is currently in a video call.

Reads on-screen window metadata via macOS Quartz (no special permissions
required beyond running on a standard desktop session) and matches process
owner + window title against signatures for Microsoft Teams, Google Meet
(in any major browser), and Zoom.

The pure ``detect_call_from_windows`` function takes a list of
window-info dicts (CGWindow-shaped) so it can be unit tested without
touching AppKit. ``detect_active_call`` is the thin macOS wrapper that
calls Quartz and forwards the dicts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

BROWSER_OWNERS = (
    "google chrome",
    "chrome",
    "arc",
    "safari",
    "microsoft edge",
    "edge",
    "brave",
    "vivaldi",
    "firefox",
)


@dataclass(frozen=True)
class CallSignal:
    """A detected active call."""

    app: str           # human-readable app, e.g. "Microsoft Teams"
    source: str        # short tag for code: "teams" | "meet" | "zoom"
    title: str | None  # the window title that matched, for context


def _matches_teams(owner: str, title: str) -> bool:
    if "teams" not in owner.lower():
        return False
    # Teams' main window is just "Microsoft Teams". Inside a call, the
    # frontmost window title contains the meeting name or substrings like
    # "Meeting", "Calling", or "Call with".
    t = title.lower()
    return any(s in t for s in ("meeting", "calling", "call with", " | "))


def _matches_meet(owner: str, title: str) -> bool:
    owner_low = owner.lower()
    if not any(b in owner_low for b in BROWSER_OWNERS):
        return False
    t = title.lower()
    # Google Meet tabs are titled "Meet - <name>" or include the URL.
    # The main Meet landing page is "Google Meet" — we exclude that so the
    # signal only fires once the user is actually in a meeting.
    if t.startswith("meet -") or " - meet -" in t:
        return True
    if "meet.google.com" in t and "meet -" in t:
        return True
    return False


def _matches_zoom(owner: str, title: str) -> bool:
    if "zoom" not in owner.lower():
        return False
    t = title.lower()
    return any(s in t for s in ("meeting", "webinar"))


_MATCHERS = (
    ("teams", "Microsoft Teams", _matches_teams),
    ("meet", "Google Meet", _matches_meet),
    ("zoom", "Zoom", _matches_zoom),
)


def detect_call_from_windows(windows: Iterable[dict]) -> CallSignal | None:
    """Pure detection — scan the provided window dicts for a known call signature.

    Each window dict should expose ``kCGWindowOwnerName`` (process name)
    and ``kCGWindowName`` (window title), the keys Quartz uses.
    """
    for w in windows:
        owner = (w.get("kCGWindowOwnerName") or "").strip()
        title = (w.get("kCGWindowName") or "").strip()
        if not owner:
            continue
        for source, label, matcher in _MATCHERS:
            if matcher(owner, title):
                return CallSignal(app=label, source=source, title=title or None)
    return None


def detect_active_call() -> CallSignal | None:
    """Read live on-screen windows on macOS and run detection.

    Returns None silently if Quartz is unavailable (non-macOS, missing
    pyobjc-framework-Quartz) so callers can treat detection as a soft hint.
    """
    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListOptionOnScreenOnly,
        )
    except ImportError:
        return None
    raw = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID) or []
    windows = [dict(w) for w in raw]
    return detect_call_from_windows(windows)
