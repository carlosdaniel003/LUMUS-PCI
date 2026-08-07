import inspect
import unittest
from unittest.mock import patch

import numpy as np

from src.platform.area_roi_editor_v4 import AreaRoiEditorV4Mixin
from src.platform.rotated_roi_editor import RotatedAreaRoiEditorMixin
from src.ui.main_window_parts.image.rotacao_visual_principal import (
    converter_delta_visual_para_original,
    obter_ponto_canvas_view,
    obter_retangulo_canvas_view,
)


class FakeView:
    def __init__(self, rotacao=90):
        self.rotacao_visual_principal = rotacao
        self.botao_rotacao_principal = None
        self.imagem_canvas_original = None
        self.escala_exibicao = 1.0
        self.deslocamento_imagem_x = 0
        self.deslocamento_imagem_y = 0
        self.status = []

    def atualizar_status(self, mensagem):
        self.status.append(str(mensagem))


class RotatedRoiEditorTests(unittest.TestCase):
    def test_delta_das_setas_segue_orientacao_visual(self):
        self.assertEqual((-1, 0), converter_delta_visual_para_original(-1, 0, 0))
        self.assertEqual((0, 1), converter_delta_visual_para_original(-1, 0, 90))
        self.assertEqual((1, 0), converter_delta_visual_para_original(-1, 0, 180))
        self.assertEqual((0, -1), converter_delta_visual_para_original(-1, 0, 270))

        self.assertEqual((0, -1), converter_delta_visual_para_original(0, -1, 0))
        self.assertEqual((-1, 0), converter_delta_visual_para_original(0, -1, 90))
        self.assertEqual((0, 1), converter_delta_visual_para_original(0, -1, 180))
        self.assertEqual((1, 0), converter_delta_visual_para_original(0, -1, 270))

    def test_ponto_original_e_projetado_no_canvas_rotacionado(self):
        view = FakeView(rotacao=90)
        view.imagem_canvas_original = np.zeros((3, 4, 3), dtype=np.uint8)
        view.escala_exibicao = 2.0
        view.deslocamento_imagem_x = 10
        view.deslocamento_imagem_y = 20

        self.assertEqual(
            (10.0, 22.0),
            obter_ponto_canvas_view(view, 1, 2),
        )

    def test_retangulo_rotacionado_e_normalizado(self):
        view = FakeView(rotacao=90)
        view.imagem_canvas_original = np.zeros((3, 4, 3), dtype=np.uint8)
        view.escala_exibicao = 1.0

        self.assertEqual(
            (0.0, 0.0, 2.0, 3.0),
            obter_retangulo_canvas_view(view, 0, 0, 3, 2),
        )

    def test_handles_do_editor_acompanham_rotacao(self):
        editor = object.__new__(RotatedAreaRoiEditorMixin)
        editor.view = FakeView(rotacao=90)
        editor.view.imagem_canvas_original = np.zeros((3, 4, 3), dtype=np.uint8)
        editor._area_roi_ids = {"LED_001", "LED_002"}
        editor._bbox_area_selecionada = lambda: (0, 0, 3, 2)

        handles = editor._handles_canvas()

        self.assertEqual((2.0, 0.0), handles["nw"])
        self.assertEqual((0.0, 3.0), handles["se"])

    def test_iniciar_selecao_restaura_rotacao_se_fluxo_interno_tentar_zerar(self):
        editor = object.__new__(RotatedAreaRoiEditorMixin)
        editor.view = FakeView(rotacao=270)
        editor.modo_atual = "selecionar_leds_camera"

        def fluxo_antigo(_self):
            _self.view.rotacao_visual_principal = 0

        with patch.object(
            AreaRoiEditorV4Mixin,
            "iniciar_selecao_led",
            fluxo_antigo,
        ):
            RotatedAreaRoiEditorMixin.iniciar_selecao_led(editor)

        self.assertEqual(270, editor.view.rotacao_visual_principal)
        self.assertTrue(editor.view.status)
        self.assertIn("270°", editor.view.status[-1])

    def test_editor_rotacionado_nao_grava_camera_nem_mascaras(self):
        import src.platform.rotated_roi_editor as modulo

        codigo = inspect.getsource(modulo)
        self.assertNotIn("config_repository", codigo)
        self.assertNotIn("camera_service", codigo)
        self.assertNotIn("salvar_leds_fixos", codigo)
        self.assertNotIn("salvar_configuracoes_sistema", codigo)


if __name__ == "__main__":
    unittest.main()
