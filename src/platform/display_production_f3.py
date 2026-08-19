from __future__ import annotations

import tkinter as tk

from src.platform.display_production_f3_window import DisplayProductionF3Window
from src.platform.display_theme import DISPLAY_INK
from src.platform.raspberry_pi3_settings import (
    OPERATION_PREVIEW_HEIGHT,
    OPERATION_PREVIEW_WIDTH,
)


class DisplayProductionF3Mixin:
    """Fase 1 do modo F3, totalmente separado do runtime de Produção F2.

    O F3 possui janela, flag e timer próprios. A única integração operacional é
    a leitura de ``camera_frame_atual`` já produzida pelo ODIN. Nenhum método de
    análise F2 é sobrescrito ou chamado por esta camada.
    """

    DISPLAY_F3_PREVIEW_INTERVAL_MS = 90
    DISPLAY_F3_BUTTON_BG = "#0E7490"
    DISPLAY_F3_BUTTON_ACTIVE_BG = "#0891B2"

    def __init__(self, *args, **kwargs) -> None:
        self.display_f3_window: DisplayProductionF3Window | None = None
        self.display_f3_ativo = False
        self.display_f3_after_id = None
        super().__init__(*args, **kwargs)
        self._instalar_modo_display_f3()

    def _criar_janela_producao_display_f3(self) -> DisplayProductionF3Window:
        return DisplayProductionF3Window(
            root=self.root,
            on_close=self.fechar_tela_producao_display_f3,
            preview_width=max(480, int(OPERATION_PREVIEW_WIDTH)),
            preview_height=max(360, int(OPERATION_PREVIEW_HEIGHT)),
        )

    def _f2_esta_aberto(self) -> bool:
        if bool(getattr(self, "operacao_ativa", False)):
            return True
        janela = getattr(self, "operacao_window", None)
        if janela is None:
            return False
        try:
            return bool(janela.visible)
        except Exception:
            return False

    def _instalar_modo_display_f3(self) -> None:
        self.display_f3_window = self._criar_janela_producao_display_f3()

        self.root.bind(
            "<F3>",
            lambda _event: self.abrir_tela_producao_display_f3(),
            add="+",
        )

        parent = getattr(self.view, "frame_topo_direita", self.root)
        self.botao_operacao_display_f3 = tk.Button(
            parent,
            text="DISPLAY  F3",
            command=self.abrir_tela_producao_display_f3,
            font=("DejaVu Sans", 10, "bold"),
            bg=self.DISPLAY_F3_BUTTON_BG,
            fg="#FFFFFF",
            activebackground=self.DISPLAY_F3_BUTTON_ACTIVE_BG,
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
        )

        if parent is self.root:
            self.botao_operacao_display_f3.place(
                relx=1.0,
                x=-188,
                y=16,
                anchor="ne",
            )
            self.botao_operacao_display_f3.lift()
        else:
            self.botao_operacao_display_f3.pack(
                side=tk.RIGHT,
                padx=(0, 8),
                pady=18,
            )

    def abrir_tela_producao_display_f3(self) -> bool:
        """Abre F3 sem inicializar engine, trigger, contadores ou estado F2."""
        if self.display_f3_ativo:
            janela = self.display_f3_window
            if janela is not None:
                try:
                    janela.show()
                except Exception:
                    pass
            return True

        if self._f2_esta_aberto():
            try:
                self.view.atualizar_status(
                    "Feche a Produção F2 antes de abrir a Produção Display F3."
                )
            except Exception:
                pass
            return False

        # F3 não cria nem substitui um serviço de câmera. Caso a tela ao vivo
        # ainda esteja desligada, pede ao fluxo existente que a inicie e passa
        # a consumir somente camera_frame_atual quando ele ficar disponível.
        if not bool(getattr(self, "camera_ativa", False)):
            try:
                self.iniciar_tela_ao_vivo()
            except Exception:
                pass

        self.display_f3_ativo = True
        janela = self.display_f3_window
        if janela is not None:
            janela.show_waiting_camera()
            janela.show()

        self._agendar_preview_display_f3(0)
        return True

    def fechar_tela_producao_display_f3(self) -> None:
        """Fecha somente a camada F3; a câmera e o F2 não são parados."""
        self.display_f3_ativo = False

        if self.display_f3_after_id is not None:
            try:
                self.root.after_cancel(self.display_f3_after_id)
            except Exception:
                pass
            self.display_f3_after_id = None

        janela = self.display_f3_window
        if janela is not None:
            try:
                janela.hide()
            except Exception:
                pass

        try:
            self.root.after_idle(self.root.focus_force)
        except Exception:
            pass

    def _agendar_preview_display_f3(
        self,
        atraso_ms: int | None = None,
    ) -> None:
        if not self.display_f3_ativo or self.display_f3_after_id is not None:
            return
        atraso = (
            self.DISPLAY_F3_PREVIEW_INTERVAL_MS
            if atraso_ms is None
            else max(0, int(atraso_ms))
        )
        try:
            self.display_f3_after_id = self.root.after(
                atraso,
                self._atualizar_preview_display_f3,
            )
        except Exception:
            self.display_f3_after_id = None

    def _atualizar_preview_display_f3(self) -> None:
        self.display_f3_after_id = None
        if not self.display_f3_ativo:
            return

        janela = self.display_f3_window
        frame = getattr(self, "camera_frame_atual", None)
        if janela is not None:
            try:
                janela.update_camera_preview(frame)
            except Exception:
                pass

        self._agendar_preview_display_f3()

    # Marcador explícito usado pelos testes de isolamento arquitetural.
    @staticmethod
    def responsabilidades_f3() -> tuple[str, ...]:
        return (
            "janela_f3",
            "atalho_f3",
            "preview_camera_somente_leitura",
            "ciclo_abertura_fechamento_f3",
        )
