import inspect
import unittest
from unittest.mock import patch

import src.ui.main_window_parts.image.fullscreen_image_viewer as modulo
from src.ui.main_window_parts.image.fullscreen_image_viewer import (
    VISUALIZACOES_TELA_CHEIA,
    calcular_encaixe_imagem,
    configurar_abertura_imagens_tela_cheia,
    evento_abrir_imagem_principal_tela_cheia,
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
