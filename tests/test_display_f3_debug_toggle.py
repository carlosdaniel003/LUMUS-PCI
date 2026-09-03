from __future__ import annotations

import inspect
import unittest

import src.platform.display_f3_debug_toggle as module


class _Window:
    pass


class _App:
    def __init__(self, window=None):
        self.display_f3_window = window


class DisplayF3DebugToggleTests(unittest.TestCase):
    def test_debug_is_off_by_default(self):
        window = _Window()
        self.assertFalse(module.debug_tecnico_ativo_display_f3(window))
        self.assertFalse(module.debug_tecnico_ativo_display_f3(_App(window)))

    def test_explicit_flag_controls_debug(self):
        window = _Window()
        window._display_f3_technical_debug_enabled = True
        self.assertTrue(module.debug_tecnico_ativo_display_f3(window))
        self.assertTrue(module.debug_tecnico_ativo_display_f3(_App(window)))
        window._display_f3_technical_debug_enabled = False
        self.assertFalse(module.debug_tecnico_ativo_display_f3(_App(window)))

    def test_installer_adds_toggle_next_to_debug_and_defaults_off(self):
        source = inspect.getsource(module.instalar_toggle_debug_tecnico_display_f3)
        self.assertIn("tk.Checkbutton", source)
        self.assertIn("tk.BooleanVar(value=False)", source)
        self.assertIn("column=3", source)
        self.assertIn("set_technical_debug_enabled(False)", source)
        self.assertIn("state=tk.NORMAL if enabled else tk.DISABLED", inspect.getsource(module.aplicar_estado_debug_tecnico_display_f3))

    def test_open_debug_is_blocked_while_toggle_is_off(self):
        source = inspect.getsource(module.instalar_toggle_debug_tecnico_display_f3)
        self.assertIn("if not self.is_technical_debug_enabled()", source)
        self.assertIn("return None", source)

    def test_module_isolated_from_f2(self):
        source = inspect.getsource(module)
        self.assertNotIn("src.platform.f2_", source)
        self.assertNotIn("F2Automatic", source)


if __name__ == "__main__":
    unittest.main()
