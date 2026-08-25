from __future__ import annotations

import inspect
import unittest

import cv2
import numpy as np

from src.models.led_selection import LedSelection
from src.platform.f2_automatic_cycle_guard import (
    F2_AUTO_REMOVAL_SCORE_REQUIRED,
    F2_AUTO_TRIGGER_ON_FRAMES_REQUIRED,
    F2_AUTO_VISUAL_FIRST_REMOVAL_FRAMES_REQUIRED,
    F2_AUTO_VISUAL_KNOWN_EMPTY_FRAMES_REQUIRED,
    F2AutomaticCycleGuardMixin,
    F2AutomaticCycleState,
    F2VisualBoardRemovalDetector,
)


class F2AutomaticCycleGuardTests(unittest.TestCase):
    @staticmethod
    def _leds():
        return [
            LedSelection("LED_001", 220, 180, 10),
            LedSelection("LED_002", 320, 180, 10),
            LedSelection("LED_003", 220, 280, 10),
            LedSelection("LED_004", 320, 280, 10),
        ]

    @staticmethod
    def _scene(
        *,
        board: bool = True,
        leds_on: bool = False,
        brightness_shift: int = 0,
        hand_x: int | None = None,
    ):
        base = max(0, min(255, 35 + int(brightness_shift)))
        frame = np.full((480, 640, 3), base, dtype=np.uint8)

        if board:
            board_level = max(0, min(255, 105 + int(brightness_shift)))
            cv2.rectangle(
                frame,
                (150, 105),
                (490, 370),
                (board_level, board_level, board_level),
                thickness=-1,
            )
            # Estrutura fixa da placa fora das ROIs dos LEDs.
            cv2.rectangle(frame, (175, 130), (465, 345), (70, 70, 70), 3)
            cv2.line(frame, (180, 235), (460, 235), (150, 150, 150), 3)
            cv2.line(frame, (370, 130), (370, 345), (155, 155, 155), 3)

        led_level = 245 if leds_on else 55
        for led in F2AutomaticCycleGuardTests._leds():
            cv2.circle(
                frame,
                (led.centro_x, led.centro_y),
                8,
                (led_level, led_level, led_level),
                thickness=-1,
            )

        if hand_x is not None:
            x1 = max(0, int(hand_x))
            x2 = min(639, x1 + 150)
            cv2.rectangle(frame, (x1, 120), (x2, 350), (190, 160, 130), -1)

        return frame

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

    def test_same_board_cannot_trigger_twice_while_waiting_visual_removal(self):
        cycle = F2AutomaticCycleState(trigger_on_frames_required=2)
        board = {"LED_001": "ACESO", "LED_002": "APAGADO"}

        self.assertFalse(cycle.should_trigger(board, can_trigger=True))
        self.assertTrue(cycle.should_trigger(board, can_trigger=True))
        cycle.mark_inspected()

        for _ in range(100):
            self.assertFalse(cycle.should_trigger(board, can_trigger=True))

        self.assertTrue(cycle.waiting_removal)

    def test_led_on_off_does_not_count_as_visual_removal(self):
        detector = F2VisualBoardRemovalDetector(
            first_removal_frames_required=3,
            known_empty_frames_required=2,
        )
        leds = self._leds()
        self.assertTrue(
            detector.capture_board(
                self._scene(board=True, leds_on=True),
                leds,
            )
        )

        # A placa é exatamente a mesma; apenas os LEDs desligam. Como as ROIs
        # são excluídas da comparação, isso nunca pode liberar um novo ciclo.
        for _ in range(40):
            self.assertFalse(
                detector.observe_removal(
                    self._scene(board=True, leds_on=False)
                )
            )

        self.assertIsNone(detector.empty_reference)
        self.assertIsNotNone(detector.board_reference)

    def test_small_global_light_change_does_not_count_as_removal(self):
        detector = F2VisualBoardRemovalDetector(first_removal_frames_required=3)
        leds = self._leds()
        detector.capture_board(self._scene(board=True), leds)

        for shift in (3, 6, 8, 5, 2, 7, 4, 6):
            self.assertFalse(
                detector.observe_removal(
                    self._scene(board=True, brightness_shift=shift)
                )
            )

        self.assertIsNone(detector.empty_reference)

    def test_moving_hand_does_not_become_empty_reference(self):
        detector = F2VisualBoardRemovalDetector(first_removal_frames_required=3)
        leds = self._leds()
        detector.capture_board(self._scene(board=True, leds_on=True), leds)

        # Há grande mudança visual, mas a cena não fica estável; portanto uma
        # mão passando pela câmera não equivale a placa retirada.
        for hand_x in (80, 130, 180, 230, 280, 330, 260, 190, 120):
            self.assertFalse(
                detector.observe_removal(
                    self._scene(board=True, leds_on=True, hand_x=hand_x)
                )
            )

        self.assertIsNone(detector.empty_reference)

    def test_first_real_removal_learns_empty_jig(self):
        detector = F2VisualBoardRemovalDetector(
            first_removal_frames_required=3,
            known_empty_frames_required=2,
        )
        leds = self._leds()
        detector.capture_board(self._scene(board=True, leds_on=True), leds)
        empty = self._scene(board=False, leds_on=False)

        # Primeiro frame ainda contém a transição placa -> suporte vazio.
        self.assertFalse(detector.observe_removal(empty))
        self.assertFalse(detector.observe_removal(empty))
        self.assertFalse(detector.observe_removal(empty))
        self.assertTrue(detector.observe_removal(empty))
        self.assertIsNotNone(detector.empty_reference)
        self.assertIsNone(detector.board_reference)

    def test_known_empty_reference_rearms_second_board_without_led_state(self):
        detector = F2VisualBoardRemovalDetector(
            first_removal_frames_required=2,
            known_empty_frames_required=2,
        )
        leds = self._leds()
        empty = self._scene(board=False)

        detector.capture_board(self._scene(board=True, leds_on=True), leds)
        self.assertFalse(detector.observe_removal(empty))
        self.assertFalse(detector.observe_removal(empty))
        self.assertTrue(detector.observe_removal(empty))
        self.assertIsNotNone(detector.empty_reference)

        # Segunda placa: desligar LEDs não aproxima a estrutura da cena da
        # referência do suporte vazio.
        detector.capture_board(self._scene(board=True, leds_on=True), leds)
        for _ in range(20):
            self.assertFalse(
                detector.observe_removal(
                    self._scene(board=True, leds_on=False)
                )
            )

        # Somente a volta real ao suporte vazio libera outra placa.
        self.assertFalse(detector.observe_removal(empty))
        self.assertTrue(detector.observe_removal(empty))

    def test_cycle_rearms_only_after_visual_detector_confirms_removal(self):
        cycle = F2AutomaticCycleState(trigger_on_frames_required=2)
        detector = F2VisualBoardRemovalDetector(
            first_removal_frames_required=2,
            known_empty_frames_required=2,
        )
        leds = self._leds()
        first_states = {"LED_001": "ACESO"}
        second_states = {"LED_002": "ACESO"}

        self.assertFalse(cycle.should_trigger(first_states, can_trigger=True))
        self.assertTrue(cycle.should_trigger(first_states, can_trigger=True))
        cycle.mark_inspected()
        detector.capture_board(self._scene(board=True, leds_on=True), leds)

        for _ in range(10):
            self.assertFalse(
                detector.observe_removal(
                    self._scene(board=True, leds_on=False)
                )
            )
            self.assertFalse(cycle.should_trigger(first_states, can_trigger=True))

        empty = self._scene(board=False)
        self.assertFalse(detector.observe_removal(empty))
        self.assertFalse(detector.observe_removal(empty))
        self.assertTrue(detector.observe_removal(empty))
        self.assertTrue(cycle.confirm_removal())

        self.assertFalse(cycle.should_trigger(second_states, can_trigger=True))
        self.assertTrue(cycle.should_trigger(second_states, can_trigger=True))

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

    def test_result_hold_is_explicitly_detected(self):
        guard = object.__new__(F2AutomaticCycleGuardMixin)
        guard._operacao_resultado_after_id = "after-result"
        self.assertTrue(guard._f2_auto_result_hold_active())

        guard._operacao_resultado_after_id = None
        self.assertFalse(guard._f2_auto_result_hold_active())

    def test_result_hold_protects_visual_removal_observation_in_runtime(self):
        source = inspect.getsource(
            F2AutomaticCycleGuardMixin._f2_auto_analyze_current_frame
        )
        self.assertIn("_f2_auto_result_hold_active", source)
        self.assertIn("_f2_auto_observe_removal", source)

    def test_mark_inspected_captures_current_frame_as_board_reference(self):
        guard = object.__new__(F2AutomaticCycleGuardMixin)
        guard._f2_auto_cycle = F2AutomaticCycleState()
        guard._f2_auto_visual_removal = F2VisualBoardRemovalDetector()
        guard.camera_frame_atual = self._scene(board=True, leds_on=True)
        guard.operacao_leds_preview = self._leds()

        guard._f2_auto_mark_inspected()

        self.assertTrue(guard._f2_auto_cycle.waiting_removal)
        self.assertIsNotNone(guard._f2_auto_visual_removal.board_reference)
        self.assertIsNotNone(guard._f2_auto_visual_removal.valid_mask)

    def test_default_first_visual_removal_is_conservative(self):
        self.assertGreaterEqual(F2_AUTO_REMOVAL_SCORE_REQUIRED, 6)
        self.assertGreaterEqual(F2_AUTO_VISUAL_FIRST_REMOVAL_FRAMES_REQUIRED, 6)

    def test_known_empty_still_requires_multiple_frames(self):
        self.assertGreaterEqual(F2_AUTO_VISUAL_KNOWN_EMPTY_FRAMES_REQUIRED, 3)

    def test_default_entry_has_stability_debounce(self):
        self.assertGreaterEqual(F2_AUTO_TRIGGER_ON_FRAMES_REQUIRED, 2)

    def test_guard_is_visual_only_and_does_not_patch_display_f3(self):
        import src.platform.f2_automatic_cycle_guard as module

        source = inspect.getsource(module)
        self.assertIn("F2VisualBoardRemovalDetector", source)
        self.assertNotIn("gpio_trigger_service", source)
        self.assertNotIn("DisplayProductionF3Window", source)
        self.assertNotIn("DisplayAutomaticCheckF3Mixin", source)


if __name__ == "__main__":
    unittest.main()
