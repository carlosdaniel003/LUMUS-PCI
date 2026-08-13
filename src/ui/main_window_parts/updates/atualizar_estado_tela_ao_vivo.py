def atualizar_estado_tela_ao_vivo(self, ativa: bool) -> None:
    self.tela_ao_vivo_ativa = bool(ativa)

    botao_screenshot = getattr(self, "botao_screenshot_principal", None)
    if botao_screenshot is not None:
        try:
            botao_screenshot.config(
                state="normal" if ativa else "disabled",
                cursor="hand2" if ativa else "arrow",
            )
        except Exception:
            pass

    if not hasattr(self, "botao_tela_ao_vivo"):
        return

    if self.botao_tela_ao_vivo is None:
        return

    if ativa:
        self.botao_tela_ao_vivo.config(
            text="Parar câmera",
            bg="#3F1D1D",
            fg="#FECACA",
            activebackground="#7F1D1D",
        )
    else:
        self.botao_tela_ao_vivo.config(
            text="Tela ao vivo",
            bg="#0F3D24",
            fg="#BBF7D0",
            activebackground="#14532D",
        )
