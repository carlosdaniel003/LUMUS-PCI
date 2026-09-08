from __future__ import annotations

import inspect
import unittest

import src.platform.display_f3_check_transition_guard as transition_guard


class DisplayF3BoardReferenceRelativeFallbackTests(unittest.TestCase):
    @staticmethod
    def _item(key: str, score: float, kind: str | None = None) -> dict:
        resolved_kind = kind or ("check" if key.startswith("check:") else key)
        return {
            "key": key,
            "kind": resolved_kind,
            "score": float(score),
            "threshold": 0.72,
            "wins": 0,
            "losses": 0,
            "comparisons": 0,
            "error_total": 0.0,
        }

    def test_debug_real_placa_desligada_seleciona_off_por_dominancia(self):
        prepared = [
            self._item("off", 0.4306),
            self._item("empty", 0.2483),
            self._item("check:CHECK_004", 0.1281),
            self._item("check:CHECK_003", 0.0653),
            self._item("check:CHECK_002", 0.0578),
            self._item("check:CHECK_001", 0.0445),
        ]

        winner = transition_guard._fallback_estado_fisico_por_dominancia_referencias_f3(
            prepared,
            True,
        )

        self.assertIsNotNone(winner)
        self.assertEqual(winner["key"], "off")
        self.assertTrue(winner["physical_low_score_fallback"])
        self.assertGreater(winner["physical_low_score_fallback_margin"], 0.18)

    def test_debug_real_suporte_vazio_seleciona_empty_por_dominancia(self):
        prepared = [
            self._item("empty", 0.4136),
            self._item("off", 0.1959),
            self._item("check:CHECK_003", 0.1747),
            self._item("check:CHECK_004", 0.1739),
            self._item("check:CHECK_002", 0.1702),
            self._item("check:CHECK_001", 0.1684),
        ]

        winner = transition_guard._fallback_estado_fisico_por_dominancia_referencias_f3(
            prepared,
            True,
        )

        self.assertIsNotNone(winner)
        self.assertEqual(winner["key"], "empty")
        self.assertTrue(winner["physical_low_score_fallback"])
        self.assertGreater(winner["physical_low_score_fallback_ratio"], 2.0)

    def test_estado_ambiguo_permanece_unknown(self):
        prepared = [
            self._item("off", 0.39),
            self._item("empty", 0.34),
            self._item("check:CHECK_001", 0.20),
        ]
        winner = transition_guard._fallback_estado_fisico_por_dominancia_referencias_f3(
            prepared,
            True,
        )
        self.assertIsNone(winner)

    def test_check_com_score_maior_impede_fallback_fisico(self):
        prepared = [
            self._item("off", 0.43),
            self._item("empty", 0.20),
            self._item("check:CHECK_001", 0.48),
        ]
        winner = transition_guard._fallback_estado_fisico_por_dominancia_referencias_f3(
            prepared,
            True,
        )
        self.assertIsNone(winner)

    def test_empty_tem_criterio_mais_conservador(self):
        prepared = [
            self._item("empty", 0.34),
            self._item("off", 0.10),
            self._item("check:CHECK_001", 0.10),
        ]
        winner = transition_guard._fallback_estado_fisico_por_dominancia_referencias_f3(
            prepared,
            True,
        )
        self.assertIsNone(winner)

    def test_fallback_exige_as_duas_referencias_fisicas_configuradas(self):
        prepared = [
            self._item("off", 0.50),
            self._item("empty", 0.10),
        ]
        winner = transition_guard._fallback_estado_fisico_por_dominancia_referencias_f3(
            prepared,
            False,
        )
        self.assertIsNone(winner)

    def test_fallback_nao_reduz_threshold_dos_checks(self):
        source = inspect.getsource(
            transition_guard._fallback_estado_fisico_por_dominancia_referencias_f3
        )
        self.assertNotIn('winner = by_key.get("check:', source)
        self.assertIn('str(overall.get("key") or "")', source)
        self.assertIn('startswith("check:")', source)

    def test_modulo_permanece_exclusivo_do_f3(self):
        source = inspect.getsource(transition_guard)
        self.assertNotIn("display_production_f2", source)
        self.assertNotIn("DisplayProductionF2", source)


if __name__ == "__main__":
    unittest.main()
