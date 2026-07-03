import tkinter as tk


def criar_item_metadado(self, titulo: str, valor: str, destaque: bool = False) -> tk.Label:
    indice = int(getattr(self, "_indice_metadado", 0))
    linha = indice // 4
    coluna = indice % 4
    self._indice_metadado = indice + 1

    frame = tk.Frame(self.frame_metadados, bg=self.COR_CARD)
    frame.grid(
        row=linha,
        column=coluna,
        sticky="nsew",
        padx=7,
        pady=3,
    )

    label_titulo = tk.Label(
        frame,
        text=f"{titulo}: ",
        font=("Segoe UI", 8, "bold"),
        fg=self.COR_TEXTO_3,
        bg=self.COR_CARD,
        anchor="w",
    )
    label_titulo.pack(side=tk.LEFT)

    label_valor = tk.Label(
        frame,
        text=valor,
        font=("Segoe UI", 8, "bold"),
        fg=self.COR_VERDE_CLARO if destaque else self.COR_TEXTO_2,
        bg=self.COR_CARD,
        anchor="w",
        justify=tk.LEFT,
    )
    label_valor.pack(side=tk.LEFT, fill=tk.X, expand=True)
    return label_valor
