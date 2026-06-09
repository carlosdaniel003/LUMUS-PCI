from src.ui.main_window_parts.lifecycle.obter_geometria_monitor_atual import formatar_geometria_janela


def maximizar_janela(self) -> None:
    self.root.attributes("-topmost", False)
    self.root.attributes("-fullscreen", False)
    self.root.overrideredirect(False)
    self.root.update_idletasks()

    self.tela_cheia_ativa = False

    geometria_monitor = self.obter_geometria_monitor_atual()

    geometria_maximizada = formatar_geometria_janela(
        largura_janela=geometria_monitor["work_largura"],
        altura_janela=geometria_monitor["work_altura"],
        posicao_x=geometria_monitor["work_x"],
        posicao_y=geometria_monitor["work_y"],
    )

    self.root.state("normal")
    self.root.geometry(geometria_maximizada)
    self.root.update_idletasks()

    try:
        self.root.state("zoomed")
    except Exception:
        pass