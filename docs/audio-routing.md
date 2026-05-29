# Audio routing

To record **both sides of a call**, macOS needs to send the call audio somewhere Meeting Capture can read. The standard way is to install **BlackHole** (a virtual audio driver) and configure a **Multi-Output Device** so audio reaches both your speakers/headphones (so you can hear) and BlackHole (so it can be recorded).

This is a one-time setup. After it's done, every call you record will include both your voice and the other side.

## Step 1: Install BlackHole

```bash
brew install blackhole-2ch
```

The `setup.sh` script does this for you. If you missed it, run the command manually.

After installing, BlackHole appears as both an input and output device in macOS. You can confirm by running:

```bash
meet devices
```

You should see `BlackHole 2ch` in the list.

## Step 2: Create a Multi-Output Device

Open **Audio MIDI Setup** (⌘-Space → "Audio MIDI Setup"):

1. Click the **`+`** at the bottom-left → **Create Multi-Output Device**.
2. In the right pane, check:
   - Your real output (e.g. `MacBook Pro Speakers`, `AirPods`)
   - `BlackHole 2ch`
3. Rename it something memorable (right-click → Rename) like *"Meeting Capture Output"*.

This is what your Mac will use as its output during meetings. The same audio goes to two places at once: your ears (your real device) and BlackHole (the recorder).

!!! tip "Drift correction"
    If you mix BlackHole with AirPods (Bluetooth), enable "Drift Correction" on the BlackHole row. It compensates for the small clock differences between the two devices.

## Step 3: Switch system Output before a meeting

In **System Settings → Sound → Output**, pick your new Multi-Output Device.

You can switch back to plain headphones / speakers afterwards. Some people leave the Multi-Output as their permanent output and forget about it — both work.

## Verify

1. Open the menu bar app: `meet menubar`.
2. Open the **Capture mode** submenu. "Mic + system audio (via BlackHole)" should be selectable. If it's grayed out, click **Re-scan devices** in the main menu.
3. Open a YouTube video — anything with audible speech.
4. Click **Start Recording**, wait 10 seconds while the video plays and you talk into your mic.
5. Click **Stop Recording**, wait for the summary.
6. The transcript should contain both the video's words and yours.

## Alternative: Aggregate Device

Older Meeting Capture builds required creating an **Aggregate Device** in Audio MIDI Setup that combined your mic + BlackHole into a single input. That's no longer necessary — the app now opens two parallel input streams (your chosen mic + BlackHole) and mixes them with ffmpeg after recording stops.

You can still create an Aggregate Device if you prefer the single-stream workflow. Just pick it from the **Mic device** submenu instead of your real mic, and set Capture mode to "Mic only".

## Troubleshooting

See [Troubleshooting → Only my voice was recorded](troubleshooting.md#only-my-voice-was-recorded).
