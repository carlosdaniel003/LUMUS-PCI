from __future__ import annotations

import inspect
import unittest

import src.platform.display_f3_h1_single_frame_probe as module


class _App:
    @staticmethod
    def _display_auto_is_reference_gate(context):
        return int((context or {}).get("current_index", -1)) == 0

    @staticmethod
    def _display_auto_is_transient_check(context):
        return str((context or {}).get("check_name") or "").upper() == "BLUE"


class DisplayF3H1SingleFrameProbeTests(unittest.TestCase):
    def test_h1_first_check_needs_one_exact_positive_frame(self):
        result = module.frames_necessarios_sonda_positiva_f3(
            _App(),
            {"current_index": 0, "check_name": "H1"},
        )
        self.assertEqual(1, result)

    def test_blue_needs_one_exact_positive_frame(self):
        result = module.frames_necessarios_sonda_positiva_f3(
            _App(),
            {"current_index": 1, "check_name": "BLUE"},
        )
        self.assertEqual(1, result)

    def test_stable_usb_keeps_two_frames(self):
        result = module.frames_necessarios_sonda_positiva_f3(
            _App(),
            {"current_index": 2, "check_name": "USB"},
        )
        self.assertEqual(2, result)

    def test_module_has_no_f2_dependency(self):
        source = inspect.getsource(module)
        self.assertNotIn("src.platform.f2_", source)
        self.assertNotIn("F2Automatic", source)


if __name__ == "__main__":
    unittest.main()
