import tkinter as tk


def criar_kpi(self, parent, titulo: str, valor: str) -> tk.Frame:
    frame = tk.Frame(
        parent,
        bg=self.COR_CARD_2,
        height=46,
    )
    frame.pack_propagate(False)

    label_titulo = tk.Label(
        frame,
        text=titulo,
        font=("Segoe UI", 7, "bold"),
        fg=self.COR_TEXTO_3,
        bg=self.COR_CARD_2,
    )
    label_titulo.pack(anchor="center", pady=(5, 0))

    label_valor = tk.Label(
        frame,
        text=valor,
        font=("Segoe UI", 10, "bold"),
        fg=self.COR_TEXTO,
        bg=self.COR_CARD_2,
    )
    label_valor.pack(anchor="center")

    frame.label_valor = label_valor
    return frame
