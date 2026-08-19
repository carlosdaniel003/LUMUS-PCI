from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from src.ui.operation_window_raspberry import RaspberryOperationWindow


class DisplayProductionF3Window(RaspberryOperationWindow):
    """Janela visual independente para o novo modo Produção Display (F3).

    Fase 3: câmera somente leitura + Projeto Display + máscaras + CHECKS.
    Ainda não existe análise automática, engine de CHECK ou resultado OK/NG.
    """

    def __init__(
        self,
        root,
        on_close: Callable[[], None],
        on_configure: Callable[[], None] | None = None,
        preview_width: int = 640,
        preview_height: int = 480,
    ) -> None:
        super().__init__(
            root=root,
            on_trigger=lambda: None,
            on_close=on_close,
            preview_width=preview_width,
            preview_height=preview_height,
        )

        self.on_configure = on_configure
        self.brand_label.configure(text="ODIN  |  PRODUÇÃO DISPLAY  F3")
        self.mode_label.configure(text="DISPLAY • PROJETO + MÁSCARAS + CHECKS")
        self.status_label.configure(text="AGUARDANDO CÂMERA")
        self.detail_label.configure(
            text=(
                "Fase 3 • configuração de CHECKS por máscara. "
                "Ainda sem análise automática."
            )
        )
        self.preview_title.configure(text="DISPLAY • CÂMERA AO VIVO")
        self.preview_legend.configure(
            text="FASE 3 • CONFIGURAÇÃO DE CHECKS • SEM ANÁLISE",
            fg=self.PREVIEW_MUTED,
        )
        self.footer_label.configure(text="F3 ou ESC: voltar ao ODIN")

        self.led_summary_label.grid_remove()
        self.metrics_frame.grid_remove()

        self.project_frame = tk.Frame(
            self.analysis_panel,
            bg="#0B1220",
            highlightbackground="#334155",
            highlightthickness=1,
        )
        self.project_frame.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=20,
            pady=(4, 18),
        )
        self.project_frame.grid_columnconfigure(0, weight=1)

        self.project_info_label = tk.Label(
            self.project_frame,
            text="PROJETO DISPLAY: NENHUM",
            font=("DejaVu Sans", 11, "bold"),
            bg="#0B1220",
            fg="#E2E8F0",
            anchor="w",
            justify="left",
        )
        self.project_info_label.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=12,
            pady=(10, 2),
        )

        self.project_detail_label = tk.Label(
            self.project_frame,
            text="Resolução mestre: --  •  Máscaras: 0  •  CHECKS: 0",
            font=("DejaVu Sans", 9),
            bg="#0B1220",
            fg="#94A3B8",
            anchor="w",
            justify="left",
        )
        self.project_detail_label.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=12,
            pady=(0, 10),
        )

        self.project_config_button = tk.Button(
            self.project_frame,
            text="CONFIGURAR PROJETO DISPLAY",
            command=self._open_project_config,
            font=("DejaVu Sans", 9, "bold"),
            bg="#0E7490",
            fg="#FFFFFF",
            activebackground="#0891B2",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
        )
        self.project_config_button.grid(
            row=0,
            column=1,
            rowspan=2,
            sticky="e",
            padx=12,
            pady=10,
        )

        self.container.bind("<Return>", self._ignorar_trigger)
        self.container.bind("<KP_Enter>", self._ignorar_trigger)
        self.container.bind("<F2>", self._ignorar_trigger)
        self.container.bind("<F3>", self._handle_close)
        self.container.bind("<Escape>", self._handle_close)
        self.container.unbind("<F1>")

    def _open_project_config(self) -> None:
        if self.on_configure is not None:
            self.on_configure()

    @staticmethod
    def _ignorar_trigger(_event=None):
        return "break"

    def set_project_info(
        self,
        name: str | None,
        master_resolution=None,
        mask_count: int = 0,
        check_count: int = 0,
    ) -> None:
        project_name = str(name or "NENHUM")
        resolution_text = "--"
        if isinstance(master_resolution, (list, tuple)) and len(master_resolution) >= 2:
            resolution_text = f"{int(master_resolution[0])}x{int(master_resolution[1])}"
        self.project_info_label.configure(text=f"PROJETO DISPLAY: {project_name}")
        self.project_detail_label.configure(
            text=(
                f"Resolução mestre: {resolution_text}  •  "
                f"Máscaras: {int(mask_count)}  •  CHECKS: {int(check_count)}"
            )
        )

    def show_waiting_camera(self) -> None:
        self.status_label.configure(text="AGUARDANDO CÂMERA")
        self.detail_label.configure(
            text="Aguardando um frame válido da câmera ao vivo do ODIN."
        )
        self.set_preview_status("Aguardando câmera", self.PREVIEW_MUTED)

    def show_camera_ready(self, width: int, height: int) -> None:
        self.status_label.configure(text="DISPLAY F3")
        self.detail_label.configure(
            text=(
                f"Câmera ao vivo • {int(width)}x{int(height)} • "
                "Fase 3 sem análise automática"
            )
        )

    def update_camera_preview(self, frame) -> bool:
        """Renderiza somente o frame; não recebe ROIs nem estado do F2."""
        if frame is None or getattr(frame, "size", 0) == 0:
            self.show_waiting_camera()
            return False

        height, width = frame.shape[:2]
        rendered = self.update_preview(frame, leds=())
        if rendered:
            self.show_camera_ready(width, height)
        return rendered
