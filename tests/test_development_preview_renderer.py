import unittest

import numpy as np

from src.platform.blue_operation_window import (
    substituir_texto_marcacao_azul,
)
from src.ui.main_window_parts.image.atualizar_imagem_principal_redimensionada import (
    _codificar_ppm_bgr,
)


class DevelopmentPreviewRendererTests(unittest.TestCase):
    def test_ppm_converte_bgr_para_rgb_sem_compactacao(self):
        imagem = np.array([[[10, 20, 30]]], dtype=np.uint8)
        dados = _codificar_ppm_bgr(imagem)
        self.assertTrue(dados.startswith(b"P6\n1 1\n255\n"))
        self.assertEqual(bytes((30, 20, 10)), dados[-3:])

    def test_texto_de_producao_indica_marcacao_azul(self):
        texto = "LEDs apagados: LED_001\nMarcados em vermelho na câmera"
        corrigido = substituir_texto_marcacao_azul(texto)
        self.assertIn("Marcados em azul na câmera", corrigido)
        self.assertNotIn("vermelho", corrigido)


if __name__ == "__main__":
    unittest.main()
