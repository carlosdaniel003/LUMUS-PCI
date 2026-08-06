import unittest

from src.platform.display_settings_fullscreen import (
    calcular_margem_responsiva,
)


class DisplaySettingsFullscreenTests(unittest.TestCase):
    def test_margem_compacta_em_tela_menor(self):
        self.assertEqual(18, calcular_margem_responsiva(900))

    def test_margem_intermediaria_em_tela_media(self):
        self.assertEqual(42, calcular_margem_responsiva(1280))

    def test_margem_centraliza_conteudo_em_full_hd(self):
        self.assertEqual(220, calcular_margem_responsiva(1920))

    def test_margem_possui_limite_maximo(self):
        self.assertEqual(220, calcular_margem_responsiva(3840))

    def test_largura_invalida_nao_quebra_calculo(self):
        self.assertEqual(18, calcular_margem_responsiva(-1))


if __name__ == "__main__":
    unittest.main()
