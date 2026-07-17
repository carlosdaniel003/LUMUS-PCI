import unittest

from src.ui.main_window_parts.lifecycle.alternar_tela_cheia import (
    REFORCO_TELA_CHEIA_MS,
    alternar_tela_cheia,
)
from src.ui.main_window_parts.lifecycle.sair_tela_cheia import sair_tela_cheia


class FakeRoot:
    def __init__(self):
        self.commands = []
        self.after_calls = []
        self.cancelled = []

    def attributes(self, name, value):
        self.commands.append(("attributes", name, value))

    def overrideredirect(self, value):
        self.commands.append(("overrideredirect", value))

    def state(self, value):
        self.commands.append(("state", value))

    def geometry(self, value):
        self.commands.append(("geometry", value))

    def update_idletasks(self):
        self.commands.append(("update_idletasks",))

    def lift(self):
        self.commands.append(("lift",))

    def focus_force(self):
        self.commands.append(("focus_force",))

    def after(self, delay, callback):
        after_id = f"after-{len(self.after_calls) + 1}"
        self.after_calls.append((after_id, delay, callback))
        return after_id

    def after_cancel(self, after_id):
        self.cancelled.append(after_id)


class FakeView:
    def __init__(self):
        self.root = FakeRoot()
        self.tela_cheia_ativa = False
        self._reforco_tela_cheia_after_id = None
        self.maximize_calls = 0

    def obter_geometria_monitor_atual(self):
        return {
            "monitor_x": 0,
            "monitor_y": 0,
            "monitor_largura": 1920,
            "monitor_altura": 1080,
        }

    def maximizar_janela(self):
        self.maximize_calls += 1

    def sair_tela_cheia(self, evento=None):
        return sair_tela_cheia(self, evento)


class FullscreenNativeTests(unittest.TestCase):
    def test_entrada_usa_fullscreen_nativo_e_geometria_do_monitor(self):
        view = FakeView()

        retorno = alternar_tela_cheia(view)

        self.assertEqual("break", retorno)
        self.assertTrue(view.tela_cheia_ativa)
        self.assertIn(("geometry", "1920x1080+0+0"), view.root.commands)
        self.assertIn(
            ("attributes", "-fullscreen", True),
            view.root.commands,
        )
        self.assertIn(("overrideredirect", False), view.root.commands)
        self.assertNotIn(("overrideredirect", True), view.root.commands)
        self.assertEqual(1, len(view.root.after_calls))
        self.assertEqual(
            REFORCO_TELA_CHEIA_MS,
            view.root.after_calls[0][1],
        )

    def test_reforco_reaplica_fullscreen_depois_do_mapeamento(self):
        view = FakeView()
        alternar_tela_cheia(view)
        _after_id, _delay, callback = view.root.after_calls[0]

        callback()

        fullscreen_true = [
            command
            for command in view.root.commands
            if command == ("attributes", "-fullscreen", True)
        ]
        self.assertEqual(2, len(fullscreen_true))
        self.assertIsNone(view._reforco_tela_cheia_after_id)

    def test_f11_para_sair_cancela_reforco_pendente(self):
        view = FakeView()
        alternar_tela_cheia(view)
        pending_id = view._reforco_tela_cheia_after_id

        retorno = alternar_tela_cheia(view)

        self.assertEqual("break", retorno)
        self.assertFalse(view.tela_cheia_ativa)
        self.assertIn(pending_id, view.root.cancelled)
        self.assertIn(
            ("attributes", "-fullscreen", False),
            view.root.commands,
        )
        self.assertEqual(80, view.root.after_calls[-1][1])


if __name__ == "__main__":
    unittest.main()
