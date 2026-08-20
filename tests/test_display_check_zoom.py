from __future__ import annotations

import inspect
import unittest

from src.platform import display_check_editor
from src.platform.display_check_zoom import (
    instalar_zoom_check_display,
    proximo_zoom_check_ctrl_a,
)
from src.ui.main_window_parts.image.selection_zoom import (
    ZOOM_SELECAO_MAX,
    ZOOM_SELECAO_MIN,
)


class DisplayCheckZoomTests(unittest.TestCase):
    def test_ctrl_a_avanca_zoom_e_retorna_ao_enquadramento_no_maximo(self):
        self.assertGreater(
            proximo_zoom_check_ctrl_a(ZOOM_SELECAO_MIN),
            ZOOM_SELECAO_MIN,
        )
        self.assertEqual(
            ZOOM_SELECAO_MIN,
            proximo_zoom_check_ctrl_a(ZOOM_SELECAO_MAX),
        )

    def test_zoom_esta_instalado_somente_na_classe_visual_de_check(self):
        instalar_zoom_check_display()
        cls = display_check_editor.DisplayCheckMaskEditorWindow
        self.assertTrue(getattr(cls, "_odin_display_check_zoom", False))
        self.assertTrue(hasattr(cls, "_evento_ctrl_a_zoom_check"))
        self.assertTrue(hasattr(cls, "_evento_zoom_check"))
        self.assertTrue(hasattr(cls, "_iniciar_pan_check"))
        self.assertTrue(hasattr(cls, "_arrastar_pan_check"))

    def test_bindings_incluem_ctrl_a_ctrl_roda_e_pan(self):
        source = inspect.getsource(
            __import__(
                "src.platform.display_check_zoom",
                fromlist=["instalar_zoom_check_display"],
            )
        )
        for token in (
            '"<Control-a>"',
            '"<Control-A>"',
            '"<MouseWheel>"',
            '"<Button-4>"',
            '"<Button-5>"',
            '"<Button-2>"',
            '"<B2-Motion>"',
            "calcular_viewport_zoom_selecao",
            "calcular_centro_zoom_ancorado",
            "proximo_fator_zoom_selecao",
        ):
            self.assertIn(token, source)

    def test_renderizacao_de_zoom_usa_recorte_visivel_e_nao_imagem_8x_inteira(self):
        source = inspect.getsource(
            __import__(
                "src.platform.display_check_zoom",
                fromlist=["instalar_zoom_check_display"],
            )
        )
        self.assertIn("viewport.origem_visual_y:viewport.fim_visual_y", source)
        self.assertIn("viewport.origem_visual_x:viewport.fim_visual_x", source)
        self.assertIn("viewport.largura_render", source)
        self.assertIn("viewport.altura_render", source)

    def test_extensao_nao_depende_do_estado_mutavel_da_producao_f2(self):
        source = inspect.getsource(
            __import__(
                "src.platform.display_check_zoom",
                fromlist=["instalar_zoom_check_display"],
            )
        )
        for forbidden in (
            "leds_selecionados",
            "leds_fixos_configurados",
            "operacao_engine",
            "operacao_ativa",
            "preparar_tela_operacao",
            "disparar_inspecao_operacao",
            "linux_f2_fixed_resolution",
            "ConfigRepository",
            "LedSelection",
        ):
            self.assertNotIn(forbidden, source)

    def test_editor_de_mascaras_f3_carrega_a_extensao_sem_mudar_f2(self):
        source = inspect.getsource(
            __import__(
                "src.platform.display_mask_editor",
                fromlist=["DisplayMaskEditorWindow"],
            )
        )
        self.assertIn("src.platform.display_check_zoom", source)


if __name__ == "__main__":
    unittest.main()
