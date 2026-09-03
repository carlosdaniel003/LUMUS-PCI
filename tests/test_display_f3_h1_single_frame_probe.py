from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import src.platform.display_auto_check_runtime as runtime_module
import src.platform.display_f3_h1_single_frame_probe as module
import src.platform.display_f3_live_runtime_fix as live_runtime_module
from src.platform.display_auto_check_analyzer import DisplayAutomaticCheckAnalyzer
from src.platform.display_f3_exact_check_template import F3_EXACT_TEMPLATE_SOURCE


class _App:
    def __init__(self):
        self._display_f3_live_probe_signature = None
        self._display_f3_live_probe_ok_frames = 0

    @staticmethod
    def _display_auto_is_reference_gate(context):
        return int((context or {}).get("current_index", -1)) == 0

    @staticmethod
    def _display_auto_is_transient_check(context):
        return str((context or {}).get("check_name") or "").upper() == "BLUE"


def _exact_analysis(*, failed_on: bool = False, off_mismatches: int = 2) -> dict:
    results = []
    for index in range(7):
        matched = not (failed_on and index == 3)
        results.append(
            {
                "mask_id": f"ON_{index}",
                "expected": "on",
                "classified": "on" if matched else "off",
                "matched": matched,
            }
        )
    for index in range(3):
        matched = index >= off_mismatches
        results.append(
            {
                "mask_id": f"OFF_{index}",
                "expected": "off",
                "classified": "off" if matched else "on",
                "matched": matched,
            }
        )
    return {
        "ready": True,
        "approved": all(bool(item["matched"]) for item in results),
        "reference_authority": F3_EXACT_TEMPLATE_SOURCE,
        "mask_results": results,
    }


class DisplayF3H1SingleFrameProbeTests(unittest.TestCase):
    def test_h1_first_check_needs_one_exact_positive_frame(self):
        result = module.frames_necessarios_sonda_positiva_f3(
            _App(),
            {"current_index": 0, "check_name": "H1"},
        )
        self.assertEqual(1, result)

    def test_blue_needs_one_exact_positive_frame(self):
        result = module.frames_necessarios_sonda_positiva_f3(
            _App(),
            {"current_index": 1, "check_name": "BLUE"},
        )
        self.assertEqual(1, result)

    def test_stable_usb_keeps_two_frames(self):
        result = module.frames_necessarios_sonda_positiva_f3(
            _App(),
            {"current_index": 2, "check_name": "USB"},
        )
        self.assertEqual(2, result)

    def test_h1_positive_probe_ignores_only_off_template_photometric_mismatches(self):
        analysis = _exact_analysis(failed_on=False, off_mismatches=2)
        evidence = module.avaliar_sonda_positiva_f3(
            _App(),
            {
                "project_name": "TESTE",
                "check_id": "CHECK_001",
                "check_name": "H1",
                "current_index": 0,
            },
            analysis,
        )

        self.assertTrue(evidence["approved"])
        self.assertEqual(module.F3_POSITIVE_PROBE_MODE_ON_MASKS, evidence["mode"])
        self.assertEqual(7, evidence["on_total"])
        self.assertEqual(7, evidence["on_matched"])
        self.assertEqual(2, evidence["off_template_mismatches"])
        self.assertFalse(evidence["original_approved"])

    def test_h1_positive_probe_never_confirms_when_one_expected_on_mask_fails(self):
        analysis = _exact_analysis(failed_on=True, off_mismatches=0)
        evidence = module.avaliar_sonda_positiva_f3(
            _App(),
            {
                "project_name": "TESTE",
                "check_id": "CHECK_001",
                "check_name": "H1",
                "current_index": 0,
            },
            analysis,
        )

        self.assertFalse(evidence["approved"])
        self.assertEqual(6, evidence["on_matched"])

    def test_h1_exact_probe_advances_in_first_frame_when_all_expected_on_match(self):
        app = _App()
        analysis = _exact_analysis(failed_on=False, off_mismatches=2)
        stability = module.atualizar_estabilidade_sonda_positiva_f3(
            app,
            {
                "project_name": "TESTE",
                "check_id": "CHECK_001",
                "check_name": "H1",
                "current_index": 0,
            },
            analysis,
        )

        self.assertTrue(stability["confirm"])
        self.assertEqual(1, stability["required"])
        self.assertTrue(analysis["positive_probe_approved"])
        self.assertFalse(analysis["exact_all_masks_approved"])
        self.assertEqual(7, analysis["positive_on_matched_count"])
        self.assertIn("7_de_7", analysis["reason"])

    def test_semantic_analysis_is_not_relaxed_by_positive_exact_probe_rule(self):
        analysis = _exact_analysis(failed_on=False, off_mismatches=1)
        analysis.pop("reference_authority", None)
        analysis["approved"] = False

        evidence = module.avaliar_sonda_positiva_f3(
            _App(),
            {
                "project_name": "TESTE",
                "check_id": "CHECK_001",
                "check_name": "H1",
                "current_index": 0,
            },
            analysis,
        )

        self.assertFalse(evidence["approved"])
        self.assertEqual("full_analysis", evidence["mode"])

    def test_runtime_ng_authority_is_restored_to_learned_semantic_analyzer(self):
        sentinel = object()
        with patch.object(runtime_module, "DisplayAutomaticCheckAnalyzer", sentinel), patch.object(
            live_runtime_module,
            "DisplayAutomaticCheckAnalyzer",
            sentinel,
        ):
            module.restaurar_analisador_semantico_runtime_f3()
            self.assertIs(
                DisplayAutomaticCheckAnalyzer,
                runtime_module.DisplayAutomaticCheckAnalyzer,
            )
            self.assertIs(
                DisplayAutomaticCheckAnalyzer,
                live_runtime_module.DisplayAutomaticCheckAnalyzer,
            )

    def test_module_has_no_f2_dependency(self):
        source = inspect.getsource(module)
        self.assertNotIn("src.platform.f2_", source)
        self.assertNotIn("F2Automatic", source)


if __name__ == "__main__":
    unittest.main()
