from __future__ import annotations

import sys

import cv2

from src.platform.linux_camera_backend import (
    LinuxCameraBackendCandidate,
    construir_candidatos_linux,
    descobrir_dispositivos_video,
    opencv_tem_gstreamer,
)
from src.platform.raspberry_pi3_settings import (
    CAMERA_RESOLUTION_FALLBACKS,
    CAMERA_SCAN_MAX_INDEX,
)
from src.platform.threaded_camera_service import (
    ThreadedRaspberryPi3CameraService,
)


class NativeResolutionThreadedCameraService(
    ThreadedRaspberryPi3CameraService
):
    """Captura nativa UHD com fallback de resolução sem perder fluidez."""

    def __init__(self, *args, **kwargs) -> None:
        self._candidato_aberto: LinuxCameraBackendCandidate | None = None
        super().__init__(*args, **kwargs)

    def _candidatos_linux(
        self,
    ) -> tuple[LinuxCameraBackendCandidate, ...]:
        dispositivos = descobrir_dispositivos_video(
            indice_solicitado=self._indice_camera_solicitado,
            indice_ativo=self._indice_camera_ativo,
            indice_maximo=CAMERA_SCAN_MAX_INDEX,
        )
        return construir_candidatos_linux(
            dispositivos=dispositivos,
            largura=self.largura,
            altura=self.altura,
            fps=max(1, int(self.fps or 30)),
            gstreamer_disponivel=opencv_tem_gstreamer(),
            resolucoes_preferidas=CAMERA_RESOLUTION_FALLBACKS,
        )

    def _configurar_capture_direto(
        self,
        capture,
        candidato: LinuxCameraBackendCandidate,
    ) -> None:
        # O backend automático deve negociar livremente com o driver.
        if candidato.tipo == "auto":
            return

        if candidato.formato in ("MJPG", "YUY2"):
            fourcc = (
                "MJPG"
                if candidato.formato == "MJPG"
                else "YUYV"
            )
            try:
                capture.set(
                    cv2.CAP_PROP_FOURCC,
                    cv2.VideoWriter_fourcc(*fourcc),
                )
            except Exception:
                pass

        largura = max(1, int(candidato.largura or self.largura))
        altura = max(1, int(candidato.altura or self.altura))
        fps = max(1, int(self.fps or 30))

        for propriedade, valor in (
            (cv2.CAP_PROP_FRAME_WIDTH, largura),
            (cv2.CAP_PROP_FRAME_HEIGHT, altura),
            (cv2.CAP_PROP_FPS, fps),
        ):
            try:
                capture.set(propriedade, valor)
            except Exception:
                pass

        try:
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        except Exception:
            pass

    def _abrir_candidato_linux(
        self,
        candidato: LinuxCameraBackendCandidate,
    ):
        capture = super()._abrir_candidato_linux(candidato)
        if capture is not None:
            self._candidato_aberto = candidato
        return capture

    def _abrir_camera(self) -> bool:
        self._candidato_aberto = None
        abriu = super()._abrir_camera()
        if not abriu or not sys.platform.startswith("linux"):
            return abriu

        candidato = self._candidato_aberto
        if candidato is None:
            return abriu

        if candidato.largura > 0 and candidato.altura > 0:
            self._resolucao_solicitada = (
                int(candidato.largura),
                int(candidato.altura),
            )
        else:
            self._resolucao_solicitada = None

        self._fps_solicitado = max(1, int(self.fps or 30))
        self._formato_solicitado = candidato.formato
        return abriu
