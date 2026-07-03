import tkinter as tk
from tkinter import ttk


def criar_tabela_inferior(self) -> None:
    self.frame_tabela = self.criar_card(self.frame_dashboard)
    self.frame_tabela.grid(
        row=1,
        column=0,
        columnspan=3,
        sticky="nsew",
        padx=0,
        pady=(2, 0),
    )
    self.frame_tabela.grid_rowconfigure(1, weight=1)
    self.frame_tabela.grid_columnconfigure(0, weight=1)

    self.criar_titulo_card(
        self.frame_tabela,
        "Histórico da sessão / LEDs analisados",
    ).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=12,
        pady=(6, 3),
    )

    colunas = (
        "id",
        "posicao",
        "status",
        "confianca",
        "v_mean",
        "v_max",
        "glow",
        "observacao",
    )
    self.tabela_historico = ttk.Treeview(
        self.frame_tabela,
        columns=colunas,
        show="headings",
        height=3,
    )

    titulos = {
        "id": "ID LED",
        "posicao": "Posição (x, y)",
        "status": "Status",
        "confianca": "Confiança",
        "v_mean": "v_mean",
        "v_max": "v_max",
        "glow": "Glow",
        "observacao": "Observação",
    }
    larguras = {
        "id": 100,
        "posicao": 120,
        "status": 90,
        "confianca": 95,
        "v_mean": 80,
        "v_max": 80,
        "glow": 80,
        "observacao": 460,
    }

    for coluna in colunas:
        self.tabela_historico.heading(
            coluna,
            text=titulos[coluna],
        )
        self.tabela_historico.column(
            coluna,
            width=larguras[coluna],
            anchor=tk.CENTER,
        )

    self.tabela_historico.grid(
        row=1,
        column=0,
        sticky="nsew",
        padx=10,
        pady=(0, 8),
    )
