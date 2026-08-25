from __future__ import annotations

import inspect
from types import SimpleNamespace
import unittest

from src.core.f2_led_physical_guard import (
    F2_PHYSICAL_MIN_HOT_245,
    F2_PHYSICAL_MIN_HOT_250,
    F2_PHYSICAL_MIN_PERCENT_ON,
    F2_PHYSICAL_STRONG_PERCENT_ON,
    aplicar_guarda_emissao_fisica_f2,
    avaliar_emissao_fisica_f2,
)
from src.models.led_features import LedFeatures


class F2LedPhysicalGuardTests(unittest.TestCase):
    @staticmethod
    def reference_on() -> LedFeatures:
        # hot250 vem da referência ACESO registrada no Debug Tecnico (2).
        return LedFeatures(
            percent_on=0.80,
            percent_hot_245=0.12,
            percent_hot_250=0.107383,
        )

    @staticmethod
    def result(status: str, features: LedFeatures):
        return SimpleNamespace(
            status=status,
            valor_binario=1 if status == "ACESO" else 0,
            features=features,
            motivos=[],
            falha_luminosidade=False,
            indice_luminosidade=1.0,
            score_falha_luminosidade=0.0,
        )

    def test_envelope_do_debug_com_placa_desligada_nao_e_emissao(self):
        # LED_010 foi um dos casos mais permissivos do novo debug: 25,8% da
        # ROI acima de V=160, hot245=3,8% e hot250=3,5%, mesmo assim era apenas
        # reflexo com a placa totalmente desligada.
        features = LedFeatures(
            percent_on=0.258110,
            percent_hot_245=0.038082,
            percent_hot_250=0.035261,
            v_max=255.0,
            v_p99=255.0,
            glow_score=111.6579,
            center_to_ring_v=25.7641,
        )

        evaluation = avaliar_emissao_fisica_f2(
            features,
            reference_on=self.reference_on(),
        )

        self.assertFalse(evaluation.emitted)
        self.assertLess(features.percent_on, evaluation.min_percent_on)
        self.assertLess(features.percent_hot_245, evaluation.min_hot_245)
        self.assertLess(features.percent_hot_250, evaluation.min_hot_250)

    def test_reflexo_com_glow_muito_alto_continua_apagado(self):
        # LED_019/035/040 do debug chegavam a glow ~177..180 sem emissão real.
        features = LedFeatures(
            percent_on=0.095,
            percent_hot_245=0.034,
            percent_hot_250=0.030,
            v_max=255.0,
            v_p99=255.0,
            glow_score=180.141,
            center_to_ring_v=53.3146,
        )
        result = self.result("ACESO", features)

        aplicar_guarda_emissao_fisica_f2(
            result,
            reference_on=self.reference_on(),
        )

        self.assertEqual("APAGADO", result.status)
        self.assertEqual(0, result.valor_binario)
        self.assertTrue(any("sem emissão física" in reason for reason in result.motivos))

    def test_led_realmente_aceso_mantem_aceso(self):
        features = LedFeatures(
            percent_on=0.92,
            percent_hot_245=0.16,
            percent_hot_250=0.11,
            v_max=255.0,
            v_p99=255.0,
            glow_score=170.0,
        )
        result = self.result("ACESO", features)

        aplicar_guarda_emissao_fisica_f2(
            result,
            reference_on=self.reference_on(),
        )

        self.assertEqual("ACESO", result.status)
        self.assertEqual(1, result.valor_binario)

    def test_area_muito_ampla_preserva_aceso_mesmo_com_hot_core_variavel(self):
        features = LedFeatures(
            percent_on=F2_PHYSICAL_STRONG_PERCENT_ON + 0.05,
            percent_hot_245=0.025,
            percent_hot_250=0.020,
            v_max=255.0,
            v_p99=250.0,
        )
        evaluation = avaliar_emissao_fisica_f2(
            features,
            reference_on=self.reference_on(),
        )
        self.assertTrue(evaluation.emitted)

    def test_pouca_luz_nao_e_sobrescrita_pela_guarda_de_aceso_saudavel(self):
        result = self.result(
            "POUCA_LUZ",
            LedFeatures(
                percent_on=0.20,
                percent_hot_245=0.02,
                percent_hot_250=0.01,
            ),
        )

        aplicar_guarda_emissao_fisica_f2(
            result,
            reference_on=self.reference_on(),
        )

        self.assertEqual("POUCA_LUZ", result.status)

    def test_limites_tem_margem_sobre_o_debug_desligado(self):
        self.assertGreater(F2_PHYSICAL_MIN_PERCENT_ON, 0.258110)
        self.assertGreater(F2_PHYSICAL_MIN_HOT_245, 0.038082)
        self.assertGreater(F2_PHYSICAL_MIN_HOT_250, 0.035261)
        self.assertGreater(F2_PHYSICAL_STRONG_PERCENT_ON, 0.258110)

    def test_modulo_nao_altera_display_f3(self):
        import src.core.f2_led_physical_guard as module

        source = inspect.getsource(module)
        self.assertNotIn("DisplayAutomaticCheckF3Mixin", source)
        self.assertNotIn("DisplayProductionF3Mixin", source)
        self.assertNotIn("display_auto_check", source)


if __name__ == "__main__":
    unittest.main()
