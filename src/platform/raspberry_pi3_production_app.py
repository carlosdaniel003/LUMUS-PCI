from __future__ import annotations

import tkinter as tk

import src.platform.raspberry_pi3_profile as raspberry_pi3_profile
from src.platform.automatic_led_detection import (
    AutomaticLedDetectionMixin,
)
from src.platform.camera_advanced_config import (
    instalar_normalizacao_config_repository,
)
from src.platform.camera_stability_runtime import (
    RaspberryCameraStabilityMixin,
)
from src.platform.display_awake_runtime import (
    LinuxDisplayAwakeMixin,
)
from src.platform.display_theme import (
    DISPLAY_INK,
    DISPLAY_YELLOW,
    DISPLAY_YELLOW_DARK,
    DisplayThemeMixin,
)
from src.platform.fixed_full_hd_camera_service import (
    FixedFullHdCameraService,
)
from src.platform.fixed_mask_geometry_guard import (
    FixedMaskGeometryGuardMixin,
    instalar_repositorio_mascaras_absolutas,
)
from src.platform.fullscreen_led_selection import (
    FullscreenLedSelectionMixin,
)
from src.platform.gpio_raspberry_app import (
    GPIOEnabledRaspberryPi3ODINApp,
)
from src.platform.led_mask_resolution_sync import (
    ResolutionSynchronizedLedMasksMixin,
)
from src.platform.led_project_preview import (
    LedProjectPreviewMixin,
)
from src.platform.led_project_preview_store import (
    instalar_preview_projeto_led_store,
)
from src.platform.led_project_repository import (
    instalar_repositorio_projetos_led,
)
from src.platform.native_resolution_config import (
    NativeResolutionConfigMixin,
)
from src.platform.raspberry_enter_trigger import (
    RaspberryEnterTriggerMixin,
)
from src.platform.raspberry_pi3_settings import (
    OPERATION_PREVIEW_HEIGHT,
    OPERATION_PREVIEW_WIDTH,
)
from src.platform.raspberry_runtime_fixes import (
    RaspberryRuntimeFixesMixin,
)
from src.platform.reference_capture import (
    ReferenceCaptureMixin,
)
from src.platform.reference_project_sets import (
    ProjectReferenceSetsMixin,
)
from src.platform.segment_display_operation_window import (
    SegmentDisplayOperationWindow,
)
from src.platform.segment_display_roi_editor import (
    SegmentDisplayRoiEditorMixin,
)
from src.platform.segment_display_runtime import (
    SegmentDisplayRuntimeMixin,
)
from src.platform.segment_project_geometry_persistence import (
    SegmentProjectGeometryPersistenceMixin,
    instalar_preservacao_segmentos_resolution_sync,
)


class RaspberryPi3ProductionApp(
    LinuxDisplayAwakeMixin,
    DisplayThemeMixin,
    LedProjectPreviewMixin,
    ProjectReferenceSetsMixin,
    ReferenceCaptureMixin,
    FullscreenLedSelectionMixin,
    FixedMaskGeometryGuardMixin,
    SegmentProjectGeometryPersistenceMixin,
    SegmentDisplayRuntimeMixin,
    SegmentDisplayRoiEditorMixin,
    ResolutionSynchronizedLedMasksMixin,
    NativeResolutionConfigMixin,
    RaspberryCameraStabilityMixin,
    RaspberryRuntimeFixesMixin,
    RaspberryEnterTriggerMixin,
    AutomaticLedDetectionMixin,
    GPIOEnabledRaspberryPi3ODINApp,
):
    """Perfil final do display com ROI circular e segmento chanfrado."""

    def __init__(self, root: tk.Tk) -> None:
        raspberry_pi3_profile.RaspberryPi3CameraService = FixedFullHdCameraService
        instalar_normalizacao_config_repository()
        instalar_repositorio_projetos_led()
        instalar_preview_projeto_led_store()
        instalar_repositorio_mascaras_absolutas()
        instalar_preservacao_segmentos_resolution_sync()
        super().__init__(root)

    def _tem_referencia_pouca_luz_ativa(self) -> bool:
        grupos = getattr(self, "_referencias_ativas_por_tipo", None)
        if isinstance(grupos, dict):
            return bool(grupos.get("pouca_luz"))
        return getattr(self, "features_referencia_pouca_luz", None) is not None

    def preparar_tela_operacao(self) -> None:
        resultado = super().preparar_tela_operacao()
        self.operacao_engine.definir_diagnostico_pouca_luz_habilitado(
            self._tem_referencia_pouca_luz_ativa()
        )
        return resultado

    def _instalar_tela_operacao(self) -> None:
        self.operacao_window = SegmentDisplayOperationWindow(
            root=self.root,
            on_trigger=self.disparar_inspecao_operacao,
            on_close=self.fechar_tela_operacao,
            preview_width=OPERATION_PREVIEW_WIDTH,
            preview_height=OPERATION_PREVIEW_HEIGHT,
        )

        self.root.bind(
            "<F2>",
            lambda _event: self.abrir_tela_operacao(),
            add="+",
        )

        parent = getattr(self.view, "frame_topo_direita", self.root)
        self.botao_operacao = tk.Button(
            parent,
            text="PRODUÇÃO  F2",
            command=self.abrir_tela_operacao,
            font=("DejaVu Sans", 10, "bold"),
            bg=DISPLAY_YELLOW,
            fg=DISPLAY_INK,
            activebackground=DISPLAY_YELLOW_DARK,
            activeforeground=DISPLAY_INK,
            relief="flat",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
        )

        if parent is self.root:
            self.botao_operacao.place(
                relx=1.0,
                x=-18,
                y=16,
                anchor="ne",
            )
            self.botao_operacao.lift()
        else:
            self.botao_operacao.pack(
                side=tk.RIGHT,
                padx=(0, 8),
                pady=18,
            )
