from __future__ import annotations

import inspect
import unittest

from src.platform.f2_automatic_cycle_guard import (
    F2_AUTO_REMOVAL_SCORE_REQUIRED,
    F2_AUTO_TRIGGER_ON_FRAMES_REQUIRED,
    F2AutomaticCycleGuardMixin,
    F2AutomaticCycleState,
)


class F2AutomaticCycleGuardTests(unittest.TestCase):
    def test_start_without_board_is_ignored_and_neutral(self):
        cycle = F2AutomaticCycleState()
        states = {
            "LED_001": "APAGADO",
            "LED_002": "APAGADO",
            "LED_003": "APAGADO",
        }

        self.assertFalse(cycle.should_trigger(states, can_trigger=True))
        self.assertEqual(cycle.visible_states(states), {})
        self.assertFalse(cycle.waiting_removal)

    def test_on_requires_two_fresh_frames_before_trigger(self):
        cycle = F2AutomaticCycleState(trigger_on_frames_required=2)
        states = {
            "LED_001": "ACESO",
            "LED_002": "APAGADO",
            "LED_003": "APAGADO",
        }

        self.assertFalse(cycle.should_trigger(states, can_trigger=True))
        self.assertTrue(cycle.should_trigger(states, can_trigger=True))
        self.assertEqual(cycle.visible_states(states), states)
        # A classe decide somente o gatilho. OK/NG continua sendo responsabilidade
        # do OperationEngine oficial, portanto não existe qualquer regra de OK aqui.
        self.assertFalse(hasattr(cycle, "is_ok"))

    def test_single_on_glitch_does_not_trigger(self):
        cycle = F2AutomaticCycleState(trigger_on_frames_required=2)
        on = {"LED_001": "ACESO"}
        off = {"LED_001": "APAGADO"}

        self.assertFalse(cycle.should_trigger(on, can_trigger=True))
        self.assertFalse(cycle.should_trigger(off, can_trigger=True))
        self.assertFalse(cycle.should_trigger(on, can_trigger=True))

    def test_all_off_board_never_fires_false_ng(self):
        cycle = F2AutomaticCycleState()
        states = {f"LED_{index:03d}": "APAGADO" for index in range(1, 43)}

        for _ in range(20):
            self.assertFalse(cycle.should_trigger(states, can_trigger=True))
        self.assertFalse(cycle.waiting_removal)

    def test_same_board_cannot_trigger_twice_before_removal(self):
        cycle = F2AutomaticCycleState(trigger_on_frames_required=2)
        board = {"LED_001": "ACESO", "LED_002": "APAGADO"}

        self.assertFalse(cycle.should_trigger(board, can_trigger=True))
        self.assertTrue(cycle.should_trigger(board, can_trigger=True))
        cycle.mark_inspected()
        self.assertTrue(cycle.waiting_removal)

        for _ in range(100):
            self.assertFalse(cycle.observe_after_result(board))
            self.assertFalse(cycle.should_trigger(board, can_trigger=True))

        self.assertTrue(cycle.waiting_removal)
        self.assertEqual(cycle.removal_score, 0)

    def test_any_on_during_removal_resets_off_sequence(self):
        cycle = F2AutomaticCycleState(removal_score_required=5)
        cycle.mark_inspected()
        off = {"LED_001": "APAGADO", "LED_002": "APAGADO"}
        on = {"LED_001": "ACESO", "LED_002": "APAGADO"}

        for _ in range(4):
            self.assertFalse(cycle.observe_after_result(off))
        self.assertEqual(cycle.removal_score, 4)

        self.assertFalse(cycle.observe_after_result(on))
        self.assertEqual(cycle.removal_score, 0)

        for _ in range(4):
            self.assertFalse(cycle.observe_after_result(off))
        self.assertTrue(cycle.observe_after_result(off))
        self.assertFalse(cycle.waiting_removal)

    def test_second_board_can_trigger_after_confirmed_removal(self):
        cycle = F2AutomaticCycleState(
            removal_score_required=3,
            trigger_on_frames_required=2,
        )
        first_board = {"LED_001": "ACESO", "LED_002": "APAGADO"}
        empty = {"LED_001": "APAGADO", "LED_002": "APAGADO"}
        second_board = {"LED_001": "APAGADO", "LED_002": "ACESO"}

        self.assertFalse(cycle.should_trigger(first_board, can_trigger=True))
        self.assertTrue(cycle.should_trigger(first_board, can_trigger=True))
        cycle.mark_inspected()
        removed = False
        for _ in range(3):
            removed = cycle.observe_after_result(empty)
        self.assertTrue(removed)
        self.assertFalse(cycle.waiting_removal)
        self.assertFalse(cycle.should_trigger(second_board, can_trigger=True))
        self.assertTrue(cycle.should_trigger(second_board, can_trigger=True))

    def test_low_light_only_is_neutral_before_board_detection(self):
        cycle = F2AutomaticCycleState()
        states = {"LED_001": "POUCA_LUZ", "LED_002": "APAGADO"}

        self.assertFalse(cycle.should_trigger(states, can_trigger=True))
        self.assertEqual(cycle.visible_states(states), {})

    def test_low_light_remains_visible_while_inspected_board_waits_removal(self):
        cycle = F2AutomaticCycleState()
        states = {"LED_001": "POUCA_LUZ", "LED_002": "APAGADO"}
        cycle.mark_inspected()

        self.assertEqual(cycle.visible_states(states), states)

    def test_low_light_noise_becomes_neutral_after_removal_confirmation(self):
        cycle = F2AutomaticCycleState(removal_score_required=2)
        states = {"LED_001": "POUCA_LUZ", "LED_002": "APAGADO"}
        cycle.mark_inspected()

        self.assertFalse(cycle.observe_after_result(states))
        self.assertEqual(cycle.visible_states(states), states)
        self.assertTrue(cycle.observe_after_result(states))
        self.assertFalse(cycle.waiting_removal)
        self.assertEqual(cycle.visible_states(states), {})

    def test_result_hold_is_explicitly_detected(self):
        guard = object.__new__(F2AutomaticCycleGuardMixin)
        guard._operacao_resultado_after_id = "after-result"
        self.assertTrue(guard._f2_auto_result_hold_active())

        guard._operacao_resultado_after_id = None
        self.assertFalse(guard._f2_auto_result_hold_active())

    def test_result_hold_protects_removal_observation_in_runtime(self):
        source = inspect.getsource(
            F2AutomaticCycleGuardMixin._f2_auto_analyze_current_frame
        )
        self.assertIn("_f2_auto_result_hold_active", source)
        self.assertIn("observe_after_result", source)

    def test_default_removal_confirmation_is_over_one_second(self):
        self.assertGreaterEqual(F2_AUTO_REMOVAL_SCORE_REQUIRED, 10)

    def test_default_entry_has_stability_debounce(self):
        self.assertGreaterEqual(F2_AUTO_TRIGGER_ON_FRAMES_REQUIRED, 2)

    def test_guard_is_f2_named_and_does_not_patch_display_f3(self):
        import src.platform.f2_automatic_cycle_guard as module

        source = inspect.getsource(module)
        self.assertIn("F2AutomaticCycleGuardMixin", source)
        self.assertNotIn("DisplayProductionF3Window", source)
        self.assertNotIn("DisplayAutomaticCheckF3Mixin", source)


if __name__ == "__main__":
    unittest.main()
