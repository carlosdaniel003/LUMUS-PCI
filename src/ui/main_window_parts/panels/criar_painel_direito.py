import tkinter as tk


def _criar_card_visual(
    self,
    parent,
    titulo: str,
    texto_placeholder: str,
):
    card = self.criar_card(parent)
    card.grid_rowconfigure(1, weight=1)
    card.grid_columnconfigure(0, weight=1)

    self.criar_titulo_card(
        card,
        titulo,
    ).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=9,
        pady=(7, 4),
    )

    canvas = tk.Canvas(
        card,
        bg="#020617",
        highlightthickness=1,
        highlightbackground=self.COR_BORDA,
        bd=0,
        relief=tk.FLAT,
        width=120,
        height=88,
    )
    canvas.grid(
        row=1,
        column=0,
        sticky="nsew",
        padx=8,
        pady=(0, 8),
    )

    self.desenhar_placeholder(
        canvas,
        texto_placeholder,
    )

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

    self.criar_titulo_card(
        card,
        titulo,
    ).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=10,
        pady=(8, 4),
    )

    texto = tk.Text(
        card,
        bg="#020617",
        fg=self.COR_TEXTO_2,
        insertbackground=self.COR_TEXTO,
        font=("Consolas", 8),
        relief=tk.FLAT,
        wrap=tk.WORD,
        height=6,
        bd=0,
    )
    texto.grid(
        row=1,
        column=0,
        sticky="nsew",
        padx=10,
        pady=(0, 9),
    )

    if texto_inicial:
        texto.insert(tk.END, texto_inicial)

    setattr(self, atributo_texto, texto)
    return card, texto


def criar_painel_direito(self) -> None:
    """
    Cria o painel lateral direito sem obrigar três cards largos na mesma linha.

    A imagem de teste ocupa a largura superior. Máscara e ROI ficam abaixo,
    enquanto Debug e Log dividem a faixa inferior. Essa composição reduz a
    largura mínima do painel e devolve espaço para a câmera principal.
    """
    self.frame_direito = tk.Frame(
        self.frame_dashboard,
        bg=self.COR_FUNDO_APP,
    )
    self.frame_direito.grid(
        row=0,
        column=2,
        sticky="nsew",
        padx=(6, 0),
        pady=(0, 6),
    )

    self.frame_direito.grid_rowconfigure(
        0,
        weight=3,
        minsize=235,
    )
    self.frame_direito.grid_rowconfigure(
        1,
        weight=2,
        minsize=145,
    )
    self.frame_direito.grid_columnconfigure(0, weight=1)

    self.frame_visuais_direita = tk.Frame(
        self.frame_direito,
        bg=self.COR_FUNDO_APP,
    )
    self.frame_visuais_direita.grid(
        row=0,
        column=0,
        sticky="nsew",
        pady=(0, 5),
    )
    self.frame_visuais_direita.grid_rowconfigure(
        0,
        weight=3,
        minsize=110,
    )
    self.frame_visuais_direita.grid_rowconfigure(
        1,
        weight=2,
        minsize=95,
    )
    self.frame_visuais_direita.grid_columnconfigure(
        0,
        weight=1,
        uniform="visuais_direita",
    )
    self.frame_visuais_direita.grid_columnconfigure(
        1,
        weight=1,
        uniform="visuais_direita",
    )

    (
        self.frame_imagem_teste,
        self.canvas_imagem_teste,
    ) = _criar_card_visual(
        self,
        self.frame_visuais_direita,
        "Imagem de teste • Canal V",
        "Imagem processada\nEtapa 2",
    )
    self.frame_imagem_teste.grid(
        row=0,
        column=0,
        columnspan=2,
        sticky="nsew",
        pady=(0, 4),
    )

    (
        self.frame_mascara,
        self.canvas_mascara,
    ) = _criar_card_visual(
        self,
        self.frame_visuais_direita,
        "Máscara / ROI",
        "Máscara visual\nEtapa 2",
    )
    self.frame_mascara.grid(
        row=1,
        column=0,
        sticky="nsew",
        padx=(0, 4),
        pady=(4, 0),
    )

    (
        self.frame_roi_debug,
        self.canvas_roi_debug,
    ) = _criar_card_visual(
        self,
        self.frame_visuais_direita,
        "ROI ampliado",
        "ROI debug\nEtapa 2",
    )
    self.frame_roi_debug.grid(
        row=1,
        column=1,
        sticky="nsew",
        padx=(4, 0),
        pady=(4, 0),
    )

    self.frame_textos_direita = tk.Frame(
        self.frame_direito,
        bg=self.COR_FUNDO_APP,
    )
    self.frame_textos_direita.grid(
        row=1,
        column=0,
        sticky="nsew",
        pady=(5, 0),
    )
    self.frame_textos_direita.grid_rowconfigure(0, weight=1)
    self.frame_textos_direita.grid_columnconfigure(
        0,
        weight=1,
        uniform="cards_texto_direita",
    )
    self.frame_textos_direita.grid_columnconfigure(
        1,
        weight=1,
        uniform="cards_texto_direita",
    )

    self.frame_debug, self.texto_resultados = _criar_card_texto(
        self,
        self.frame_textos_direita,
        "Debug técnico",
        "texto_resultados",
    )
    self.frame_debug.grid(
        row=0,
        column=0,
        sticky="nsew",
        padx=(0, 4),
    )

    self.frame_log_producao, self.texto_log_producao = _criar_card_texto(
        self,
        self.frame_textos_direita,
        "Log produção",
        "texto_log_producao",
        "Nenhuma análise de produção registrada.",
    )
    self.frame_log_producao.grid(
        row=0,
        column=1,
        sticky="nsew",
        padx=(4, 0),
    )
    self.texto_log_producao.configure(state=tk.DISABLED)
