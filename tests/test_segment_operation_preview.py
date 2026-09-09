import unittest

from src.models.led_selection import LedSelection
from src.platform.segment_display_operation_window import (
    F2_ANALYZED_WAITING_FONT_MAX,
    F2_ANALYZED_WAITING_FONT_MIN,
    F2_ANALYZED_WAITING_TEXT,
    SegmentDisplayOperationWindow,
    tamanho_fonte_status_analisado_f2,
)


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


class FakeLabel:
    def __init__(self):
        self.options = {}
        self.visible = False

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def grid(self, *args, **kwargs):
        self.visible = True

    def grid_remove(self):
        self.visible = False


class FakePanel:
    def __init__(self, width: int):
        self.width = width

    def winfo_width(self):
        return self.width


class SegmentOperationPreviewTests(unittest.TestCase):
    def _window(self):
        window = SegmentDisplayOperationWindow.__new__(SegmentDisplayOperationWindow)
        window.preview_canvas = FakeCanvas()
        window._failed_led_ids = frozenset()
        return window

    def _status_window(self):
        window = SegmentDisplayOperationWindow.__new__(SegmentDisplayOperationWindow)
        window.board_presence_label = FakeLabel()
        window._board_presence_status = "unknown"
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

    def test_status_mostra_placa_ligada(self):
        window = self._status_window()
        window.set_board_presence_status("board_on", enabled=True)
        self.assertTrue(window.board_presence_label.visible)
        self.assertEqual(
            "STATUS DA PLACA: PLACA PRESENTE — LIGADA",
            window.board_presence_label.options["text"],
        )

    def test_status_mostra_placa_desligada(self):
        window = self._status_window()
        window.set_board_presence_status("board_off", enabled=True)
        self.assertEqual(
            "STATUS DA PLACA: PLACA PRESENTE — DESLIGADA",
            window.board_presence_label.options["text"],
        )

    def test_status_mostra_placa_ausente(self):
        window = self._status_window()
        window.set_board_presence_status("empty_support", enabled=True)
        self.assertEqual(
            "STATUS DA PLACA: PLACA AUSENTE",
            window.board_presence_label.options["text"],
        )

    def test_status_some_quando_automatico_desativado(self):
        window = self._status_window()
        window.set_board_presence_status("board_on", enabled=True)
        self.assertTrue(window.board_presence_label.visible)
        window.set_board_presence_status(None, enabled=False)
        self.assertFalse(window.board_presence_label.visible)

    def test_aviso_pos_analise_f2_reserva_duas_linhas(self):
        window = SegmentDisplayOperationWindow.__new__(SegmentDisplayOperationWindow)
        window.status_label = FakeLabel()
        window.analysis_panel = FakePanel(640)

        window._aplicar_status_pos_analise_f2()

        self.assertEqual(
            F2_ANALYZED_WAITING_TEXT,
            window.status_label.options["text"],
        )
        self.assertEqual(2, window.status_label.options["height"])
        self.assertEqual("center", window.status_label.options["justify"])
        self.assertEqual(0, window.status_label.options["wraplength"])

    def test_fonte_pos_analise_reduz_em_painel_estreito(self):
        fonte_larga = tamanho_fonte_status_analisado_f2(700)
        fonte_estreita = tamanho_fonte_status_analisado_f2(320)

        self.assertGreater(fonte_larga, fonte_estreita)
        self.assertLessEqual(fonte_larga, F2_ANALYZED_WAITING_FONT_MAX)
        self.assertGreaterEqual(fonte_estreita, F2_ANALYZED_WAITING_FONT_MIN)


if __name__ == "__main__":
    unittest.main()