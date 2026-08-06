import inspect
import unittest

import src.platform.display_settings_fullscreen as modulo
from src.platform.display_settings_fullscreen import (
    calcular_margem_responsiva,
    instalar_configuracoes_fullscreen_display,
)
from src.ui.main_window import ODINView


class FakeRootFrame:
    def __init__(self):
        self.pack_calls = []

    def pack_configure(self, **kwargs):
        self.pack_calls.append(kwargs)


class FakeWindow:
    def __init__(self, width=1920):
        self.width = width
        self.frame = FakeRootFrame()
        self.bindings = {}
        self.attr_calls = []
        self.lift_calls = 0
        self.focus_calls = 0

    def winfo_children(self):
        return (self.frame,)

    def winfo_width(self):
        return self.width

    def bind(self, event, callback, add=None):
        self.bindings[event] = callback

    def overrideredirect(self, _value):
        return None

    def attributes(self, name, value):
        self.attr_calls.append((name, value))

    def lift(self):
        self.lift_calls += 1

    def focus_force(self):
        self.focus_calls += 1


class DisplaySettingsFullscreenTests(unittest.TestCase):
    def test_margem_compacta_em_tela_menor(self):
        self.assertEqual(14, calcular_margem_responsiva(900))

    def test_margem_intermediaria_em_tela_media(self):
        self.assertEqual(24, calcular_margem_responsiva(1280))

    def test_margem_responsiva_em_full_hd(self):
        self.assertEqual(52, calcular_margem_responsiva(1920))

    def test_margem_possui_limite_maximo(self):
        self.assertEqual(72, calcular_margem_responsiva(3840))

    def test_largura_invalida_nao_quebra_calculo(self):
        self.assertEqual(14, calcular_margem_responsiva(-1))

    def test_modulo_nao_troca_pack_por_grid(self):
        codigo = inspect.getsource(modulo)
        self.assertNotIn(".grid(", codigo)
        self.assertNotIn("_organizar_linha_controle", codigo)

    def test_modulo_nao_patcha_tema_global(self):
        codigo = inspect.getsource(modulo)
        self.assertNotIn("DisplayThemeMixin", codigo)
        self.assertNotIn("_PATCH_THEME", codigo)

    def test_existe_apenas_uma_reaplicacao_tardia(self):
        codigo = inspect.getsource(modulo)
        self.assertEqual(1, codigo.count("janela.after("))
        self.assertNotIn("for atraso in", codigo)

    def test_fullscreen_e_ativado_somente_uma_vez(self):
        janela = FakeWindow()

        modulo._ativar_tela_cheia(janela)
        modulo._ativar_tela_cheia(janela)

        self.assertEqual([("-fullscreen", True)], janela.attr_calls)
        self.assertEqual(1, janela.lift_calls)
        self.assertEqual(1, janela.focus_calls)

    def test_resize_igual_nao_dispara_reflow_repetido(self):
        janela = FakeWindow(width=1920)

        modulo._instalar_margem_responsiva(janela)
        self.assertEqual(1, len(janela.frame.pack_calls))

        callback = janela.bindings["<Configure>"]
        evento_full_hd = type("Event", (), {"width": 1920})()
        callback(evento_full_hd)
        callback(evento_full_hd)

        self.assertEqual(1, len(janela.frame.pack_calls))

        evento_hd = type("Event", (), {"width": 1280})()
        callback(evento_hd)
        self.assertEqual(2, len(janela.frame.pack_calls))

    def test_instalador_e_idempotente(self):
        original = ODINView.abrir_janela_configuracoes
        try:
            instalar_configuracoes_fullscreen_display()
            primeira = ODINView.abrir_janela_configuracoes
            instalar_configuracoes_fullscreen_display()
            segunda = ODINView.abrir_janela_configuracoes

            self.assertIs(primeira, segunda)
            self.assertTrue(
                getattr(
                    primeira,
                    "_odin_display_settings_fullscreen_estavel",
                    False,
                )
            )
            self.assertIs(original, getattr(primeira, "_odin_original"))
        finally:
            ODINView.abrir_janela_configuracoes = original


if __name__ == "__main__":
    unittest.main()
