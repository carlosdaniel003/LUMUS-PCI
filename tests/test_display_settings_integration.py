import inspect
import unittest

import src.platform.raspberry_pi3_production_app as app_module


class DisplaySettingsIntegrationTests(unittest.TestCase):
    def test_perfil_instala_uma_unica_camada_de_configuracoes(self):
        codigo = inspect.getsource(app_module)

        self.assertEqual(
            1,
            codigo.count("instalar_configuracoes_fullscreen_display()"),
        )
        self.assertNotIn("instalar_ponte_tema_configuracoes", codigo)
        self.assertNotIn("instalar_redesign_configuracoes_display", codigo)
        self.assertNotIn("instalar_ux_configuracoes_display()", codigo)

    def test_perfil_preserva_camera_fixa_e_mascaras_absolutas(self):
        codigo = inspect.getsource(app_module)

        self.assertIn("FixedFullHdCameraService", codigo)
        self.assertIn("instalar_repositorio_mascaras_absolutas()", codigo)
        self.assertIn("FullscreenLedSelectionMixin", codigo)


if __name__ == "__main__":
    unittest.main()
