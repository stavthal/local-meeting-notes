# PyInstaller spec file for Meeting Capture.
#
# Invoke via ./build/build_dmg.sh, which runs:
#   pyinstaller build/MeetingCapture.spec --noconfirm --clean
#
# All paths are relative to the project root, because the build script
# always cd's there before invoking pyinstaller.

# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

APP_NAME = "Meeting Capture"
BUNDLE_ID = "com.steve.meetingcapture"
VERSION = "0.1.0"

block_cipher = None

a = Analysis(
    ["build/app_entry.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("meeting_capture/assets", "meeting_capture/assets"),
    ],
    hiddenimports=[
        # Modules that PyInstaller's static analysis can miss because they
        # are imported dynamically inside the package or via PyObjC magic.
        "meeting_capture",
        "meeting_capture.menubar",
        "meeting_capture.recorder",
        "meeting_capture.transcriber",
        "meeting_capture.summarizer",
        "meeting_capture.call_detection",
        "meeting_capture.cli",
        "mlx",
        "mlx.core",
        "mlx.nn",
        "mlx_whisper",
        "Quartz",
        "objc",
        "rumps",
        "sounddevice",
        "soundfile",
        "questionary",
        "huggingface_hub",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon="meeting_capture/assets/AppIcon.icns",
    bundle_identifier=BUNDLE_ID,
    version=VERSION,
    info_plist={
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        # Hide the Dock icon — this is a menu bar app.
        "LSUIElement": True,
        # macOS TCC prompts shown on first capture / detection.
        "NSMicrophoneUsageDescription": (
            "Meeting Capture records your meetings locally to transcribe "
            "and summarize them. Recording only starts when you click "
            "Start Recording."
        ),
        "NSAppleEventsUsageDescription": (
            "Detects active Teams / Meet / Zoom call windows so the menu "
            "can show 'Call detected'. No window contents are read."
        ),
        "LSMinimumSystemVersion": "13.0",
        # Allow signed-app reuse of the bundle id under different versions.
        "NSHumanReadableCopyright": "© 2026 Stavros Thalassinos. MIT License.",
    },
)
