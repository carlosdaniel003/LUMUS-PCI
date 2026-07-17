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
    CAMERA_FPS,
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
    def test_perfil_equilibrio_e_1080p30(self):
        self.assertEqual((1920, 1080), (CAMERA_WIDTH, CAMERA_HEIGHT))
        self.assertEqual(30, CAMERA_FPS)
        self.assertEqual((1920, 1080), CAMERA_RESOLUTION_FALLBACKS[0])
        self.assertIn((2560, 1440), CAMERA_RESOLUTION_FALLBACKS)
        self.assertIn((3840, 2160), CAMERA_RESOLUTION_FALLBACKS)
        self.assertEqual((640, 480), CAMERA_RESOLUTION_FALLBACKS[-1])

    def test_candidatos_comecam_em_1080p_e_mantem_maiores_e_menores(self):
        candidatos = construir_candidatos_linux(
            (("/dev/video0", 0),),
            largura=1920,
            altura=1080,
            fps=30,
            gstreamer_disponivel=True,
            resolucoes_preferidas=CAMERA_RESOLUTION_FALLBACKS,
        )
        primeiro = candidatos[0]
        self.assertEqual("gstreamer", primeiro.tipo)
        self.assertEqual("MJPG", primeiro.formato)
        self.assertEqual((1920, 1080), (primeiro.largura, primeiro.altura))
        resolucoes = {
            (item.largura, item.altura)
            for item in candidatos
            if item.largura > 0 and item.altura > 0
        }
        self.assertIn((3840, 2160), resolucoes)
        self.assertIn((1280, 720), resolucoes)

    def test_v4l2_aplica_resolucao_do_fallback_escolhido(self):
        service = object.__new__(NativeResolutionThreadedCameraService)
        service.largura = 1920
        service.altura = 1080
        service.fps = 30
        capture = FakeCapture()
        candidato = LinuxCameraBackendCandidate(
            key="v4l2:0:MJPG:1280x720",
            nome="V4L2 MJPG 1280x720",
            tipo="v4l2",
            origem=0,
            backend=cv2.CAP_V4L2,
            dispositivo="/dev/video0",
            formato="MJPG",
            largura=1280,
            altura=720,
            indice=0,
        )

        service._configurar_capture_direto(capture, candidato)
        definicoes = dict(capture.definicoes)
        self.assertEqual(1280, definicoes[cv2.CAP_PROP_FRAME_WIDTH])
        self.assertEqual(720, definicoes[cv2.CAP_PROP_FRAME_HEIGHT])
        self.assertEqual(30, definicoes[cv2.CAP_PROP_FPS])


if __name__ == "__main__":
    unittest.main()
