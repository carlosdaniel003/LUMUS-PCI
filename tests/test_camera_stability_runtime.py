import unittest
from dataclasses import dataclass

import numpy as np

from src.core.operation_engine import OperationResult
from src.platform.camera_stability_runtime import RaspberryCameraStabilityMixin


@dataclass
class LedResult:
    id: str
    status: str
    valor_binario: int


class FakeEngine:
    def __init__(self, resultados):
        self.resultados = iter(resultados)

    def analyze(self, _frame):
        return next(self.resultados)


class FakeCamera:
    def __init__(self):
        self.frames = [
            (1, np.zeros((4, 4, 3), dtype=np.uint8)),
            (2, np.zeros((4, 4, 3), dtype=np.uint8)),
            (3, np.zeros((4, 4, 3), dtype=np.uint8)),
        ]
        self.index = 0

    def obter_ultimo_frame_estavel(self):
        self.index = 1
        return self.frames[0]

    def aguardar_proximo_frame_estavel(self, depois_frame_id, timeout_s):
        item = self.frames[self.index]
        self.index += 1
        return item


def resultado(falha):
    item = LedResult(
        id="LED_001",
        status="APAGADO" if falha else "ACESO",
        valor_binario=0 if falha else 1,
    )
    return OperationResult(
        ok=not falha,
        failed_led_ids=("LED_001",) if falha else (),
        results=(item,),
        elapsed_seconds=0.01,
    )


class Base:
    def __init__(self):
        self.camera_service = FakeCamera()
        self.operacao_engine = FakeEngine(
            [resultado(True), resultado(False), resultado(False)]
        )
        self.ultimo_resultado_operacao = None
        self.ultimo_frame_operacao = None


class App(RaspberryCameraStabilityMixin, Base):
    pass


class CameraStabilityRuntimeTests(unittest.TestCase):
    def test_ng_transitorio_e_consolidado_antes_do_log(self):
        app = App()
        final = app.operacao_engine.analyze(None)
        self.assertTrue(final.ok)
        self.assertIs(app.ultimo_resultado_operacao, final)
        self.assertIsNotNone(app.ultimo_frame_operacao)


if __name__ == "__main__":
    unittest.main()
