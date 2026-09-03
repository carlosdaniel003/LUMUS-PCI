from __future__ import annotations

import inspect
import unittest
from collections import deque

import src.platform.display_f3_runtime_performance_guard as module


class _Window:
    def __init__(self, visible=True):
        self.visible = visible


class _App:
    def __init__(self):
        self.display_f3_ativo = True
        self.display_f3_result_after_id = None
        self._display_f3_waiting_empty_rearm = False
        self._display_f3_waiting_new_board_after_empty = False
        self.display_f3_window = _Window(True)
        self.configuration_open = False
        self.camera_ultimo_frame_id = 1
        self._display_f3_operational_state = {
            "kind": "check",
            "allow_auto": True,
            "physical_state_key": "check:CHECK_001",
            "reference_scores": {"check:CHECK_001": 0.91},
        }

    def _display_auto_configuration_open(self):
        return self.configuration_open

    def _obter_rotacao_visual_display_f3(self):
        return 0


class DisplayF3RuntimePerformanceGuardTests(unittest.TestCase):
    def test_hidden_probe_pauses_while_configuration_is_open(self):
        app = _App()
        app.configuration_open = True
        self.assertFalse(module.sonda_oculta_permitida_display_f3(app))

    def test_hidden_probe_pauses_during_result_rearm_or_hidden_window(self):
        app = _App()
        app.display_f3_result_after_id = "result-after"
        self.assertFalse(module.sonda_oculta_permitida_display_f3(app))

        app.display_f3_result_after_id = None
        app._display_f3_waiting_empty_rearm = True
        self.assertFalse(module.sonda_oculta_permitida_display_f3(app))

        app._display_f3_waiting_empty_rearm = False
        app._display_f3_waiting_new_board_after_empty = True
        self.assertFalse(module.sonda_oculta_permitida_display_f3(app))

        app._display_f3_waiting_new_board_after_empty = False
        app.display_f3_window.visible = False
        self.assertFalse(module.sonda_oculta_permitida_display_f3(app))

    def test_hidden_probe_remains_available_in_active_f3_production(self):
        self.assertTrue(module.sonda_oculta_permitida_display_f3(_App()))

    def test_trace_sampling_does_not_record_every_frame(self):
        app = _App()
        context = {
            "project_name": "TESTE",
            "check_id": "CHECK_001",
            "check_name": "H1",
        }
        analysis = {"ready": True, "approved": False}

        self.assertTrue(
            module.deve_registrar_rastro_display_f3(
                app,
                context=context,
                analysis=analysis,
                advance=None,
                now_monotonic=10.0,
            )
        )
        app._display_f3_perf_last_context_signature = ("TESTE", "CHECK_001")
        app._display_f3_perf_last_probe_approved = False
        app._display_f3_perf_last_trace_monotonic = 10.0

        self.assertFalse(
            module.deve_registrar_rastro_display_f3(
                app,
                context=context,
                analysis=analysis,
                advance=None,
                now_monotonic=10.05,
            )
        )
        self.assertTrue(
            module.deve_registrar_rastro_display_f3(
                app,
                context=context,
                analysis=analysis,
                advance=None,
                now_monotonic=10.25,
            )
        )

    def test_approved_transition_and_real_advance_are_always_recorded(self):
        app = _App()
        app._display_f3_perf_last_context_signature = ("TESTE", "CHECK_001")
        app._display_f3_perf_last_probe_approved = False
        app._display_f3_perf_last_trace_monotonic = 10.0
        context = {"project_name": "TESTE", "check_id": "CHECK_001"}

        self.assertTrue(
            module.deve_registrar_rastro_display_f3(
                app,
                context=context,
                analysis={"approved": True},
                advance=None,
                now_monotonic=10.01,
            )
        )
        app._display_f3_perf_last_probe_approved = True
        self.assertTrue(
            module.deve_registrar_rastro_display_f3(
                app,
                context=context,
                analysis={"approved": True},
                advance={"advanced": True},
                now_monotonic=10.02,
            )
        )

    def test_compact_recorder_marks_skipped_token_without_growing_history(self):
        app = _App()
        app._display_f3_live_trace = deque(maxlen=module.F3_PERF_TRACE_MAX_FRAMES)
        app._display_f3_perf_last_context_signature = ("TESTE", "CHECK_001")
        app._display_f3_perf_last_probe_approved = False
        app._display_f3_perf_last_trace_monotonic = 10**12

        module.registrar_rastro_compacto_display_f3(
            app,
            token=("camera", 2),
            context={"project_name": "TESTE", "check_id": "CHECK_001"},
            analysis={"ready": True, "approved": False, "mask_results": []},
            analysis_source="core_auto_analysis",
            stability={"frames": 0, "required": 2},
            advance=None,
        )

        self.assertEqual(("camera", 2), app._display_f3_live_trace_last_token)
        self.assertEqual(0, len(app._display_f3_live_trace))

    def test_debug_refresh_and_history_are_bounded(self):
        self.assertGreaterEqual(module.F3_PERF_DEBUG_REFRESH_MS, 1000)
        self.assertLessEqual(module.F3_PERF_TRACE_DETAIL_FRAMES, 16)
        self.assertLessEqual(module.F3_PERF_TRACE_MAX_FRAMES, 100)

    def test_module_isolated_from_f2(self):
        source = inspect.getsource(module)
        self.assertNotIn("src.platform.f2_", source)
        self.assertNotIn("F2Automatic", source)


if __name__ == "__main__":
    unittest.main()
