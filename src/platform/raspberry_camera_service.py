from __future__ import annotations

import math

import cv2

from src.infra.camera_service import CameraService
from src.platform.camera_advanced_config import (
    normalizar_controles_avancados,
)


class RaspberryPi3CameraService(CameraService):
    """CameraService para webcam USB usando V4L2 no Raspberry Pi OS."""

    CONTROLES_AVANCADOS = (
        "auto_exposure",
        "exposure",
        "gain",
        "autofocus",
        "focus",
        "auto_white_balance",
        "white_balance",
        "brightness",
        "gamma",
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        for nome in self.CONTROLES_AVANCADOS:
            self._status_controles_camera.setdefault(
                nome,
                {
                    "status": "aguardando_camera",
                    "valor_solicitado": None,
                    "valor_lido": None,
                },
            )

    @classmethod
    def _normalizar_configuracoes_camera(
        cls,
        configuracoes_camera: dict | None,
    ) -> dict:
        resultado = CameraService._normalizar_configuracoes_camera(
            configuracoes_camera
        )
        return normalizar_controles_avancados(
            resultado,
            configuracoes_camera,
        )

    def iniciar(self) -> None:
        if self._ativo:
            return

        self._ativo = True
        self._falhas_consecutivas = 0
        self._proxima_reconexao_em = 0.0
        self._definir_estado(
            self.ESTADO_CONECTANDO,
            f"Conectando câmera {self.indice_camera} via V4L2...",
        )
        self._abrir_camera()

    def atualizar_configuracoes_camera(
        self,
        configuracoes_camera: dict | None,
    ) -> None:
        super().atualizar_configuracoes_camera(
            configuracoes_camera
        )

        # Aplicação pontual após Salvar. Não adiciona processamento ao loop
        # normal de captura nem ao caminho crítico da inspeção.
        if self._capture is not None:
            self._aplicar_configuracoes_hardware()

    def _abrir_camera(self) -> bool:
        self._liberar_camera()
        self._definir_estado(
            self.ESTADO_ESTABILIZANDO,
            f"Abrindo câmera {self.indice_camera} via V4L2...",
        )

        capture = None
        backend_name = "V4L2"

        for backend, candidate_name in (
            (cv2.CAP_V4L2, "V4L2"),
            (cv2.CAP_ANY, "automático Linux"),
        ):
            try:
                candidate = cv2.VideoCapture(
                    self.indice_camera,
                    backend,
                )
            except Exception:
                candidate = None

            if candidate is not None and candidate.isOpened():
                capture = candidate
                backend_name = candidate_name
                break

            if candidate is not None:
                try:
                    candidate.release()
                except Exception:
                    pass

        if capture is None:
            self._capture = None
            self._agendar_reconexao(
                f"Câmera {self.indice_camera} não abriu via V4L2."
            )
            return False

        self._capture = capture
        self._backend_name = backend_name
        self._aplicar_perfil_capture(capture)

        try:
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        self._controles_pendentes = True
        self._falhas_consecutivas = 0
        self._definir_estado(
            self.ESTADO_ESTABILIZANDO,
            (
                f"Câmera {self.indice_camera} aberta via "
                f"{backend_name}. Aguardando primeiro frame..."
            ),
        )
        return True

    def _aplicar_controle_automatico(
        self,
        capture,
        nome: str,
        propriedade: int | None,
        valor: float,
    ) -> None:
        if propriedade is None:
            self._registrar_status_controle(
                nome,
                "nao_suportado",
                valor_solicitado=valor,
            )
            return

        try:
            aplicado = bool(capture.set(propriedade, float(valor)))
        except Exception:
            aplicado = False

        valor_lido = None
        if aplicado:
            try:
                leitura = float(capture.get(propriedade))
                if math.isfinite(leitura):
                    valor_lido = leitura
            except Exception:
                pass

        self._registrar_status_controle(
            nome,
            "aplicado" if aplicado else "nao_suportado",
            valor_solicitado=float(valor),
            valor_lido=valor_lido,
        )

    def _valor_auto_exposure(self, automatico: bool) -> float:
        backend = str(
            getattr(self, "_backend_name", "V4L2")
        ).lower()

        if "v4l2" in backend or "linux" in backend:
            return 3.0 if automatico else 1.0

        return 0.75 if automatico else 0.25

    def _aplicar_configuracoes_hardware(self) -> None:
        capture = self._capture
        estava_pendente = self._controles_pendentes

        if capture is None or not estava_pendente:
            return

        # Mantém pan, tilt, contraste, nitidez e saturação exatamente no fluxo
        # existente antes de aplicar os controles adicionais.
        super()._aplicar_configuracoes_hardware()

        configuracoes = self.obter_configuracoes_camera()

        exposicao_automatica = bool(
            configuracoes.get("exposure_auto", True)
        )
        self._aplicar_controle_automatico(
            capture,
            "auto_exposure",
            getattr(cv2, "CAP_PROP_AUTO_EXPOSURE", None),
            self._valor_auto_exposure(exposicao_automatica),
        )

        if exposicao_automatica:
            self._registrar_status_controle(
                "exposure",
                "automatico",
                valor_solicitado=configuracoes.get("exposure"),
            )
        else:
            self._aplicar_controle_hardware(
                capture,
                "exposure",
                getattr(cv2, "CAP_PROP_EXPOSURE", None),
                bool(configuracoes.get("exposure_enabled", False)),
                float(configuracoes.get("exposure", 100.0)),
            )

        self._aplicar_controle_hardware(
            capture,
            "gain",
            getattr(cv2, "CAP_PROP_GAIN", None),
            bool(configuracoes.get("gain_enabled", False)),
            float(configuracoes.get("gain", 0.0)),
        )

        foco_automatico = bool(
            configuracoes.get("focus_auto", True)
        )
        self._aplicar_controle_automatico(
            capture,
            "autofocus",
            getattr(cv2, "CAP_PROP_AUTOFOCUS", None),
            1.0 if foco_automatico else 0.0,
        )

        if foco_automatico:
            self._registrar_status_controle(
                "focus",
                "automatico",
                valor_solicitado=configuracoes.get("focus"),
            )
        else:
            self._aplicar_controle_hardware(
                capture,
                "focus",
                getattr(cv2, "CAP_PROP_FOCUS", None),
                bool(configuracoes.get("focus_enabled", False)),
                float(configuracoes.get("focus", 0.0)),
            )

        balanço_automatico = bool(
            configuracoes.get("white_balance_auto", True)
        )
        self._aplicar_controle_automatico(
            capture,
            "auto_white_balance",
            getattr(cv2, "CAP_PROP_AUTO_WB", None),
            1.0 if balanço_automatico else 0.0,
        )

        if balanço_automatico:
            self._registrar_status_controle(
                "white_balance",
                "automatico",
                valor_solicitado=configuracoes.get("white_balance"),
            )
        else:
            self._aplicar_controle_hardware(
                capture,
                "white_balance",
                getattr(cv2, "CAP_PROP_WB_TEMPERATURE", None),
                bool(
                    configuracoes.get(
                        "white_balance_enabled",
                        False,
                    )
                ),
                float(configuracoes.get("white_balance", 4500.0)),
            )

        for nome, propriedade, padrao in (
            ("brightness", getattr(cv2, "CAP_PROP_BRIGHTNESS", None), 128.0),
            ("gamma", getattr(cv2, "CAP_PROP_GAMMA", None), 100.0),
        ):
            self._aplicar_controle_hardware(
                capture,
                nome,
                propriedade,
                bool(configuracoes.get(f"{nome}_enabled", False)),
                float(configuracoes.get(nome, padrao)),
            )

    def _publicar_frame(self, frame) -> None:
        frame_height, frame_width = frame.shape[:2]
        backend_name = getattr(self, "_backend_name", "V4L2")

        with self._lock:
            self._ultimo_frame = frame.copy()
            self._frame_id += 1
            self._resolucao = (frame_width, frame_height)
            self._estado = self.ESTADO_CONECTADA
            self._mensagem = (
                f"Câmera conectada via {backend_name}. "
                f"Resolução real: {frame_width}x{frame_height}."
            )
