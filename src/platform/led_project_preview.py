from __future__ import annotations

import base64
import hashlib
import re
import tkinter as tk
from pathlib import Path

import cv2

from config import CONFIG_DIR
from src.core.roi_geometry import (
    TIPO_ROI_SEGMENTO,
    bbox_roi,
    normalizar_tipo_roi,
    pontos_segmento,
)
from src.platform.led_project_preview_store import (
    definir_preview_projeto_led,
    obter_preview_projeto_led,
)


PREVIEW_LARGURA = 220
PREVIEW_ALTURA = 150
PREVIEW_BASE_LARGURA = 1920
PREVIEW_BASE_ALTURA = 1080
PREVIEW_MARGEM = 10
PREVIEW_JPEG_QUALIDADE = 84
PREVIEW_DIR = CONFIG_DIR / "led_project_previews"


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


def _criar_photo_preview_real(imagem, largura: int, altura: int):
    if imagem is None or getattr(imagem, "size", 0) == 0:
        return None
    largura = max(1, int(largura))
    altura = max(1, int(altura))
    interpolacao = (
        cv2.INTER_AREA
        if largura < imagem.shape[1] or altura < imagem.shape[0]
        else cv2.INTER_LINEAR
    )
    reduzida = cv2.resize(
        imagem,
        (largura, altura),
        interpolation=interpolacao,
    )
    sucesso, buffer = cv2.imencode(".png", reduzida)
    if not sucesso:
        return None
    dados = base64.b64encode(buffer).decode("ascii")
    return tk.PhotoImage(data=dados)


def _slug_preview_projeto(nome: str) -> str:
    normalizado = str(nome or "").strip()
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", normalizado).strip("_").lower()
    slug = slug or "projeto"
    digest = hashlib.sha1(normalizado.encode("utf-8")).hexdigest()[:8]
    return f"{slug}_{digest}"


class LedProjectPreviewMixin:
    """Acrescenta preview real sem substituir o gerenciador de projetos."""

    def _salvar_leds_no_projeto(
        self,
        nome_projeto: str,
        parent=None,
        confirmar_substituicao: bool = True,
    ) -> bool:
        salvo = super()._salvar_leds_no_projeto(
            nome_projeto,
            parent=parent,
            confirmar_substituicao=confirmar_substituicao,
        )
        if salvo:
            self._anexar_snapshot_real_ao_projeto(nome_projeto)
            self._led_project_preview_revision = (
                int(getattr(self, "_led_project_preview_revision", 0)) + 1
            )
        return salvo

    def _fonte_snapshot_projeto(self):
        candidatos = []
        if getattr(self, "camera_ativa", False):
            candidatos.append(getattr(self, "camera_frame_atual", None))
        candidatos.extend(
            (
                getattr(self, "imagem_original", None),
                getattr(self, "camera_frame_atual", None),
            )
        )
        for imagem in candidatos:
            if imagem is None or getattr(imagem, "size", 0) == 0:
                continue
            try:
                return imagem.copy()
            except Exception:
                continue
        return None

    def _anexar_snapshot_real_ao_projeto(self, nome_projeto: str) -> bool:
        imagem = self._fonte_snapshot_projeto()
        if imagem is None:
            return False

        try:
            PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
            caminho = PREVIEW_DIR / f"{_slug_preview_projeto(nome_projeto)}.jpg"
            sucesso = cv2.imwrite(
                str(caminho),
                imagem,
                [cv2.IMWRITE_JPEG_QUALITY, PREVIEW_JPEG_QUALIDADE],
            )
            if not sucesso:
                return False
            return definir_preview_projeto_led(
                self.config_repository,
                nome_projeto,
                str(caminho),
            )
        except Exception:
            return False

    def _carregar_snapshot_real_projeto(self, nome_projeto: str):
        dados = obter_preview_projeto_led(
            self.config_repository,
            nome_projeto,
        )
        if not isinstance(dados, dict):
            return None, None

        caminho = str(dados.get("image_path") or "").strip()
        if not caminho:
            return None, None
        arquivo = Path(caminho)
        if not arquivo.exists() or not arquivo.is_file():
            return None, caminho

        imagem = cv2.imread(str(arquivo), cv2.IMREAD_COLOR)
        if imagem is None or getattr(imagem, "size", 0) == 0:
            return None, caminho
        return imagem, caminho

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

        label_legenda = tk.Label(
            painel,
            text="Imagem real • amarelo: ROIs salvas",
            font=("Segoe UI", 7),
            fg="#64748B",
            bg="#0B1728",
            anchor="w",
            justify=tk.LEFT,
        )
        label_legenda.pack(fill=tk.X, padx=10, pady=(0, 8))

        estado = {
            "nome": None,
            "quantidade": None,
            "revision": None,
        }

        def atualizar_preview(_evento=None) -> None:
            try:
                nome = self._nome_projeto_da_selecao(lista)
                revision = int(getattr(self, "_led_project_preview_revision", 0))
                if nome is None:
                    self._desenhar_preview_projeto(
                        canvas,
                        label_nome,
                        label_qtd,
                        label_legenda,
                        None,
                        [],
                    )
                    estado["nome"] = None
                    estado["quantidade"] = 0
                    estado["revision"] = revision
                    return

                leds = self.config_repository.carregar_leds_fixos(projeto=nome)
                quantidade = len(leds)
                if (
                    estado["nome"] == nome
                    and estado["quantidade"] == quantidade
                    and estado["revision"] == revision
                ):
                    return

                self._desenhar_preview_projeto(
                    canvas,
                    label_nome,
                    label_qtd,
                    label_legenda,
                    nome,
                    leds,
                )
                estado["nome"] = nome
                estado["quantidade"] = quantidade
                estado["revision"] = revision
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

    def _desenhar_preview_projeto(
        self,
        canvas,
        label_nome,
        label_qtd,
        label_legenda,
        nome: str | None,
        leds,
    ) -> None:
        canvas.delete("all")
        canvas._odin_photo_preview = None

        if not nome:
            label_nome.configure(text="Nenhum projeto")
            label_qtd.configure(text="Selecione uma configuração")
            label_legenda.configure(text="Imagem real • amarelo: ROIs salvas")
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

        imagem, caminho = self._carregar_snapshot_real_projeto(nome)
        if imagem is None:
            label_legenda.configure(
                text=(
                    "Imagem real ainda não anexada.\n"
                    "Salve os LEDs deste projeto para criar a preview."
                )
            )
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
                PREVIEW_ALTURA / 2 - 8,
                text="SEM IMAGEM REAL",
                fill="#94A3B8",
                font=("Segoe UI", 8, "bold"),
            )
            canvas.create_text(
                PREVIEW_LARGURA / 2,
                PREVIEW_ALTURA / 2 + 10,
                text="salve o projeto para anexar",
                fill="#64748B",
                font=("Segoe UI", 7),
            )
            return

        altura_imagem, largura_imagem = imagem.shape[:2]
        escala, offset_x, offset_y, _, _ = calcular_transformacao_preview(
            [],
            largura_canvas=PREVIEW_LARGURA,
            altura_canvas=PREVIEW_ALTURA,
            largura_base=largura_imagem,
            altura_base=altura_imagem,
        )
        largura_desenho = max(1, int(round(largura_imagem * escala)))
        altura_desenho = max(1, int(round(altura_imagem * escala)))
        foto = _criar_photo_preview_real(
            imagem,
            largura_desenho,
            altura_desenho,
        )
        if foto is not None:
            canvas._odin_photo_preview = foto
            canvas.create_image(
                offset_x,
                offset_y,
                image=foto,
                anchor="nw",
            )

        canvas.create_rectangle(
            offset_x,
            offset_y,
            offset_x + largura_desenho,
            offset_y + altura_desenho,
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
                        fill="",
                        outline="#FACC15",
                        width=2,
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
                fill="",
                outline="#FACC15",
                width=2,
            )

        label_legenda.configure(text="Imagem real salva • amarelo: ROIs salvas")
