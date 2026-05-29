"""Allow ``python -m meeting_capture`` to launch the menu bar app directly.

Useful as a fallback when the pipx-installed ``meet menubar`` command isn't
on PATH (for example, immediately after install in the same shell session).
"""

from .menubar import run


if __name__ == "__main__":
    run()
