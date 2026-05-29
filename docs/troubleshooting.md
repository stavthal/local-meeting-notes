# Troubleshooting

## Only my voice was recorded

The most common issue. It means BlackHole isn't in the chain, so the other side of the call never reached the recorder.

Check, in order:

1. **Is BlackHole installed?** Run `meet devices`. You should see `BlackHole 2ch` in the list. If not: `brew install blackhole-2ch`.
2. **Is "Mic + system audio" selected?** Open the menu bar app → Capture mode → confirm the checkmark is on `Mic + system audio (via BlackHole)`. If it's grayed out with "— BlackHole not installed", BlackHole isn't visible to PortAudio yet. Click **Re-scan devices** in the main menu. If still grayed out, restart `meet menubar`.
3. **Is your macOS Output routed through a Multi-Output Device?** System Settings → Sound → Output → it should be a Multi-Output Device that includes BlackHole. See [Audio routing](audio-routing.md).

## BlackHole installed but not detected

PortAudio caches its device list at process start. If you install BlackHole while `meet menubar` is already running:

1. Click **Re-scan devices** in the menu (commit `42ac2ec` made this re-scan capture mode too — older versions need a full restart).
2. If still not detected, quit the app entirely (menu → Quit) and re-launch.
3. As a last resort, restart Core Audio: `sudo killall coreaudiod`. Mac will reload all audio drivers.

## Ollama errors

```
Could not reach Ollama at http://localhost:11434.
```

The Ollama server isn't running. Start it:

```bash
brew services start ollama
```

If you get `model "llama3.1:8b" not found`, the model hasn't been pulled yet:

```bash
ollama pull llama3.1:8b
```

The menu bar app's dependency wizard catches all three Ollama states (binary missing, server down, model missing) and gives you the exact command for each. Open it via **Install missing dependencies…**.

## "ffmpeg is required for mlx-whisper audio loading"

`brew install ffmpeg`.

## Microphone permission denied

macOS gates microphone access via TCC (the privacy framework). Meeting Capture needs explicit permission.

- **CLI/menu bar via pipx**: The first call to `record` will trigger the TCC prompt, allowing whichever Terminal you ran it from. If you say no, you'll see no audio recorded. To grant later: **System Settings → Privacy & Security → Microphone → Terminal (or your IDE) → on**.
- **DMG-installed `.app`**: First launch shows the TCC prompt with the friendly description from `Info.plist`. To grant later: **System Settings → Privacy & Security → Microphone → Meeting Capture → on**.

## Transcript is gibberish

- Check the WAV played correctly: `open ~/Documents/meeting-capture/recordings/<file>.wav`.
- If audio is silent or quiet, Whisper hallucinates. Make sure the recording actually captured speech.
- If the meeting was in a language other than English, that's the default Whisper behavior. Pass `--language <code>` (not yet wired into the CLI — to be added; for now, use `mlx-whisper` directly).

## Build (`./build/build_dmg.sh`) fails

### `error: install_requires is no longer supported`

You're hitting py2app on a modern setuptools. Meeting Capture switched to PyInstaller in commit `156063a` to dodge this. Make sure you've got the latest:

```bash
git pull
rm -rf build/.venv-build
./build/build_dmg.sh
```

### `ERROR: script '.../build/build/app_entry.py' not found`

Fixed in commit `5950bd2`. PyInstaller resolves paths relative to the spec file's directory; the fix uses `../` paths in the spec. Pull the latest.

### mlx_whisper fails at runtime

PyInstaller may not pick up MLX's native dylibs automatically. If you see `libmlx.dylib not found` when launching the built `.app`, you need to add `binaries=[...]` to `build/MeetingCapture.spec` pointing at the dylib inside the build venv. [Open an issue](https://github.com/stavthal/local-meeting-notes/issues/new) with the exact error.

## Menu bar app crashes on launch

Most likely culprit was a rumps `clear()` bug fixed in commit `a249df1`. Make sure you're on the latest, then refresh pipx:

```bash
git pull
pipx install --force .
meet menubar
```

If it still crashes, paste the stack trace in a GitHub issue.

## Nothing in this list helped

Open a [GitHub issue](https://github.com/stavthal/local-meeting-notes/issues/new) with:

- macOS version
- `python3 --version`
- Output of `meet devices`
- The error message or stack trace
