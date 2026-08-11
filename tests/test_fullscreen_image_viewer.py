import inspect
import unittest
from unittest.mock import patch

import numpy as np

import src.ui.main_window_parts.image.fullscreen_image_viewer as modulo
from src.ui.main_window_parts.image.fullscreen_image_viewer import (
    CTRL_MASK,
    VISUALIZACOES_AUXILIARES_COM_ZOOM,
    VISUALIZACOES_TELA_CHEIA,
    calcular_encaixe_imagem,
    calcular_viewport_zoom_tela_cheia,
    configurar_abertura_imagens_tela_cheia,
    evento_abrir_imagem_principal_tela_cheia,
    evento_arrastar_pan_imagem_tela_cheia,
    evento_iniciar_pan_imagem_tela_cheia,
    evento_zoom_imagem_tela_cheia,
)


class FakeCanvas:
    def __init__(self):
        self.bindings = []
        self.config = {}

    def bind(self, evento, callback, add=None):
        self.bindings.append((evento, callback, add))

    def configure(self, **kwargs):
        self.config.update(kwargs)


class FakeView:
    def __init__(self):
        self.canvas = FakeCanvas()
        self.canvas_mapa_intensidade = FakeCanvas()
        self.canvas_imagem_teste = FakeCanvas()
        self.canvas_mascara = FakeCanvas()
        self.canvas_roi_debug = FakeCanvas()
        self.selecao_led_ativa = False
        self.selecao_manual_camera_visivel = False
        self._imagens_tela_cheia_bindings_instalados = False

    def evento_abrir_imagem_principal_tela_cheia(self, evento=None):
        return evento

    def abrir_imagem_tela_cheia(self, chave):
        return chave


class FakeEvent:
    def __init__(self, x=800, y=450, delta=0, num=None, state=0):
        self.x = x
        self.y = y
        self.delta = delta
        self.num = num
        self.state = state


class FakeZoomCanvas(FakeCanvas):
    def __init__(self, largura=1600, altura=900):
        super().__init__()
        self.largura = largura
        self.altura = altura

    def winfo_width(self):
        return self.largura

    def winfo_height(self):
        return self.altura


class FakeZoomView:
    def __init__(self, chave="heatmap"):
        self.canvas_imagem_tela_cheia = FakeZoomCanvas()
        self.chave_imagem_tela_cheia = chave
        self.imagens_auxiliares_originais = {
            "heatmap": np.zeros((1080, 1920, 3), dtype=np.uint8),
            "canal_v": np.zeros((1080, 1920, 3), dtype=np.uint8),
            "mascara": np.zeros((1080, 1920, 3), dtype=np.uint8),
            "roi_debug": np.zeros((360, 640, 3), dtype=np.uint8),
        }
        self.rotacao_visual_principal = 0
        self._fullscreen_zoom_fator = 1.0
        self._fullscreen_zoom_centro_x = None
        self._fullscreen_zoom_centro_y = None
        self._fullscreen_pan_ativo = False
        self._fullscreen_pan_ultimo_x = None
        self._fullscreen_pan_ultimo_y = None


class FullscreenImageViewerTests(unittest.TestCase):
    def test_registra_exatamente_os_cinco_paineis_solicitados(self):
        self.assertEqual(
            {
                "principal",
                "heatmap",
                "canal_v",
                "mascara",
                "roi_debug",
            },
            set(VISUALIZACOES_TELA_CHEIA),
        )

    def test_zoom_fica_restrito_aos_quatro_paineis_tecnicos(self):
        self.assertEqual(
            {"heatmap", "canal_v", "mascara", "roi_debug"},
            set(VISUALIZACOES_AUXILIARES_COM_ZOOM),
        )
        self.assertNotIn("principal", VISUALIZACOES_AUXILIARES_COM_ZOOM)

    def test_encaixe_preserva_proporcao_e_limites(self):
        escala, largura, altura, x, y = calcular_encaixe_imagem(
            1920,
            1080,
            1600,
            900,
            margem=18,
        )

        self.assertGreater(escala, 0)
        self.assertLessEqual(largura, 1564)
        self.assertLessEqual(altura, 864)
        self.assertAlmostEqual(largura / altura, 1920 / 1080, places=2)
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)

    def test_encaixe_funciona_para_imagem_vertical(self):
        _, largura, altura, x, y = calcular_encaixe_imagem(
            600,
            1200,
            1920,
            1080,
        )
        self.assertLess(altura, 1080)
        self.assertLess(largura, 1920)
        self.assertGreater(x, y)

    def test_viewport_zoom_renderiza_so_area_visivel(self):
        base = calcular_viewport_zoom_tela_cheia(
            1920,
            1080,
            1600,
            900,
            fator_zoom=1.0,
        )
        ampliado = calcular_viewport_zoom_tela_cheia(
            1920,
            1080,
            1600,
            900,
            fator_zoom=8.0,
            centro_imagem_x=960,
            centro_imagem_y=540,
        )

        self.assertGreater(ampliado.escala, base.escala)
        self.assertGreater(ampliado.largura_virtual, 1600)
        self.assertGreater(ampliado.altura_virtual, 900)
        # O bitmap realmente criado continua aproximadamente do tamanho da tela,
        # em vez de virar uma imagem completa 8x maior.
        self.assertLessEqual(ampliado.largura_render, 1620)
        self.assertLessEqual(ampliado.altura_render, 920)

    def test_bindings_sao_instalados_uma_unica_vez(self):
        view = FakeView()

        configurar_abertura_imagens_tela_cheia(view)
        primeira_quantidade = sum(
            len(canvas.bindings)
            for canvas in (
                view.canvas,
                view.canvas_mapa_intensidade,
                view.canvas_imagem_teste,
                view.canvas_mascara,
                view.canvas_roi_debug,
            )
        )
        configurar_abertura_imagens_tela_cheia(view)
        segunda_quantidade = sum(
            len(canvas.bindings)
            for canvas in (
                view.canvas,
                view.canvas_mapa_intensidade,
                view.canvas_imagem_teste,
                view.canvas_mascara,
                view.canvas_roi_debug,
            )
        )

        self.assertEqual(5, primeira_quantidade)
        self.assertEqual(primeira_quantidade, segunda_quantidade)
        self.assertEqual("<ButtonRelease-1>", view.canvas.bindings[0][0])
        self.assertEqual("+", view.canvas.bindings[0][2])

    def test_auxiliares_recebem_cursor_de_abertura(self):
        view = FakeView()
        configurar_abertura_imagens_tela_cheia(view)

        for canvas in (
            view.canvas_mapa_intensidade,
            view.canvas_imagem_teste,
            view.canvas_mascara,
            view.canvas_roi_debug,
        ):
            self.assertEqual("hand2", canvas.config.get("cursor"))

    def test_scroll_sem_ctrl_nao_altera_zoom_auxiliar(self):
        view = FakeZoomView("heatmap")

        with patch.object(modulo, "_agendar_redesenho") as redesenhar:
            retorno = evento_zoom_imagem_tela_cheia(
                view,
                FakeEvent(delta=120, state=0),
            )

        self.assertIsNone(retorno)
        self.assertEqual(1.0, view._fullscreen_zoom_fator)
        redesenhar.assert_not_called()

    def test_ctrl_scroll_aplica_zoom_auxiliar_ancorado(self):
        view = FakeZoomView("canal_v")

        with patch.object(modulo, "_agendar_redesenho") as redesenhar:
            retorno = evento_zoom_imagem_tela_cheia(
                view,
                FakeEvent(x=1200, y=450, delta=120, state=CTRL_MASK),
            )

        self.assertEqual("break", retorno)
        self.assertGreater(view._fullscreen_zoom_fator, 1.0)
        self.assertIsNotNone(view._fullscreen_zoom_centro_x)
        self.assertIsNotNone(view._fullscreen_zoom_centro_y)
        # Como o cursor estava à direita do centro, o centro visual acompanha
        # esse ponto para que a âncora sob o mouse permaneça estável.
        self.assertGreater(view._fullscreen_zoom_centro_x, 960.0)
        redesenhar.assert_called_once_with(view)

    def test_ctrl_scroll_nao_altera_imagem_principal(self):
        view = FakeZoomView("principal")

        with patch.object(modulo, "_agendar_redesenho") as redesenhar:
            retorno = evento_zoom_imagem_tela_cheia(
                view,
                FakeEvent(delta=120, state=CTRL_MASK),
            )

        self.assertIsNone(retorno)
        self.assertEqual(1.0, view._fullscreen_zoom_fator)
        redesenhar.assert_not_called()

    def test_botao_do_meio_arrasta_visualizacao_ampliada(self):
        view = FakeZoomView("mascara")
        view._fullscreen_zoom_fator = 2.0
        view._fullscreen_zoom_centro_x = 960.0
        view._fullscreen_zoom_centro_y = 540.0

        retorno_inicio = evento_iniciar_pan_imagem_tela_cheia(
            view,
            FakeEvent(x=800, y=450),
        )
        self.assertEqual("break", retorno_inicio)
        self.assertTrue(view._fullscreen_pan_ativo)
        self.assertEqual("fleur", view.canvas_imagem_tela_cheia.config.get("cursor"))

        with patch.object(modulo, "_agendar_redesenho") as redesenhar:
            retorno_arraste = evento_arrastar_pan_imagem_tela_cheia(
                view,
                FakeEvent(x=900, y=410),
            )

        self.assertEqual("break", retorno_arraste)
        self.assertLess(view._fullscreen_zoom_centro_x, 960.0)
        self.assertGreater(view._fullscreen_zoom_centro_y, 540.0)
        redesenhar.assert_called_once_with(view)

        retorno_fim = modulo._finalizar_pan_imagem_tela_cheia(view)
        self.assertEqual("break", retorno_fim)
        self.assertFalse(view._fullscreen_pan_ativo)
        self.assertEqual("arrow", view.canvas_imagem_tela_cheia.config.get("cursor"))

    def test_pan_sem_zoom_nao_e_ativado(self):
        view = FakeZoomView("roi_debug")

        retorno = evento_iniciar_pan_imagem_tela_cheia(
            view,
            FakeEvent(x=800, y=450),
        )

        self.assertEqual("break", retorno)
        self.assertFalse(view._fullscreen_pan_ativo)

    def test_principal_nao_abre_durante_selecao_de_leds(self):
        view = FakeView()
        view.selecao_led_ativa = True

        with patch.object(modulo, "abrir_imagem_tela_cheia") as abrir:
            evento_abrir_imagem_principal_tela_cheia(view)
            abrir.assert_not_called()

    def test_principal_abre_fora_do_editor(self):
        view = FakeView()

        with patch.object(modulo, "abrir_imagem_tela_cheia") as abrir:
            evento_abrir_imagem_principal_tela_cheia(view)
            abrir.assert_called_once_with(view, "principal")

    def test_visualizador_nao_mexe_na_camera_ou_mascaras(self):
        codigo = inspect.getsource(modulo)
        self.assertNotIn("camera_service", codigo)
        self.assertNotIn("leds_fixos_configurados =", codigo)
        self.assertNotIn("resolucao_camera", codigo)
        self.assertNotIn("VideoCapture", codigo)


if __name__ == "__main__":
    unittest.main()
