from __future__ import annotations

import tkinter as tk

import cv2

from src.ui.main_window_parts.image.exibir_imagem_em_canvas import (
    preparar_imagem_auxiliar_visual,
)


VISUALIZACOES_TELA_CHEIA = {
    "principal": "Imagem principal • Ao vivo",
    "heatmap": "Mapa de intensidade",
    "canal_v": "Imagem de teste • Canal V",
    "mascara": "Máscara / ROI",
    "roi_debug": "ROI ampliado",
}


def calcular_encaixe_imagem(
    largura_imagem: int,
    altura_imagem: int,
    largura_canvas: int,
    altura_canvas: int,
    margem: int = 18,
) -> tuple[float, int, int, int, int]:
    """Calcula escala e posição central sem distorcer a imagem."""
    largura_imagem = max(1, int(largura_imagem))
    altura_imagem = max(1, int(altura_imagem))
    largura_canvas = max(1, int(largura_canvas))
    altura_canvas = max(1, int(altura_canvas))
    margem = max(0, int(margem))

    largura_util = max(1, largura_canvas - (margem * 2))
    altura_util = max(1, altura_canvas - (margem * 2))

    escala = min(
        largura_util / largura_imagem,
        altura_util / altura_imagem,
    )
    largura_final = max(1, int(round(largura_imagem * escala)))
    altura_final = max(1, int(round(altura_imagem * escala)))
    x = int((largura_canvas - largura_final) / 2)
    y = int((altura_canvas - altura_final) / 2)
    return escala, largura_final, altura_final, x, y


def _codificar_ppm_bgr(imagem_bgr) -> bytes:
    altura, largura = imagem_bgr.shape[:2]
    imagem_rgb = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2RGB)
    cabecalho = f"P6\n{largura} {altura}\n255\n".encode("ascii")
    return cabecalho + imagem_rgb.tobytes()


def _imagem_fonte(self, chave: str):
    if chave == "principal":
        return getattr(self, "imagem_canvas_original", None)

    imagens = getattr(self, "imagens_auxiliares_originais", {})
    imagem = imagens.get(chave)
    if imagem is None:
        return None

    # Os quatro painéis derivados usam a mesma orientação visual da imagem
    # principal também quando são abertos em tela cheia. A cópia original
    # permanece intacta no dicionário de fontes.
    return preparar_imagem_auxiliar_visual(
        imagem,
        getattr(self, "rotacao_visual_principal", 0),
    )


def _janela_valida(self) -> bool:
    janela = getattr(self, "janela_imagem_tela_cheia", None)
    if janela is None:
        return False
    try:
        return bool(janela.winfo_exists())
    except Exception:
        return False


def _normalizar_lista(valor):
    if valor is None:
        return []
    if isinstance(valor, (list, tuple)):
        return list(valor)
    return [valor]


def _desenhar_overlay_resultados(
    self,
    canvas: tk.Canvas,
    resultados,
    escala: float,
    offset_x: int,
    offset_y: int,
) -> None:
    for resultado in _normalizar_lista(resultados):
        try:
            centro_x = offset_x + int(round(resultado.centro_x * escala))
            centro_y = offset_y + int(round(resultado.centro_y * escala))
            raio = max(4, int(round(resultado.raio * escala)))
            valor_binario = int(resultado.valor_binario)
        except Exception:
            continue

        cor = self.COR_VERDE_CLARO if valor_binario == 1 else "#3B82F6"
        largura = 2 if valor_binario == 1 else 4
        raio_visual = raio if valor_binario == 1 else max(raio, int(raio * 1.25))

        canvas.create_oval(
            centro_x - raio_visual,
            centro_y - raio_visual,
            centro_x + raio_visual,
            centro_y + raio_visual,
            outline=cor,
            width=largura,
            tags=("fullscreen_overlay",),
        )
        canvas.create_line(
            centro_x - raio_visual,
            centro_y,
            centro_x + raio_visual,
            centro_y,
            fill=cor,
            width=1,
            tags=("fullscreen_overlay",),
        )
        canvas.create_line(
            centro_x,
            centro_y - raio_visual,
            centro_x,
            centro_y + raio_visual,
            fill=cor,
            width=1,
            tags=("fullscreen_overlay",),
        )

        id_led = str(getattr(resultado, "id", "LED"))
        numero = id_led.split("_")[-1] if "_" in id_led else id_led

        if valor_binario == 0:
            texto = f"{numero} NG"
            x_label = centro_x + raio_visual + 7
            y_label = centro_y - raio_visual
            largura_texto = max(58, len(texto) * 9)
            canvas.create_rectangle(
                x_label - 5,
                y_label - 22,
                x_label + largura_texto,
                y_label + 3,
                fill="#061A33",
                outline=cor,
                width=1,
                tags=("fullscreen_overlay",),
            )
            canvas.create_text(
                x_label,
                y_label - 10,
                text=texto,
                fill=cor,
                font=("Segoe UI", 10, "bold"),
                anchor=tk.W,
                tags=("fullscreen_overlay",),
            )
        else:
            tamanho = max(8, min(15, int(round(8 * max(1.0, escala)))))
            canvas.create_oval(
                centro_x - tamanho,
                centro_y - tamanho,
                centro_x + tamanho,
                centro_y + tamanho,
                fill="#03120A",
                outline=cor,
                width=1,
                tags=("fullscreen_overlay",),
            )
            canvas.create_text(
                centro_x,
                centro_y,
                text=numero,
                fill=cor,
                font=("Segoe UI", 8, "bold"),
                tags=("fullscreen_overlay",),
            )


def _desenhar_overlay_selecoes(
    self,
    canvas: tk.Canvas,
    selecoes,
    escala: float,
    offset_x: int,
    offset_y: int,
) -> None:
    for selecao in _normalizar_lista(selecoes):
        try:
            centro_x = offset_x + int(round(selecao.centro_x * escala))
            centro_y = offset_y + int(round(selecao.centro_y * escala))
            raio = max(4, int(round(selecao.raio * escala)))
        except Exception:
            continue

        id_led = str(getattr(selecao, "id", "LED"))
        numero = id_led.split("_")[-1] if "_" in id_led else id_led
        cor = self.COR_AMARELO

        canvas.create_oval(
            centro_x - raio,
            centro_y - raio,
            centro_x + raio,
            centro_y + raio,
            outline=cor,
            width=2,
            tags=("fullscreen_overlay",),
        )
        canvas.create_line(
            centro_x - raio,
            centro_y,
            centro_x + raio,
            centro_y,
            fill=cor,
            tags=("fullscreen_overlay",),
        )
        canvas.create_line(
            centro_x,
            centro_y - raio,
            centro_x,
            centro_y + raio,
            fill=cor,
            tags=("fullscreen_overlay",),
        )
        canvas.create_text(
            centro_x,
            centro_y,
            text=numero,
            fill=cor,
            font=("Segoe UI", 8, "bold"),
            tags=("fullscreen_overlay",),
        )


def redesenhar_imagem_tela_cheia(self) -> None:
    if not _janela_valida(self):
        return

    canvas = getattr(self, "canvas_imagem_tela_cheia", None)
    chave = getattr(self, "chave_imagem_tela_cheia", None)
    if canvas is None or not chave:
        return

    imagem = _imagem_fonte(self, chave)
    canvas.delete("fullscreen_imagem")
    canvas.delete("fullscreen_overlay")
    canvas.delete("fullscreen_placeholder")

    if imagem is None:
        canvas.create_text(
            max(1, canvas.winfo_width()) / 2,
            max(1, canvas.winfo_height()) / 2,
            text="Sem imagem disponível",
            fill=self.COR_TEXTO_2,
            font=("Segoe UI", 18, "bold"),
            tags=("fullscreen_placeholder",),
        )
        return

    try:
        imagem_local = imagem.copy()
    except Exception:
        imagem_local = imagem

    if len(imagem_local.shape) == 2:
        imagem_bgr = cv2.cvtColor(imagem_local, cv2.COLOR_GRAY2BGR)
    else:
        imagem_bgr = imagem_local

    altura_imagem, largura_imagem = imagem_bgr.shape[:2]
    largura_canvas = max(1, int(canvas.winfo_width()))
    altura_canvas = max(1, int(canvas.winfo_height()))
    escala, largura_final, altura_final, x, y = calcular_encaixe_imagem(
        largura_imagem,
        altura_imagem,
        largura_canvas,
        altura_canvas,
    )

    if largura_final != largura_imagem or altura_final != altura_imagem:
        interpolacao = cv2.INTER_AREA if escala < 1.0 else cv2.INTER_LINEAR
        imagem_bgr = cv2.resize(
            imagem_bgr,
            (largura_final, altura_final),
            interpolation=interpolacao,
        )

    try:
        dados_ppm = _codificar_ppm_bgr(imagem_bgr)
        imagem_tk = tk.PhotoImage(data=dados_ppm, format="PPM")
    except tk.TclError:
        sucesso, buffer = cv2.imencode(".png", imagem_bgr)
        if not sucesso:
            return
        import base64

        imagem_tk = tk.PhotoImage(
            data=base64.b64encode(buffer).decode("ascii")
        )

    self.imagem_tela_cheia_tk = imagem_tk
    canvas.create_image(
        x,
        y,
        image=imagem_tk,
        anchor=tk.NW,
        tags=("fullscreen_imagem",),
    )

    if chave == "principal":
        resultados = getattr(self, "ultimo_resultado_led_atual", None)
        if _normalizar_lista(resultados):
            _desenhar_overlay_resultados(
                self,
                canvas,
                resultados,
                escala,
                x,
                y,
            )
        else:
            _desenhar_overlay_selecoes(
                self,
                canvas,
                getattr(self, "ultimo_led_selecionado", None),
                escala,
                x,
                y,
            )


def _agendar_redesenho(self) -> None:
    if not _janela_valida(self):
        return
    janela = self.janela_imagem_tela_cheia
    pendente = getattr(self, "_redesenho_imagem_tela_cheia_pendente", None)
    if pendente is not None:
        return

    def executar():
        self._redesenho_imagem_tela_cheia_pendente = None
        redesenhar_imagem_tela_cheia(self)

    try:
        self._redesenho_imagem_tela_cheia_pendente = janela.after_idle(executar)
    except Exception:
        self._redesenho_imagem_tela_cheia_pendente = None


def atualizar_imagem_tela_cheia_se_aberta(self, chave: str) -> None:
    if not _janela_valida(self):
        return
    if getattr(self, "chave_imagem_tela_cheia", None) != chave:
        return
    _agendar_redesenho(self)


def fechar_imagem_tela_cheia(self, _evento=None) -> None:
    janela = getattr(self, "janela_imagem_tela_cheia", None)
    pendente = getattr(self, "_redesenho_imagem_tela_cheia_pendente", None)
    if janela is not None and pendente is not None:
        try:
            janela.after_cancel(pendente)
        except Exception:
            pass

    self._redesenho_imagem_tela_cheia_pendente = None
    self.canvas_imagem_tela_cheia = None
    self.imagem_tela_cheia_tk = None
    self.chave_imagem_tela_cheia = None
    self.janela_imagem_tela_cheia = None

    if janela is not None:
        try:
            janela.destroy()
        except Exception:
            pass


def abrir_imagem_tela_cheia(
    self,
    chave: str,
    titulo: str | None = None,
) -> None:
    if chave not in VISUALIZACOES_TELA_CHEIA:
        return
    if _imagem_fonte(self, chave) is None:
        return

    if _janela_valida(self):
        fechar_imagem_tela_cheia(self)

    titulo = titulo or VISUALIZACOES_TELA_CHEIA[chave]
    janela = tk.Toplevel(self.root)
    janela.title(f"{titulo} - ODIN")
    janela.configure(bg=self.COR_FUNDO_APP)
    janela.protocol("WM_DELETE_WINDOW", self.fechar_imagem_tela_cheia)
    janela.bind("<Escape>", self.fechar_imagem_tela_cheia)

    cabecalho = tk.Frame(
        janela,
        bg=self.COR_TOPO,
        bd=0,
        highlightthickness=0,
    )
    cabecalho.pack(fill=tk.X, side=tk.TOP)

    tk.Label(
        cabecalho,
        text=titulo,
        bg=self.COR_TOPO,
        fg=self.COR_TEXTO,
        font=("Segoe UI", 14, "bold"),
        anchor="w",
    ).pack(side=tk.LEFT, padx=(20, 12), pady=12)

    tk.Label(
        cabecalho,
        text="Esc para fechar",
        bg=self.COR_TOPO,
        fg=self.COR_TEXTO_3,
        font=("Segoe UI", 9),
    ).pack(side=tk.RIGHT, padx=(10, 14), pady=12)

    tk.Button(
        cabecalho,
        text="✕",
        command=self.fechar_imagem_tela_cheia,
        bg=self.COR_CARD_2,
        fg=self.COR_TEXTO,
        activebackground=self.COR_VERMELHO,
        activeforeground="#FFFFFF",
        relief=tk.FLAT,
        bd=0,
        highlightthickness=0,
        font=("Segoe UI", 12, "bold"),
        padx=16,
        pady=7,
        cursor="hand2",
    ).pack(side=tk.RIGHT, padx=(0, 12), pady=7)

    canvas = tk.Canvas(
        janela,
        bg="#020617",
        bd=0,
        highlightthickness=0,
        relief=tk.FLAT,
        cursor="arrow",
    )
    canvas.pack(fill=tk.BOTH, expand=True)

    self.janela_imagem_tela_cheia = janela
    self.canvas_imagem_tela_cheia = canvas
    self.chave_imagem_tela_cheia = chave
    self.imagem_tela_cheia_tk = None
    self._redesenho_imagem_tela_cheia_pendente = None

    canvas.bind("<Configure>", lambda _e: _agendar_redesenho(self), add="+")

    try:
        janela.attributes("-fullscreen", True)
    except Exception:
        try:
            janela.state("zoomed")
        except Exception:
            largura = max(800, int(janela.winfo_screenwidth()))
            altura = max(600, int(janela.winfo_screenheight()))
            janela.geometry(f"{largura}x{altura}+0+0")

    try:
        janela.lift()
        janela.focus_force()
    except Exception:
        pass

    _agendar_redesenho(self)


def evento_abrir_imagem_principal_tela_cheia(self, _evento=None) -> None:
    # Durante o modo Selecionar LEDs, o clique pertence exclusivamente ao
    # editor de ROIs e nunca deve abrir o visualizador.
    if bool(getattr(self, "selecao_led_ativa", False)):
        return
    if bool(getattr(self, "selecao_manual_camera_visivel", False)):
        return
    abrir_imagem_tela_cheia(self, "principal")


def configurar_abertura_imagens_tela_cheia(self) -> None:
    """Vincula os cinco painéis visuais ao visualizador fullscreen."""
    if getattr(self, "_imagens_tela_cheia_bindings_instalados", False):
        return

    # ButtonRelease preserva o Button-1 original do canvas principal, usado
    # pelo editor de LEDs. A abertura é bloqueada quando esse modo está ativo.
    self.canvas.bind(
        "<ButtonRelease-1>",
        self.evento_abrir_imagem_principal_tela_cheia,
        add="+",
    )

    pares = (
        (self.canvas_mapa_intensidade, "heatmap"),
        (self.canvas_imagem_teste, "canal_v"),
        (self.canvas_mascara, "mascara"),
        (self.canvas_roi_debug, "roi_debug"),
    )
    for canvas, chave in pares:
        canvas.configure(cursor="hand2")
        canvas.bind(
            "<Button-1>",
            lambda _e, c=chave: self.abrir_imagem_tela_cheia(c),
            add="+",
        )

    self._imagens_tela_cheia_bindings_instalados = True
