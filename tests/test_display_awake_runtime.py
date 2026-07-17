import subprocess
import unittest

from src.platform.display_awake_runtime import (
    LinuxDisplayAwakeController,
    parse_xset_display_state,
)
from src.ui.main_window_parts.lifecycle.configurar_atalhos_tela import (
    configurar_atalhos_tela,
)
from src.ui.main_window_parts.lifecycle.init_view import (
    __init__ as init_view,
)


XSET_OUTPUT = """
Screen Saver:
  prefer blanking:  yes    allow exposures:  yes
  timeout:  600    cycle:  600
DPMS (Energy Star):
  Standby: 600    Suspend: 900    Off: 1200
  DPMS is Enabled
"""


class FakeProcess:
    _next_pid = 999000

    def __init__(self, command):
        self.command = list(command)
        self.pid = FakeProcess._next_pid
        FakeProcess._next_pid += 1
        self.terminated = False
        self.killed = False

    def poll(self):
        return 0 if self.terminated or self.killed else None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        self.terminated = True
        return 0

    def kill(self):
        self.killed = True


class FakeRoot:
    def __init__(self):
        self.commands = []
        self.bindings = {}
        self.after_calls = []
        self.screen_width = 1366
        self.screen_height = 768

    def update_idletasks(self):
        return None

    def winfo_id(self):
        return 321

    def winfo_screenwidth(self):
        return self.screen_width

    def winfo_screenheight(self):
        return self.screen_height

    def title(self, value):
        self.commands.append(("title", value))

    def geometry(self, value):
        self.commands.append(("geometry", value))

    def minsize(self, width, height):
        self.commands.append(("minsize", width, height))

    def configure(self, **kwargs):
        self.commands.append(("configure", kwargs))

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback

    def after(self, delay, callback):
        self.after_calls.append((delay, callback))
        return f"after-{len(self.after_calls)}"


class DummyView:
    COR_FUNDO_APP = "#000000"

    def __init__(self):
        self.fullscreen_calls = 0
        self.root = None
        self.callbacks = None

    def configurar_atalhos_tela(self):
        configurar_atalhos_tela(self)

    def configurar_estilo_tabela(self):
        return None

    def criar_layout(self):
        return None

    def iniciar_relogio_sistema(self):
        return None

    def alternar_tela_cheia(self, _event=None):
        self.fullscreen_calls += 1
        return "break"

    def sair_tela_cheia(self, _event=None):
        return "break"


class DisplayAwakeRuntimeTests(unittest.TestCase):
    def test_parseia_estado_xset_para_restauracao(self):
        state = parse_xset_display_state(XSET_OUTPUT)
        self.assertEqual(600, state.screensaver_timeout)
        self.assertEqual(600, state.screensaver_cycle)
        self.assertTrue(state.dpms_enabled)
        self.assertEqual((600, 900, 1200), (
            state.dpms_standby,
            state.dpms_suspend,
            state.dpms_off,
        ))

    def test_inibe_e_restaura_tela_no_linux(self):
        root = FakeRoot()
        commands = []
        processes = []

        def which(command):
            return f"/usr/bin/{command}"

        def runner(command, **_kwargs):
            commands.append(list(command))
            stdout = XSET_OUTPUT if command == ["xset", "q"] else ""
            return subprocess.CompletedProcess(command, 0, stdout, "")

        def popen(command, **_kwargs):
            process = FakeProcess(command)
            processes.append(process)
            return process

        controller = LinuxDisplayAwakeController(
            root=root,
            platform_name="linux",
            environ={"DISPLAY": ":0"},
            which=which,
            runner=runner,
            popen=popen,
        )

        controller.start()

        self.assertTrue(controller.active)
        self.assertIn(
            ["xdg-screensaver", "suspend", "321"],
            commands,
        )
        self.assertIn(["xset", "s", "off"], commands)
        self.assertIn(["xset", "-dpms"], commands)
        self.assertEqual(2, len(processes))
        self.assertIn("systemd-inhibit", controller.strategies)

        controller.stop()

        self.assertFalse(controller.active)
        self.assertIn(
            ["xdg-screensaver", "resume", "321"],
            commands,
        )
        self.assertIn(["xset", "s", "600", "600"], commands)
        self.assertIn(["xset", "+dpms"], commands)
        self.assertIn(
            ["xset", "dpms", "600", "900", "1200"],
            commands,
        )
        self.assertTrue(all(item.terminated for item in processes))

    def test_sem_sessao_grafica_permanece_inativo(self):
        controller = LinuxDisplayAwakeController(
            root=FakeRoot(),
            platform_name="linux",
            environ={},
            which=lambda _command: None,
        )
        controller.start()
        self.assertFalse(controller.active)

    def test_interface_inicia_em_tela_cheia_e_f11_alterna(self):
        root = FakeRoot()
        view = DummyView()
        callbacks = {
            "capturar_frame_camera_para_analise": lambda _event=None: None,
        }

        init_view(view, root, callbacks, raio_atual_px=15)

        self.assertIn("<F11>", root.bindings)
        self.assertEqual(view.alternar_tela_cheia, root.bindings["<F11>"])
        self.assertEqual((120, view.alternar_tela_cheia), root.after_calls[-1])
        self.assertIn(("geometry", "1366x768"), root.commands)
        self.assertIn(("minsize", 1280, 760), root.commands)

        root.after_calls[-1][1]()
        self.assertEqual(1, view.fullscreen_calls)


if __name__ == "__main__":
    unittest.main()
