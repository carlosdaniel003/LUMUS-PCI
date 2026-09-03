from __future__ import annotations

from src.platform.display_project_config import DisplayProjectConfigWindow


F3_CONFIG_MIN_WIDTH = 760
F3_CONFIG_MIN_HEIGHT = 540


def maximizar_janela_configuracao_display_f3(window) -> str:
    """Maximiza a configuração F3 com fallback Windows/Linux/Tk genérico."""
    try:
        window.resizable(True, True)
    except Exception:
        pass
    try:
        window.minsize(F3_CONFIG_MIN_WIDTH, F3_CONFIG_MIN_HEIGHT)
    except Exception:
        pass
    try:
        window.update_idletasks()
    except Exception:
        pass

    # Windows/Tk: estado maximizado nativo mantém barra de título e controles.
    try:
        window.state("zoomed")
        return "state_zoomed"
    except Exception:
        pass

    # X11/Linux: alguns window managers expõem o zoom como atributo Tk.
    try:
        window.attributes("-zoomed", True)
        return "attribute_zoomed"
    except Exception:
        pass

    # Fallback neutro: ocupa a área de tela disponível sem tamanho fixo 820x680.
    try:
        width = max(F3_CONFIG_MIN_WIDTH, int(window.winfo_screenwidth()))
        height = max(F3_CONFIG_MIN_HEIGHT, int(window.winfo_screenheight()))
        window.geometry(f"{width}x{height}+0+0")
        return "screen_geometry"
    except Exception:
        return "unavailable"


_INSTALLED = False


def instalar_configuracao_responsiva_display_f3() -> None:
    """Faz o botão CONFIGURAR do F3 abrir em janela maximizada e redimensionável."""
    global _INSTALLED
    if _INSTALLED:
        return

    cls = DisplayProjectConfigWindow
    if bool(getattr(cls, "_display_f3_responsive_config_installed", False)):
        _INSTALLED = True
        return

    original_init = cls.__init__

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._display_f3_config_window_mode = maximizar_janela_configuracao_display_f3(
            self.window
        )

        # Reaplica depois que o gerenciador de janelas terminou de montar o
        # Toplevel. Evita que geometry/transient do Tk devolva a janela a 820x680.
        try:
            self.window.after_idle(
                lambda owner=self: maximizar_janela_configuracao_display_f3(
                    owner.window
                )
            )
        except Exception:
            pass

    cls.__init__ = init
    cls._display_f3_responsive_config_installed = True
    _INSTALLED = True
