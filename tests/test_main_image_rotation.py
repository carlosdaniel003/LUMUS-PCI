import inspect
import unittest

import numpy as np

import src.ui.main_window_parts.image.rotacao_visual_principal as modulo
from src.ui.main_window_parts.image.rotacao_visual_principal import (
    converter_ponto_original_para_visual,
    converter_ponto_visual_para_original,
    dimensoes_visuais,
    normalizar_rotacao_visual,
    proxima_rotacao_visual,
    rotacionar_imagem_principal,
    rotacionar_imagem_visual,
)


class FakeView:
    def __init__(self):
        self.selecao_led_ativa = False
        self.rotacao_visual_principal = 0
        self.botao_rotacao_principal = None
        self.imagem_canvas_original = None
        self.status = []

    def atualizar_status(self, mensagem):
        self.status.append(mensagem)


class MainImageRotationTests(unittest.TestCase):
    def test_normalizacao_e_ciclo(self):
        self.assertEqual(0, normalizar_rotacao_visual(None))
        self.assertEqual(0, normalizar_rotacao_visual(360))
        self.assertEqual(90, proxima_rotacao_visual(0))
        self.assertEqual(180, proxima_rotacao_visual(90))
        self.assertEqual(270, proxima_rotacao_visual(180))
        self.assertEqual(0, proxima_rotacao_visual(270))

    def test_dimensoes_trocam_apenas_em_90_e_270(self):
        self.assertEqual((1920, 1080), dimensoes_visuais(1920, 1080, 0))
        self.assertEqual((1080, 1920), dimensoes_visuais(1920, 1080, 90))
        self.assertEqual((1920, 1080), dimensoes_visuais(1920, 1080, 180))
        self.assertEqual((1080, 1920), dimensoes_visuais(1920, 1080, 270))

    def test_rotacao_da_copia_nao_muta_fonte(self):
        imagem = np.array(
            [
                [[1, 1, 1], [2, 2, 2], [3, 3, 3]],
                [[4, 4, 4], [5, 5, 5], [6, 6, 6]],
            ],
            dtype=np.uint8,
        )
        original = imagem.copy()
        rotacionada = rotacionar_imagem_visual(imagem, 90)

        self.assertEqual((3, 2, 3), rotacionada.shape)
        self.assertTrue(np.array_equal(imagem, original))
        self.assertEqual(4, int(rotacionada[0, 0, 0]))
        self.assertEqual(1, int(rotacionada[0, 1, 0]))

    def test_pontos_fazem_roundtrip_em_todas_rotacoes(self):
        largura = 1920
        altura = 1080
        pontos = [(0, 0), (1919, 1079), (423, 711), (1007, 515)]

        for rotacao in (0, 90, 180, 270):
            for x, y in pontos:
                vx, vy = converter_ponto_original_para_visual(
                    x,
                    y,
                    largura,
                    altura,
                    rotacao,
                )
                ox, oy = converter_ponto_visual_para_original(
                    vx,
                    vy,
                    largura,
                    altura,
                    rotacao,
                )
                self.assertAlmostEqual(x, ox)
                self.assertAlmostEqual(y, oy)

    def test_botao_bloqueia_rotacao_durante_editor(self):
        view = FakeView()
        view.selecao_led_ativa = True

        rotacionar_imagem_principal(view)

        self.assertEqual(0, view.rotacao_visual_principal)
        self.assertEqual(1, len(view.status))
        self.assertIn("Selecionar LEDs", view.status[0])

    def test_modulo_nao_altera_camera_config_ou_mascaras(self):
        codigo = inspect.getsource(modulo)
        self.assertNotIn("camera_service", codigo)
        self.assertNotIn("config_repository", codigo)
        self.assertNotIn("leds_fixos_configurados =", codigo)
        self.assertNotIn("salvar_configuracoes_sistema", codigo)

    def test_redesenho_visual_nao_chama_desenhar_canvas(self):
        codigo = inspect.getsource(modulo.redesenhar_rotacao_visual_principal)
        self.assertNotIn("desenhar_canvas(", codigo)
        self.assertNotIn("adicionar_resultado_historico", codigo)


if __name__ == "__main__":
    unittest.main()
