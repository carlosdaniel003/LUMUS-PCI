import unittest

import cv2
import numpy as np

from src.platform.frame_integrity import FrameIntegrityValidator


class FrameIntegrityValidatorTests(unittest.TestCase):
    def setUp(self):
        self.base = np.zeros((480, 640, 3), dtype=np.uint8)
        for y in range(480):
            self.base[y, :, :] = (40 + y // 8, 70 + y // 10, 90 + y // 12)
        cv2.rectangle(self.base, (40, 190), (600, 230), (180, 180, 180), -1)
        for x in range(80, 600, 55):
            cv2.circle(self.base, (x, 130), 8, (20, 20, 255), -1)
            cv2.circle(self.base, (x, 330), 8, (20, 20, 255), -1)

    def test_frames_normais_sao_aceitos(self):
        validador = FrameIntegrityValidator()
        self.assertTrue(validador.avaliar(self.base).valido)

        segundo = self.base.copy()
        segundo = cv2.convertScaleAbs(segundo, alpha=1.0, beta=2)
        resultado = validador.avaliar(segundo)
        self.assertTrue(resultado.valido, resultado)

    def test_variacao_global_de_brilho_nao_parece_banda(self):
        validador = FrameIntegrityValidator()
        validador.avaliar(self.base)
        mais_claro = cv2.convertScaleAbs(self.base, alpha=1.0, beta=20)
        resultado = validador.avaliar(mais_claro)
        self.assertTrue(resultado.valido, resultado)

    def test_bandas_horizontais_deslocadas_sao_rejeitadas(self):
        validador = FrameIntegrityValidator()
        validador.avaliar(self.base)

        corrompido = self.base.copy()
        corrompido[120:155] = self.base[260:295]
        corrompido[250:285] = self.base[70:105]
        corrompido[360:390] = self.base[180:210]

        resultado = validador.avaliar(corrompido)
        self.assertFalse(resultado.valido, resultado)
        self.assertEqual("bandas_horizontais", resultado.motivo)
        self.assertGreaterEqual(resultado.grupos_horizontais, 2)

    def test_validador_nao_aprende_com_frame_rejeitado(self):
        validador = FrameIntegrityValidator()
        validador.avaliar(self.base)
        corrompido = self.base.copy()
        corrompido[100:140] = self.base[280:320]
        corrompido[300:340] = self.base[40:80]

        self.assertFalse(validador.avaliar(corrompido).valido)
        self.assertFalse(validador.avaliar(corrompido).valido)
        self.assertTrue(validador.avaliar(self.base).valido)


if __name__ == "__main__":
    unittest.main()
