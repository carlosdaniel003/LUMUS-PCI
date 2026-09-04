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


def _copy_report(window, top, status_label=None) -> bool:
    report = str(getattr(window, "_display_f3_manual_snapshot_report", "") or "")
    if not report:
        return False
    try:
        top.clipboard_clear()
        top.clipboard_append(report)
        top.update()
        if status_label is not None:
            status_label.configure(text="DEBUG COPIADO")
        return True
    except Exception:
        if status_label is not None:
            try:
                status_label.configure(text="NÃO FOI POSSÍVEL COPIAR")
            except Exception:
                pass
        return False


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
    maximizar_janela_workspace_f3(top)
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
        text="RELATÓRIO PRONTO PARA CÓPIA",
        font=("Segoe UI", 9, "bold"),
        bg=manual_module.DEBUG_BG,
        fg=manual_module.DEBUG_MUTED,
        anchor="w",
    )
    status.pack(anchor="w", pady=(22, 0))

    actions = tk.Frame(shell, bg=manual_module.DEBUG_BG)
    actions.pack(fill="x")

    tk.Button(
        actions,
        text="COPIAR DEBUG",
        command=lambda: _copy_report(window, top, status),
        font=("Segoe UI", 10, "bold"),
        bg=manual_module.DEBUG_ACTION,
        fg="#FFFFFF",
        activebackground=manual_module.DEBUG_ACTION_ACTIVE,
        activeforeground="#FFFFFF",
        relief="flat",
        bd=0,
        padx=16,
        pady=8,
        cursor="hand2",
    ).pack(side="left")

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
