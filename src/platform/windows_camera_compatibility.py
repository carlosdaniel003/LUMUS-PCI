from __future__ import annotations

import sys

from src.platform.raspberry_pi3_settings import CAMERA_FPS, CAMERA_HEIGHT, CAMERA_WIDTH


class WindowsCameraCompatibilityMixin:
    """Prioriza o perfil solicitado no Windows e usa AUTO apenas como fallback."""

    WINDOWS_RESOLUTION_PROBE_FRAMES = 12

    def __init__(self, *args, **kwargs) -> None:
        self._windows_exigir_resolucao_solicitada = False
        self._windows_fallback_automatico_ativo = False
        self._windows_ultima_resolucao_probe: tuple[int, int] | None = None
        super().__init__(*args, **kwargs)

    @staticmethod
    def _windows_native_settings(configuracoes_camera: dict | None) -> dict:
        configuracoes = dict(configuracoes_camera or {})
        modo = str(configuracoes.get("resolution_mode", "auto")).lower()

        if modo == "auto":
            configuracoes.update(
                {
                    "resolution_mode": "auto",
                    "width": int(configuracoes.get("width", CAMERA_WIDTH)),
                    "height": int(configuracoes.get("height", CAMERA_HEIGHT)),
                    "fps_mode": "auto",
                    "fps": 0,
                    "format": "AUTO",
                }
            )
            return configuracoes

        configuracoes["width"] = int(configuracoes.get("width", CAMERA_WIDTH))
        configuracoes["height"] = int(configuracoes.get("height", CAMERA_HEIGHT))
        configuracoes.setdefault("fps_mode", "manual")
        configuracoes.setdefault("fps", CAMERA_FPS)
        configuracoes.setdefault("format", "MJPG")
        return configuracoes

    def _capture_entrega_frame_inicial(self, capture) -> bool:
        if (
            not sys.platform.startswith("win")
            or not self._windows_exigir_resolucao_solicitada
        ):
            return super()._capture_entrega_frame_inicial(capture)

        esperado = (int(self.largura), int(self.altura))
        self._windows_ultima_resolucao_probe = None

        for _ in range(max(1, int(self.WINDOWS_RESOLUTION_PROBE_FRAMES))):
            try:
                sucesso, frame = capture.read()
            except Exception:
                sucesso, frame = False, None

            frame = self._normalizar_frame(frame) if sucesso else None
            if not self._frame_basico_valido(frame):
                continue

            altura_real, largura_real = frame.shape[:2]
            atual = (int(largura_real), int(altura_real))
            self._windows_ultima_resolucao_probe = atual
            if atual == esperado:
                return True

        return False

    def _abrir_camera(self) -> bool:
        if not sys.platform.startswith("win") or self.perfil_automatico:
            self._windows_exigir_resolucao_solicitada = False
            self._windows_fallback_automatico_ativo = False
            return super()._abrir_camera()

        perfil = {
            "perfil_automatico": bool(self.perfil_automatico),
            "fps": int(self.fps),
            "formato_camera": str(self.formato_camera),
            "resolucao_solicitada": self._resolucao_solicitada,
            "fps_solicitado": self._fps_solicitado,
            "formato_solicitado": self._formato_solicitado,
        }

        self._windows_exigir_resolucao_solicitada = True
        self._windows_fallback_automatico_ativo = False
        if super()._abrir_camera():
            self._windows_exigir_resolucao_solicitada = False
            return True

        # Com resolução mestre de projeto não existe fallback para outro modo.
        # Se 640x480 foi salvo com as ROIs, somente 640x480 é aceito.
        resolucao_travada = getattr(
            self,
            "_resolucao_mestra_travada",
            None,
        )
        if resolucao_travada is not None:
            self._windows_exigir_resolucao_solicitada = False
            self._windows_fallback_automatico_ativo = False
            try:
                self._definir_estado(
                    self.ESTADO_DESCONECTADA,
                    (
                        "A câmera não confirmou a resolução mestre "
                        f"{resolucao_travada[0]}x{resolucao_travada[1]}. "
                        "Aguardando reconexão no mesmo modo."
                    ),
                )
            except Exception:
                pass
            return False

        self._windows_exigir_resolucao_solicitada = False
        self.perfil_automatico = True
        self.fps = 0
        self.formato_camera = "AUTO"

        try:
            abriu = super()._abrir_camera()
        finally:
            self.perfil_automatico = perfil["perfil_automatico"]
            self.fps = perfil["fps"]
            self.formato_camera = perfil["formato_camera"]
            self._resolucao_solicitada = perfil["resolucao_solicitada"]
            self._fps_solicitado = perfil["fps_solicitado"]
            self._formato_solicitado = perfil["formato_solicitado"]

        self._windows_fallback_automatico_ativo = bool(abriu)
        if abriu:
            try:
                self._definir_estado(
                    self.ESTADO_ESTABILIZANDO,
                    (
                        "A resolução solicitada não foi confirmada pelos "
                        "backends do Windows. Usando negociação automática "
                        "compatível com a câmera."
                    ),
                )
            except Exception:
                pass
        return bool(abriu)

    def obter_diagnostico_fluxo(self) -> dict:
        diagnostico = super().obter_diagnostico_fluxo()
        diagnostico.update(
            {
                "windows_resolucao_solicitada_prioritaria": bool(
                    sys.platform.startswith("win")
                    and not self.perfil_automatico
                ),
                "windows_fallback_automatico": bool(
                    self._windows_fallback_automatico_ativo
                ),
                "windows_ultima_resolucao_probe": (
                    self._windows_ultima_resolucao_probe
                ),
            }
        )
        return diagnostico
