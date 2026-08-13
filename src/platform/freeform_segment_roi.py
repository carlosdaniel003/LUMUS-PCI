from __future__ import annotations

import math
import tkinter as tk
from typing import Iterable

from src.core.roi_geometry import (
    TIPO_ROI_SEGMENTO,
    dimensoes_segmento,
    normalizar_angulo_segmento,
    normalizar_tipo_roi,
    roi_dentro_imagem,
)
from src.models.led_selection import LedSelection


ROI_FREEFORM_TAG = "roi_freeform_segment_draft"
FECHAR_SEGMENTO_DISTANCIA_CANVAS_PX = 18
PONTO_MINIMO_DISTANCIA_CANVAS_PX = 4
AREA_MINIMA_SEGMENTO_LIVRE = 4.0


def copiar_led_com_segmento_livre(led: LedSelection) -> LedSelection:
    return LedSelection(
        id=str(led.id),
        centro_x=int(led.centro_x),
        centro_y=int(led.centro_y),
        raio=int(led.raio),
        tipo_roi=getattr(led, "tipo_roi", "circulo"),
        largura=getattr(led, "largura", None),
        altura=getattr(led, "altura", None),
        angulo=float(getattr(led, "angulo", 0.0) or 0.0),
        pontos_segmento_livre=(
            list(getattr(led, "pontos_segmento_livre", None) or ()) or None
        ),
    )


def _criar_rois_escaladas_com_segmento_livre(
    leds: Iterable[LedSelection],
    centro_grupo_x: float,
    centro_grupo_y: float,
    escala: float,
) -> list[LedSelection]:
    from src.core.roi_geometry import raio_compatibilidade_segmento

    resultado = []
    for origem in leds:
        led = copiar_led_com_segmento_livre(origem)
        led.centro_x = int(
            round(
                centro_grupo_x
                + (int(origem.centro_x) - centro_grupo_x) * escala
            )
        )
        led.centro_y = int(
            round(
                centro_grupo_y
                + (int(origem.centro_y) - centro_grupo_y) * escala
            )
        )

        if normalizar_tipo_roi(getattr(led, "tipo_roi", None)) == TIPO_ROI_SEGMENTO:
            pontos_livres = getattr(led, "pontos_segmento_livre", None)
            if pontos_livres:
                led = LedSelection(
                    id=led.id,
                    centro_x=led.centro_x,
                    centro_y=led.centro_y,
                    raio=led.raio,
                    tipo_roi=TIPO_ROI_SEGMENTO,
                    angulo=led.angulo,
                    pontos_segmento_livre=[
                        (float(x) * escala, float(y) * escala)
                        for x, y in pontos_livres
                    ],
                )
            else:
                led.largura = max(
                    8,
                    int(round(int(led.largura or 48) * escala)),
                )
                led.altura = max(
                    4,
                    int(round(int(led.altura or 14) * escala)),
                )
                led.raio = raio_compatibilidade_segmento(
                    led.largura,
                    led.altura,
                )
        else:
            led.raio = int(round(int(led.raio) * escala))
        resultado.append(led)
    return resultado


def instalar_suporte_segmento_livre_editor() -> None:
    """Mantém os vértices livres nas cópias/movimentos do editor existente."""
    import src.platform.area_roi_editor as area_roi_editor
    import src.platform.area_roi_editor_v4 as area_roi_editor_v4
    import src.platform.bulk_roi_editor as bulk_roi_editor
    import src.platform.rotated_roi_editor as rotated_roi_editor
    import src.platform.segment_display_roi_editor as segment_display_roi_editor

    bulk_roi_editor.copiar_led = copiar_led_com_segmento_livre
    bulk_roi_editor._criar_rois_escaladas = (
        _criar_rois_escaladas_com_segmento_livre
    )
    area_roi_editor.copiar_led = copiar_led_com_segmento_livre
    area_roi_editor_v4.copiar_led = copiar_led_com_segmento_livre
    rotated_roi_editor.copiar_led = copiar_led_com_segmento_livre
    segment_display_roi_editor.copiar_led = copiar_led_com_segmento_livre


def _area_poligono(pontos: list[tuple[float, float]]) -> float:
    area = 0.0
    for indice, (x1, y1) in enumerate(pontos):
        x2, y2 = pontos[(indice + 1) % len(pontos)]
        area += float(x1) * float(y2) - float(x2) * float(y1)
    return abs(area) / 2.0


def criar_segmento_livre_por_pontos(
    pontos: Iterable[tuple[float, float]],
    id_roi: str = "SEG_001",
) -> LedSelection:
    vertices = [(float(x), float(y)) for x, y in pontos]
    if len(vertices) < 3:
        raise ValueError("Um segmento por pontos precisa de pelo menos 3 vértices.")
    if _area_poligono(vertices) < AREA_MINIMA_SEGMENTO_LIVRE:
        raise ValueError("O contorno desenhado não possui área suficiente.")

    xs = [p[0] for p in vertices]
    ys = [p[1] for p in vertices]
    centro_x = int(round((min(xs) + max(xs)) / 2.0))
    centro_y = int(round((min(ys) + max(ys)) / 2.0))
    pontos_locais = [
        (float(x) - centro_x, float(y) - centro_y)
        for x, y in vertices
    ]

    return LedSelection(
        id=str(id_roi),
        centro_x=centro_x,
        centro_y=centro_y,
        raio=2,
        tipo_roi=TIPO_ROI_SEGMENTO,
        angulo=0.0,
        pontos_segmento_livre=pontos_locais,
    )


instalar_suporte_segmento_livre_editor()


class FreeformSegmentDrawingMixin:
    """Adiciona criação de segmento poligonal por cliques sucessivos."""

    def __init__(self, *args, **kwargs) -> None:
        self._segmento_livre_ativo = False
        self._segmento_livre_pontos: list[tuple[int, int]] = []
        self._segmento_livre_mouse: tuple[int, int] | None = None
        self._botao_tipo_roi_segmento_livre = None
        super().__init__(*args, **kwargs)

    def _modo_segmento_livre_ativo(self) -> bool:
        return bool(
            self._segmento_livre_ativo
            and normalizar_tipo_roi(getattr(self, "tipo_roi_edicao", None))
            == TIPO_ROI_SEGMENTO
        )

    def _cancelar_rascunho_segmento_livre(
        self,
        mensagem: bool = False,
    ) -> None:
        tinha_pontos = bool(self._segmento_livre_pontos)
        self._segmento_livre_pontos = []
        self._segmento_livre_mouse = None
        canvas = getattr(getattr(self, "view", None), "canvas", None)
        if canvas is not None:
            try:
                canvas.delete(ROI_FREEFORM_TAG)
            except Exception:
                pass
        if mensagem and tinha_pontos:
            self.view.atualizar_status(
                "Desenho do segmento por pontos cancelado."
            )

    def _selecionar_tipo_roi_toolbar(self, tipo: str) -> None:
        self._cancelar_rascunho_segmento_livre(mensagem=False)
        self._segmento_livre_ativo = False
        super()._selecionar_tipo_roi_toolbar(tipo)
        self._atualizar_botoes_tipo_roi()

    def _selecionar_segmento_livre_toolbar(self) -> None:
        self._cancelar_rascunho_segmento_livre(mensagem=False)
        self._segmento_livre_ativo = True
        super()._selecionar_tipo_roi_toolbar(TIPO_ROI_SEGMENTO)
        self._atualizar_botoes_tipo_roi()
        self.view.atualizar_status(
            "Segmento por pontos: clique no primeiro vértice e continue clicando "
            "para fixar cada linha. Clique próximo do primeiro ponto para fechar."
        )
        canvas = getattr(self, "_selecao_tela_cheia_canvas", None)
        if canvas is not None:
            try:
                canvas.focus_set()
            except Exception:
                pass

    def _atualizar_botoes_tipo_roi(self) -> None:
        super()._atualizar_botoes_tipo_roi()
        livre = self._modo_segmento_livre_ativo()

        botao_normal = getattr(self, "_botao_tipo_roi_segmento", None)
        if botao_normal is not None and livre:
            try:
                botao_normal.configure(
                    bg="#182231",
                    fg="#DCE5EF",
                    activebackground="#243246",
                    activeforeground="#FFFFFF",
                )
            except Exception:
                pass

        botao_livre = self._botao_tipo_roi_segmento_livre
        if botao_livre is not None:
            try:
                botao_livre.configure(
                    bg="#D6A900" if livre else "#182231",
                    fg="#111318" if livre else "#DCE5EF",
                    activebackground="#F5C518" if livre else "#243246",
                    activeforeground="#111318" if livre else "#FFFFFF",
                )
            except Exception:
                pass

    def _criar_interface_selecao_tela_cheia(self):
        janela, canvas = super()._criar_interface_selecao_tela_cheia()
        botao_segmento = getattr(self, "_botao_tipo_roi_segmento", None)
        parent = getattr(botao_segmento, "master", None)
        if parent is not None:
            self._botao_tipo_roi_segmento_livre = tk.Button(
                parent,
                text="✎ Segmento por pontos",
                command=self._selecionar_segmento_livre_toolbar,
                font=("DejaVu Sans", 8, "bold"),
                relief="flat",
                bd=0,
                padx=10,
                pady=5,
                cursor="hand2",
            )
            self._botao_tipo_roi_segmento_livre.pack(
                side=tk.LEFT,
                padx=(4, 0),
            )
        self._atualizar_botoes_tipo_roi()
        return janela, canvas

    def _ponto_canvas_segmento_livre(
        self,
        ponto: tuple[float, float],
    ) -> tuple[float, float]:
        converter = getattr(self, "_ponto_canvas_rotacionado", None)
        if callable(converter):
            return converter(float(ponto[0]), float(ponto[1]))
        escala = max(
            1e-9,
            float(getattr(self.view, "escala_exibicao", 1.0) or 1.0),
        )
        return (
            float(getattr(self.view, "deslocamento_imagem_x", 0.0))
            + float(ponto[0]) * escala,
            float(getattr(self.view, "deslocamento_imagem_y", 0.0))
            + float(ponto[1]) * escala,
        )

    def _distancia_canvas_para_ponto(
        self,
        evento,
        ponto: tuple[float, float],
    ) -> float:
        px, py = self._ponto_canvas_segmento_livre(ponto)
        return math.hypot(
            float(getattr(evento, "x", 0.0)) - px,
            float(getattr(evento, "y", 0.0)) - py,
        )

    def _desenhar_rascunho_segmento_livre(self) -> None:
        canvas = getattr(getattr(self, "view", None), "canvas", None)
        if canvas is None:
            return
        try:
            canvas.delete(ROI_FREEFORM_TAG)
        except Exception:
            return

        pontos = list(self._segmento_livre_pontos)
        if not pontos:
            return

        pontos_canvas = [
            self._ponto_canvas_segmento_livre(ponto)
            for ponto in pontos
        ]
        if len(pontos_canvas) >= 2:
            achatados = [valor for ponto in pontos_canvas for valor in ponto]
            canvas.create_line(
                *achatados,
                fill="#38BDF8",
                width=3,
                tags=ROI_FREEFORM_TAG,
            )

        mouse = self._segmento_livre_mouse
        if mouse is not None:
            x1, y1 = pontos_canvas[-1]
            x2, y2 = self._ponto_canvas_segmento_livre(mouse)
            canvas.create_line(
                x1,
                y1,
                x2,
                y2,
                fill="#7DD3FC",
                width=2,
                dash=(6, 4),
                tags=ROI_FREEFORM_TAG,
            )

        for indice, (x, y) in enumerate(pontos_canvas):
            raio = 7 if indice == 0 else 4
            cor = "#FBBF24" if indice == 0 else "#38BDF8"
            canvas.create_oval(
                x - raio,
                y - raio,
                x + raio,
                y + raio,
                fill=cor,
                outline="#0F172A",
                width=1,
                tags=ROI_FREEFORM_TAG,
            )

        if len(pontos) >= 3 and mouse is not None:
            primeiro_x, primeiro_y = pontos_canvas[0]
            mouse_x, mouse_y = self._ponto_canvas_segmento_livre(mouse)
            if math.hypot(mouse_x - primeiro_x, mouse_y - primeiro_y) <= FECHAR_SEGMENTO_DISTANCIA_CANVAS_PX:
                canvas.create_oval(
                    primeiro_x - 11,
                    primeiro_y - 11,
                    primeiro_x + 11,
                    primeiro_y + 11,
                    outline="#22C55E",
                    width=3,
                    tags=ROI_FREEFORM_TAG,
                )

    def _desenhar_overlay_editor_roi(self) -> None:
        super()._desenhar_overlay_editor_roi()
        if self._modo_segmento_livre_ativo():
            self._desenhar_rascunho_segmento_livre()

    def _adicionar_ponto_segmento_livre(
        self,
        evento,
        imagem_x: int,
        imagem_y: int,
    ) -> str:
        ponto = (int(imagem_x), int(imagem_y))
        if not self._segmento_livre_pontos:
            self._segmento_livre_pontos = [ponto]
            self._segmento_livre_mouse = ponto
            self._desenhar_rascunho_segmento_livre()
            self.view.atualizar_status(
                "Primeiro ponto fixado. Mova o mouse e clique para criar a próxima linha; "
                "feche clicando novamente perto do ponto amarelo."
            )
            return "break"

        primeiro = self._segmento_livre_pontos[0]
        if self._distancia_canvas_para_ponto(evento, primeiro) <= FECHAR_SEGMENTO_DISTANCIA_CANVAS_PX:
            if len(self._segmento_livre_pontos) < 3:
                self.view.atualizar_status(
                    "O segmento por pontos precisa de pelo menos 3 vértices antes de fechar."
                )
                return "break"
            self._finalizar_segmento_livre()
            return "break"

        ultimo = self._segmento_livre_pontos[-1]
        if self._distancia_canvas_para_ponto(evento, ultimo) < PONTO_MINIMO_DISTANCIA_CANVAS_PX:
            return "break"

        self._segmento_livre_pontos.append(ponto)
        self._segmento_livre_mouse = ponto
        self._desenhar_rascunho_segmento_livre()
        self.view.atualizar_status(
            f"Ponto {len(self._segmento_livre_pontos)} fixado. Continue desenhando ou "
            "clique perto do ponto amarelo para fechar o segmento."
        )
        return "break"

    def _finalizar_segmento_livre(self) -> None:
        pontos = list(self._segmento_livre_pontos)
        try:
            candidato = criar_segmento_livre_por_pontos(
                pontos,
                self._proximo_id_segmento(),
            )
        except ValueError as exc:
            self.view.atualizar_status(f"Segmento não criado: {exc}")
            return

        largura = int(getattr(self, "largura_original", 0) or 0)
        altura = int(getattr(self, "altura_original", 0) or 0)
        if not roi_dentro_imagem(candidato, largura, altura):
            self.view.atualizar_status(
                "Segmento não criado: algum ponto ultrapassa os limites da imagem."
            )
            return

        novos = [
            copiar_led_com_segmento_livre(item)
            for item in self._leds_editaveis()
        ]
        novos.append(candidato)
        self._substituir_leds_editaveis(novos)
        self._cancelar_rascunho_segmento_livre(mensagem=False)
        self._selecionar_ids([candidato.id], mensagem=False)
        self._atualizar_pos_edicao_roi()
        self.view.desenhar_canvas(
            self.leds_selecionados,
            self.resultados_led_atual,
        )
        self.view.atualizar_status(
            f"{candidato.id} criado por {len(pontos)} pontos. O contorno fechado "
            "é a ROI real do segmento e será salvo com o projeto."
        )

    def evento_clique_esquerdo(self, evento) -> str | None:
        if not self._modo_edicao_roi_ativo() or not self._modo_segmento_livre_ativo():
            return super().evento_clique_esquerdo(evento)

        estado = int(getattr(evento, "state", 0) or 0)
        if estado & 0x0001 and not self._segmento_livre_pontos:
            return super().evento_clique_esquerdo(evento)

        coordenadas = self.view.converter_canvas_para_imagem_original(
            evento.x,
            evento.y,
        )
        if coordenadas is None:
            return "break"
        imagem_x, imagem_y = coordenadas

        if not self._segmento_livre_pontos:
            atingido = getattr(self, "_led_atingido", lambda *_: None)(
                imagem_x,
                imagem_y,
            )
            if atingido is not None:
                return super().evento_clique_esquerdo(evento)

        return self._adicionar_ponto_segmento_livre(
            evento,
            imagem_x,
            imagem_y,
        )

    def _evento_motion_selecao(self, evento) -> str | None:
        retorno = super()._evento_motion_selecao(evento)
        if (
            self._modo_segmento_livre_ativo()
            and self._segmento_livre_pontos
            and not bool(getattr(self, "_selecao_pan_ativo", False))
        ):
            coordenadas = self.view.converter_canvas_para_imagem_original(
                evento.x,
                evento.y,
            )
            if coordenadas is not None:
                self._segmento_livre_mouse = (
                    int(coordenadas[0]),
                    int(coordenadas[1]),
                )
                self._desenhar_rascunho_segmento_livre()
        return retorno

    def _evento_arrastar_roi(self, evento) -> str | None:
        if self._modo_segmento_livre_ativo() and self._segmento_livre_pontos:
            coordenadas = self.view.converter_canvas_para_imagem_original(
                evento.x,
                evento.y,
            )
            if coordenadas is not None:
                self._segmento_livre_mouse = (
                    int(coordenadas[0]),
                    int(coordenadas[1]),
                )
                self._desenhar_rascunho_segmento_livre()
                self._atualizar_lupa_dinamica(evento)
            return "break"
        return super()._evento_arrastar_roi(evento)

    def _evento_soltar_roi(self, evento) -> str | None:
        if self._modo_segmento_livre_ativo() and self._segmento_livre_pontos:
            return "break"
        return super()._evento_soltar_roi(evento)

    def _evento_cancelar_selecao_roi(self, evento=None) -> str | None:
        if self._segmento_livre_pontos:
            self._cancelar_rascunho_segmento_livre(mensagem=True)
            return "break"
        return super()._evento_cancelar_selecao_roi(evento)

    @staticmethod
    def _imagem_para_local_segmento(
        led: LedSelection,
        imagem_x: float,
        imagem_y: float,
    ) -> tuple[float, float]:
        dx = float(imagem_x) - float(led.centro_x)
        dy = float(imagem_y) - float(led.centro_y)
        angulo = math.radians(-float(led.angulo))
        cos_a = math.cos(angulo)
        sin_a = math.sin(angulo)
        return dx * cos_a - dy * sin_a, dx * sin_a + dy * cos_a

    def _transformar_handle(self, imagem_x: int, imagem_y: int):
        origem = list(getattr(self, "_area_roi_snapshot_selected", []) or [])
        if len(origem) == 1:
            led = origem[0]
            pontos = getattr(led, "pontos_segmento_livre", None)
            if pontos:
                handle = str(getattr(self, "_area_roi_handle", "") or "")
                if handle == "rotate":
                    candidato = copiar_led_com_segmento_livre(led)
                    dx = float(imagem_x) - candidato.centro_x
                    dy = float(imagem_y) - candidato.centro_y
                    candidato.angulo = normalizar_angulo_segmento(
                        math.degrees(math.atan2(dy, dx)) + 90.0
                    )
                else:
                    local_x, local_y = self._imagem_para_local_segmento(
                        led,
                        imagem_x,
                        imagem_y,
                    )
                    largura_antiga, altura_antiga = dimensoes_segmento(led)
                    largura_nova = float(largura_antiga)
                    altura_nova = float(altura_antiga)
                    if handle in {"e", "w", "ne", "nw", "se", "sw"}:
                        largura_nova = max(1.0, abs(local_x) * 2.0)
                    if handle in {"n", "s", "ne", "nw", "se", "sw"}:
                        altura_nova = max(1.0, abs(local_y) * 2.0)
                    escala_x = largura_nova / max(1.0, float(largura_antiga))
                    escala_y = altura_nova / max(1.0, float(altura_antiga))
                    candidato = LedSelection(
                        id=led.id,
                        centro_x=led.centro_x,
                        centro_y=led.centro_y,
                        raio=led.raio,
                        tipo_roi=TIPO_ROI_SEGMENTO,
                        angulo=led.angulo,
                        pontos_segmento_livre=[
                            (float(x) * escala_x, float(y) * escala_y)
                            for x, y in pontos
                        ],
                    )

                if roi_dentro_imagem(
                    candidato,
                    int(getattr(self, "largura_original", 0) or 0),
                    int(getattr(self, "altura_original", 0) or 0),
                ):
                    return [candidato]
                return [copiar_led_com_segmento_livre(led)]

        return super()._transformar_handle(imagem_x, imagem_y)

    def _confirmar_selecao_tela_cheia(self) -> None:
        self._cancelar_rascunho_segmento_livre(mensagem=False)
        super()._confirmar_selecao_tela_cheia()

    def _fechar_interface_selecao_tela_cheia(self) -> None:
        self._cancelar_rascunho_segmento_livre(mensagem=False)
        super()._fechar_interface_selecao_tela_cheia()
        self._botao_tipo_roi_segmento_livre = None
