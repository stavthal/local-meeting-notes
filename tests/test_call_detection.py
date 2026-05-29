"""Tests for the pure call-detection logic."""

import unittest

from meeting_capture.call_detection import CallSignal, detect_call_from_windows


def _w(owner: str, title: str) -> dict:
    return {"kCGWindowOwnerName": owner, "kCGWindowName": title}


class CallDetectionTests(unittest.TestCase):
    # --- positive matches ----------------------------------------------------

    def test_detects_teams_meeting_window(self):
        signal = detect_call_from_windows([
            _w("Microsoft Teams", "Meeting with Acme | Microsoft Teams"),
        ])
        self.assertIsNotNone(signal)
        self.assertEqual(signal.source, "teams")
        self.assertEqual(signal.app, "Microsoft Teams")

    def test_detects_teams_call_with_window(self):
        signal = detect_call_from_windows([
            _w("Microsoft Teams (work or school)", "Call with Maria"),
        ])
        self.assertIsNotNone(signal)
        self.assertEqual(signal.source, "teams")

    def test_detects_google_meet_in_chrome(self):
        signal = detect_call_from_windows([
            _w("Google Chrome", "Meet - abc-defg-hij"),
        ])
        self.assertIsNotNone(signal)
        self.assertEqual(signal.source, "meet")
        self.assertEqual(signal.app, "Google Meet")

    def test_detects_google_meet_in_arc(self):
        signal = detect_call_from_windows([
            _w("Arc", "Meet - daily-standup"),
        ])
        self.assertIsNotNone(signal)
        self.assertEqual(signal.source, "meet")

    def test_detects_google_meet_in_safari(self):
        signal = detect_call_from_windows([
            _w("Safari", "Meet - foo-bar-baz"),
        ])
        self.assertIsNotNone(signal)
        self.assertEqual(signal.source, "meet")

    def test_detects_zoom_meeting(self):
        signal = detect_call_from_windows([
            _w("zoom.us", "Zoom Meeting"),
        ])
        self.assertIsNotNone(signal)
        self.assertEqual(signal.source, "zoom")

    # --- negative cases ------------------------------------------------------

    def test_teams_main_window_alone_is_not_a_call(self):
        # Just having Teams open shouldn't fire detection.
        signal = detect_call_from_windows([
            _w("Microsoft Teams", "Microsoft Teams"),
        ])
        self.assertIsNone(signal)

    def test_browser_without_meet_tab_is_not_a_call(self):
        signal = detect_call_from_windows([
            _w("Google Chrome", "Inbox - Gmail"),
            _w("Arc", "Notion — Roadmap"),
        ])
        self.assertIsNone(signal)

    def test_meet_landing_page_is_not_a_call(self):
        # The Meet landing page title is just "Google Meet" — no "Meet - X".
        signal = detect_call_from_windows([
            _w("Google Chrome", "Google Meet"),
        ])
        self.assertIsNone(signal)

    def test_zoom_app_open_without_meeting_is_not_a_call(self):
        signal = detect_call_from_windows([
            _w("zoom.us", "Zoom"),
        ])
        self.assertIsNone(signal)

    def test_empty_window_list_returns_none(self):
        self.assertIsNone(detect_call_from_windows([]))

    def test_windows_missing_keys_are_skipped(self):
        signal = detect_call_from_windows([
            {},                               # no keys at all
            {"kCGWindowName": "Meet - lol"},  # missing owner
            _w("Google Chrome", "Meet - real-meeting"),
        ])
        self.assertIsNotNone(signal)
        self.assertEqual(signal.source, "meet")

    def test_returns_first_matching_window_in_order(self):
        signal = detect_call_from_windows([
            _w("Microsoft Teams", "Meeting with Eng"),
            _w("Google Chrome", "Meet - other-call"),
        ])
        # Teams comes first in the input → Teams wins.
        self.assertEqual(signal.source, "teams")

    # --- shape ---------------------------------------------------------------

    def test_signal_carries_title_for_context(self):
        signal = detect_call_from_windows([
            _w("Google Chrome", "Meet - daily-standup"),
        ])
        self.assertIsInstance(signal, CallSignal)
        self.assertEqual(signal.title, "Meet - daily-standup")


if __name__ == "__main__":
    unittest.main()
