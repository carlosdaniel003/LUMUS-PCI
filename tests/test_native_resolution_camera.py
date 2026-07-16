import unittest

import cv2

from src.platform.linux_camera_backend import (
    LinuxCameraBackendCandidate,
    construir_candidatos_linux,
)
from src.platform.native_threaded_camera_service import (
    NativeResolutionThreadedCameraService,
)
from src.platform.raspberry_pi3_settings import (
    CAMERA_HEIGHT,
    CAMERA_RESOLUTION_FALLBACKS,
    CAMERA_WIDTH,
)


class FakeCapture:
    def __init__(self):
        self.definicoes = []

    def set(self, propriedade, valor):
        self.definicoes.append((propriedade, valor))
        return True


class NativeResolutionCameraTests(unittest.TestCase):
    def test_perfil_prioriza_uhd(self):
        self.assertEqual((3840, 2160), (CAMERA_WIDTH, CAMERA_HEIGHT))
        self.assertEqual((3840, 2160), CAMERA_RESOLUTION_FALLBACKS[0])
        self.assertIn((1920, 1080), CAMERA_RESOLUTION_FALLBACKS)
        self.assertEqual((640, 480), CAMERA_RESOLUTION_FALLBACKS[-1])

    def test_candidatos_comecam_em_uhd_e_mantem_fallback(self):
        candidatos = construir_candidatos_linux(
            (("/dev/video0", 0),),
            largura=3840,
            altura=2160,
            fps=30,
            gstreamer_disponivel=True,
            resolucoes_preferidas=CAMERA_RESOLUTION_FALLBACKS,
        )
        primeiro = candidatos[0]
        self.assertEqual("gstreamer", primeiro.tipo)
        self.assertEqual("MJPG", primeiro.formato)
        self.assertEqual((3840, 2160), (primeiro.largura, primeiro.altura))
        self.assertTrue(
            any(
                (item.largura, item.altura) == (1920, 1080)
                for item in candidatos
            )
        )

    def test_v4l2_aplica_resolucao_do_fallback_escolhido(self):
        service = object.__new__(NativeResolutionThreadedCameraService)
        service.largura = 3840
        service.altura = 2160
        service.fps = 30
        capture = FakeCapture()
        candidato = LinuxCameraBackendCandidate(
            key="v4l2:0:MJPG:1920x1080",
            nome="V4L2 MJPG 1920x1080",
            tipo="v4l2",
            origem=0,
            backend=cv2.CAP_V4L2,
            dispositivo="/dev/video0",
            formato="MJPG",
            largura=1920,
            altura=1080,
            indice=0,
        )

        service._configurar_capture_direto(capture, candidato)
        definicoes = dict(capture.definicoes)
        self.assertEqual(1920, definicoes[cv2.CAP_PROP_FRAME_WIDTH])
        self.assertEqual(1080, definicoes[cv2.CAP_PROP_FRAME_HEIGHT])
        self.assertEqual(30, definicoes[cv2.CAP_PROP_FPS])


if __name__ == "__main__":
    unittest.main()
