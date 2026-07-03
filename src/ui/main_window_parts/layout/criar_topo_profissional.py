import tkinter as tk


def criar_topo_profissional(self) -> None:
    self.frame_topo = tk.Frame(
        self.frame_principal,
        bg=self.COR_TOPO,
        height=88,
    )
    self.frame_topo.pack(
        fill=tk.X,
        padx=10,
        pady=(8, 4),
    )
    self.frame_topo.pack_propagate(False)
    self.frame_topo.grid_columnconfigure(0, weight=0, minsize=220)
    self.frame_topo.grid_columnconfigure(1, weight=1)
    self.frame_topo.grid_columnconfigure(2, weight=0, minsize=330)
    self.frame_topo.grid_rowconfigure(0, weight=1)

    self.frame_marca = tk.Frame(
        self.frame_topo,
        bg=self.COR_TOPO,
        width=220,
    )
    self.frame_marca.grid(
        row=0,
        column=0,
        sticky="nsew",
        padx=(10, 8),
    )
    self.frame_marca.pack_propagate(False)

    self.label_icone = tk.Label(
        self.frame_marca,
        text="▌",
        font=("Segoe UI", 34, "bold"),
        fg=self.COR_VERDE_CLARO,
        bg=self.COR_TOPO,
    )
    self.label_icone.pack(side=tk.LEFT, padx=(0, 7))

    self.frame_titulo = tk.Frame(
        self.frame_marca,
        bg=self.COR_TOPO,
    )
    self.frame_titulo.pack(
        side=tk.LEFT,
        fill=tk.BOTH,
        expand=True,
    )

    self.label_titulo = tk.Label(
        self.frame_titulo,
        text="ODIN",
        font=("Segoe UI", 20, "bold"),
        fg=self.COR_TEXTO,
        bg=self.COR_TOPO,
        anchor="center",
        justify=tk.CENTER,
    )
    self.label_titulo.pack(fill=tk.X, pady=(12, 0))

    self.label_subtitulo = tk.Label(
        self.frame_titulo,
        text="Observador Digital Inteligente",
        font=("Segoe UI", 8, "bold"),
        fg=self.COR_TEXTO_3,
        bg=self.COR_TOPO,
        anchor="center",
        justify=tk.CENTER,
    )
    self.label_subtitulo.pack(fill=tk.X)

    # A área fixa da direita é criada antes dos botões centrais para impedir
    # que o toolbar expansível esconda o botão PRODUÇÃO.
    self.frame_topo_direita = tk.Frame(
        self.frame_topo,
        bg=self.COR_TOPO,
        width=330,
    )
    self.frame_topo_direita.grid(
        row=0,
        column=2,
        sticky="nsew",
        padx=(6, 10),
    )
    self.frame_topo_direita.pack_propagate(False)

    self.botao_configuracoes = tk.Button(
        self.frame_topo_direita,
        text="⚙",
        command=self.callbacks["abrir_configuracoes"],
        font=("Segoe UI", 19),
        fg=self.COR_TEXTO_2,
        bg=self.COR_TOPO,
        activebackground=self.COR_CARD_2,
        activeforeground=self.COR_TEXTO,
        relief=tk.FLAT,
        bd=0,
        cursor="hand2",
    )
    self.botao_configuracoes.pack(
        side=tk.RIGHT,
        padx=(6, 0),
        pady=18,
    )

    self.botao_toggle_relogio = tk.Button(
        self.frame_topo_direita,
        text="Hora ON",
        command=self.alternar_visibilidade_relogio,
        width=8,
        height=2,
        bg="#0F3D24",
        fg="#BBF7D0",
        activebackground="#14532D",
        activeforeground=self.COR_TEXTO,
        relief=tk.FLAT,
        bd=0,
        font=("Segoe UI", 8, "bold"),
        cursor="hand2",
    )
    self.botao_toggle_relogio.pack(
        side=tk.RIGHT,
        padx=(0, 6),
        pady=22,
    )

    self.frame_botoes = tk.Frame(
        self.frame_topo,
        bg=self.COR_TOPO,
    )
    self.frame_botoes.grid(
        row=0,
        column=1,
        sticky="nsew",
        pady=18,
    )
    for coluna in range(7):
        self.frame_botoes.grid_columnconfigure(
            coluna,
            weight=1,
            uniform="toolbar_topo",
        )
    self.frame_botoes.grid_rowconfigure(0, weight=1)

    self.botao_tela_ao_vivo = self.criar_botao_topo(
        texto="Tela ao vivo",
        comando=self.callbacks["alternar_tela_ao_vivo"],
        ativo=True,
        cor_fundo="#0F3D24",
        cor_texto="#BBF7D0",
    )
    self.botao_tela_ao_vivo.grid(
        row=0,
        column=0,
        sticky="nsew",
        padx=2,
    )

    self.criar_botao_topo(
        texto="Carregar imagem",
        comando=self.callbacks["carregar_imagem"],
        cor_fundo="#0B2742",
        cor_texto="#BAE6FD",
    ).grid(row=0, column=1, sticky="nsew", padx=2)

    self.botao_selecionar_leds = self.criar_botao_topo(
        texto="Selecionar LEDs",
        comando=self.callbacks["iniciar_selecao_led"],
    )
    self.botao_selecionar_leds.grid(
        row=0,
        column=2,
        sticky="nsew",
        padx=2,
    )

    self.criar_botao_topo(
        texto="Detectar LEDs\nAutomático",
        comando=self.callbacks["detectar_leds_automaticamente"],
        cor_fundo="#3B2F0B",
        cor_texto="#FDE68A",
    ).grid(row=0, column=3, sticky="nsew", padx=2)

    self.criar_botao_topo(
        texto="Carregar LEDs",
        comando=self.callbacks["carregar_leds_fixos"],
        cor_fundo="#13210F",
        cor_texto="#BBF7D0",
    ).grid(row=0, column=4, sticky="nsew", padx=2)

    self.criar_botao_topo(
        texto="Analisar",
        comando=self.callbacks["analisar_led_selecionado"],
        cor_fundo="#0F3D24",
        cor_texto="#BBF7D0",
    ).grid(row=0, column=5, sticky="nsew", padx=2)

    self.criar_botao_topo(
        texto="Limpar seleção",
        comando=self.callbacks["limpar_tela"],
    ).grid(row=0, column=6, sticky="nsew", padx=2)
