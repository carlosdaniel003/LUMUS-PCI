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


class RaspberryPi3ProductionApp(
    AutomaticLedDetectionMixin,
    GPIOEnabledRaspberryPi3ODINApp,
):
    """Perfil final do Raspberry com o acesso à produção integrado ao topo."""

    def __init__(self, root: tk.Tk) -> None:
        instalar_normalizacao_config_repository()
        instalar_repositorio_projetos_led()
        super().__init__(root)

    def _instalar_tela_operacao(self) -> None:
        super()._instalar_tela_operacao()

        botao_anterior = self.botao_operacao
        try:
            botao_anterior.place_forget()
            botao_anterior.destroy()
        except tk.TclError:
            pass

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
        else:
            self.botao_operacao.pack(
                side=tk.RIGHT,
                padx=(0, 8),
                pady=18,
            )
