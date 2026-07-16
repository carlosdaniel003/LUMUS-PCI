import unittest
from dataclasses import dataclass

import numpy as np

from src.core.operation_engine import OperationResult
from src.platform.operation_confirmation import (
    consolidar_capturas_operacao,
    dois_resultados_confirmam_ng,
)


@dataclass
class LedResult:
    id: str
    status: str
    valor_binario: int


def criar_resultado(falhos, tempo=0.01):
    falhos = set(falhos)
    resultados = tuple(
        LedResult(
            id=led_id,
            status="APAGADO" if led_id in falhos else "ACESO",
            valor_binario=0 if led_id in falhos else 1,
        )
        for led_id in ("LED_001", "LED_002", "LED_003")
    )
    return OperationResult(
        ok=not falhos,
        failed_led_ids=tuple(sorted(falhos)),
        results=resultados,
        elapsed_seconds=tempo,
    )


class OperationConfirmationTests(unittest.TestCase):
    def test_dois_ng_iguais_confirmam_cedo(self):
        primeiro = criar_resultado({"LED_002"})
        segundo = criar_resultado({"LED_002"})
        self.assertTrue(dois_resultados_confirmam_ng(primeiro, segundo))

    def test_ng_transitorio_vira_ok_por_maioria(self):
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        capturas = [
            (1, frame, criar_resultado({"LED_002"})),
            (2, frame, criar_resultado(set())),
            (3, frame, criar_resultado(set())),
        ]
        _, _, resultado = consolidar_capturas_operacao(capturas)
        self.assertTrue(resultado.ok)
        self.assertEqual((), resultado.failed_led_ids)

    def test_ng_repetido_permanece_ng(self):
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        capturas = [
            (1, frame, criar_resultado({"LED_002"})),
            (2, frame, criar_resultado(set())),
            (3, frame, criar_resultado({"LED_002"})),
        ]
        _, _, resultado = consolidar_capturas_operacao(capturas)
        self.assertFalse(resultado.ok)
        self.assertEqual(("LED_002",), resultado.failed_led_ids)
        mapa = {item.id: item for item in resultado.results}
        self.assertEqual(0, mapa["LED_002"].valor_binario)
        self.assertEqual("APAGADO", mapa["LED_002"].status)

    def test_falhas_aleatorias_nao_formam_ng(self):
        frame = np.zeros((10, 10, 3), dtype=np.uint8)
        capturas = [
            (1, frame, criar_resultado({"LED_001"})),
            (2, frame, criar_resultado({"LED_002"})),
            (3, frame, criar_resultado({"LED_003"})),
        ]
        _, _, resultado = consolidar_capturas_operacao(capturas)
        self.assertTrue(resultado.ok)
        self.assertEqual((), resultado.failed_led_ids)


if __name__ == "__main__":
    unittest.main()
