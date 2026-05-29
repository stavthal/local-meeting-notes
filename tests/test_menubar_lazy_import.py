"""Verify the menubar module can be imported without rumps and that the
CLI exposes the `menubar` command even on hosts that lack rumps."""

import importlib
import sys
import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner


class MenubarLazyImportTests(unittest.TestCase):
    def test_menubar_module_imports_without_rumps_installed(self):
        # rumps is not available on Linux — the module must still be importable
        # so the CLI can advertise the `menubar` subcommand.
        sys.modules.pop("meeting_capture.menubar", None)
        importlib.import_module("meeting_capture.menubar")

    def test_run_raises_systemexit_with_install_hint_when_rumps_missing(self):
        sys.modules.pop("meeting_capture.menubar", None)
        from meeting_capture import menubar

        # Force `import rumps` to fail.
        with patch.dict(sys.modules, {"rumps": None}):
            with self.assertRaises(SystemExit) as ctx:
                menubar.run()
        self.assertIn("rumps", str(ctx.exception))

    def test_cli_menubar_command_is_registered(self):
        sys.modules.pop("meeting_capture.cli", None)
        from meeting_capture.cli import cli

        # The command must be discoverable so `meet menubar --help` works
        # regardless of whether rumps is installed.
        runner = CliRunner()
        result = runner.invoke(cli, ["menubar", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("menu bar", result.output.lower())

    def test_build_app_wires_state_and_menu_structure(self):
        # Inject a fake rumps so _build_app constructs an app object whose
        # state machine we can poke without touching AppKit.
        from meeting_capture import menubar

        fake_rumps = _make_fake_rumps()

        app = menubar._build_app(fake_rumps)

        self.assertFalse(app.is_recording)
        self.assertFalse(app.is_processing)
        self.assertIsNone(app.selected_device_index)
        # Status row should advertise "Ready" in the idle state.
        self.assertIn("Ready", app.status_item.title)

    def test_safe_clear_tolerates_uninitialized_submenu(self):
        # rumps MenuItem._menu is None until the first add(). Calling clear()
        # on it raises AttributeError. _safe_clear must swallow that so
        # _populate_* helpers can be called from __init__.
        from meeting_capture import menubar

        class BareMenuItem:
            def clear(self):
                raise AttributeError("'NoneType' object has no attribute 'removeAllItems'")

        # Should not raise.
        menubar._safe_clear(BareMenuItem())


def _make_fake_rumps():
    """Build a stand-in rumps module exposing just the surface menubar.py uses."""
    fake = MagicMock()

    class _FakeApp:
        def __init__(self, **kwargs):
            self.title = kwargs.get("title", "")
            self.icon = kwargs.get("icon")
            self.menu = []

        def run(self):  # not called in tests
            pass

    class _FakeMenuItem:
        def __init__(self, title, callback=None):
            self.title = title
            self.callback = callback
            self.state = False
            self._children: list = []

        def set_callback(self, cb):
            self.callback = cb

        def clear(self):
            self._children.clear()

        def add(self, child):
            self._children.append(child)

    class _FakeTimer:
        def __init__(self, fn, interval):
            self.fn = fn
            self.interval = interval

        def start(self):
            pass

        def stop(self):
            pass

    fake.App = _FakeApp
    fake.MenuItem = _FakeMenuItem
    fake.Timer = _FakeTimer
    fake.separator = object()
    fake.alert = MagicMock()
    fake.notification = MagicMock()
    fake.quit_application = MagicMock()
    return fake


if __name__ == "__main__":
    unittest.main()
