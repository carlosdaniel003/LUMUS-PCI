import unittest

from src.ui.main_window_parts.image.selection_zoom import (
    ZOOM_SELECAO_MAX,
    calcular_centro_zoom_ancorado,
    calcular_escala_zoom_selecao,
    calcular_viewport_zoom_selecao,
    proximo_fator_zoom_selecao,
)


class SelectionZoomMathTests(unittest.TestCase):
    def test_zoom_parte_de_100_e_respeita_limite_superior(self):
        fator = 1.0
        fator = proximo_fator_zoom_selecao(fator, 1)
        self.assertGreater(fator, 1.0)

        for _ in range(40):
            fator = proximo_fator_zoom_selecao(fator, 1)
        self.assertEqual(ZOOM_SELECAO_MAX, fator)

        for _ in range(40):
            fator = proximo_fator_zoom_selecao(fator, -1)
        self.assertEqual(1.0, fator)

    def test_100_porcento_mantem_fit_centralizado(self):
        viewport = calcular_viewport_zoom_selecao(
            largura_visual=1920,
            altura_visual=1080,
            largura_canvas=1600,
            altura_canvas=900,
            fator_zoom=1.0,
        )
        self.assertAlmostEqual(1600 / 1920, viewport.escala, places=6)
        self.assertEqual(1600, viewport.largura_virtual)
        self.assertEqual(900, viewport.altura_virtual)
        self.assertEqual(0, viewport.deslocamento_virtual_x)
        self.assertEqual(0, viewport.deslocamento_virtual_y)

    def test_zoom_8x_nao_cria_photoimage_8x_maior_que_a_tela(self):
        viewport = calcular_viewport_zoom_selecao(
            largura_visual=1920,
            altura_visual=1080,
            largura_canvas=1600,
            altura_canvas=900,
            fator_zoom=8.0,
            centro_visual_x=960,
            centro_visual_y=540,
        )
        self.assertGreater(viewport.largura_virtual, 10000)
        self.assertGreater(viewport.altura_virtual, 6000)
        self.assertLessEqual(viewport.largura_render, 1620)
        self.assertLessEqual(viewport.altura_render, 920)

    def test_zoom_mantem_ponto_sob_cursor(self):
        largura_visual = 1920
        altura_visual = 1080
        largura_canvas = 1600
        altura_canvas = 900
        atual = calcular_viewport_zoom_selecao(
            largura_visual,
            altura_visual,
            largura_canvas,
            altura_canvas,
            1.0,
        )
        ponteiro_x = 1100
        ponteiro_y = 350
        novo_fator = 2.0
        nova_escala = calcular_escala_zoom_selecao(
            largura_visual,
            altura_visual,
            largura_canvas,
            altura_canvas,
            novo_fator,
        )
        centro_x, centro_y = calcular_centro_zoom_ancorado(
            ponteiro_x=ponteiro_x,
            ponteiro_y=ponteiro_y,
            escala_atual=atual.escala,
            deslocamento_atual_x=atual.deslocamento_virtual_x,
            deslocamento_atual_y=atual.deslocamento_virtual_y,
            largura_virtual_atual=atual.largura_virtual,
            altura_virtual_atual=atual.altura_virtual,
            nova_escala=nova_escala,
            largura_canvas=largura_canvas,
            altura_canvas=altura_canvas,
            largura_visual=largura_visual,
            altura_visual=altura_visual,
        )
        novo = calcular_viewport_zoom_selecao(
            largura_visual,
            altura_visual,
            largura_canvas,
            altura_canvas,
            novo_fator,
            centro_x,
            centro_y,
        )

        ancora_visual_x = (
            ponteiro_x - atual.deslocamento_virtual_x
        ) / atual.escala
        ancora_visual_y = (
            ponteiro_y - atual.deslocamento_virtual_y
        ) / atual.escala
        novo_canvas_x = (
            novo.deslocamento_virtual_x
            + ancora_visual_x * novo.escala
        )
        novo_canvas_y = (
            novo.deslocamento_virtual_y
            + ancora_visual_y * novo.escala
        )
        self.assertAlmostEqual(ponteiro_x, novo_canvas_x, delta=1.5)
        self.assertAlmostEqual(ponteiro_y, novo_canvas_y, delta=1.5)


if __name__ == "__main__":
    unittest.main()
