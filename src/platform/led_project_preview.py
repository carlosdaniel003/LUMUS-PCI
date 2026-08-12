from __future__ import annotations

import tkinter as tk

from src.core.roi_geometry import (
    TIPO_ROI_SEGMENTO,
    bbox_roi,
    normalizar_tipo_roi,
    pontos_segmento,
)


PREVIEW_LARGURA = 220
PREVIEW_ALTURA = 150
PREVIEW_BASE_LARGURA = 1920
PREVIEW_BASE_ALTURA = 1080
PREVIEW_MARGEM = 10


def calcular_transformacao_preview(
    leds,
    largura_canvas: int = PREVIEW_LARGURA,
    altura_canvas: int = PREVIEW_ALTURA,
    largura_base: int = PREVIEW_BASE_LARGURA,
    altura_base: int = PREVIEW_BASE_ALTURA,
) -> tuple[float, float, float, int, int]:
    """Calcula escala letterbox mantendo a posição absoluta das ROIs."""
    largura_base = max(1, int(largura_base or PREVIEW_BASE_LARGURA))
    altura_base = max(1, int(altura_base or PREVIEW_BASE_ALTURA))

    for led in leds or ():
        try:
            _x1, _y1, x2, y2 = bbox_roi(led)
        except Exception:
            continue
        largura_base = max(largura_base, int(x2) + PREVIEW_MARGEM)
        altura_base = max(altura_base, int(y2) + PREVIEW_MARGEM)

    largura_util = max(1, int(largura_canvas) - PREVIEW_MARGEM * 2)
    altura_util = max(1, int(altura_canvas) - PREVIEW_MARGEM * 2)
    escala = min(
        largura_util / float(largura_base),
        altura_util / float(altura_base),
    )
    largura_desenho = float(largura_base) * escala
    altura_desenho = float(altura_base) * escala
    offset_x = (float(largura_canvas) - largura_desenho) / 2.0
    offset_y = (float(altura_canvas) - altura_desenho) / 2.0
    return escala, offset_x, offset_y, largura_base, altura_base


def _projetar_ponto(
    x: float,
    y: float,
    escala: float,
    offset_x: float,
    offset_y: float,
) -> tuple[float, float]:
    return (
        offset_x + float(x) * escala,
        offset_y + float(y) * escala,
    )


class LedProjectPreviewMixin:
    """Acrescenta preview sem substituir o gerenciador existente de projetos."""

    def _selecionar_projeto_led_existente(self, projetos: list[str]) -> str | None:
        token = object()
        self._led_project_preview_token = token
        self.root.after(
            0,
            lambda: self._instalar_preview_gerenciador_leds(token, tentativas=0),
        )
        try:
            return super()._selecionar_projeto_led_existente(projetos)
        finally:
            if getattr(self, "_led_project_preview_token", None) is token:
                self._led_project_preview_token = None

    def _instalar_preview_gerenciador_leds(
        self,
        token,
        tentativas: int = 0,
    ) -> None:
        if getattr(self, "_led_project_preview_token", None) is not token:
            return

        janela = self._encontrar_janela_gerenciador_leds()
        if janela is None:
            if tentativas < 20:
                self.root.after(
                    20,
                    lambda: self._instalar_preview_gerenciador_leds(
                        token,
                        tentativas=tentativas + 1,
                    ),
                )
            return

        lista = self._encontrar_listbox(janela)
        if lista is None:
            return

        frame_lista = lista.master
        frame_conteudo = getattr(frame_lista, "master", None)
        if frame_conteudo is None:
            return

        if getattr(janela, "_odin_preview_projeto_instalado", False):
            return
        janela._odin_preview_projeto_instalado = True

        self._ampliar_janela_para_preview(janela)

        frame_acoes = None
        for filho in frame_conteudo.winfo_children():
            if filho is frame_lista:
                continue
            if isinstance(filho, tk.Frame):
                frame_acoes = filho
                break

        painel = tk.Frame(
            frame_conteudo,
            bg="#0B1728",
            width=244,
            highlightthickness=1,
            highlightbackground="#1E293B",
        )
        painel.pack_propagate(False)
        pack_kwargs = {
            "side": tk.RIGHT,
            "fill": tk.Y,
            "padx": (12, 0),
        }
        if frame_acoes is not None:
            pack_kwargs["before"] = frame_acoes
        painel.pack(**pack_kwargs)

        tk.Label(
            painel,
            text="PREVIEW DO PROJETO",
            font=("Segoe UI", 9, "bold"),
            fg="#F9FAFB",
            bg="#0B1728",
            anchor="w",
        ).pack(fill=tk.X, padx=10, pady=(10, 3))

        label_nome = tk.Label(
            painel,
            text="",
            font=("Segoe UI", 9, "bold"),
            fg="#FACC15",
            bg="#0B1728",
            anchor="w",
        )
        label_nome.pack(fill=tk.X, padx=10)

        label_qtd = tk.Label(
            painel,
            text="",
            font=("Segoe UI", 8),
            fg="#94A3B8",
            bg="#0B1728",
            anchor="w",
        )
        label_qtd.pack(fill=tk.X, padx=10, pady=(1, 6))

        canvas = tk.Canvas(
            painel,
            width=PREVIEW_LARGURA,
            height=PREVIEW_ALTURA,
            bg="#020617",
            bd=0,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#253247",
        )
        canvas.pack(padx=10, pady=(0, 6))

        tk.Label(
            painel,
            text="Amarelo: ROIs salvas",
            font=("Segoe UI", 7),
            fg="#64748B",
            bg="#0B1728",
            anchor="w",
        ).pack(fill=tk.X, padx=10, pady=(0, 8))

        estado = {"nome": None, "quantidade": None}

        def atualizar_preview(_evento=None) -> None:
            try:
                nome = self._nome_projeto_da_selecao(lista)
                if nome is None:
                    self._desenhar_preview_projeto(
                        canvas,
                        label_nome,
                        label_qtd,
                        None,
                        [],
                    )
                    estado["nome"] = None
                    estado["quantidade"] = 0
                    return

                leds = self.config_repository.carregar_leds_fixos(projeto=nome)
                quantidade = len(leds)
                if estado["nome"] == nome and estado["quantidade"] == quantidade:
                    return

                self._desenhar_preview_projeto(
                    canvas,
                    label_nome,
                    label_qtd,
                    nome,
                    leds,
                )
                estado["nome"] = nome
                estado["quantidade"] = quantidade
            except tk.TclError:
                return

        def acompanhar_selecao() -> None:
            if getattr(self, "_led_project_preview_token", None) is not token:
                return
            try:
                if not janela.winfo_exists():
                    return
            except tk.TclError:
                return
            atualizar_preview()
            janela.after(120, acompanhar_selecao)

        lista.bind("<<ListboxSelect>>", atualizar_preview, add="+")
        janela.after(20, atualizar_preview)
        janela.after(120, acompanhar_selecao)

    def _encontrar_janela_gerenciador_leds(self):
        for filho in self.root.winfo_children():
            if not isinstance(filho, tk.Toplevel):
                continue
            try:
                if filho.title() == "Gerenciar configurações de LEDs":
                    return filho
            except tk.TclError:
                continue
        return None

    @staticmethod
    def _encontrar_listbox(widget):
        try:
            filhos = widget.winfo_children()
        except tk.TclError:
            return None
        for filho in filhos:
            if isinstance(filho, tk.Listbox):
                return filho
            encontrado = LedProjectPreviewMixin._encontrar_listbox(filho)
            if encontrado is not None:
                return encontrado
        return None

    def _ampliar_janela_para_preview(self, janela) -> None:
        largura = 925
        altura = 500
        try:
            pos_x = self.root.winfo_rootx() + max(
                0,
                (self.root.winfo_width() - largura) // 2,
            )
            pos_y = self.root.winfo_rooty() + max(
                0,
                (self.root.winfo_height() - altura) // 2,
            )
            janela.geometry(f"{largura}x{altura}+{pos_x}+{pos_y}")
        except tk.TclError:
            pass

    def _nome_projeto_da_selecao(self, lista) -> str | None:
        try:
            selecao = lista.curselection()
        except tk.TclError:
            return None
        if not selecao:
            return None

        nomes = self.config_repository.listar_projetos_led()
        indice = int(selecao[0])
        if indice < 0 or indice >= len(nomes):
            return None
        return str(nomes[indice])

    def _dimensoes_base_preview(self, leds) -> tuple[int, int]:
        for imagem in (
            getattr(self, "camera_frame_atual", None),
            getattr(self, "imagem_original", None),
        ):
            shape = getattr(imagem, "shape", None)
            if shape is not None and len(shape) >= 2:
                altura = int(shape[0])
                largura = int(shape[1])
                if largura > 0 and altura > 0:
                    return largura, altura
        return PREVIEW_BASE_LARGURA, PREVIEW_BASE_ALTURA

    def _desenhar_preview_projeto(
        self,
        canvas,
        label_nome,
        label_qtd,
        nome: str | None,
        leds,
    ) -> None:
        canvas.delete("all")
        if not nome:
            label_nome.configure(text="Nenhum projeto")
            label_qtd.configure(text="Selecione uma configuração")
            canvas.create_text(
                PREVIEW_LARGURA / 2,
                PREVIEW_ALTURA / 2,
                text="SEM PROJETO",
                fill="#64748B",
                font=("Segoe UI", 9, "bold"),
            )
            return

        leds = list(leds or ())
        label_nome.configure(text=str(nome))
        label_qtd.configure(
            text=f"{len(leds)} ROI{'s' if len(leds) != 1 else ''} salva{'s' if len(leds) != 1 else ''}"
        )

        if not leds:
            canvas.create_rectangle(
                8,
                8,
                PREVIEW_LARGURA - 8,
                PREVIEW_ALTURA - 8,
                outline="#253247",
                width=1,
            )
            canvas.create_text(
                PREVIEW_LARGURA / 2,
                PREVIEW_ALTURA / 2,
                text="SEM LEDs",
                fill="#64748B",
                font=("Segoe UI", 9, "bold"),
            )
            return

        largura_base, altura_base = self._dimensoes_base_preview(leds)
        escala, offset_x, offset_y, largura_base, altura_base = (
            calcular_transformacao_preview(
                leds,
                largura_canvas=PREVIEW_LARGURA,
                altura_canvas=PREVIEW_ALTURA,
                largura_base=largura_base,
                altura_base=altura_base,
            )
        )

        x1, y1 = _projetar_ponto(0, 0, escala, offset_x, offset_y)
        x2, y2 = _projetar_ponto(
            largura_base,
            altura_base,
            escala,
            offset_x,
            offset_y,
        )
        canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            outline="#334155",
            width=1,
        )

        for led in leds:
            tipo = normalizar_tipo_roi(getattr(led, "tipo_roi", None))
            if tipo == TIPO_ROI_SEGMENTO:
                coords = []
                for ponto in pontos_segmento(led):
                    px, py = _projetar_ponto(
                        float(ponto[0]),
                        float(ponto[1]),
                        escala,
                        offset_x,
                        offset_y,
                    )
                    coords.extend((px, py))
                if len(coords) >= 6:
                    canvas.create_polygon(
                        *coords,
                        fill="#3A3208",
                        outline="#FACC15",
                        width=1,
                    )
                continue

            centro_x, centro_y = _projetar_ponto(
                getattr(led, "centro_x", 0),
                getattr(led, "centro_y", 0),
                escala,
                offset_x,
                offset_y,
            )
            raio = max(2.0, float(getattr(led, "raio", 1) or 1) * escala)
            canvas.create_oval(
                centro_x - raio,
                centro_y - raio,
                centro_x + raio,
                centro_y + raio,
                fill="#3A3208",
                outline="#FACC15",
                width=1,
            )
