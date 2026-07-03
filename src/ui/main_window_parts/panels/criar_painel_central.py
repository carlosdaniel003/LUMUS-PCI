import tkinter as tk


def criar_painel_central(self) -> None:
    # Mapa e resultado ocupam a mesma linha da câmera. O mapa recebe o dobro
    # da largura do painel de resultado e toda a altura disponível.
    self.frame_central = tk.Frame(
        self.frame_dashboard,
        bg=self.COR_FUNDO_APP,
    )
    self.frame_central.grid(
        row=0,
        column=1,
        columnspan=2,
        sticky="nsew",
        padx=(4, 0),
        pady=(0, 4),
    )
    self.frame_central.grid_rowconfigure(0, weight=1)
    self.frame_central.grid_columnconfigure(0, weight=4)
    self.frame_central.grid_columnconfigure(1, weight=2)

    self.frame_mapa = self.criar_card(self.frame_central)
    self.frame_mapa.grid(
        row=0,
        column=0,
        sticky="nsew",
        padx=(0, 4),
    )
    self.frame_mapa.grid_rowconfigure(1, weight=1)
    self.frame_mapa.grid_columnconfigure(0, weight=1)

    self.criar_titulo_card(
        self.frame_mapa,
        "Mapa de intensidade",
    ).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=10,
        pady=(6, 3),
    )

    self.canvas_mapa_intensidade = tk.Canvas(
        self.frame_mapa,
        bg="#020617",
        highlightthickness=1,
        highlightbackground=self.COR_BORDA,
        bd=0,
        width=1,
        height=1,
    )
    self.canvas_mapa_intensidade.grid(
        row=1,
        column=0,
        sticky="nsew",
        padx=6,
        pady=(0, 6),
    )
    self.desenhar_placeholder(
        self.canvas_mapa_intensidade,
        "Mapa de intensidade\nEtapa 2",
    )

    self.frame_resultado = self.criar_card(self.frame_central)
    self.frame_resultado.grid(
        row=0,
        column=1,
        sticky="nsew",
        padx=(4, 0),
    )
    self.frame_resultado.grid_columnconfigure(0, weight=1)
    self.frame_resultado.grid_rowconfigure(4, weight=1)

    self.criar_titulo_card(
        self.frame_resultado,
        "RESULTADO GERAL",
    ).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=8,
        pady=(6, 0),
    )

    self.label_resultado_grande = tk.Label(
        self.frame_resultado,
        text="SEM ANÁLISE",
        font=("Segoe UI", 14, "bold"),
        fg=self.COR_TEXTO_3,
        bg=self.COR_CARD,
        anchor="w",
    )
    self.label_resultado_grande.grid(
        row=1,
        column=0,
        sticky="ew",
        padx=8,
        pady=(2, 0),
    )

    self.label_confianca = tk.Label(
        self.frame_resultado,
        text="Confiança: --",
        font=("Segoe UI", 8, "bold"),
        fg=self.COR_TEXTO_2,
        bg=self.COR_CARD,
        justify=tk.LEFT,
        anchor="w",
    )
    self.label_confianca.grid(
        row=2,
        column=0,
        sticky="ew",
        padx=8,
        pady=(0, 1),
    )

    self.canvas_barra_confianca = tk.Canvas(
        self.frame_resultado,
        height=6,
        bg=self.COR_CARD,
        highlightthickness=0,
        bd=0,
    )
    self.canvas_barra_confianca.grid(
        row=3,
        column=0,
        sticky="ew",
        padx=8,
        pady=(0, 3),
    )
    self.desenhar_barra_confianca(0.0, self.COR_NEUTRO)

    self.frame_kpis = tk.Frame(
        self.frame_resultado,
        bg=self.COR_CARD,
    )
    self.frame_kpis.grid(
        row=4,
        column=0,
        sticky="nsew",
        padx=5,
        pady=(0, 5),
    )
    for coluna in range(2):
        self.frame_kpis.grid_columnconfigure(
            coluna,
            weight=1,
            uniform="kpis_resultado",
        )
    for linha in range(3):
        self.frame_kpis.grid_rowconfigure(
            linha,
            weight=1,
            uniform="linhas_kpis_resultado",
        )

    self.card_binario = self.criar_kpi(
        self.frame_kpis,
        "Valor binário",
        "--",
    )
    self.card_binario.grid(
        row=0,
        column=0,
        sticky="nsew",
        padx=2,
        pady=2,
    )

    self.card_v_mean = self.criar_kpi(
        self.frame_kpis,
        "v_mean",
        "--",
    )
    self.card_v_mean.grid(
        row=0,
        column=1,
        sticky="nsew",
        padx=2,
        pady=2,
    )

    self.card_v_max = self.criar_kpi(
        self.frame_kpis,
        "v_max",
        "--",
    )
    self.card_v_max.grid(
        row=1,
        column=0,
        sticky="nsew",
        padx=2,
        pady=2,
    )

    self.card_dist_on = self.criar_kpi(
        self.frame_kpis,
        "Dist. aceso",
        "--",
    )
    self.card_dist_on.grid(
        row=1,
        column=1,
        sticky="nsew",
        padx=2,
        pady=2,
    )

    self.card_dist_off = self.criar_kpi(
        self.frame_kpis,
        "Dist. apagado",
        "--",
    )
    self.card_dist_off.grid(
        row=2,
        column=0,
        sticky="nsew",
        padx=2,
        pady=2,
    )

    self.card_glow = self.criar_kpi(
        self.frame_kpis,
        "Glow score",
        "--",
    )
    self.card_glow.grid(
        row=2,
        column=1,
        sticky="nsew",
        padx=2,
        pady=2,
    )
