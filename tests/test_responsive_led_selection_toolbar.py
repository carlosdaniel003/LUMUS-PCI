import inspect
import unittest
from unittest.mock import patch

from src.platform.fullscreen_led_selection import FullscreenLedSelectionMixin
from src.platform.responsive_led_selection_toolbar import (
    _aplicar_layout_toolbar_roi,
    calcular_perfil_toolbar_roi,
    deve_reagir_configure_toolbar_roi,
)


class _FakeWidget:
    def __init__(self, master=None, manager="pack"):
        self.master = master
        self.manager = manager
        self.grid_calls = 0
        self.forget_calls = 0
        self.configure_calls = 0
        self.column_calls = 0

    def winfo_manager(self):
        return self.manager

    def pack_forget(self):
        self.forget_calls += 1
        self.manager = ""

    def grid_forget(self):
        self.forget_calls += 1
        self.manager = ""

    def place_forget(self):
        self.forget_calls += 1
        self.manager = ""

    def grid(self, **_kwargs):
        self.grid_calls += 1
        self.manager = "grid"

    def configure(self, **_kwargs):
        self.configure_calls += 1

    def pack_configure(self, **_kwargs):
        return None

    def pack_propagate(self, *_args):
        return None

    def grid_propagate(self, *_args):
        return None

    def grid_columnconfigure(self, *_args, **_kwargs):
        self.column_calls += 1


class _FakeWindow:
    def __init__(self, largura=1366):
        self.largura = largura

    def winfo_width(self):
        return self.largura

    def winfo_screenwidth(self):
        return 1920


class _FakeApp:
    pass


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

    def test_configure_repetido_nao_remapeia_botoes(self):
        app = _FakeApp()
        janela = _FakeWindow(1366)
        barra = _FakeWidget(manager="pack")
        seletor = _FakeWidget(master=barra, manager="pack")
        frame_botoes = _FakeWidget(master=seletor, manager="pack")
        botoes = [
            _FakeWidget(master=frame_botoes, manager="pack")
            for _ in range(4)
        ]

        with patch(
            "src.platform.responsive_led_selection_toolbar._widgets_ferramenta",
            return_value=botoes,
        ), patch(
            "src.platform.responsive_led_selection_toolbar._localizar_textos_barra",
            return_value=(None, None),
        ):
            _aplicar_layout_toolbar_roi(app, janela)
            grids_iniciais = [botao.grid_calls for botao in botoes]
            forgets_iniciais = [botao.forget_calls for botao in botoes]

            _aplicar_layout_toolbar_roi(app, janela)
            janela.largura = 1400
            _aplicar_layout_toolbar_roi(app, janela)

            self.assertEqual(grids_iniciais, [botao.grid_calls for botao in botoes])
            self.assertEqual(
                forgets_iniciais,
                [botao.forget_calls for botao in botoes],
            )

            janela.largura = 900
            _aplicar_layout_toolbar_roi(app, janela)

        self.assertTrue(all(botao.grid_calls == 2 for botao in botoes))
        self.assertEqual(
            forgets_iniciais,
            [botao.forget_calls for botao in botoes],
        )

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

    def test_forget_de_todos_os_botoes_ocorre_antes_do_primeiro_grid(self):
        import src.platform.responsive_led_selection_toolbar as modulo

        fonte = inspect.getsource(modulo._posicionar_botoes_ferramenta)
        pos_if = fonte.index("if primeira_montagem:")
        pos_forget = fonte.index("_esquecer_geometria(botao)")
        pos_grid_loop = fonte.index("for indice, botao in enumerate(botoes):")
        pos_grid = fonte.index("botao.grid(")
        self.assertLess(pos_if, pos_forget)
        self.assertLess(pos_forget, pos_grid_loop)
        self.assertLess(pos_grid_loop, pos_grid)


if __name__ == "__main__":
    unittest.main()
