from __future__ import annotations

import tkinter as tk

from src.platform.automatic_led_detection import (
    AutomaticLedDetectionMixin,
)
from src.platform.camera_advanced_config import (
    instalar_normalizacao_config_repository,
)
from src.platform.gpio_raspberry_app import (
    GPIOEnabledRaspberryPi3ODINApp,
)
from src.platform.led_project_repository import (
    instalar_repositorio_projetos_led,
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
    StableRaspberryOperationWindow,
)


class RaspberryPi3ProductionApp(
    RaspberryRuntimeFixesMixin,
    RaspberryEnterTriggerMixin,
    AutomaticLedDetectionMixin,
    GPIOEnabledRaspberryPi3ODINApp,
):
    """Perfil final do Raspberry com o acesso à produção integrado ao topo."""

    def __init__(self, root: tk.Tk) -> None:
        instalar_normalizacao_config_repository()
        instalar_repositorio_projetos_led()
        super().__init__(root)

    def _instalar_tela_operacao(self) -> None:
        # O perfil final usa uma janela própria: metade para o resultado e
        # metade para a câmera responsiva. A variante estável também garante
        # que nenhum foco, grab ou callback visual bloqueie a tela principal.
        self.operacao_window = StableRaspberryOperationWindow(
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

        parent = getattr(
            self.view,
            "frame_topo_direita",
            self.root,
        )

        self.botao_operacao = tk.Button(
            parent,
            text="PRODUÇÃO  F2",
            command=self.abrir_tela_operacao,
            font=("DejaVu Sans", 10, "bold"),
            bg="#16A34A",
            fg="#FFFFFF",
            activebackground="#15803D",
            activeforeground="#FFFFFF",
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
