import unittest

from src.platform.display_settings_redesign import (
    BUTTON_ROLES,
    SECTION_ACCENTS,
    calcular_tamanho_janela,
    texto_ajuda_rodape,
)


class DisplaySettingsRedesignTests(unittest.TestCase):
    def test_tamanho_confortavel_em_full_hd(self):
        self.assertEqual((1040, 820), calcular_tamanho_janela(1920, 1080))

    def test_tamanho_respeita_monitor_menor(self):
        self.assertEqual((820, 680), calcular_tamanho_janela(900, 720))

    def test_secoes_usam_acentos_semanticos(self):
        self.assertEqual("info", SECTION_ACCENTS["Referências fixas"])
        self.assertEqual("selection", SECTION_ACCENTS["LEDs fixos"])
        self.assertEqual("primary", SECTION_ACCENTS["Raio de seleção dos LEDs"])
        self.assertEqual("success", SECTION_ACCENTS["Armazenamento"])
        self.assertEqual("warning", SECTION_ACCENTS["Rotação da imagem"])

    def test_botoes_principais_e_secundarios_tem_hierarquia(self):
        self.assertEqual("success_outline", BUTTON_ROLES["Ref. aceso"])
        self.assertEqual("danger_outline", BUTTON_ROLES["Ref. apagado"])
        self.assertEqual("selection_outline", BUTTON_ROLES["Configurar LEDs"])
        self.assertEqual("primary", BUTTON_ROLES["Salvar LEDs"])
        self.assertEqual("primary", BUTTON_ROLES["Salvar"])
        self.assertEqual("neutral", BUTTON_ROLES["Cancelar"])

    def test_rodape_informa_navegacao_sem_texto_excessivo(self):
        texto = texto_ajuda_rodape()
        self.assertIn("Roda do mouse", texto)
        self.assertIn("Ctrl+1/2", texto)
        self.assertIn("Ctrl+Enter", texto)
        self.assertIn("Esc", texto)
        self.assertLess(len(texto), 190)


if __name__ == "__main__":
    unittest.main()
