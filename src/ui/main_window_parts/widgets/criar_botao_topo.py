import tkinter as tk


def criar_botao_topo(
    self,
    texto: str,
    comando,
    ativo: bool = True,
    cor_fundo: str = "#0B1626",
    cor_texto: str = "#E5E7EB",
) -> tk.Button:
    return tk.Button(
        self.frame_botoes,
        text=texto,
        command=comando if ativo else None,
        width=10,
        height=2,
        wraplength=92,
        justify=tk.CENTER,
        bg=cor_fundo if ativo else "#111827",
        fg=cor_texto if ativo else "#64748B",
        activebackground="#122033",
        activeforeground=self.COR_TEXTO,
        disabledforeground="#64748B",
        relief=tk.FLAT,
        bd=0,
        font=("Segoe UI", 8, "bold"),
        cursor="hand2" if ativo else "arrow",
    )
