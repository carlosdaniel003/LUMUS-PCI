def sair_tela_cheia(self, evento=None):
    if not self.tela_cheia_ativa:
        return "break"

    self.root.attributes("-topmost", False)
    self.root.attributes("-fullscreen", False)
    self.root.overrideredirect(False)
    self.root.update_idletasks()

    self.tela_cheia_ativa = False
    self.root.after(80, self.maximizar_janela)

    return "break"