from __future__ import annotations

from collections.abc import Callable

from src.ui.operation_window_raspberry import RaspberryOperationWindow


class DisplayProductionF3Window(RaspberryOperationWindow):
    """Janela visual independente para o novo modo Produção Display (F3).

    Fase 1: reutiliza somente o renderer de preview da produção atual. Não há
    análise, trigger por Enter, checks, engine, resultado OK/NG ou estado F2.
    """

    def __init__(
        self,
        root,
        on_close: Callable[[], None],
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

        self.brand_label.configure(text="ODIN  |  PRODUÇÃO DISPLAY  F3")
        self.mode_label.configure(text="DISPLAY • ISOLAMENTO ARQUITETURAL")
        self.status_label.configure(text="AGUARDANDO CÂMERA")
        self.detail_label.configure(
            text=(
                "Fase 1 • câmera ao vivo compartilhada em modo somente leitura. "
                "Análise automática e CHECKS serão adicionados nas próximas fases."
            )
        )
        self.preview_title.configure(text="DISPLAY • CÂMERA AO VIVO")
        self.preview_legend.configure(
            text="FASE 1 • SEM ANÁLISE",
            fg=self.PREVIEW_MUTED,
        )
        self.footer_label.configure(text="F3 ou ESC: voltar ao ODIN")

        # Estes componentes pertencem ao fluxo F2 e não participam do F3.
        self.led_summary_label.grid_remove()
        self.metrics_frame.grid_remove()

        # O F3 não possui trigger manual. Enter é consumido localmente e nunca
        # chega ao callback/engine usado pelo modo F2. F2 também é consumido
        # enquanto esta tela possui foco, impedindo dois modos de produção
        # simultâneos sem alterar o binding original do F2 na aplicação.
        self.container.bind("<Return>", self._ignorar_trigger)
        self.container.bind("<KP_Enter>", self._ignorar_trigger)
        self.container.bind("<F2>", self._ignorar_trigger)
        self.container.bind("<F3>", self._handle_close)
        self.container.bind("<Escape>", self._handle_close)
        self.container.unbind("<F1>")

    @staticmethod
    def _ignorar_trigger(_event=None):
        return "break"

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
                "Fase 1 sem análise"
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
