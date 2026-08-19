import inspect
import unittest

from src.platform.fullscreen_led_selection import FullscreenLedSelectionMixin
from src.platform.responsive_led_selection_toolbar import (
    calcular_perfil_toolbar_roi,
    deve_reagir_configure_toolbar_roi,
)


class ResponsiveLedSelectionToolbarTests(unittest.TestCase):
    def test_notebook_mantem_quatro_ferramentas_com_area_clicavel_maior(self):
        perfil = calcular_perfil_toolbar_roi(1366)
        self.assertEqual("notebook", perfil["nome"])
        self.assertEqual(4, perfil["colunas"])
        self.assertGreaterEqual(perfil["fonte"], 10)
        self.assertGreaterEqual(perfil["padx"], 12)
        self.assertGreaterEqual(perfil["pady"], 7)

    def test_monitor_grande_aumenta_botoes(self):
        notebook = calcular_perfil_toolbar_roi(1366)
        amplo = calcular_perfil_toolbar_roi(1920)
        self.assertEqual("amplo", amplo["nome"])
        self.assertGreater(amplo["fonte"], notebook["fonte"])
        self.assertGreater(amplo["padx"], notebook["padx"])
        self.assertGreater(amplo["pady"], notebook["pady"])

    def test_tela_estreita_quebra_ferramentas_em_duas_colunas(self):
        perfil = calcular_perfil_toolbar_roi(900)
        self.assertEqual("compacto", perfil["nome"])
        self.assertEqual(2, perfil["colunas"])

    def test_patch_responsivo_esta_instalado_no_editor_real(self):
        metodo = FullscreenLedSelectionMixin._criar_interface_selecao_tela_cheia
        self.assertTrue(getattr(metodo, "_odin_toolbar_responsiva", False))

    def test_configure_que_muda_so_altura_nao_reagenda_layout(self):
        self.assertFalse(deve_reagir_configure_toolbar_roi(1366, 1366))

    def test_microoscilacao_x11_nao_reagenda_layout(self):
        self.assertFalse(deve_reagir_configure_toolbar_roi(1367, 1366))
        self.assertFalse(deve_reagir_configure_toolbar_roi(1365, 1366))

    def test_resize_real_reagenda_layout(self):
        self.assertTrue(deve_reagir_configure_toolbar_roi(1400, 1366))

    def test_cruzar_breakpoint_reage_mesmo_com_um_pixel(self):
        self.assertEqual("compacto", calcular_perfil_toolbar_roi(1049)["nome"])
        self.assertEqual("notebook", calcular_perfil_toolbar_roi(1050)["nome"])
        self.assertTrue(deve_reagir_configure_toolbar_roi(1050, 1049))

    def test_layout_usa_grid_elastico_sem_remap_continuo(self):
        import src.platform.responsive_led_selection_toolbar as modulo

        fonte = inspect.getsource(modulo)
        self.assertIn('sticky="nsew"', fonte)
        self.assertIn('uniform="ferramentas_roi"', fonte)
        self.assertIn('janela.bind("<Configure>"', fonte)
        self.assertIn("wraplength", fonte)
        self.assertIn("barra.configure(height=1)", fonte)
        self.assertIn("_odin_toolbar_roi_layout_inicializado", fonte)
        self.assertIn("if not inicializado:", fonte)
        self.assertIn("primeira_montagem=False", fonte)
        self.assertIn("deve_reagir_configure_toolbar_roi", fonte)

    def test_documenta_que_forget_so_e_usado_na_montagem_inicial(self):
        import src.platform.responsive_led_selection_toolbar as modulo

        fonte = inspect.getsource(modulo._posicionar_botoes_ferramenta)
        self.assertIn("if primeira_montagem:", fonte)
        self.assertIn("_esquecer_geometria(botao)", fonte)
        self.assertIn("botao.grid(", fonte)


if __name__ == "__main__":
    unittest.main()
