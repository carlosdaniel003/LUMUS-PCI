import unittest

from src.models.led_selection import LedSelection
from src.platform.segment_display_operation_window import SegmentDisplayOperationWindow


class FakeCanvas:
    def __init__(self):
        self.calls = []

    def create_polygon(self, *args, **kwargs):
        self.calls.append(("polygon", args, kwargs))
        return len(self.calls)

    def create_oval(self, *args, **kwargs):
        self.calls.append(("oval", args, kwargs))
        return len(self.calls)

    def create_text(self, *args, **kwargs):
        self.calls.append(("text", args, kwargs))
        return len(self.calls)

    def create_rectangle(self, *args, **kwargs):
        self.calls.append(("rectangle", args, kwargs))
        return len(self.calls)


class SegmentOperationPreviewTests(unittest.TestCase):
    def _window(self):
        window = SegmentDisplayOperationWindow.__new__(SegmentDisplayOperationWindow)
        window.preview_canvas = FakeCanvas()
        window._failed_led_ids = frozenset()
        return window

    def test_segmento_e_desenhado_com_poligono(self):
        window = self._window()
        segmento = LedSelection(
            "DIGITO_1_A",
            100,
            60,
            1,
            tipo_roi="segmento",
            largura=70,
            altura=14,
            angulo=-5,
        )

        window._draw_guides([segmento], 200, 120, 1.0, 0, 0)

        tipos = [chamada[0] for chamada in window.preview_canvas.calls]
        self.assertIn("polygon", tipos)
        self.assertIn("rectangle", tipos)  # guia geral da placa

    def test_circulo_continua_sendo_desenhado_com_oval(self):
        window = self._window()
        circulo = LedSelection("LED_001", 50, 50, 10)

        window._draw_guides([circulo], 200, 120, 1.0, 0, 0)

        tipos = [chamada[0] for chamada in window.preview_canvas.calls]
        self.assertIn("oval", tipos)

    def test_segmento_ng_mantem_marcacao_de_falha(self):
        window = self._window()
        window._failed_led_ids = frozenset({"DIGITO_2_F"})
        segmento = LedSelection(
            "DIGITO_2_F",
            80,
            60,
            1,
            tipo_roi="segmento",
            largura=55,
            altura=12,
            angulo=88,
        )

        window._draw_guides([segmento], 200, 120, 1.0, 0, 0)

        textos = [
            chamada[2].get("text", "")
            for chamada in window.preview_canvas.calls
            if chamada[0] == "text"
        ]
        self.assertIn("DIGITO_2_F APAGADO", textos)


if __name__ == "__main__":
    unittest.main()
