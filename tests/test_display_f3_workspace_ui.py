from __future__ import annotations

import inspect
import unittest

import src.platform.display_f3_workspace_ui as module


class _Window:
    def __init__(self):
        self.resizable_value = None
        self.min_size = None
        self.state_value = None

    def resizable(self, width, height):
        self.resizable_value = (width, height)

    def minsize(self, width, height):
        self.min_size = (width, height)

    def update_idletasks(self):
        return None

    def state(self, value):
        self.state_value = value


class DisplayF3WorkspaceUiTests(unittest.TestCase):
    def test_native_maximize_preserves_title_bar(self):
        window = _Window()
        mode = module.maximizar_janela_workspace_f3(window)
        self.assertEqual("state_zoomed", mode)
        self.assertEqual((True, True), window.resizable_value)
        self.assertEqual("zoomed", window.state_value)

    def test_project_navigation_is_narrower_than_workspace(self):
        self.assertLess(module.F3_PROJECT_NAV_WIDTH, 360)
        self.assertGreaterEqual(module.F3_WORKSPACE_MAX_WIDTH, 1000)
        source = inspect.getsource(module.aplicar_workspace_projeto_display_f3)
        self.assertIn('fill="y"', source)
        self.assertIn("expand=False", source)
        self.assertIn("_centralizar_conteudo_canvas", source)

    def test_all_f3_configuration_windows_are_covered(self):
        source = inspect.getsource(module.instalar_workspace_telas_display_f3)
        for name in (
            "DisplayProjectConfigWindow",
            "DisplayCheckManagerWindow",
            "DisplayCheckMaskEditorWindow",
            "DisplayMaskEditorWindow",
            "DisplayReferenceConfigWindow",
            "DisplayReferenceRoiDialog",
        ):
            self.assertIn(name, source)
        self.assertNotIn('attributes("-fullscreen", True)', source)

    def test_editor_resize_is_debounced(self):
        self.assertGreaterEqual(module.F3_EDITOR_REDRAW_DELAY_MS, 50)
        source = inspect.getsource(module._instalar_redraw_configuracao_debounced)
        self.assertIn("after_cancel", source)
        self.assertIn("F3_EDITOR_REDRAW_DELAY_MS", source)

    def test_module_isolated_from_f2(self):
        source = inspect.getsource(module)
        self.assertNotIn("src.platform.f2_", source)
        self.assertNotIn("F2Automatic", source)


if __name__ == "__main__":
    unittest.main()
