import inspect
import unittest

import numpy as np

import src.ui.main_window_parts.image.exibir_imagem_em_canvas as canvas_aux_module
from src.ui.main_window_parts.image.exibir_imagem_em_canvas import (
    preparar_imagem_auxiliar_visual,
)
from src.ui.main_window_parts.image.fullscreen_image_viewer import _imagem_fonte
from src.ui.main_window_parts.image.rotacao_visual_principal import (
    PAINEIS_AUXILIARES_ROTACIONADOS,
    definir_rotacao_visual_principal,
    redesenhar_paineis_auxiliares_rotacionados,
)


class FakeAuxView:
    def __init__(self):
        self.rotacao_visual_principal = 90
        self.botao_rotacao_principal = None
        self.imagem_canvas_original = None
        self.canvas_mapa_intensidade = object()
        self.canvas_imagem_teste = object()
        self.canvas_mascara = object()
        self.canvas_roi_debug = object()
        self.imagens_auxiliares_originais = {
            "heatmap": np.full((2, 3, 3), 10, dtype=np.uint8),
            "canal_v": np.full((3, 4), 20, dtype=np.uint8),
            "mascara": np.full((4, 5, 3), 30, dtype=np.uint8),
            "roi_debug": np.full((5, 6, 3), 40, dtype=np.uint8),
        }
        self.chamadas = []
        self.fullscreen_updates = []

    def exibir_imagem_em_canvas(self, canvas, imagem, chave):
        self.chamadas.append((canvas, chave, imagem.copy()))

    def atualizar_imagem_tela_cheia_se_aberta(self, chave):
        self.fullscreen_updates.append(chave)


class AuxiliaryImageRotationTests(unittest.TestCase):
    def test_quatro_paineis_derivados_estao_registrados(self):
        self.assertEqual(
            {
                "heatmap",
                "canal_v",
                "mascara",
                "roi_debug",
            },
            {chave for _, chave in PAINEIS_AUXILIARES_ROTACIONADOS},
        )

    def test_preview_auxiliar_segue_quatro_orientacoes_sem_mutar_fonte(self):
        imagem = np.array(
            [
                [[1, 1, 1], [2, 2, 2], [3, 3, 3]],
                [[4, 4, 4], [5, 5, 5], [6, 6, 6]],
            ],
            dtype=np.uint8,
        )
        original = imagem.copy()

        self.assertTrue(
            np.array_equal(preparar_imagem_auxiliar_visual(imagem, 0), imagem)
        )
        self.assertTrue(
            np.array_equal(
                preparar_imagem_auxiliar_visual(imagem, 90),
                np.rot90(imagem, k=3),
            )
        )
        self.assertTrue(
            np.array_equal(
                preparar_imagem_auxiliar_visual(imagem, 180),
                np.rot90(imagem, k=2),
            )
        )
        self.assertTrue(
            np.array_equal(
                preparar_imagem_auxiliar_visual(imagem, 270),
                np.rot90(imagem, k=1),
            )
        )
        self.assertTrue(np.array_equal(imagem, original))

    def test_redesenho_reenvia_as_quatro_fontes_originais(self):
        view = FakeAuxView()
        fontes_antes = {
            chave: imagem.copy()
            for chave, imagem in view.imagens_auxiliares_originais.items()
        }

        redesenhar_paineis_auxiliares_rotacionados(view)

        self.assertEqual(4, len(view.chamadas))
        self.assertEqual(
            ["heatmap", "canal_v", "mascara", "roi_debug"],
            [chave for _, chave, _ in view.chamadas],
        )
        for chave, original in fontes_antes.items():
            self.assertTrue(
                np.array_equal(view.imagens_auxiliares_originais[chave], original)
            )

    def test_fullscreen_auxiliar_tambem_recebe_rotacao_atual(self):
        view = FakeAuxView()
        fonte = view.imagens_auxiliares_originais["heatmap"].copy()
        fonte[0, 0] = (1, 2, 3)
        fonte[1, 2] = (7, 8, 9)
        view.imagens_auxiliares_originais["heatmap"] = fonte

        exibida = _imagem_fonte(view, "heatmap")

        self.assertEqual((3, 2, 3), exibida.shape)
        self.assertTrue(np.array_equal(exibida, np.rot90(fonte, k=3)))
        self.assertTrue(
            np.array_equal(view.imagens_auxiliares_originais["heatmap"], fonte)
        )

    def test_troca_de_rotacao_notifica_todos_os_cinco_fullscreens(self):
        view = FakeAuxView()

        definir_rotacao_visual_principal(view, 180)

        self.assertEqual(180, view.rotacao_visual_principal)
        self.assertEqual(
            ["principal", "heatmap", "canal_v", "mascara", "roi_debug"],
            view.fullscreen_updates,
        )

    def test_renderizador_auxiliar_aplica_rotacao_so_na_camada_visual(self):
        codigo = inspect.getsource(canvas_aux_module)
        self.assertIn("preparar_imagem_auxiliar_visual", codigo)
        self.assertIn("rotacao_visual_principal", codigo)
        self.assertNotIn("camera_service", codigo)
        self.assertNotIn("config_repository", codigo)
        self.assertNotIn("salvar_leds_fixos", codigo)


if __name__ == "__main__":
    unittest.main()
