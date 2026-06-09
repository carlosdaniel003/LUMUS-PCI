from src.ui.main_window_parts.lifecycle.obter_geometria_monitor_atual import formatar_geometria_janela


def alternar_tela_cheia(self, evento=None):
    if self.tela_cheia_ativa:
        self.sair_tela_cheia(evento)
        return "break"

    geometria_monitor = self.obter_geometria_monitor_atual()

    self.root.attributes("-fullscreen", False)
    self.root.state("normal")
    self.root.update_idletasks()

    geometria_tela_cheia = formatar_geometria_janela(
        largura_janela=geometria_monitor["monitor_largura"],
        altura_janela=geometria_monitor["monitor_altura"],
        posicao_x=geometria_monitor["monitor_x"],
        posicao_y=geometria_monitor["monitor_y"],
    )

    self.root.overrideredirect(True)
    self.root.geometry(geometria_tela_cheia)
    self.root.attributes("-topmost", True)
    self.root.lift()
    self.root.focus_force()

    self.tela_cheia_ativa = True

    return "break"