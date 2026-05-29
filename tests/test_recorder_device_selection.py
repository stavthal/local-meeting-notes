import unittest

from meeting_capture.recorder import (
    _device_priority,
    _should_exclude_device,
    choose_input_device,
    find_blackhole_device,
    input_device_candidates,
    probe_input_devices,
    select_active_input_device,
)


DEVICES = [
    {"name": "MacBook Pro Speakers", "max_input_channels": 0},
    {"name": "MacBook Pro Microphone", "max_input_channels": 1},
    {"name": "BlackHole 2ch", "max_input_channels": 2},
    {"name": "Meeting Aggregate Device", "max_input_channels": 4},
]


class RecorderDeviceSelectionTests(unittest.TestCase):
    def test_input_device_candidates_exclude_output_only_devices(self):
        candidates = input_device_candidates(DEVICES)

        self.assertEqual([device.index for device in candidates], [1, 2, 3])

    def test_device_priority_prefers_aggregate_and_loopback_inputs(self):
        self.assertGreater(
            _device_priority("Meeting Aggregate Device"),
            _device_priority("MacBook Pro Microphone"),
        )
        self.assertGreater(
            _device_priority("BlackHole 2ch"),
            _device_priority("MacBook Pro Microphone"),
        )

    def test_input_device_candidates_skip_continuity_and_camera_inputs(self):
        devices = [
            {"name": "MacBook Pro Microphone", "max_input_channels": 1},
            {"name": "Steve's iPhone Microphone", "max_input_channels": 1},
            {"name": "iPad Microphone", "max_input_channels": 1},
            {"name": "FaceTime HD Camera (Built-in)", "max_input_channels": 1},
            {"name": "BlackHole 2ch", "max_input_channels": 2},
        ]

        names = [c.name for c in input_device_candidates(devices)]

        self.assertEqual(names, ["MacBook Pro Microphone", "BlackHole 2ch"])

    def test_should_exclude_device_matches_continuity_and_camera_names(self):
        self.assertTrue(_should_exclude_device("Steve's iPhone Microphone"))
        self.assertTrue(_should_exclude_device("iPad Microphone"))
        self.assertTrue(_should_exclude_device("Apple Watch Microphone"))
        self.assertTrue(_should_exclude_device("FaceTime HD Camera"))
        self.assertFalse(_should_exclude_device("AirPods Pro"))
        self.assertFalse(_should_exclude_device("BlackHole 2ch"))
        self.assertFalse(_should_exclude_device("MacBook Pro Microphone"))

    def test_find_blackhole_device_returns_candidate_when_present(self):
        devices = [
            {"name": "MacBook Pro Microphone", "max_input_channels": 1},
            {"name": "BlackHole 2ch", "max_input_channels": 2},
            {"name": "Stavros's AirPods", "max_input_channels": 1},
        ]
        result = find_blackhole_device(devices)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "BlackHole 2ch")
        self.assertEqual(result.index, 1)

    def test_find_blackhole_device_returns_none_when_missing(self):
        devices = [
            {"name": "MacBook Pro Microphone", "max_input_channels": 1},
            {"name": "Stavros's AirPods", "max_input_channels": 1},
        ]
        self.assertIsNone(find_blackhole_device(devices))

    def test_should_exclude_device_matches_webcam_inputs(self):
        # External USB webcam mics — typically low quality, never the right
        # source for meeting capture. The Creative Cam Sync was in Steve's
        # real device list and was being probed unnecessarily.
        self.assertTrue(_should_exclude_device("Creative Live! Cam Sync 1080p V2 Audio"))
        self.assertTrue(_should_exclude_device("Logitech BRIO Webcam"))
        self.assertTrue(_should_exclude_device("OBS Virtual Camera"))
        # Real personal mics shouldn't get caught by the webcam patterns.
        self.assertFalse(_should_exclude_device("Stavros's AirPods"))
        self.assertFalse(_should_exclude_device("Shure MV7"))

    def test_device_priority_prefers_personal_headsets_over_builtin_mic(self):
        # AirPods, headsets, etc. should rank above the MacBook built-in mic
        # so probing picks them when both have signal.
        self.assertGreater(
            _device_priority("AirPods Pro"),
            _device_priority("MacBook Pro Microphone"),
        )
        self.assertGreater(
            _device_priority("Jabra Evolve 75 Headset"),
            _device_priority("MacBook Pro Microphone"),
        )
        # But virtual/aggregate devices still outrank personal mics — capturing
        # both sides of the call beats capturing only the user's voice.
        self.assertGreater(
            _device_priority("Meeting Aggregate Device"),
            _device_priority("AirPods Pro"),
        )
        self.assertGreater(
            _device_priority("BlackHole 2ch"),
            _device_priority("AirPods Pro"),
        )

    def test_select_active_input_prefers_call_capture_device_with_signal(self):
        selected = select_active_input_device(
            devices=DEVICES,
            rms_probe=lambda candidate: {
                1: 0.25,
                2: 0.04,
                3: 0.06,
            }[candidate.index],
            threshold=0.01,
        )

        self.assertEqual(selected.index, 3)
        self.assertEqual(selected.name, "Meeting Aggregate Device")
        self.assertEqual(selected.max_input_channels, 4)

    def test_select_active_input_falls_back_to_loudest_generic_input(self):
        devices = [
            {"name": "USB Audio Input", "max_input_channels": 1},
            {"name": "External Microphone", "max_input_channels": 1},
        ]

        selected = select_active_input_device(
            devices=devices,
            rms_probe=lambda candidate: {
                0: 0.03,
                1: 0.2,
            }[candidate.index],
            threshold=0.01,
        )

        self.assertEqual(selected.index, 1)

    def test_select_active_input_errors_when_no_input_has_signal(self):
        with self.assertRaisesRegex(RuntimeError, "No input device with audio signal"):
            select_active_input_device(
                devices=DEVICES,
                rms_probe=lambda candidate: 0.0,
                threshold=0.01,
            )

    def test_probe_input_devices_records_signal_for_each_input(self):
        probes = probe_input_devices(
            devices=DEVICES,
            rms_probe=lambda candidate: {
                1: 0.50,
                2: 0.00,
                3: 0.08,
            }[candidate.index],
        )

        self.assertEqual([probe.candidate.index for probe in probes], [1, 2, 3])
        self.assertEqual([probe.rms for probe in probes], [0.50, 0.00, 0.08])

    def test_choose_input_device_falls_back_to_highest_priority_when_no_signal(self):
        # All probes silent — picker should still show with highest-priority
        # candidate as default rather than raising.
        probes = probe_input_devices(
            devices=DEVICES,
            rms_probe=lambda candidate: 0.0,
        )
        captured_default: list[int] = []

        def chooser(_probes, recommended_probe):
            captured_default.append(recommended_probe.candidate.index)
            return recommended_probe.candidate.index

        selected = choose_input_device(probes, threshold=0.01, chooser=chooser)

        self.assertEqual(captured_default, [3])  # Aggregate Device — highest priority
        self.assertEqual(selected.index, 3)
        self.assertEqual(selected.name, "Meeting Aggregate Device")

    def test_choose_input_device_uses_prompted_index(self):
        probes = probe_input_devices(
            devices=DEVICES,
            rms_probe=lambda candidate: {
                1: 0.50,
                2: 0.00,
                3: 0.08,
            }[candidate.index],
        )

        selected = choose_input_device(
            probes,
            threshold=0.01,
            chooser=lambda candidates, recommended: 2,
        )

        self.assertEqual(selected.index, 2)
        self.assertEqual(selected.name, "BlackHole 2ch")


if __name__ == "__main__":
    unittest.main()
