from __future__ import annotations

import tkinter as tk

from src.platform.display_production_f3_window import DisplayProductionF3Window


F3_DEBUG_TOGGLE_OFF_TEXT = "DEBUG OFF"
F3_DEBUG_TOGGLE_ON_TEXT = "DEBUG ON"


def debug_tecnico_ativo_display_f3(target) -> bool:
    """Consulta o estado explícito do debug técnico; o padrão é sempre OFF."""
    window = getattr(target, "display_f3_window", target)
    if window is None:
        return False
    return bool(getattr(window, "_display_f3_technical_debug_enabled", False))


def _limpar_telemetria_debug_display_f3(window) -> None:
    """Libera histórico diagnóstico quando o operador desliga o debug."""
    owner = getattr(window, "_display_f3_debug_owner", None)
    if owner is None:
        return

    history = getattr(owner, "_display_f3_live_trace", None)
    try:
        history.clear()
    except Exception:
        pass
    owner._display_f3_live_probe_last_analysis = None
    owner._display_f3_perf_last_context_signature = None
    owner._display_f3_perf_last_probe_approved = False
    owner._display_f3_perf_last_trace_monotonic = None


def aplicar_estado_debug_tecnico_display_f3(window, enabled: bool) -> None:
    """Liga/desliga apenas diagnóstico; a análise produtiva do F3 continua ativa."""
    enabled = bool(enabled)
    window._display_f3_technical_debug_enabled = enabled

    variable = getattr(window, "_display_f3_technical_debug_var", None)
    if variable is not None:
        try:
            if bool(variable.get()) != enabled:
                variable.set(enabled)
        except Exception:
            pass

    toggle = getattr(window, "technical_debug_toggle", None)
    if toggle is not None:
        try:
            toggle.configure(
                text=F3_DEBUG_TOGGLE_ON_TEXT if enabled else F3_DEBUG_TOGGLE_OFF_TEXT,
                bg="#0E7490" if enabled else "#1E293B",
                activebackground="#0891B2" if enabled else "#334155",
            )
        except Exception:
            pass

    button = getattr(window, "technical_debug_button", None)
    if button is not None:
        try:
            button.configure(
                state=tk.NORMAL if enabled else tk.DISABLED,
                cursor="hand2" if enabled else "arrow",
            )
        except Exception:
            pass

    if enabled:
        return

    # Desligar deve interromper imediatamente refresh/telemetria da janela.
    try:
        window.close_technical_debug()
    except Exception:
        pass
    _limpar_telemetria_debug_display_f3(window)


_INSTALLED = False


def instalar_toggle_debug_tecnico_display_f3() -> None:
    """Instala controle explícito de custo do DEBUG TÉCNICO somente no F3."""
    global _INSTALLED
    if _INSTALLED:
        return

    cls = DisplayProductionF3Window
    if bool(getattr(cls, "_display_f3_debug_toggle_installed", False)):
        _INSTALLED = True
        return

    original_init = cls.__init__
    original_open_debug = cls.open_technical_debug
    original_set_provider = cls.set_technical_debug_provider

    def set_debug_enabled(self, enabled: bool) -> None:
        aplicar_estado_debug_tecnico_display_f3(self, enabled)

    def is_debug_enabled(self) -> bool:
        return debug_tecnico_ativo_display_f3(self)

    def open_debug(self):
        if not self.is_technical_debug_enabled():
            return None
        return original_open_debug(self)

    def set_provider(self, provider) -> None:
        # Guardamos o owner da lambda para limpar a telemetria ao desligar.
        try:
            closure = getattr(provider, "__closure__", None) or ()
            for cell in closure:
                candidate = getattr(cell, "cell_contents", None)
                if candidate is not None and hasattr(candidate, "display_f3_window"):
                    self._display_f3_debug_owner = candidate
                    break
        except Exception:
            pass
        original_set_provider(self, provider)

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)

        self._display_f3_technical_debug_enabled = False
        self._display_f3_technical_debug_var = tk.BooleanVar(value=False)
        self._display_f3_debug_owner = None

        toggle = tk.Checkbutton(
            self.project_frame,
            text=F3_DEBUG_TOGGLE_OFF_TEXT,
            variable=self._display_f3_technical_debug_var,
            command=lambda owner=self: owner.set_technical_debug_enabled(
                bool(owner._display_f3_technical_debug_var.get())
            ),
            indicatoron=False,
            font=("DejaVu Sans", 8, "bold"),
            bg="#1E293B",
            fg="#E2E8F0",
            activebackground="#334155",
            activeforeground="#FFFFFF",
            selectcolor="#0E7490",
            relief="flat",
            bd=0,
            padx=9,
            pady=6,
            cursor="hand2",
            highlightthickness=0,
        )
        toggle.grid(
            row=0,
            column=3,
            rowspan=2,
            sticky="e",
            padx=(0, 10),
            pady=7,
        )
        self.technical_debug_toggle = toggle
        self.set_technical_debug_enabled(False)

    cls.set_technical_debug_enabled = set_debug_enabled
    cls.is_technical_debug_enabled = is_debug_enabled
    cls.open_technical_debug = open_debug
    cls.set_technical_debug_provider = set_provider
    cls.__init__ = init
    cls._display_f3_debug_toggle_installed = True
    _INSTALLED = True
