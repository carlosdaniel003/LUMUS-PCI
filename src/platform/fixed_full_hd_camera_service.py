from __future__ import annotations

import sys

from src.platform.linux_camera_backend import (
    LinuxCameraBackendCandidate,
    construir_candidatos_linux,
    descobrir_dispositivos_video,
    opencv_tem_gstreamer,
)
from src.platform.raspberry_pi3_settings import (
    CAMERA_FPS,
    CAMERA_HEIGHT,
    CAMERA_SCAN_MAX_INDEX,
    CAMERA_WIDTH,
)
from src.platform.threaded_camera_service import (
    ThreadedRaspberryPi3CameraService,
)


class FixedFullHdCameraService(ThreadedRaspberryPi3CameraService):
    """Captura fixa em 1920x1080 a 20 FPS, sem fallback de resolução."""

    RESOLUTION_MISMATCH_BEFORE_SWITCH = 3
    RESOLUTION_PROBE_FRAMES = 4

    def __init__(
        self,
        indice_camera: int,
        largura: int = CAMERA_WIDTH,
        altura: int = CAMERA_HEIGHT,
        fps: int = CAMERA_FPS,
        **kwargs,
    ) -> None:
        configuracoes = self._fixed_settings(
            kwargs.pop("configuracoes_camera", None)
        )
        self._resolution_mismatch_count = 0
        super().__init__(
            indice_camera=indice_camera,
            largura=CAMERA_WIDTH,
            altura=CAMERA_HEIGHT,
            fps=CAMERA_FPS,
            configuracoes_camera=configuracoes,
            **kwargs,
        )

    @staticmethod
    def _fixed_settings(configuracoes_camera: dict | None) -> dict:
        configuracoes = dict(configuracoes_camera or {})
        configuracoes.update(
            {
                "resolution_mode": "full_hd",
                "width": CAMERA_WIDTH,
                "height": CAMERA_HEIGHT,
                "fps_mode": "manual",
                "fps": CAMERA_FPS,
                "format": "MJPG",
            }
        )
        return configuracoes

    @staticmethod
    def _is_fixed_candidate(
        candidato: LinuxCameraBackendCandidate,
    ) -> bool:
        return (
            int(candidato.largura) == CAMERA_WIDTH
            and int(candidato.altura) == CAMERA_HEIGHT
        )

    def atualizar_configuracoes_camera(
        self,
        configuracoes_camera: dict | None,
    ) -> None:
        self.largura = CAMERA_WIDTH
        self.altura = CAMERA_HEIGHT
        self.fps = CAMERA_FPS
        super().atualizar_configuracoes_camera(
            self._fixed_settings(configuracoes_camera)
        )

    def _candidatos_linux(
        self,
    ) -> tuple[LinuxCameraBackendCandidate, ...]:
        dispositivos = descobrir_dispositivos_video(
            indice_solicitado=self._indice_camera_solicitado,
            indice_ativo=self._indice_camera_ativo,
            indice_maximo=CAMERA_SCAN_MAX_INDEX,
        )
        candidatos = construir_candidatos_linux(
            dispositivos=dispositivos,
            largura=CAMERA_WIDTH,
            altura=CAMERA_HEIGHT,
            fps=CAMERA_FPS,
            gstreamer_disponivel=opencv_tem_gstreamer(),
            resolucoes_preferidas=((CAMERA_WIDTH, CAMERA_HEIGHT),),
        )
        return tuple(
            candidato
            for candidato in candidatos
            if self._is_fixed_candidate(candidato)
        )

    def _abrir_candidato_linux(
        self,
        candidato: LinuxCameraBackendCandidate,
    ):
        if not self._is_fixed_candidate(candidato):
            return None

        capture = super()._abrir_candidato_linux(candidato)
        if capture is None:
            return None

        frames_na_resolucao = 0
        for _ in range(self.RESOLUTION_PROBE_FRAMES):
            try:
                sucesso, frame = capture.read()
            except Exception:
                sucesso, frame = False, None
            frame = self._normalizar_frame(frame) if sucesso else None
            if not self._frame_basico_valido(frame):
                continue
            altura_real, largura_real = frame.shape[:2]
            if (
                int(largura_real) == CAMERA_WIDTH
                and int(altura_real) == CAMERA_HEIGHT
            ):
                frames_na_resolucao += 1

        if frames_na_resolucao > 0:
            return capture

        try:
            capture.release()
        except Exception:
            pass
        return None

    def _reiniciar_estado_fluxo(self) -> None:
        super()._reiniciar_estado_fluxo()
        self._resolution_mismatch_count = 0

    def _publicar_frame_otimizado(self, frame, estavel: bool) -> None:
        altura_real, largura_real = frame.shape[:2]
        if (
            int(largura_real) != CAMERA_WIDTH
            or int(altura_real) != CAMERA_HEIGHT
        ):
            self._resolution_mismatch_count += 1
            self._ultimo_motivo_descarte = (
                "A câmera entregou "
                f"{largura_real}x{altura_real}; esperado "
                f"{CAMERA_WIDTH}x{CAMERA_HEIGHT}."
            )
            if (
                self._resolution_mismatch_count
                >= self.RESOLUTION_MISMATCH_BEFORE_SWITCH
            ):
                self._resolution_mismatch_count = 0
                if sys.platform.startswith("linux"):
                    self._trocar_backend_linux(
                        "A pipeline alterou a resolução fixa."
                    )
                else:
                    self._agendar_reconexao(
                        "A câmera não manteve 1920x1080."
                    )
                    self._reiniciar_estado_fluxo()
            return

        self._resolution_mismatch_count = 0
        super()._publicar_frame_otimizado(frame, estavel=estavel)

    def obter_diagnostico_fluxo(self) -> dict:
        diagnostico = super().obter_diagnostico_fluxo()
        diagnostico.update(
            {
                "perfil_camera_fixo": True,
                "resolucao_fixa": (CAMERA_WIDTH, CAMERA_HEIGHT),
                "fps_fixo": CAMERA_FPS,
                "divergencias_resolucao": int(
                    self._resolution_mismatch_count
                ),
            }
        )
        return diagnostico
