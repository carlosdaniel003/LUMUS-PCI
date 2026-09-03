from __future__ import annotations

import inspect
import unittest

import src.platform.display_f3_probe_rearm_guard as module


class _App:
    def __init__(
        self,
        *,
        waiting_empty: bool = False,
        waiting_new_board: bool = False,
    ) -> None:
        self._display_f3_waiting_empty_rearm = waiting_empty
        self._display_f3_waiting_new_board_after_empty = waiting_new_board
        self._display_f3_live_probe_ok_frames = 4
        self._display_f3_live_probe_signature = ("TESTE", "CHECK_001")


class DisplayF3ProbeRearmGuardTests(unittest.TestCase):
    @staticmethod
    def _context() -> dict:
        return {
            "project_name": "TESTE",
            "check_id": "CHECK_001",
            "check_name": "H1",
            "current_index": 0,
        }

    def test_terminal_waiting_empty_blocks_recycled_h1(self):
        app = _App(waiting_empty=True)
        calls = []
        analysis = {"ready": True, "approved": True}

        def original(*args):
            calls.append(args)
            return {"advanced": True}

        result = module.avancar_sonda_com_guard_rearme_display_f3(
            app,
            self._context(),
            analysis,
            {"confirm": True, "frames": 1, "required": 1},
            original,
        )

        self.assertFalse(result["advanced"])
        self.assertEqual("aguardando_rearme_fisico", result["reason"])
        self.assertTrue(result["waiting_empty_rearm"])
        self.assertEqual([], calls)
        self.assertEqual(0, app._display_f3_live_probe_ok_frames)
        self.assertIsNone(app._display_f3_live_probe_signature)
        self.assertTrue(analysis["positive_probe_blocked"])

    def test_waiting_new_board_after_empty_also_blocks_probe(self):
        app = _App(waiting_new_board=True)
        calls = []

        def original(*args):
            calls.append(args)
            return {"advanced": True}

        result = module.avancar_sonda_com_guard_rearme_display_f3(
            app,
            self._context(),
            {"ready": True, "approved": True},
            {"confirm": True, "frames": 1, "required": 1},
            original,
        )

        self.assertFalse(result["advanced"])
        self.assertTrue(result["waiting_new_board_after_empty"])
        self.assertEqual([], calls)

    def test_normal_cycle_delegates_to_original_probe_advance(self):
        app = _App()
        calls = []

        def original(*args):
            calls.append(args)
            return {"advanced": True, "reason": "normal"}

        result = module.avancar_sonda_com_guard_rearme_display_f3(
            app,
            self._context(),
            {"ready": True, "approved": True},
            {"confirm": True},
            original,
        )

        self.assertTrue(result["advanced"])
        self.assertEqual("normal", result["reason"])
        self.assertEqual(1, len(calls))

    def test_module_is_f3_only(self):
        source = inspect.getsource(module)
        self.assertNotIn("src.platform.f2_", source)
        self.assertNotIn("F2Automatic", source)


if __name__ == "__main__":
    unittest.main()
