import unittest
from unittest.mock import patch

import cv2

from src.platform.adaptive_camera_service import (
    BalancedAdaptiveCameraService,
)
from src.platform.camera_performance_profile import (
    CameraPerformanceResult,
)
from src.platform.linux_camera_backend import (
    LinuxCameraBackendCandidate,
)


def result(
    key: str,
    width: int,
    height: int,
    comfortable: bool,
    excellent: bool,
) -> CameraPerformanceResult:
    return CameraPerformanceResult(
        candidate_key=key,
        width=width,
        height=height,
        measured_fps=30.0 if excellent else 25.0,
        valid_ratio=1.0,
        corrupted_ratio=0.0,
        flicker_ratio=0.0,
        jitter_ratio=0.0,
        valid_frames=16,
        total_reads=16,
        comfortable=comfortable,
        excellent=excellent,
        score=120.0,
    )


def candidate(key: str, width: int, height: int):
    return LinuxCameraBackendCandidate(
        key=key,
        nome=key,
        tipo="gstreamer",
        origem="pipeline",
        backend=cv2.CAP_GSTREAMER,
        dispositivo="/dev/video0",
        formato="MJPG",
        largura=width,
        altura=height,
        indice=0,
    )


class AdaptiveCameraServiceTests(unittest.TestCase):
    def test_resolucao_superior_testa_alternativa_ate_excelente(self):
        service = object.__new__(BalancedAdaptiveCameraService)
        service.ESTADO_ESTABILIZANDO = "estabilizando"
        service._definir_estado = lambda *_args, **_kwargs: None
        resultados_simulados = iter(
            (
                result("qhd-lento", 2560, 1440, True, False),
                result("qhd-estavel", 2560, 1440, True, True),
            )
        )
        service._avaliar_candidato = lambda _item: next(
            resultados_simulados
        )
        resultados = []

        service._avaliar_grupo(
            [
                candidate("qhd-lento", 2560, 1440),
                candidate("qhd-estavel", 2560, 1440),
            ],
            limite=2,
            resultados=resultados,
        )

        self.assertEqual(2, len(resultados))
        self.assertTrue(resultados[-1].excellent)

    def test_duas_janelas_de_fps_baixo_trocam_o_perfil(self):
        service = object.__new__(BalancedAdaptiveCameraService)
        service._capture = object()
        service._runtime_opened_s = 0.0
        service._runtime_last_evaluation_s = 0.0
        service._runtime_low_fps_windows = 0
        service._runtime_downgrades = 0
        service._fps_real = 18.0
        service._backend_linux_cursor = 0
        service._candidatos_linux = lambda: (object(), object())
        trocas = []
        service._trocar_backend_linux = lambda motivo: trocas.append(motivo)

        with patch(
            "src.platform.adaptive_camera_service.sys.platform",
            "linux",
        ), patch(
            "src.platform.adaptive_camera_service.time.monotonic",
            side_effect=(10.0, 16.0),
        ):
            service._avaliar_desempenho_runtime()
            service._avaliar_desempenho_runtime()

        self.assertEqual(1, len(trocas))
        self.assertEqual(1, service._runtime_downgrades)
        self.assertIn("18.0 FPS", trocas[0])

    def test_fps_confortavel_zera_contador_de_alerta(self):
        service = object.__new__(BalancedAdaptiveCameraService)
        service._capture = object()
        service._runtime_opened_s = 0.0
        service._runtime_last_evaluation_s = 0.0
        service._runtime_low_fps_windows = 1
        service._runtime_downgrades = 0
        service._fps_real = 29.0
        service._backend_linux_cursor = 0

        with patch(
            "src.platform.adaptive_camera_service.sys.platform",
            "linux",
        ), patch(
            "src.platform.adaptive_camera_service.time.monotonic",
            return_value=10.0,
        ):
            service._avaliar_desempenho_runtime()

        self.assertEqual(0, service._runtime_low_fps_windows)
        self.assertEqual(0, service._runtime_downgrades)


if __name__ == "__main__":
    unittest.main()
