"""py2app entrypoint.

This stays at the project root so py2app picks it up cleanly. It just
forwards to the existing menu bar runner — all real code lives in the
``meeting_capture`` package.
"""

from meeting_capture.menubar import run


if __name__ == "__main__":
    run()
