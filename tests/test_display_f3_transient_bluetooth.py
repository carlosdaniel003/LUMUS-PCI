from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from src.platform.display_auto_check_runtime import DisplayAutomaticCheckF3Mixin


class DisplayF3TransientBluetoothTests(unittest.TestCase):
    def test_bluetooth_aliases_are_transient_but_usb_and_aux_are_not(self):
        for name in ("BLUETOOTH", "Bluetooth", "BLUE", "BT", "CHECK BLUETOOTH"):
            self.assertTrue(
                DisplayAutomaticCheckF3Mixin._display_auto_is_transient_check(
                    {"check_name": name}
                )
            )

        for name in ("H1", "USB", "AUX"):
            self.assertFalse(
                DisplayAutomaticCheckF3Mixin._display_auto_is_transient_check(
                    {"check_name": name}
                )
            )

    def test_bluetooth_advances_on_first_conforming_fresh_frame(self):
        app = DisplayAutomaticCheckF3Mixin.__new__(DisplayAutomaticCheckF3Mixin)
        app.display_f3_ativo = True
        app.display_f3_result_after_id = None
        app._display_project_config_window = None
        app.camera_frame_atual = np.zeros((10, 10, 3), dtype=np.uint8)
        app.camera_ultimo_frame_id = 10
        app.display_f3_window = SimpleNamespace(
            set_preview_status=lambda *_args, **_kwargs: None
        )
        app.display_project_repository = SimpleNamespace(
            obter_projeto_ativo=lambda: "DISPLAY A"
        )
        app.display_check_runtime = SimpleNamespace(
            snapshot=lambda: {
                "current_index": 1,
                "current_check": {
                    "id": "CHECK_002",
                    "name": "BLUETOOTH",
                },
            }
        )
        app._display_auto_analyzer = SimpleNamespace(
            repository=app.display_project_repository,
            analyze=lambda **_kwargs: {
                "ready": True,
                "approved": True,
                "matched_mask_count": 2,
                "active_mask_count": 2,
            },
        )
        app._display_auto_signature = None
        app._display_auto_last_decision = None
        app._display_auto_stable_frames = 0
        app._display_auto_transition_frames = 1
        app._display_auto_last_frame_token = None
        app._display_auto_last_analysis = None
        app._obter_rotacao_visual_display_f3 = lambda: 0

        events = []
        app.registrar_resultado_check_display_f3 = (
            lambda approved: events.append(bool(approved))
            or {"event": "check_advanced"}
        )

        app._process_display_auto_check()

        self.assertEqual([True], events)
        self.assertEqual(0, app._display_auto_stable_frames)


if __name__ == "__main__":
    unittest.main()
