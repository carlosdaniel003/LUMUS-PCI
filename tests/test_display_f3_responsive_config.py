from __future__ import annotations

import inspect
import unittest

import src.platform.display_f3_responsive_config as module


class _WindowZoomed:
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


class _WindowFallback(_WindowZoomed):
    def __init__(self):
        super().__init__()
        self.geometry_value = None

    def state(self, value):
        raise RuntimeError("zoomed unsupported")

    def attributes(self, *args):
        raise RuntimeError("attribute unsupported")

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080

    def geometry(self, value):
        self.geometry_value = value


class DisplayF3ResponsiveConfigTests(unittest.TestCase):
    def test_uses_native_zoom_and_enables_resize(self):
        window = _WindowZoomed()
        mode = module.maximizar_janela_configuracao_display_f3(window)
        self.assertEqual("state_zoomed", mode)
        self.assertEqual((True, True), window.resizable_value)
        self.assertEqual("zoomed", window.state_value)
        self.assertEqual(
            (module.F3_CONFIG_MIN_WIDTH, module.F3_CONFIG_MIN_HEIGHT),
            window.min_size,
        )

    def test_has_full_screen_geometry_fallback(self):
        window = _WindowFallback()
        mode = module.maximizar_janela_configuracao_display_f3(window)
        self.assertEqual("screen_geometry", mode)
        self.assertEqual("1920x1080+0+0", window.geometry_value)

    def test_installer_reapplies_maximize_after_layout(self):
        source = inspect.getsource(module.instalar_configuracao_responsiva_display_f3)
        self.assertIn("after_idle", source)
        self.assertIn("maximizar_janela_configuracao_display_f3", source)

    def test_module_isolated_from_f2(self):
        source = inspect.getsource(module)
        self.assertNotIn("src.platform.f2_", source)
        self.assertNotIn("F2Automatic", source)


if __name__ == "__main__":
    unittest.main()
