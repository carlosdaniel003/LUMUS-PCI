from __future__ import annotations

import unittest

# Carrega as extensões oficiais do Display/F3, incluindo o gate estrito.
import src.platform.display_check_sequence_runtime  # noqa: F401
from src.platform.display_auto_check_runtime import DisplayAutomaticCheckF3Mixin


class DisplayF3StrictManualTransitionGateTests(unittest.TestCase):
    def test_strict_gate_is_installed_in_f3_runtime(self):
        self.assertTrue(
            getattr(
                DisplayAutomaticCheckF3Mixin,
                "_odin_display_strict_manual_transition_gate",
                False,
            )
        )

    def test_partial_target_pattern_never_releases_manual_gate(self):
        partial_usb = {
            "ready": True,
            "approved": False,
            "matched_mask_count": 2,
            "active_mask_count": 4,
            "mask_results": [
                {
                    "mask_id": "USB_A",
                    "expected": "on",
                    "classified": "on",
                    "matched": True,
                    "confidence": 0.99,
                },
                {
                    "mask_id": "USB_B",
                    "expected": "off",
                    "classified": "off",
                    "matched": True,
                    "confidence": 0.99,
                },
                {
                    "mask_id": "USB_C",
                    "expected": "on",
                    "classified": "off",
                    "matched": False,
                    "confidence": 0.99,
                },
                {
                    "mask_id": "USB_D",
                    "expected": "off",
                    "classified": "on",
                    "matched": False,
                    "confidence": 0.99,
                },
            ],
        }

        self.assertFalse(
            DisplayAutomaticCheckF3Mixin._display_auto_has_manual_entry_evidence(
                partial_usb
            )
        )

    def test_complete_target_pattern_releases_manual_gate(self):
        complete_usb = {
            "ready": True,
            "approved": True,
            "matched_mask_count": 4,
            "active_mask_count": 4,
        }

        self.assertTrue(
            DisplayAutomaticCheckF3Mixin._display_auto_has_manual_entry_evidence(
                complete_usb
            )
        )

    def test_not_ready_never_releases_manual_gate(self):
        self.assertFalse(
            DisplayAutomaticCheckF3Mixin._display_auto_has_manual_entry_evidence(
                {"ready": False, "approved": True}
            )
        )


if __name__ == "__main__":
    unittest.main()
