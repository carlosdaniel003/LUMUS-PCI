import tkinter as tk


def sair_tela_cheia(self, evento=None):
    if not self.tela_cheia_ativa:
        return "break"

    reforco_after_id = getattr(self, "_reforco_tela_cheia_after_id", None)
    self._reforco_tela_cheia_after_id = None
    if reforco_after_id is not None:
        try:
            self.root.after_cancel(reforco_after_id)
        except tk.TclError:
            pass

    try:
        self.root.attributes("-topmost", False)
        self.root.attributes("-fullscreen", False)
        self.root.overrideredirect(False)
        self.root.update_idletasks()
    except tk.TclError:
        pass

    self.tela_cheia_ativa = False
    try:
        self.root.after(80, self.maximizar_janela)
    except tk.TclError:
        pass

    return "break"
