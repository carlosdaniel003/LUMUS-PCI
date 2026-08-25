from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from src.core.operation_engine import (
    F2_STRONG_ON_DISTANCE_RATIO,
    F2_STRONG_ON_MIN_PERCENT_ON,
    OperationEngine,
)


class F2StrongOnReconciliationTests(unittest.TestCase):
    @staticmethod
    def _result(
        distancia_on: float,
        distancia_off: float,
        confianca: float,
        *,
        percent_on: float = 1.0,
        apagado_forte: bool = False,
    ):
        return SimpleNamespace(
            status="APAGADO",
            valor_binario=0,
            distancia_on=distancia_on,
            distancia_off=distancia_off,
            brilho_indica_aceso=True,
            similaridade_indica_aceso=True,
            pico_indica_aceso=True,
            features=SimpleNamespace(percent_on=percent_on),
            motivos=[
                "brilho médio favorece aceso",
                "pico/área quente compatível",
                "similaridade óptica forte com aceso",
                "apagado forte" if apagado_forte else "apagado não confirmado",
            ],
            confianca=confianca,
        )

    def test_quatro_falsos_apagados_do_debug_sao_reconciliados(self):
        casos = (
            # LED_001
            (319.1046, 567.8738, 0.5219),
            # LED_002
            (352.8077, 545.4728, 0.5351),
            # LED_004
            (331.8938, 556.9207, 0.5274),
            # LED_027
            (259.1294, 620.4056, 0.5000),
        )

        for distancia_on, distancia_off, confianca in casos:
            with self.subTest(
                distancia_on=distancia_on,
                distancia_off=distancia_off,
            ):
                result = self._result(
                    distancia_on,
                    distancia_off,
                    confianca,
                )
                self.assertLessEqual(
                    distancia_on / distancia_off,
                    F2_STRONG_ON_DISTANCE_RATIO,
                )

                OperationEngine._reconciliar_falso_apagado_f2(result)

                self.assertEqual(result.status, "ACESO")
                self.assertEqual(result.valor_binario, 1)
                self.assertGreaterEqual(result.confianca, confianca)
                self.assertIn(
                    "F2 produção: similaridade forte confirmou aceso",
                    result.motivos,
                )

    def test_apagado_forte_nunca_e_promovido_para_aceso(self):
        result = self._result(
            150.0,
            500.0,
            0.80,
            apagado_forte=True,
        )

        OperationEngine._reconciliar_falso_apagado_f2(result)

        self.assertEqual(result.status, "APAGADO")
        self.assertEqual(result.valor_binario, 0)

    def test_similaridade_fraca_nao_e_promovida(self):
        result = self._result(
            400.0,
            500.0,
            0.55,
        )
        self.assertGreater(
            result.distancia_on / result.distancia_off,
            F2_STRONG_ON_DISTANCE_RATIO,
        )

        OperationEngine._reconciliar_falso_apagado_f2(result)

        self.assertEqual(result.status, "APAGADO")

    def test_roi_sem_luminosidade_ampla_nao_e_promovida(self):
        result = self._result(
            200.0,
            500.0,
            0.60,
            percent_on=F2_STRONG_ON_MIN_PERCENT_ON - 0.01,
        )

        OperationEngine._reconciliar_falso_apagado_f2(result)

        self.assertEqual(result.status, "APAGADO")

    def test_display_f3_nao_usa_operation_engine(self):
        source = Path(
            "src/platform/display_auto_check_analyzer.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("OperationEngine", source)
        self.assertNotIn("_reconciliar_falso_apagado_f2", source)


if __name__ == "__main__":
    unittest.main()
