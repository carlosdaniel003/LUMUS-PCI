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

    # A área superior recebe a maior parte da altura. A tabela continua
    # acessível, mas não reduz a visualização da câmera e do mapa.
    self.frame_dashboard.grid_rowconfigure(
        0,
        weight=8,
        minsize=410,
    )
    self.frame_dashboard.grid_rowconfigure(
        1,
        weight=2,
        minsize=105,
    )

    # O grupo uniforme impede que o tamanho solicitado pelos três painéis
    # auxiliares comprima a imagem principal. As proporções dão prioridade
    # à câmera ao vivo e, em seguida, ao mapa de intensidade.
    self.frame_dashboard.grid_columnconfigure(
        0,
        weight=7,
        minsize=430,
        uniform="dashboard_columns",
    )
    self.frame_dashboard.grid_columnconfigure(
        1,
        weight=4,
        minsize=300,
        uniform="dashboard_columns",
    )
    self.frame_dashboard.grid_columnconfigure(
        2,
        weight=5,
        minsize=360,
        uniform="dashboard_columns",
    )

    self.criar_painel_principal()
    self.criar_painel_central()
    self.criar_painel_direito()
    self.criar_tabela_inferior()
