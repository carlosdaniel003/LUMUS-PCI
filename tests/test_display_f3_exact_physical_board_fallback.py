from __future__ import annotations

import inspect
import unittest

import src.platform.display_f3_debug_toggle as debug_toggle_module
import src.platform.display_f3_exact_physical_board_fallback as fallback_module


class DisplayF3ExactPhysicalBoardFallbackTests(unittest.TestCase):
    @staticmethod
    def _state(scores: dict[str, float], **extra) -> dict:
        return {
            "kind": "unknown",
            "text": "IDENTIFICANDO...",
            "allow_auto": False,
            "board_references_complete": True,
            "configured_count": len(scores),
            "best_score": max(scores.values()),
            "reference_scores": dict(scores),
            **extra,
        }

    def test_debug_real_suporte_vazio_deixa_de_ser_unknown(self):
        state = self._state(
            {
                "empty": 0.4125,
                "off": 0.1968,
                "check:CHECK_003": 0.1720,
                "check:CHECK_004": 0.1705,
                "check:CHECK_002": 0.1670,
                "check:CHECK_001": 0.1656,
            }
        )

        result = fallback_module.aplicar_fallback_fisico_exato_off_empty_f3(state)

        self.assertEqual(result["kind"], "empty")
        self.assertEqual(result["text"], "PLACA FORA DO SUPORTE")
        self.assertEqual(result["physical_state_key"], "empty")
        self.assertTrue(result["physical_low_score_fallback"])
        self.assertGreater(result["physical_low_score_fallback_margin"], 0.21)
        self.assertGreater(result["physical_low_score_fallback_ratio"], 2.0)
        self.assertGreater(result["physical_low_score_check_margin"], 0.23)

    def test_debug_real_off_tambem_usa_mesma_regra_generica(self):
        state = self._state(
            {
                "off": 0.4306,
                "empty": 0.2483,
                "check:CHECK_004": 0.1281,
                "check:CHECK_003": 0.0653,
                "check:CHECK_002": 0.0578,
                "check:CHECK_001": 0.0445,
            }
        )

        result = fallback_module.aplicar_fallback_fisico_exato_off_empty_f3(state)

        self.assertEqual(result["kind"], "off")
        self.assertEqual(result["text"], "PLACA NO SUPORTE • DESLIGADA")
        self.assertEqual(result["physical_state_key"], "off")
        self.assertTrue(result["physical_low_score_fallback"])

    def test_estado_fisico_ambiguo_permanece_identificando(self):
        state = self._state(
            {
                "empty": 0.39,
                "off": 0.34,
                "check:CHECK_001": 0.20,
            }
        )
        result = fallback_module.aplicar_fallback_fisico_exato_off_empty_f3(state)
        self.assertEqual(result["kind"], "unknown")
        self.assertEqual(result["text"], "IDENTIFICANDO...")

    def test_check_mais_forte_impede_fallback_de_empty_ou_off(self):
        state = self._state(
            {
                "empty": 0.43,
                "off": 0.20,
                "check:CHECK_001": 0.48,
            }
        )
        result = fallback_module.aplicar_fallback_fisico_exato_off_empty_f3(state)
        self.assertEqual(result["kind"], "unknown")

    def test_ambiguidade_de_candidatos_que_passaram_threshold_nao_e_relaxada(self):
        state = self._state(
            {
                "empty": 0.76,
                "off": 0.75,
                "check:CHECK_001": 0.20,
            },
            ambiguous=True,
        )
        result = fallback_module.aplicar_fallback_fisico_exato_off_empty_f3(state)
        self.assertEqual(result["kind"], "unknown")
        self.assertTrue(result["ambiguous"])

    def test_fallback_nao_cria_regra_especifica_para_h1_blue_usb_aux(self):
        source = inspect.getsource(
            fallback_module.aplicar_fallback_fisico_exato_off_empty_f3
        )
        self.assertNotIn('"H1"', source)
        self.assertNotIn('"BLUE"', source)
        self.assertNotIn('"USB"', source)
        self.assertNotIn('"AUX"', source)
        self.assertIn('kind not in {"empty", "off"}', source)

    def test_bootstrap_f3_instala_fallback_no_classificador_exato(self):
        source = inspect.getsource(
            debug_toggle_module.instalar_toggle_debug_tecnico_display_f3
        )
        self.assertIn(
            "instalar_fallback_fisico_exato_off_empty_display_f3",
            source,
        )
        installer_source = inspect.getsource(
            fallback_module.instalar_fallback_fisico_exato_off_empty_display_f3
        )
        self.assertIn(
            "exact_module.classificar_estado_fisico_por_gabaritos_f3 = classifier",
            installer_source,
        )

    def test_modulo_permanece_exclusivo_do_f3(self):
        source = inspect.getsource(fallback_module)
        self.assertNotIn("display_production_f2", source)
        self.assertNotIn("DisplayProductionF2", source)


if __name__ == "__main__":
    unittest.main()
