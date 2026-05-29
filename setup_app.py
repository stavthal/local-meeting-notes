"""py2app configuration for Meeting Capture.

Invoke via ``./build_dmg.sh`` — that script handles the icon conversion
and DMG packaging too. Direct usage is:

    python setup_app.py py2app

The bundle is a "menu bar" / agent app (no Dock icon) because of
``LSUIElement=True``. Microphone permission text is set so the
TCC prompt is informative on first launch.

Notes on native deps NOT bundled:
- BlackHole (audio driver) — installed via ``brew install blackhole-2ch``
- Ollama (LLM server)      — installed via ``brew install ollama``
- ffmpeg                   — installed via ``brew install ffmpeg``

The user installs those once through ``setup.sh``; the .app reuses them
at runtime.
"""

from setuptools import setup

APP = ["app_entry.py"]

DATA_FILES = [
    (
        "meeting_capture/assets",
        [
            "meeting_capture/assets/tray_icon.png",
            "meeting_capture/assets/tray_icon@2x.png",
            "meeting_capture/assets/app_icon_source.png",
        ],
    ),
]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "meeting_capture/assets/AppIcon.icns",
    "plist": {
        "CFBundleName": "Meeting Capture",
        "CFBundleDisplayName": "Meeting Capture",
        "CFBundleIdentifier": "com.steve.meetingcapture",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        # Hide the Dock icon — this is a menu bar app.
        "LSUIElement": True,
        # macOS TCC prompts shown on first capture / detection.
        "NSMicrophoneUsageDescription": (
            "Meeting Capture records your meetings locally to transcribe and "
            "summarize them. Recording only starts when you click Start Recording."
        ),
        # Quartz window enumeration is read-only and uses no special permission,
        # but some macOS versions still nag — be polite.
        "NSAppleEventsUsageDescription": (
            "Detects active Teams / Meet / Zoom call windows so the menu can "
            "show 'Call detected'. No window contents are read."
        ),
        "LSMinimumSystemVersion": "13.0",
    },
    "packages": [
        "meeting_capture",
        "rumps",
        "sounddevice",
        "soundfile",
        "numpy",
        "requests",
        "click",
        "questionary",
        "mlx_whisper",
        "Quartz",
        "huggingface_hub",
    ],
    "includes": [
        "threading",
        "queue",
        "subprocess",
        "shutil",
        "json",
    ],
}

setup(
    name="Meeting Capture",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
