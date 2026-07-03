import tkinter as tk


def criar_painel_principal(self) -> None:
    self.frame_painel_principal = self.criar_card(
        self.frame_dashboard
    )
    self.frame_painel_principal.grid(
        row=0,
        column=0,
        sticky="nsew",
        padx=(0, 4),
        pady=(0, 4),
    )
    self.frame_painel_principal.grid_rowconfigure(1, weight=1)
    self.frame_painel_principal.grid_columnconfigure(0, weight=1)

    self.criar_titulo_card(
        self.frame_painel_principal,
        "Imagem principal • Ao vivo",
    ).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=10,
        pady=(6, 3),
    )

    # O Canvas não solicita uma dimensão fixa. Ele acompanha integralmente o
    # espaço real do grid, impedindo que uma resolução menor corte a imagem.
    self.canvas = tk.Canvas(
        self.frame_painel_principal,
        bg="#020617",
        highlightthickness=1,
        highlightbackground=self.COR_BORDA,
        cursor="crosshair",
        bd=0,
        width=1,
        height=1,
    )
    self.canvas.grid(
        row=1,
        column=0,
        sticky="nsew",
        padx=6,
        pady=(0, 4),
    )
    self.canvas.bind(
        "<Button-1>",
        self.callbacks["evento_clique_esquerdo"],
    )
    self.canvas.bind(
        "<Configure>",
        self.evento_redimensionar_canvas_principal,
    )
    self.canvas.bind("<Motion>", self.atualizar_lupa_canvas)
    self.canvas.bind("<Leave>", self.limpar_lupa_canvas)

    # Informações compactas preservam a altura útil da câmera sem remover
    # parâmetros ou o resumo da análise.
    self.frame_parametros = tk.Frame(
        self.frame_painel_principal,
        bg=self.COR_CARD,
    )
    self.frame_parametros.grid(
        row=2,
        column=0,
        sticky="ew",
        padx=6,
        pady=(0, 6),
    )
    self.frame_parametros.grid_columnconfigure(
        0,
        weight=1,
        uniform="parametros_principal",
    )
    self.frame_parametros.grid_columnconfigure(
        1,
        weight=1,
        uniform="parametros_principal",
    )

    self.frame_parametros_analise = tk.Frame(
        self.frame_parametros,
        bg=self.COR_CARD_2,
    )
    self.frame_parametros_analise.grid(
        row=0,
        column=0,
        sticky="nsew",
        padx=(0, 2),
    )

    self.label_parametros = tk.Label(
        self.frame_parametros_analise,
        text=(
            "Parâmetros  •  ref. aceso/apagado\n"
            f"ROI manual  •  raio {self.raio_atual_px}px  •  múltiplos LEDs"
        ),
        font=("Consolas", 8),
        fg=self.COR_TEXTO_2,
        bg=self.COR_CARD_2,
        justify=tk.LEFT,
        anchor="w",
    )
    self.label_parametros.pack(
        fill=tk.BOTH,
        expand=True,
        padx=6,
        pady=3,
    )

    self.frame_resumo = tk.Frame(
        self.frame_parametros,
        bg=self.COR_CARD_2,
    )
    self.frame_resumo.grid(
        row=0,
        column=1,
        sticky="nsew",
        padx=(2, 0),
    )

    self.label_resumo = tk.Label(
        self.frame_resumo,
        text=(
            "Resumo  •  sem análise\n"
            "Confiança --  •  posição --  •  binário --"
        ),
        font=("Consolas", 8),
        fg=self.COR_TEXTO_2,
        bg=self.COR_CARD_2,
        justify=tk.LEFT,
        anchor="w",
    )
    self.label_resumo.pack(
        fill=tk.BOTH,
        expand=True,
        padx=6,
        pady=3,
    )
