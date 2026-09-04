import inspect
import unittest

from src.platform.display_f3_power_deadlock_fix import (
    evidencia_direta_confirma_display_ligado_f3,
    promover_falso_off_por_energia_direta_f3,
    resumir_evidencia_energia_direta_display_f3,
)


class DisplayF3PowerDeadlockFixTests(unittest.TestCase):
    def _h1_debug_evidence(self):
        return {
            "available": True,
            "off_confirmed": False,
            "check_id": "CHECK_001",
            "expected_on_mask_count": 7,
            "off_votes": 0,
            "powered_votes": 7,
            "tie_votes": 0,
            "valid_votes": 7,
        }

    def test_h1_7_de_7_ligados_quebra_falso_off(self):
        evidence = self._h1_debug_evidence()
        summary = resumir_evidencia_energia_direta_display_f3(evidence)
        self.assertTrue(summary["strong"])
        self.assertEqual(1.0, summary["powered_ratio"])
        self.assertTrue(evidencia_direta_confirma_display_ligado_f3(evidence))

    def test_maioria_abaixo_de_80_porcento_nao_quebra_off(self):
        evidence = {
            "available": True,
            "off_confirmed": False,
            "expected_on_mask_count": 7,
            "powered_votes": 5,
            "off_votes": 2,
            "valid_votes": 7,
        }
        self.assertFalse(evidencia_direta_confirma_display_ligado_f3(evidence))

    def test_promocao_libera_analisador_sem_aprovar_check(self):
        state = {
            "kind": "off",
            "allow_auto": False,
            "physical_state_key": "off",
            "reference_scores": {"off": 0.9699, "empty": 0.3862},
        }
        context = {
            "project_name": "TESTE",
            "check_id": "CHECK_001",
            "check_name": "H1",
        }
        result = promover_falso_off_por_energia_direta_f3(
            state,
            context=context,
            evidence=self._h1_debug_evidence(),
        )
        self.assertEqual("powered", result["kind"])
        self.assertTrue(result["allow_auto"])
        self.assertTrue(result["powered_board_confirmed"])
        self.assertEqual("CHECK_001", result["expected_check_id"])
        self.assertFalse(result["physical_matches_expected_check"])
        self.assertNotIn("approved", result)
        self.assertNotIn("ok", result)

    def test_empty_e_check_fisico_nao_sao_promovidos(self):
        context = {"check_id": "CHECK_001", "check_name": "H1"}
        evidence = self._h1_debug_evidence()
        for kind in ("empty", "check", "unavailable", "unknown"):
            result = promover_falso_off_por_energia_direta_f3(
                {"kind": kind, "allow_auto": False},
                context=context,
                evidence=evidence,
            )
            self.assertEqual(kind, result["kind"])
            self.assertFalse(result["allow_auto"])

    def test_modulo_nao_aprova_resultado_nem_importa_f2(self):
        module = __import__(
            "src.platform.display_f3_power_deadlock_fix",
            fromlist=["dummy"],
        )
        source = inspect.getsource(module)
        self.assertNotIn("registrar_resultado_check_display_f3", source)
        self.assertNotIn("f2_", source.lower())


if __name__ == "__main__":
    unittest.main()
