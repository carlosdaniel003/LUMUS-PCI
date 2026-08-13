from __future__ import annotations

from datetime import datetime
from pathlib import Path
import threading

import cv2

from config import CAPTURES_DIR
from src.infra.camera_service import CameraService
from src.ui.main_window_parts.image.rotacao_visual_principal import (
    rotacionar_imagem_visual,
)


SCREENSHOT_DIR = CAPTURES_DIR / "screenshots"


def criar_caminho_screenshot_camera(
    agora: datetime | None = None,
    pasta: Path | None = None,
) -> Path:
    instante = agora or datetime.now()
    destino = pasta or SCREENSHOT_DIR
    nome = instante.strftime("odin_screenshot_%Y-%m-%d_%H-%M-%S_%f.png")
    return Path(destino) / nome


def preparar_frame_screenshot_camera(frame, rotacao_visual: int = 0):
    if frame is None:
        return None
    copia = frame.copy()
    rotacionado = rotacionar_imagem_visual(copia, rotacao_visual)
    return None if rotacionado is None else rotacionado.copy()


def salvar_frame_screenshot_camera(frame, caminho: Path) -> bool:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(caminho), frame))


class CameraScreenshotMixin:
    """Captura o último frame ao vivo sem pausar ou reiniciar a câmera."""

    def criar_callbacks(self) -> dict:
        callbacks = dict(super().criar_callbacks())
        callbacks["capturar_screenshot_camera"] = self.capturar_screenshot_camera
        return callbacks

    def capturar_screenshot_camera(self) -> Path | None:
        if not bool(getattr(self, "camera_ativa", False)):
            self.view.atualizar_status(
                "Screenshot indisponível. Ative a Tela ao vivo primeiro."
            )
            return None

        camera_service = getattr(self, "camera_service", None)
        estado = getattr(self, "camera_estado_anterior", None)
        estado_conectada = getattr(
            camera_service,
            "ESTADO_CONECTADA",
            CameraService.ESTADO_CONECTADA,
        )
        if (
            camera_service is None
            or bool(getattr(self, "camera_desconectada", False))
            or estado != estado_conectada
        ):
            self.view.atualizar_status(
                "Screenshot indisponível. Aguarde a câmera ficar conectada e estável."
            )
            return None

        frame = getattr(self, "camera_frame_atual", None)
        if frame is None:
            self.view.atualizar_status(
                "Screenshot indisponível. Aguarde o primeiro frame da câmera."
            )
            return None

        rotacao = int(
            getattr(getattr(self, "view", None), "rotacao_visual_principal", 0)
            or 0
        )
        frame_screenshot = preparar_frame_screenshot_camera(frame, rotacao)
        if frame_screenshot is None:
            self.view.atualizar_status(
                "Não foi possível preparar o frame para o screenshot."
            )
            return None

        caminho = criar_caminho_screenshot_camera()
        self.view.atualizar_status("Salvando screenshot da câmera...")

        def salvar_em_background() -> None:
            try:
                sucesso = salvar_frame_screenshot_camera(frame_screenshot, caminho)
            except Exception:
                sucesso = False

            def finalizar() -> None:
                if sucesso:
                    self.view.atualizar_status(
                        f"Screenshot salvo corretamente: {caminho}"
                    )
                else:
                    self.view.atualizar_status(
                        "Falha ao salvar o screenshot da câmera."
                    )

            try:
                self.root.after(0, finalizar)
            except Exception:
                finalizar()

        threading.Thread(
            target=salvar_em_background,
            name="odin-camera-screenshot",
            daemon=True,
        ).start()
        return caminho
