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

    # A área superior concentra câmera, mapa e painéis auxiliares. A tabela
    # inferior continua visível, mas não disputa altura com a imagem principal.
    self.frame_dashboard.grid_rowconfigure(
        0,
        weight=9,
        minsize=470,
    )
    self.frame_dashboard.grid_rowconfigure(
        1,
        weight=1,
        minsize=90,
    )

    # Não usar uniform aqui. Os canvases auxiliares possuem tamanho solicitado
    # próprio e, quando agrupados como uniformes, podem forçar a câmera principal
    # a ficar estreita. A imagem ao vivo recebe a maior parcela da largura; o
    # mapa de intensidade vem em seguida e o painel técnico usa o espaço restante.
    self.frame_dashboard.grid_columnconfigure(
        0,
        weight=8,
        minsize=560,
    )
    self.frame_dashboard.grid_columnconfigure(
        1,
        weight=5,
        minsize=340,
    )
    self.frame_dashboard.grid_columnconfigure(
        2,
        weight=5,
        minsize=390,
    )

    self.criar_painel_principal()
    self.criar_painel_central()
    self.criar_painel_direito()
    self.criar_tabela_inferior()
