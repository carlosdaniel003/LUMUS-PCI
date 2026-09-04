from __future__ import annotations

"""Tela leve para o DEBUG TÉCNICO do snapshot manual do Display F3.

O relatório completo continua disponível para suporte e para o clipboard, porém
não é inserido em um widget Text. Isso evita custo de layout/renderização de
milhares de linhas e mantém a janela consistente com os workspaces F3.
"""

import tkinter as tk

import src.platform.display_f3_manual_snapshot_debug as manual_module
from src.platform.display_f3_workspace_ui import maximizar_janela_workspace_f3
from src.platform.display_production_f3_window import DisplayProductionF3Window


DEBUG_SUMMARY = (
    "O debug técnico contém o snapshot congelado do frame analisado, dados da "
    "captura, estado físico, scores das referências, CHECK lógico, configuração "
    "das máscaras, comparação com os gabaritos, aprendizado ACESO/APAGADO e "
    "evidências de energia. O conteúdo completo não é renderizado nesta tela "
    "para evitar lentidão. Use COPIAR DEBUG para enviá-lo ao suporte."
)
COPY_START_DELAY_MS = 12
COPY_FEEDBACK_RESET_MS = 1800
READY_TEXT = "RELATÓRIO PRONTO PARA CÓPIA"


def _set_copy_feedback(
    status_label=None,
    copy_button=None,
    *,
    status_text: str,
    button_text: str,
    enabled: bool,
) -> None:
    if status_label is not None:
        try:
            status_label.configure(text=status_text)
        except Exception:
            pass
    if copy_button is not None:
        try:
            copy_button.configure(
                text=button_text,
                state=(tk.NORMAL if enabled else tk.DISABLED),
            )
        except Exception:
            pass


def _restore_copy_feedback(status_label=None, copy_button=None) -> None:
    _set_copy_feedback(
        status_label,
        copy_button,
        status_text=READY_TEXT,
        button_text="COPIAR DEBUG",
        enabled=True,
    )


def _copy_report(window, top, status_label=None, copy_button=None) -> bool:
    """Copia diretamente para o clipboard sem forçar processamento síncrono da UI."""
    report = str(getattr(window, "_display_f3_manual_snapshot_report", "") or "")
    if not report:
        _set_copy_feedback(
            status_label,
            copy_button,
            status_text="SEM DEBUG DISPONÍVEL PARA COPIAR",
            button_text="TENTAR NOVAMENTE",
            enabled=True,
        )
        return False

    try:
        top.clipboard_clear()
        top.clipboard_append(report)
        _set_copy_feedback(
            status_label,
            copy_button,
            status_text="DEBUG COPIADO COM SUCESSO",
            button_text="COPIADO",
            enabled=False,
        )
        return True
    except Exception:
        _set_copy_feedback(
            status_label,
            copy_button,
            status_text="NÃO FOI POSSÍVEL COPIAR O DEBUG",
            button_text="TENTAR NOVAMENTE",
            enabled=True,
        )
        return False


def _schedule_copy_report(window, top, status_label=None, copy_button=None) -> bool:
    """Entrega um paint ao Tk antes de copiar o relatório grande para o clipboard."""
    report = str(getattr(window, "_display_f3_manual_snapshot_report", "") or "")
    if not report:
        _set_copy_feedback(
            status_label,
            copy_button,
            status_text="SEM DEBUG DISPONÍVEL PARA COPIAR",
            button_text="TENTAR NOVAMENTE",
            enabled=True,
        )
        return False

    _set_copy_feedback(
        status_label,
        copy_button,
        status_text="COPIANDO DEBUG...",
        button_text="COPIANDO...",
        enabled=False,
    )

    def do_copy() -> None:
        copied = _copy_report(window, top, status_label, copy_button)
        if not copied:
            return
        try:
            top.after(
                COPY_FEEDBACK_RESET_MS,
                lambda: _restore_copy_feedback(status_label, copy_button),
            )
        except Exception:
            pass

    try:
        top.after(COPY_START_DELAY_MS, do_copy)
    except Exception:
        do_copy()
    return True


def _open_lightweight_snapshot_debug(window):
    report = str(getattr(window, "_display_f3_manual_snapshot_report", "") or "")
    if not report:
        return None

    existing = getattr(window, "_display_f3_snapshot_debug_window", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                existing.deiconify()
                existing.lift()
                existing.focus_force()
                return existing
        except Exception:
            pass

    top = tk.Toplevel(window.root)
    window._display_f3_snapshot_debug_window = top
    window._display_f3_snapshot_debug_text = None
    top.title("ODIN • DISPLAY F3 • DEBUG DO FRAME ANALISADO")
    top.configure(bg=manual_module.DEBUG_BG)

    # Uma única maximização, somente depois de toda a hierarquia estar criada.
    # Evita o antigo ciclo geometry -> paint -> geometry -> paint na abertura.
    try:
        top.after_idle(lambda current=top: maximizar_janela_workspace_f3(current))
    except Exception:
        pass

    shell = tk.Frame(top, bg=manual_module.DEBUG_BG)
    shell.pack(fill="both", expand=True, padx=28, pady=24)

    header = tk.Frame(shell, bg=manual_module.DEBUG_BG)
    header.pack(fill="x")
    tk.Label(
        header,
        text="DEBUG TÉCNICO • FRAME ANALISADO",
        font=("Segoe UI", 18, "bold"),
        bg=manual_module.DEBUG_BG,
        fg=manual_module.DEBUG_TEXT,
        anchor="w",
    ).pack(fill="x")

    snapshot = getattr(window, "_display_f3_manual_snapshot", {}) or {}
    frame_id = (snapshot.get("capture") or {}).get("frame_id", "--")
    sha = (snapshot.get("frame") or {}).get("sha256_24", "--")
    tk.Label(
        header,
        text=f"Frame {frame_id} • hash {sha} • conteúdo congelado no clique em ANALISAR",
        font=("Segoe UI", 10),
        bg=manual_module.DEBUG_BG,
        fg=manual_module.DEBUG_MUTED,
        anchor="w",
    ).pack(fill="x", pady=(4, 0))

    body = tk.Frame(shell, bg=manual_module.DEBUG_BG)
    body.pack(fill="both", expand=True, pady=(34, 20))

    message = tk.Label(
        body,
        text=DEBUG_SUMMARY,
        font=("Segoe UI", 12),
        bg=manual_module.DEBUG_BG,
        fg=manual_module.DEBUG_TEXT,
        justify="left",
        anchor="nw",
        wraplength=1040,
    )
    message.pack(anchor="nw", fill="x")

    def fit_message(event):
        try:
            message.configure(wraplength=max(420, int(event.width) - 8))
        except Exception:
            pass

    body.bind("<Configure>", fit_message, add="+")

    status = tk.Label(
        body,
        text=READY_TEXT,
        font=("Segoe UI", 9, "bold"),
        bg=manual_module.DEBUG_BG,
        fg=manual_module.DEBUG_MUTED,
        anchor="w",
    )
    status.pack(anchor="w", pady=(22, 0))

    actions = tk.Frame(shell, bg=manual_module.DEBUG_BG)
    actions.pack(fill="x")

    copy_button = tk.Button(
        actions,
        text="COPIAR DEBUG",
        font=("Segoe UI", 10, "bold"),
        bg=manual_module.DEBUG_ACTION,
        fg="#FFFFFF",
        activebackground=manual_module.DEBUG_ACTION_ACTIVE,
        activeforeground="#FFFFFF",
        disabledforeground="#CBD5E1",
        relief="flat",
        bd=0,
        padx=16,
        pady=8,
        cursor="hand2",
    )
    copy_button.configure(
        command=lambda: _schedule_copy_report(window, top, status, copy_button)
    )
    copy_button.pack(side="left")

    tk.Button(
        actions,
        text="FECHAR",
        command=window.close_f3_snapshot_debug,
        font=("Segoe UI", 10, "bold"),
        bg="#1E293B",
        fg=manual_module.DEBUG_TEXT,
        activebackground="#334155",
        activeforeground="#FFFFFF",
        relief="flat",
        bd=0,
        padx=16,
        pady=8,
        cursor="hand2",
    ).pack(side="right")

    top.protocol("WM_DELETE_WINDOW", window.close_f3_snapshot_debug)
    top.bind("<Escape>", lambda _event: window.close_f3_snapshot_debug())
    return top


_INSTALLED = False


def instalar_debug_snapshot_leve_display_f3() -> None:
    """Substitui somente a apresentação do snapshot; relatório permanece íntegro."""
    global _INSTALLED
    if _INSTALLED:
        return

    DisplayProductionF3Window.open_f3_snapshot_debug = (
        lambda self: _open_lightweight_snapshot_debug(self)
    )
    DisplayProductionF3Window._display_f3_snapshot_debug_lightweight_ui = True
    _INSTALLED = True
