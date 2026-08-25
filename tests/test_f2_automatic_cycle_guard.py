from __future__ import annotations

import inspect
import unittest

from src.platform.f2_automatic_cycle_guard import (
    F2_AUTO_REMOVAL_SCORE_REQUIRED,
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

    def test_at_least_one_on_starts_inspection_but_does_not_approve_itself(self):
        cycle = F2AutomaticCycleState()
        states = {
            "LED_001": "ACESO",
            "LED_002": "APAGADO",
            "LED_003": "APAGADO",
        }

        self.assertTrue(cycle.should_trigger(states, can_trigger=True))
        self.assertEqual(cycle.visible_states(states), states)
        # A classe decide somente o gatilho. OK/NG continua sendo responsabilidade
        # do OperationEngine oficial, portanto não existe qualquer regra de OK aqui.
        self.assertFalse(hasattr(cycle, "is_ok"))

    def test_all_off_board_never_fires_false_ng(self):
        cycle = F2AutomaticCycleState()
        states = {f"LED_{index:03d}": "APAGADO" for index in range(1, 43)}

        for _ in range(20):
            self.assertFalse(cycle.should_trigger(states, can_trigger=True))
        self.assertFalse(cycle.waiting_removal)

    def test_same_board_cannot_trigger_twice_before_removal(self):
        cycle = F2AutomaticCycleState()
        board = {"LED_001": "ACESO", "LED_002": "APAGADO"}

        self.assertTrue(cycle.should_trigger(board, can_trigger=True))
        cycle.mark_inspected()
        self.assertTrue(cycle.waiting_removal)

        for _ in range(10):
            self.assertFalse(cycle.observe_after_result(board))
            self.assertFalse(cycle.should_trigger(board, can_trigger=True))

        self.assertTrue(cycle.waiting_removal)
        self.assertEqual(cycle.removal_score, 0)

    def test_removal_tolerates_one_false_on_frame(self):
        cycle = F2AutomaticCycleState(removal_score_required=5, on_penalty=2)
        cycle.mark_inspected()
        off = {"LED_001": "APAGADO", "LED_002": "APAGADO"}
        flicker = {"LED_001": "ACESO", "LED_002": "APAGADO"}

        self.assertFalse(cycle.observe_after_result(off))
        self.assertFalse(cycle.observe_after_result(off))
        self.assertFalse(cycle.observe_after_result(off))
        self.assertEqual(cycle.removal_score, 3)

        self.assertFalse(cycle.observe_after_result(flicker))
        self.assertEqual(cycle.removal_score, 1)

        self.assertFalse(cycle.observe_after_result(off))
        self.assertFalse(cycle.observe_after_result(off))
        self.assertFalse(cycle.observe_after_result(off))
        self.assertTrue(cycle.observe_after_result(off))
        self.assertFalse(cycle.waiting_removal)
        self.assertEqual(cycle.removal_score, 0)

    def test_second_board_can_trigger_after_confirmed_removal(self):
        cycle = F2AutomaticCycleState(removal_score_required=3)
        first_board = {"LED_001": "ACESO", "LED_002": "APAGADO"}
        empty = {"LED_001": "APAGADO", "LED_002": "APAGADO"}
        second_board = {"LED_001": "APAGADO", "LED_002": "ACESO"}

        self.assertTrue(cycle.should_trigger(first_board, can_trigger=True))
        cycle.mark_inspected()
        for index in range(3):
            removed = cycle.observe_after_result(empty)
        self.assertTrue(removed)
        self.assertFalse(cycle.waiting_removal)
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

    def test_removal_confirmation_has_real_debounce(self):
        self.assertGreaterEqual(F2_AUTO_REMOVAL_SCORE_REQUIRED, 4)

    def test_guard_is_f2_named_and_does_not_patch_display_f3(self):
        import src.platform.f2_automatic_cycle_guard as module

        source = inspect.getsource(module)
        self.assertIn("F2AutomaticCycleGuardMixin", source)
        self.assertNotIn("DisplayProductionF3Window", source)
        self.assertNotIn("DisplayAutomaticCheckF3Mixin", source)


if __name__ == "__main__":
    unittest.main()
