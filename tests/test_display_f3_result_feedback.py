from __future__ import annotations

import unittest

from src.platform.display_auto_check_runtime import DisplayAutomaticCheckF3Mixin
from src.platform.display_production_f3_window import DisplayProductionF3Window
from src.platform.display_result_feedback import (
    DISPLAY_F3_RESULT_HOLD_MS,
    obter_feedback_espera_display_f3,
)


class DisplayF3ResultFeedbackTests(unittest.TestCase):
    def test_result_screen_is_held_for_two_seconds(self):
        self.assertEqual(2000, DISPLAY_F3_RESULT_HOLD_MS)
        self.assertEqual(
            2000,
            DisplayAutomaticCheckF3Mixin.DISPLAY_F3_RESULT_HOLD_MS,
        )

    def test_ok_waiting_feedback_matches_f2_dark_green(self):
        feedback = obter_feedback_espera_display_f3(
            {
                "current_index": 0,
                "completed_ids": (),
                "last_result": "OK",
            }
        )
        self.assertEqual(
            ("OK", "Última placa: OK • aguardando H1 da próxima placa"),
            feedback,
        )
        self.assertEqual("#14532D", DisplayProductionF3Window.COLOR_WAITING_AFTER_OK)

    def test_ng_waiting_feedback_matches_f2_dark_red(self):
        feedback = obter_feedback_espera_display_f3(
            {
                "current_index": 0,
                "completed_ids": (),
                "last_result": "NG",
            }
        )
        self.assertEqual(
            ("NG", "Última placa: NG • aguardando H1 da próxima placa"),
            feedback,
        )
        self.assertEqual("#7F1D1D", DisplayProductionF3Window.COLOR_WAITING_AFTER_NG)

    def test_previous_result_feedback_stops_after_h1_is_completed(self):
        feedback = obter_feedback_espera_display_f3(
            {
                "current_index": 1,
                "completed_ids": ("CHECK_H1",),
                "last_result": "OK",
            }
        )
        self.assertIsNone(feedback)

    def test_without_previous_result_waiting_state_stays_neutral(self):
        self.assertIsNone(
            obter_feedback_espera_display_f3(
                {
                    "current_index": 0,
                    "completed_ids": (),
                    "last_result": None,
                }
            )
        )

    def test_f3_window_received_feedback_extension(self):
        self.assertTrue(DisplayProductionF3Window._odin_display_result_feedback)


if __name__ == "__main__":
    unittest.main()
