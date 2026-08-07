import unittest

import numpy as np

from src.platform.fullscreen_led_selection import (
    CTRL_MASK,
    FullscreenLedSelectionMixin,
)


class FakeEvent:
    def __init__(self, x=800, y=450, delta=0, num=None, state=0):
        self.x = x
        self.y = y
        self.delta = delta
        self.num = num
        self.state = state


class FakeCanvas:
    def __init__(self):
        self.bindings = {}

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback

    def focus_set(self):
        return None

    def winfo_width(self):
        return 1600

    def winfo_height(self):
        return 900


class FakeView:
    def __init__(self):
        self.canvas = FakeCanvas()
        self.imagem_canvas_original = np.zeros((1080, 1920, 3), dtype=np.uint8)
        self.rotacao_visual_principal = 0
        self.escala_exibicao = 1600 / 1920
        self.largura_imagem_exibida = 1600
        self.altura_imagem_exibida = 900
        self.deslocamento_imagem_x = 0
        self.deslocamento_imagem_y = 0
        self._selecao_zoom_ativo = True
        self._selecao_zoom_fator = 1.0
        self._selecao_zoom_centro_visual_x = None
        self._selecao_zoom_centro_visual_y = None
        self.redraws = 0
        self.draws = 0
        self.status = ""

    def obter_tamanho_canvas_principal(self):
        return 1600, 900

    def atualizar_imagem_principal_redimensionada(self):
        self.redraws += 1

    def desenhar_canvas(self, _leds, _resultados):
        self.draws += 1

    def limpar_lupa_canvas(self, _evento=None):
        return None

    def atualizar_status(self, texto):
        self.status = texto

    def evento_redimensionar_canvas_principal(self, _evento=None):
        return None

    def atualizar_lupa_canvas(self, _evento=None):
        return None


class FakeBase:
    def __init__(self):
        self.view = FakeView()
        self.leds_selecionados = []
        self.resultados_led_atual = []
        self.radius_events = 0

    def _evento_roda_roi(self, _evento=None):
        self.radius_events += 1
        return "break"


class FakeApp(FullscreenLedSelectionMixin, FakeBase):
    pass


class FullscreenSelectionZoomTests(unittest.TestCase):
    def test_scroll_sem_ctrl_continua_indo_para_editor_da_roi(self):
        app = FakeApp()
        evento = FakeEvent(delta=120, state=0)

        retorno = app._evento_roda_ou_zoom_selecao(evento)

        self.assertEqual("break", retorno)
        self.assertEqual(1, app.radius_events)
        self.assertEqual(1.0, app.view._selecao_zoom_fator)

    def test_ctrl_scroll_aplica_zoom_sem_alterar_raio(self):
        app = FakeApp()
        evento = FakeEvent(delta=120, state=CTRL_MASK)

        retorno = app._evento_roda_ou_zoom_selecao(evento)

        self.assertEqual("break", retorno)
        self.assertEqual(0, app.radius_events)
        self.assertGreater(app.view._selecao_zoom_fator, 1.0)
        self.assertEqual(1, app.view.redraws)
        self.assertEqual(1, app.view.draws)
        self.assertIn("Ctrl+scroll", app.view.status)

    def test_scroll_linux_ctrl_button4_tambem_aplica_zoom(self):
        app = FakeApp()
        evento = FakeEvent(delta=0, num=4, state=CTRL_MASK)

        app._evento_roda_ou_zoom_selecao(evento)

        self.assertEqual(0, app.radius_events)
        self.assertGreater(app.view._selecao_zoom_fator, 1.0)

    def test_bindings_de_scroll_usam_despachante_zoom_ou_roi(self):
        app = FakeApp()
        canvas = FakeCanvas()

        app._configurar_eventos_canvas_tela_cheia(canvas)

        for sequencia in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.assertIn(sequencia, canvas.bindings)
            self.assertEqual(
                "_evento_roda_ou_zoom_selecao",
                canvas.bindings[sequencia].__name__,
            )


if __name__ == "__main__":
    unittest.main()
