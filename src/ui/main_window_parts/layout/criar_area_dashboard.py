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

    # A primeira linha concentra os dois elementos críticos da operação:
    # câmera ao vivo e mapa de intensidade. As visualizações auxiliares e o
    # histórico usam faixas compactas com altura previsível.
    self.frame_dashboard.grid_rowconfigure(
        0,
        weight=1,
        minsize=260,
    )
    self.frame_dashboard.grid_rowconfigure(
        1,
        weight=0,
        minsize=128,
    )
    self.frame_dashboard.grid_rowconfigure(
        2,
        weight=0,
        minsize=72,
    )

    # Não usar larguras mínimas rígidas nem uniform. Isso evita que a soma dos
    # tamanhos solicitados ultrapasse a resolução disponível no Raspberry Pi.
    # A câmera recebe a maior parcela, seguida do mapa e do resultado técnico.
    self.frame_dashboard.grid_columnconfigure(0, weight=7)
    self.frame_dashboard.grid_columnconfigure(1, weight=4)
    self.frame_dashboard.grid_columnconfigure(2, weight=2)

    self.criar_painel_principal()
    self.criar_painel_central()
    self.criar_painel_direito()
    self.criar_tabela_inferior()
