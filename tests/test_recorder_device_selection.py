import unittest

from meeting_capture.recorder import (
    _device_priority,
    choose_input_device,
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
