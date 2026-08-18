import unittest
from unittest.mock import patch

import cv2
import numpy as np

from src.platform.camera_selection import criar_classe_camera_indice_estrito
from src.platform.linux_camera_backend import LinuxCameraBackendCandidate
from src.platform.linux_camera_compatibility import (
    LinuxCameraCompatibilityMixin,
)
from src.platform.live_fixed_full_hd_camera_service import (
    LiveFixedFullHdCameraService,
)


class FakeCapture:
    def __init__(self):
        self.definicoes = []

    def set(self, propriedade, valor):
        self.definicoes.append((propriedade, valor))
        return True


class LinuxCameraCompatibilityTests(unittest.TestCase):
    def test_servico_final_usa_fallback_linux(self):
        self.assertTrue(
            issubclass(
                LiveFixedFullHdCameraService,
                LinuxCameraCompatibilityMixin,
            )
        )

    def test_full_hd_tem_prioridade_mas_resolucoes_antigas_existem(self):
        service = object.__new__(LiveFixedFullHdCameraService)
        service._indice_camera_solicitado = 0
        service._indice_camera_ativo = None

        with patch(
            "src.platform.linux_camera_compatibility.sys.platform",
            "linux",
        ), patch(
            "src.platform.linux_camera_compatibility."
            "descobrir_dispositivos_video",
            return_value=(("/dev/video0", 0),),
        ), patch(
            "src.platform.linux_camera_compatibility."
            "opencv_tem_gstreamer",
            return_value=True,
        ):
            candidatos = service._candidatos_linux()

        self.assertTrue(candidatos)
        resolucoes = [
            (item.largura, item.altura)
            for item in candidatos
        ]
        self.assertEqual((1920, 1080), resolucoes[0])
        self.assertIn((1280, 720), resolucoes)
        self.assertIn((640, 480), resolucoes)
        self.assertIn((640, 360), resolucoes)
        self.assertEqual("auto", candidatos[-1].tipo)

        ultima_1080 = max(
            indice
            for indice, resolucao in enumerate(resolucoes)
            if resolucao == (1920, 1080)
        )
        primeira_1280 = min(
            indice
            for indice, resolucao in enumerate(resolucoes)
            if resolucao == (1280, 720)
        )
        self.assertLess(ultima_1080, primeira_1280)

    def test_v4l2_fallback_configura_resolucao_do_candidato(self):
        service = object.__new__(LiveFixedFullHdCameraService)
        capture = FakeCapture()
        candidato = LinuxCameraBackendCandidate(
            key="v4l2:0:MJPG:640x480",
            nome="V4L2 MJPG 640x480",
            tipo="v4l2",
            origem=0,
            backend=cv2.CAP_V4L2,
            dispositivo="/dev/video0",
            formato="MJPG",
            largura=640,
            altura=480,
            indice=0,
        )

        with patch(
            "src.platform.linux_camera_compatibility.sys.platform",
            "linux",
        ):
            service._configurar_capture_direto(capture, candidato)

        definicoes = dict(capture.definicoes)
        self.assertEqual(640, definicoes[cv2.CAP_PROP_FRAME_WIDTH])
        self.assertEqual(480, definicoes[cv2.CAP_PROP_FRAME_HEIGHT])
        self.assertEqual(20, definicoes[cv2.CAP_PROP_FPS])

    def test_backend_automatico_nao_forca_resolucao(self):
        service = object.__new__(LiveFixedFullHdCameraService)
        capture = FakeCapture()
        candidato = LinuxCameraBackendCandidate(
            key="auto:0",
            nome="Backend automático",
            tipo="auto",
            origem=0,
            backend=cv2.CAP_ANY,
            dispositivo="/dev/video0",
            formato="AUTO",
            largura=0,
            altura=0,
            indice=0,
        )

        with patch(
            "src.platform.linux_camera_compatibility.sys.platform",
            "linux",
        ):
            service._configurar_capture_direto(capture, candidato)

        propriedades = {
            propriedade
            for propriedade, _valor in capture.definicoes
        }
        self.assertNotIn(cv2.CAP_PROP_FRAME_WIDTH, propriedades)
        self.assertNotIn(cv2.CAP_PROP_FRAME_HEIGHT, propriedades)
        self.assertNotIn(cv2.CAP_PROP_FPS, propriedades)
        self.assertNotIn(cv2.CAP_PROP_FOURCC, propriedades)

    def test_frame_640x480_e_publicado_sem_reconexao(self):
        with patch(
            "src.platform.fixed_full_hd_camera_service.sys.platform",
            "linux",
        ), patch(
            "src.platform.linux_camera_compatibility.sys.platform",
            "linux",
        ):
            service = LiveFixedFullHdCameraService(indice_camera=0)
            service._linux_compat_expected_resolution = (640, 480)
            service._backend_name = "V4L2 MJPG 640x480"
            service._backend_ativo_tipo = "v4l2"
            frame = np.zeros((480, 640, 3), dtype=np.uint8)

            service._publicar_frame_otimizado(frame, estavel=False)
            snapshot = service.obter_snapshot()

        self.assertEqual((640, 480), snapshot.resolucao)
        self.assertEqual(0, service._resolution_mismatch_count)
        self.assertEqual(service.ESTADO_CONECTADA, snapshot.estado)

    def test_indice_estrito_mantem_fallback_na_camera_escolhida(self):
        classe = criar_classe_camera_indice_estrito(
            LiveFixedFullHdCameraService
        )
        service = object.__new__(classe)
        service._indice_camera_solicitado = 1
        service._indice_camera_ativo = None

        with patch(
            "src.platform.linux_camera_compatibility.sys.platform",
            "linux",
        ), patch(
            "src.platform.linux_camera_compatibility."
            "descobrir_dispositivos_video",
            return_value=(
                ("/dev/video0", 0),
                ("/dev/video1", 1),
            ),
        ), patch(
            "src.platform.linux_camera_compatibility."
            "opencv_tem_gstreamer",
            return_value=False,
        ):
            candidatos = service._candidatos_linux()

        self.assertTrue(candidatos)
        self.assertTrue(
            all(item.indice == 1 for item in candidatos)
        )
        self.assertTrue(
            any(
                (item.largura, item.altura) == (640, 480)
                for item in candidatos
            )
        )


if __name__ == "__main__":
    unittest.main()
