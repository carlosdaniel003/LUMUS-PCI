import tkinter as tk


def criar_area_dashboard(self) -> None:
    self.frame_dashboard = tk.Frame(
        self.frame_principal,
        bg=self.COR_FUNDO_APP,
    )
    self.frame_dashboard.pack(
        fill=tk.BOTH,
        expand=True,
        padx=10,
        pady=(0, 8),
    )

    # Linha superior: somente os dois elementos de decisão da operação.
    # Linha inferior: todas as visualizações e textos de diagnóstico em uma
    # única faixa. O histórico permanece compacto na terceira linha.
    self.frame_dashboard.grid_rowconfigure(
        0,
        weight=1,
        minsize=270,
    )
    self.frame_dashboard.grid_rowconfigure(
        1,
        weight=0,
        minsize=152,
    )
    self.frame_dashboard.grid_rowconfigure(
        2,
        weight=0,
        minsize=72,
    )

    # A imagem principal recebe a maior parte do topo. O resultado geral fica
    # visível ao lado sem disputar espaço com as ferramentas de diagnóstico.
    self.frame_dashboard.grid_columnconfigure(0, weight=7)
    self.frame_dashboard.grid_columnconfigure(1, weight=3)

    self.criar_painel_principal()
    self.criar_painel_central()
    self.criar_painel_direito()
    self.criar_tabela_inferior()
