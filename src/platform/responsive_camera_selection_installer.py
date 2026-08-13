from __future__ import annotations

import threading

from src.platform.camera_selection import CameraSelectionMixin
from src.platform.responsive_camera_selection import ResponsiveCameraSelectionMixin


_PATCH_INSTALADO = False


def instalar_seletor_camera_responsivo() -> None:
    """Aplica a UI responsiva sem alterar a ordem de mixins do perfil final."""
    global _PATCH_INSTALADO
    if _PATCH_INSTALADO:
        return

    init_original = CameraSelectionMixin.__init__

    def init_responsivo(self, *args, **kwargs):
        init_original(self, *args, **kwargs)
        self._selector_worker_thread = None
        self._selector_stop_event = None
        self._selector_released_event = None
        self._selector_event_queue = None
        self._selector_latest_previews = {}
        self._selector_previews_lock = threading.RLock()
        self._selector_loading_after_id = None
        self._selector_loading_frame = None
        self._selector_loading_label = None
        self._selector_status_label = None
        self._selector_frame_previews = None

    CameraSelectionMixin.__init__ = init_responsivo

    for nome in (
        "abrir_seletor_camera",
        "_animar_loading_camera",
        "_remover_loading_camera",
        "_processar_eventos_camera",
        "_status_camera",
        "_mostrar_sem_camera",
        "_criar_card_camera_responsivo",
        "_desenhar_preview_codificado",
        "_atualizar_previews_seletor_camera",
        "_confirmar_camera_selecionada",
        "_fechar_seletor_camera",
    ):
        setattr(
            CameraSelectionMixin,
            nome,
            getattr(ResponsiveCameraSelectionMixin, nome),
        )

    CameraSelectionMixin._odin_responsive_selector_installed = True
    _PATCH_INSTALADO = True
