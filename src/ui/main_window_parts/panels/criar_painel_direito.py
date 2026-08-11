import tkinter as tk


def _criar_card_visual(self, parent, titulo: str, texto_placeholder: str):
    card = self.criar_card(parent)
    card.grid_rowconfigure(1, weight=1)
    card.grid_columnconfigure(0, weight=1)

    self.criar_titulo_card(card, titulo).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=7,
        pady=(4, 2),
    )

    canvas = tk.Canvas(
        card,
        bg="#020617",
        highlightthickness=1,
        highlightbackground=self.COR_BORDA,
        bd=0,
        relief=tk.FLAT,
        width=1,
        height=1,
    )
    canvas.grid(
        row=1,
        column=0,
        sticky="nsew",
        padx=5,
        pady=(0, 5),
    )
    self.desenhar_placeholder(canvas, texto_placeholder)
    return card, canvas


def _criar_card_texto(
    self,
    parent,
    titulo: str,
    atributo_texto: str,
    texto_inicial: str = "",
):
    card = self.criar_card(parent)
    card.grid_rowconfigure(1, weight=1)
    card.grid_columnconfigure(0, weight=1)

    self.criar_titulo_card(card, titulo).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=7,
        pady=(4, 2),
    )

    texto = tk.Text(
        card,
        bg="#020617",
        fg=self.COR_TEXTO_2,
        insertbackground=self.COR_TEXTO,
        font=("Consolas", 7),
        relief=tk.FLAT,
        wrap=tk.WORD,
        height=4,
        bd=0,
    )
    texto.grid(
        row=1,
        column=0,
        sticky="nsew",
        padx=6,
        pady=(0, 5),
    )

    if texto_inicial:
        texto.insert(tk.END, texto_inicial)

    setattr(self, atributo_texto, texto)
    return card, texto


def criar_painel_direito(self) -> None:
    # Faixa única de diagnóstico: seis cards lado a lado, na ordem usada pelo
    # operador para investigar a imagem, a ROI, a decisão e o histórico.
    self.frame_direito = tk.Frame(
        self.frame_dashboard,
        bg=self.COR_FUNDO_APP,
    )
    self.frame_direito.grid(
        row=1,
        column=0,
        columnspan=2,
        sticky="nsew",
        pady=(0, 4),
    )
    self.frame_direito.grid_rowconfigure(0, weight=1)
    for coluna in range(6):
        self.frame_direito.grid_columnconfigure(
            coluna,
            weight=1,
            uniform="faixa_diagnostico",
        )

    self.frame_imagem_teste, self.canvas_imagem_teste = _criar_card_visual(
        self,
        self.frame_direito,
        "Imagem de teste • Canal V",
        "Imagem processada\nEtapa 2",
    )
    self.frame_imagem_teste.grid(
        row=0,
        column=0,
        sticky="nsew",
        padx=(0, 3),
    )

    self.frame_mascara, self.canvas_mascara = _criar_card_visual(
        self,
        self.frame_direito,
        "Máscara / ROI",
        "Máscara visual\nEtapa 2",
    )
    self.frame_mascara.grid(
        row=0,
        column=1,
        sticky="nsew",
        padx=3,
    )

    self.frame_roi_debug, self.canvas_roi_debug = _criar_card_visual(
        self,
        self.frame_direito,
        "ROI ampliado",
        "ROI debug\nEtapa 2",
    )
    self.frame_roi_debug.grid(
        row=0,
        column=2,
        sticky="nsew",
        padx=3,
    )

    self.frame_debug, self.texto_resultados = _criar_card_texto(
        self,
        self.frame_direito,
        "Debug técnico",
        "texto_resultados",
    )
    self.frame_debug.grid(
        row=0,
        column=3,
        sticky="nsew",
        padx=3,
    )

    self.frame_log_producao, self.texto_log_producao = _criar_card_texto(
        self,
        self.frame_direito,
        "Log produção",
        "texto_log_producao",
        "Nenhuma análise de produção registrada.",
    )
    self.frame_log_producao.grid(
        row=0,
        column=4,
        sticky="nsew",
        padx=3,
    )
    self.texto_log_producao.configure(state=tk.DISABLED)

    self.frame_mapa, self.canvas_mapa_intensidade = _criar_card_visual(
        self,
        self.frame_direito,
        "Mapa de intensidade",
        "Mapa de intensidade\nEtapa 2",
    )
    self.frame_mapa.grid(
        row=0,
        column=5,
        sticky="nsew",
        padx=(3, 0),
    )
