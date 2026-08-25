from __future__ import annotations

import inspect
import unittest

from src.platform.f2_automatic_cycle_guard import (
    F2_AUTO_REFERENCE_EMPTY_FRAMES_REQUIRED,
    F2AutomaticCycleGuardMixin,
    F2AutomaticCycleState,
    F2VisualBoardRemovalDetector,
)
from src.platform.f2_automatic_presence_cycle_policy import (
    F2AutomaticPresenceCyclePolicyMixin,
)
from src.platform.f2_board_presence_references import (
    F2_BOARD_PRESENCE_EMPTY,
    F2_BOARD_PRESENCE_PRESENT,
    F2_BOARD_PRESENCE_UNKNOWN,
)
from src.platform.f2_board_status_display import (
    F2_BOARD_STATUS_EMPTY,
    F2_BOARD_STATUS_OFF,
    F2_BOARD_STATUS_ON,
    F2_BOARD_STATUS_UNKNOWN,
    F2BoardStatusDisplayMixin,
    status_visual_placa_f2,
)


class F2BoardPresenceCycleTests(unittest.TestCase):
    @staticmethod
    def _guard_waiting_removal():
        guard = object.__new__(F2AutomaticCycleGuardMixin)
        guard._f2_auto_cycle = F2AutomaticCycleState()
        guard._f2_auto_cycle.mark_inspected()
        guard._f2_auto_reference_empty_frames = 0
        guard._f2_auto_visual_removal = F2VisualBoardRemovalDetector()
        return guard

    def test_same_present_board_never_rearms(self):
        guard = self._guard_waiting_removal()
        for _ in range(200):
            self.assertFalse(
                guard._f2_auto_observe_removal(
                    frame=None,
                    presence=F2_BOARD_PRESENCE_PRESENT,
                )
            )
        self.assertTrue(guard._f2_auto_cycle.waiting_removal)
        self.assertEqual(0, guard._f2_auto_reference_empty_frames)

    def test_ambiguous_scene_never_rearms_or_accumulates_empty_time(self):
        guard = self._guard_waiting_removal()
        guard._f2_auto_reference_empty_frames = 2
        self.assertFalse(
            guard._f2_auto_observe_removal(
                frame=None,
                presence=F2_BOARD_PRESENCE_UNKNOWN,
            )
        )
        self.assertEqual(0, guard._f2_auto_reference_empty_frames)
        self.assertTrue(guard._f2_auto_cycle.waiting_removal)

    def test_only_confirmed_empty_support_rearms(self):
        guard = self._guard_waiting_removal()
        for index in range(F2_AUTO_REFERENCE_EMPTY_FRAMES_REQUIRED - 1):
            self.assertFalse(
                guard._f2_auto_observe_removal(
                    frame=None,
                    presence=F2_BOARD_PRESENCE_EMPTY,
                )
            )
            self.assertEqual(index + 1, guard._f2_auto_reference_empty_frames)

        self.assertTrue(
            guard._f2_auto_observe_removal(
                frame=None,
                presence=F2_BOARD_PRESENCE_EMPTY,
            )
        )
        self.assertFalse(guard._f2_auto_cycle.waiting_removal)
        self.assertEqual(0, guard._f2_auto_reference_empty_frames)

    def test_present_frame_resets_partial_empty_confirmation(self):
        guard = self._guard_waiting_removal()
        for _ in range(3):
            self.assertFalse(
                guard._f2_auto_observe_removal(None, F2_BOARD_PRESENCE_EMPTY)
            )
        self.assertEqual(3, guard._f2_auto_reference_empty_frames)

        self.assertFalse(
            guard._f2_auto_observe_removal(None, F2_BOARD_PRESENCE_PRESENT)
        )
        self.assertEqual(0, guard._f2_auto_reference_empty_frames)
        self.assertTrue(guard._f2_auto_cycle.waiting_removal)

    def test_runtime_usa_presenca_para_rearme_e_nao_como_gate_do_led(self):
        source = inspect.getsource(
            F2AutomaticPresenceCyclePolicyMixin._f2_auto_analyze_current_frame
        )
        self.assertIn("_f2_auto_observe_removal", source)
        self.assertIn("can_trigger=self._f2_auto_can_trigger()", source)
        self.assertNotIn("presence_allows_trigger", source)
        self.assertNotIn("F2_BOARD_PRESENCE_PRESENT", source)

    def test_settings_are_rendered_from_f2_cycle_mixin(self):
        source = inspect.getsource(F2AutomaticCycleGuardMixin.abrir_configuracoes)
        self.assertIn("render_settings", source)
        self.assertIn("_f2_board_presence_refs", source)

    def test_status_visual_identifica_placa_ligada(self):
        status = status_visual_placa_f2(
            F2_BOARD_PRESENCE_PRESENT,
            {"LED_001": "ACESO", "LED_002": "APAGADO"},
        )
        self.assertEqual(F2_BOARD_STATUS_ON, status)

    def test_status_visual_identifica_placa_desligada(self):
        status = status_visual_placa_f2(
            F2_BOARD_PRESENCE_PRESENT,
            {"LED_001": "APAGADO", "LED_002": "APAGADO"},
        )
        self.assertEqual(F2_BOARD_STATUS_OFF, status)

    def test_status_visual_considera_pouca_luz_como_placa_ligada(self):
        status = status_visual_placa_f2(
            F2_BOARD_PRESENCE_PRESENT,
            {"LED_001": "POUCA_LUZ", "LED_002": "APAGADO"},
        )
        self.assertEqual(F2_BOARD_STATUS_ON, status)

    def test_status_visual_identifica_suporte_vazio(self):
        status = status_visual_placa_f2(
            F2_BOARD_PRESENCE_EMPTY,
            {"LED_001": "APAGADO"},
        )
        self.assertEqual(F2_BOARD_STATUS_EMPTY, status)

    def test_status_visual_ambiguous_fica_identificando(self):
        status = status_visual_placa_f2(
            F2_BOARD_PRESENCE_UNKNOWN,
            {"LED_001": "ACESO"},
        )
        self.assertEqual(F2_BOARD_STATUS_UNKNOWN, status)

    def test_status_display_intercepts_only_publicacao_f2(self):
        source = inspect.getsource(F2BoardStatusDisplayMixin._f2_auto_publish_states)
        self.assertIn("set_board_presence_status", source)
        self.assertIn("super()._f2_auto_publish_states", source)
        self.assertNotIn("DisplayProductionF3", source)
        self.assertNotIn("DisplayAutomaticCheckF3", source)


if __name__ == "__main__":
    unittest.main()
