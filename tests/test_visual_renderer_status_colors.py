import unittest
from types import SimpleNamespace

import numpy as np

from src.core.visual_renderer import (
    COR_ACESO_BGR,
    COR_APAGADO_BGR,
    COR_POUCA_LUZ_BGR,
    criar_heatmap_intensidade,
    criar_imagem_canal_v,
    criar_imagem_mascara_visual,
    criar_imagem_resultados_visuais,
    criar_imagem_roi_debug_ampliado,
)


class VisualRendererStatusColorsTests(unittest.TestCase):
    @staticmethod
    def _alvo(status: str, valor_binario: int):
        return SimpleNamespace(
            id="SEG_001",
            status=status,
            valor_binario=valor_binario,
            centro_x=50,
            centro_y=50,
            raio=14,
            tipo_roi="circulo",
            largura=None,
            altura=None,
            angulo=0.0,
            confianca=0.9,
        )

    @staticmethod
    def _imagem():
        imagem = np.zeros((120, 120, 3), dtype=np.uint8)
        imagem[30:90, 30:90] = (40, 80, 160)
        return imagem

    def assertColorPresent(self, imagem, cor):
        cor_np = np.asarray(cor, dtype=np.uint8)
        pixels = np.all(imagem == cor_np, axis=2)
        self.assertTrue(bool(np.any(pixels)), f"Cor BGR {cor} não encontrada")

    def test_pouca_luz_binario_um_e_renderizada_em_amarelo(self):
        alvo = self._alvo("POUCA_LUZ", 1)
        imagem = self._imagem()

        renderizacoes = (
            criar_imagem_canal_v(imagem, [alvo]),
            criar_heatmap_intensidade(imagem, [alvo]),
            criar_imagem_mascara_visual(imagem, [alvo]),
            criar_imagem_roi_debug_ampliado(imagem, alvo),
            criar_imagem_resultados_visuais(imagem, [alvo]),
        )

        for renderizacao in renderizacoes:
            with self.subTest(shape=renderizacao.shape):
                self.assertColorPresent(renderizacao, COR_POUCA_LUZ_BGR)

    def test_aceso_ok_e_renderizado_em_verde(self):
        alvo = self._alvo("ACESO", 1)
        resultado = criar_imagem_resultados_visuais(self._imagem(), [alvo])
        self.assertColorPresent(resultado, COR_ACESO_BGR)

    def test_apagado_ng_e_renderizado_em_azul(self):
        alvo = self._alvo("APAGADO", 0)
        resultado = criar_imagem_resultados_visuais(self._imagem(), [alvo])
        self.assertColorPresent(resultado, COR_APAGADO_BGR)


if __name__ == "__main__":
    unittest.main()
