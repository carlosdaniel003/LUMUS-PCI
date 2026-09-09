from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

import src.platform.display_f3_current_check_status_sync as sync_module
import src.platform.display_f3_visual_analysis_relative_fallback as visual_module
import src.platform.display_f3_visual_roi_disambiguation as roi_module


class DisplayF3VisualRoiDisambiguationTests(unittest.TestCase):
    def test_frame_real_off_deixa_de_empatar_com_h1_quando_roi_favorece_off(self):
        resolver = roi_module._extend_visual_resolver(
            visual_module.resolver_analise_visual_candidatos_f3
        )
        candidates = {
            "board_off": {
                "score": 0.7563,
                "threshold": 0.72,
                "matched": True,
                "kind": "board_off",
                "decision_eligible": True,
            },
            "check:CHECK_001": {
                "score": 0.7528,
                "threshold": 0.72,
                "matched": True,
                "kind": "check",
                "name": "H1",
                "check_id": "CHECK_001",
                "decision_eligible": False,
                "suppressed_by_off_same_roi": True,
            },
            "empty_support": {
                "score": 0.1904,
                "threshold": 0.72,
                "matched": False,
                "kind": "empty_support",
                "decision_eligible": True,
            },
        }

        decision = resolver(candidates)

        self.assertEqual("board_off", decision["selected_reference"])
        self.assertEqual("board_off", decision["result_kind"])
        self.assertEqual(["CHECK_001"], decision["suppressed_checks_by_off_same_roi"])
        self.assertEqual(1, decision["suppressed_check_count"])

    def test_check_real_permanece_elegivel_quando_na_mesma_roi_off_nao_vence(self):
        resolver = roi_module._extend_visual_resolver(
            visual_module.resolver_analise_visual_candidatos_f3
        )
        candidates = {
            "board_off": {
                "score": 0.61,
                "threshold": 0.72,
                "matched": False,
                "kind": "board_off",
                "decision_eligible": True,
            },
            "check:CHECK_001": {
                "score": 0.88,
                "threshold": 0.72,
                "matched": True,
                "kind": "check",
                "name": "H1",
                "check_id": "CHECK_001",
                "decision_eligible": True,
                "suppressed_by_off_same_roi": False,
            },
        }

        decision = resolver(candidates)

        self.assertEqual("check:CHECK_001", decision["selected_reference"])
        self.assertEqual("check", decision["result_kind"])

    def test_comparacao_off_forca_exatamente_roi_do_check(self):
        roi = {"x": 0.31, "y": 0.37, "width": 0.38, "height": 0.18}
        off_metadata = {
            "image_path": "off.jpg",
            "roi": {"x": 0.0, "y": 0.32, "width": 0.84, "height": 0.37},
        }
        captured = {}

        def fake_score(frame, metadata):
            captured.update(metadata)
            return 0.91

        with patch.object(visual_module, "_score_reference_full_roi", fake_score):
            score = roi_module._score_off_on_check_roi(object(), off_metadata, roi)

        self.assertEqual(0.91, score)
        self.assertEqual(roi, captured["roi"])
        self.assertNotEqual(off_metadata["roi"], captured["roi"])

    def test_modulo_e_exclusivamente_visual_e_nao_usa_mascaras(self):
        source = inspect.getsource(roi_module).lower()
        self.assertIn("same_roi", source)
        self.assertIn("decision_eligible", source)
        self.assertNotIn("src.platform.f2_", source)
        self.assertNotIn("mask_results", source)
        self.assertNotIn("registrar_resultado", source)
        self.assertNotIn("concluir_check", source)

    def test_instalador_final_instala_desempate_roi_depois_do_fallback_visual(self):
        source = inspect.getsource(sync_module.instalar_sincronia_status_check_atual_display_f3)
        fallback_pos = source.index("instalar_fallback_relativo_analise_visual_display_f3()")
        roi_pos = source.index("instalar_desambiguacao_roi_analise_visual_display_f3()")
        self.assertLess(fallback_pos, roi_pos)


if __name__ == "__main__":
    unittest.main()
