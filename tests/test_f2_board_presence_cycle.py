from __future__ import annotations

import inspect
import unittest

from src.platform.f2_automatic_cycle_guard import (
    F2_AUTO_REFERENCE_EMPTY_FRAMES_REQUIRED,
    F2AutomaticCycleGuardMixin,
    F2AutomaticCycleState,
    F2VisualBoardRemovalDetector,
)
from src.platform.f2_board_presence_references import (
    F2_BOARD_PRESENCE_EMPTY,
    F2_BOARD_PRESENCE_PRESENT,
    F2_BOARD_PRESENCE_UNKNOWN,
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

    def test_runtime_blocks_empty_and_unknown_from_triggering(self):
        source = inspect.getsource(
            F2AutomaticCycleGuardMixin._f2_auto_analyze_current_frame
        )
        self.assertIn("F2_BOARD_PRESENCE_PRESENT", source)
        self.assertIn("F2_BOARD_PRESENCE_UNAVAILABLE", source)
        self.assertIn("presence_allows_trigger", source)
        self.assertNotIn("F2_BOARD_PRESENCE_EMPTY,\n            F2_BOARD_PRESENCE_UNAVAILABLE", source)

    def test_settings_are_rendered_from_f2_cycle_mixin(self):
        source = inspect.getsource(F2AutomaticCycleGuardMixin.abrir_configuracoes)
        self.assertIn("render_settings", source)
        self.assertIn("_f2_board_presence_refs", source)


if __name__ == "__main__":
    unittest.main()
