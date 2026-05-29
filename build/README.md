# Build Pipeline

Everything needed to package Meeting Capture as a draggable macOS installer.

## Files

| File | Purpose |
|------|---------|
| `build_dmg.sh` | End-to-end pipeline: venv → icons → `.app` → `.dmg`. |
| `MeetingCapture.spec` | PyInstaller spec describing the bundle, hidden imports, and `Info.plist`. |
| `app_entry.py` | Tiny launcher that PyInstaller uses as the bundled app's main entry point. |

## Run

From the project root:

```bash
./build/build_dmg.sh
```

Outputs land in `dist/`:

- `dist/Meeting Capture.app`
- `dist/MeetingCapture-<version>.dmg`

## How it works

1. **Picks the build Python.** Prefers `python3.13`, then `3.12`, `3.11`, `3.14`, then any `python3`. PyInstaller supports Python 3.8+ so any reasonable version works.

2. **Creates an isolated venv** at `build/.venv-build/`. All build dependencies (PyInstaller, PyInstaller hook contrib, plus the package itself with all runtime deps via editable install) get installed inside. Your system Python is never touched. The venv is reused on subsequent runs; delete it to force a clean rebuild.

3. **Generates `AppIcon.icns`** by downscaling `meeting_capture/assets/app_icon_source.png` to every macOS app-icon size via `sips`, then compiling the iconset with `iconutil`.

4. **Runs PyInstaller** from inside the venv against `MeetingCapture.spec`, producing `dist/Meeting Capture.app`. The spec file sets `LSUIElement=True` (menu bar app, no Dock icon), `NSMicrophoneUsageDescription`, and bundle identifier `com.steve.meetingcapture` in the `Info.plist`. Temp files go in `build_temp/` (cleaned up at the end).

5. **Wraps the `.app` in a `.dmg`** via `create-dmg`, with a draggable layout pointing at `/Applications`.

## Why PyInstaller and not py2app

We originally used py2app. py2app 0.28 (the latest release as of mid-2025) still calls legacy setuptools APIs that were removed in setuptools 70+, so the build fails with `error: install_requires is no longer supported` on any modern Python environment. Pinning setuptools below 70 conflicts with Python 3.14 support.

PyInstaller doesn't depend on `setuptools.setup()` at all, supports current Python versions, and is actively maintained. The trade-off is a slightly less "Mac-native" build process — PyInstaller doesn't know about macOS `.plist` conventions out of the box, so we declare them explicitly in `MeetingCapture.spec`'s `BUNDLE(...info_plist={...})`. Worth it.

## Native dependencies

BlackHole, Ollama, and ffmpeg cannot be bundled into the `.app` (they're system-level tools, not Python packages). On a fresh Mac, end users still need to install them — easiest via `./setup.sh` or:

```bash
brew install blackhole-2ch ollama ffmpeg
brew services start ollama
ollama pull llama3.1:8b
```

## Gatekeeper

The build is not codesigned. First launch on a Mac that didn't build the app requires right-click → Open → Open to dismiss Gatekeeper. For real distribution you'd need an Apple Developer account ($99/year), a Developer ID Application certificate, codesigning, and notarization via `notarytool`. Out of scope here.
