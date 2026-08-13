import inspect
import unittest

from src.platform.camera_screenshot import CameraScreenshotMixin, SCREENSHOT_DIR
from src.platform.raspberry_pi3_production_app import RaspberryPi3ProductionApp
from src.ui.main_window_parts.panels.criar_painel_principal import criar_painel_principal


class CameraScreenshotTests(unittest.TestCase):
    def test_perfil_final_inclui_screenshot(self):
        self.assertIn(CameraScreenshotMixin, RaspberryPi3ProductionApp.__mro__)

    def test_pasta_de_screenshot_e_capturas(self):
        self.assertEqual("screenshots", SCREENSHOT_DIR.name)
        self.assertEqual("capturas", SCREENSHOT_DIR.parent.name)

    def test_botao_e_captura_nao_reiniciam_camera(self):
        fonte_painel = inspect.getsource(criar_painel_principal)
        fonte_captura = inspect.getsource(CameraScreenshotMixin.capturar_screenshot_camera)
        self.assertIn("Screenshot", fonte_painel)
        self.assertNotIn("parar_tela_ao_vivo", fonte_captura)
        self.assertNotIn("iniciar_tela_ao_vivo", fonte_captura)
        self.assertIn("threading.Thread", fonte_captura)


if __name__ == "__main__":
    unittest.main()
