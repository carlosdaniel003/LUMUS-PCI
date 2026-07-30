from __future__ import annotations

import math
import tkinter as tk
from typing import Iterable

from config import MAX_RADIUS_PX, MIN_RADIUS_PX
from src.models.led_selection import LedSelection
from src.platform.bulk_roi_editor import (
    ROI_EDITOR_TAG,
    BulkRoiEditorMixin,
    ajustar_raios_rois,
    copiar_led,
    mover_rois,
)


DRAG_THRESHOLD_CANVAS_PX = 5
HANDLE_SIZE_CANVAS_PX = 7
HANDLE_HIT_CANVAS_PX = 14
LUPA_TAMANHO_PX = 190


def selecionar_rois_por_area(
    leds: Iterable[LedSelection],
    inicio_x: int,
    inicio_y: int,
    fim_x: int,
    fim_y: int,
) -> list[LedSelection]:
    """Retorna somente as ROIs totalmente englobadas pelo seletor."""
    esquerda = min(int(inicio_x), int(fim_x))
    direita = max(int(inicio_x), int(fim_x))
    topo = min(int(inicio_y), int(fim_y))
    base = max(int(inicio_y), int(fim_y))

    return [
        copiar_led(led)
        for led in leds
        if (
            led.centro_x - led.raio >= esquerda
            and led.centro_x + led.raio <= direita
            and led.centro_y - led.raio >= topo
            and led.centro_y + led.raio <= base
        )
    ]


def _rois_validas(
    leds: Iterable[LedSelection],
    largura: int,
    altura: int,
) -> bool:
    if largura <= 0 or altura <= 0:
        return False
    for led in leds:
        if not MIN_RADIUS_PX <= int(led.raio) <= MAX_RADIUS_PX:
            return False
        if led.centro_x - led.raio < 0:
            return False
        if led.centro_y - led.raio < 0:
            return False
        if led.centro_x + led.raio >= largura:
            return False
        if led.centro_y + led.raio >= altura:
            return False
    return True


def _limitar_transformacao(
    origem: list[LedSelection],
    fator_desejado: float,
    criar_candidato,
    largura: int,
    altura: int,
) -> list[LedSelection]:
    fator = max(0.05, float(fator_desejado))
    candidato = criar_candidato(fator)
    if _rois_validas(candidato, largura, altura):
        return candidato
    if fator <= 1.0:
        return origem

    inferior = 1.0
    superior = fator
    melhor = origem
    for _ in range(28):
        meio = (inferior + superior) / 2.0
        tentativa = criar_candidato(meio)
        if _rois_validas(tentativa, largura, altura):
            melhor = tentativa
            inferior = meio
        else:
            superior = meio
    return melhor


def escalar_rois_por_ancora(
    leds: Iterable[LedSelection],
    ancora_x: float,
    ancora_y: float,
    fator_desejado: float,
    largura: int,
    altura: int,
) -> list[LedSelection]:
    """Aumenta/reduz posições e raios, mantendo o formato do conjunto."""
    origem = [copiar_led(led) for led in leds]
    if not origem:
        return origem

    fator_minimo = max(
        MIN_RADIUS_PX / max(1, int(led.raio))
        for led in origem
    )
    fator_maximo = min(
        MAX_RADIUS_PX / max(1, int(led.raio))
        for led in origem
    )
    fator = min(
        fator_maximo,
        max(fator_minimo, float(fator_desejado)),
    )

    def criar(valor: float) -> list[LedSelection]:
        return [
            LedSelection(
                id=led.id,
                centro_x=int(round(
                    ancora_x + (led.centro_x - ancora_x) * valor
                )),
                centro_y=int(round(
                    ancora_y + (led.centro_y - ancora_y) * valor
                )),
                raio=int(round(led.raio * valor)),
            )
            for led in origem
        ]

    return _limitar_transformacao(
        origem,
        fator,
        criar,
        largura,
        altura,
    )


def esticar_rois_em_eixo(
    leds: Iterable[LedSelection],
    eixo: str,
    ancora: float,
    fator_desejado: float,
    largura: int,
    altura: int,
) -> list[LedSelection]:
    """Estica o espaçamento horizontal ou vertical sem deformar os círculos."""
    origem = [copiar_led(led) for led in leds]
    if not origem:
        return origem
    eixo = str(eixo).lower()
    if eixo not in {"x", "y"}:
        raise ValueError("eixo deve ser 'x' ou 'y'")

    def criar(valor: float) -> list[LedSelection]:
        resultado = []
        for led in origem:
            centro_x = led.centro_x
            centro_y = led.centro_y
            if eixo == "x":
                centro_x = int(round(
                    ancora + (led.centro_x - ancora) * valor
                ))
            else:
                centro_y = int(round(
                    ancora + (led.centro_y - ancora) * valor
                ))
            resultado.append(
                LedSelection(
                    id=led.id,
                    centro_x=centro_x,
                    centro_y=centro_y,
                    raio=led.raio,
                )
            )
        return resultado

    return _limitar_transformacao(
        origem,
        max(0.05, float(fator_desejado)),
        criar,
        largura,
        altura,
    )


class AreaRoiEditorMixin(BulkRoiEditorMixin):
    """Seleção retangular e edição de subconjuntos de ROIs."""

    def __init__(self, *args, **kwargs) -> None:
        self._area_roi_ids: set[str] = set()
        self._area_roi_mode: str | None = None
        self._area_roi_handle: str | None = None
        self._area_roi_press_canvas: tuple[int, int] | None = None
        self._area_roi_press_image: tuple[int, int] | None = None
        self._area_roi_current_image: tuple[int, int] | None = None
        self._area_roi_snapshot_all: list[LedSelection] = []
        self._area_roi_snapshot_selected: list[LedSelection] = []
        self._area_roi_bbox_snapshot = None
        super().__init__(*args, **kwargs)

    def _evento_clique_original(self, evento):
        # Pula o comportamento coletivo antigo e chama o clique original do app.
        return super(BulkRoiEditorMixin, self).evento_clique_esquerdo(evento)

    def _leds_area_selecionados(self) -> list[LedSelection]:
        ids = set(self._area_roi_ids)
        return [
            copiar_led(led)
            for led in self._leds_editaveis()
            if str(led.id) in ids
        ]

    @staticmethod
    def _bbox_leds(leds: Iterable[LedSelection]):
        itens = list(leds)
        if not itens:
            return None
        return (
            min(led.centro_x - led.raio for led in itens),
            min(led.centro_y - led.raio for led in itens),
            max(led.centro_x + led.raio for led in itens),
            max(led.centro_y + led.raio for led in itens),
        )

    def _bbox_area_selecionada(self):
        return self._bbox_leds(self._leds_area_selecionados())

    def _mesclar_transformados(
        self,
        transformados: Iterable[LedSelection],
    ) -> list[LedSelection]:
        por_id = {
            str(led.id): copiar_led(led)
            for led in transformados
        }
        return [
            por_id.get(str(led.id), copiar_led(led))
            for led in self._area_roi_snapshot_all
        ]

    def _selecionar_ids(self, ids: Iterable[str], mensagem: bool = True) -> bool:
        existentes = {str(led.id) for led in self._leds_editaveis()}
        self._area_roi_ids = {
            str(item)
            for item in ids
            if str(item) in existentes
        }
        self._sincronizar_preview_area()
        self._desenhar_overlay_editor_roi()
        if mensagem and self._area_roi_ids:
            self.view.atualizar_status(
                f"{len(self._area_roi_ids)} ROI(s) selecionada(s). "
                "Arraste para mover; cantos aumentam/reduzem; laterais esticam; "
                "roda ajusta raios; Delete remove."
            )
        return bool(self._area_roi_ids)

    def _selecionar_todas_rois(self, mensagem: bool = True) -> bool:
        return self._selecionar_ids(
            (str(led.id) for led in self._leds_editaveis()),
            mensagem=mensagem,
        )

    def _resetar_editor_roi(self) -> None:
        self._area_roi_ids = set()
        self._area_roi_mode = None
        self._area_roi_handle = None
        self._area_roi_press_canvas = None
        self._area_roi_press_image = None
        self._area_roi_current_image = None
        self._area_roi_snapshot_all = []
        self._area_roi_snapshot_selected = []
        self._area_roi_bbox_snapshot = None
        view = getattr(self, "view", None)
        if view is not None:
            view._roi_editor_selected_ids = set()
            view._roi_editor_marquee_image = None
        super()._resetar_editor_roi()

    def _sincronizar_preview_area(self) -> None:
        view = getattr(self, "view", None)
        if view is None:
            return
        view._roi_editor_selected_ids = set(self._area_roi_ids)
        if (
            self._area_roi_mode == "marquee"
            and self._area_roi_press_image is not None
            and self._area_roi_current_image is not None
        ):
            x1, y1 = self._area_roi_press_image
            x2, y2 = self._area_roi_current_image
            view._roi_editor_marquee_image = (
                min(x1, x2),
                min(y1, y2),
                max(x1, x2),
                max(y1, y2),
            )
        else:
            view._roi_editor_marquee_image = None

    def _atualizar_lupa_dinamica(self, evento) -> None:
        view = getattr(self, "view", None)
        if view is None or not getattr(view, "selecao_led_ativa", False):
            return
        coordenadas = view.converter_canvas_para_imagem_original(
            evento.x,
            evento.y,
        )
        if coordenadas is None:
            return
        imagem_x, imagem_y = coordenadas
        view._lupa_ultimo_tempo_s = 0.0
        view._lupa_ultima_posicao_canvas = None
        view.desenhar_lupa_canvas(
            canvas_x=evento.x,
            canvas_y=evento.y,
            imagem_x=imagem_x,
            imagem_y=imagem_y,
        )
        self._desenhar_marquee_na_lupa(
            evento,
            imagem_x,
            imagem_y,
        )

    def _desenhar_marquee_na_lupa(
        self,
        evento,
        imagem_x: int,
        imagem_y: int,
    ) -> None:
        if (
            self._area_roi_mode != "marquee"
            or self._area_roi_press_image is None
            or self._area_roi_current_image is None
        ):
            return
        imagem = getattr(self.view, "imagem_canvas_original", None)
        if imagem is None or getattr(imagem, "size", 0) == 0:
            return
        altura, largura = imagem.shape[:2]
        raio = max(3, int(getattr(self.view, "raio_atual_px", 3)))
        margem = max(28, raio * 4)
        recorte_x1 = max(0, imagem_x - margem)
        recorte_y1 = max(0, imagem_y - margem)
        recorte_x2 = min(largura, imagem_x + margem)
        recorte_y2 = min(altura, imagem_y + margem)
        if recorte_x2 <= recorte_x1 or recorte_y2 <= recorte_y1:
            return

        sx1, sy1 = self._area_roi_press_image
        sx2, sy2 = self._area_roi_current_image
        esquerda = max(min(sx1, sx2), recorte_x1)
        direita = min(max(sx1, sx2), recorte_x2)
        topo = max(min(sy1, sy2), recorte_y1)
        base = min(max(sy1, sy2), recorte_y2)
        if direita <= esquerda or base <= topo:
            return

        escala_x = LUPA_TAMANHO_PX / max(1, recorte_x2 - recorte_x1)
        escala_y = LUPA_TAMANHO_PX / max(1, recorte_y2 - recorte_y1)
        largura_canvas, _ = self.view.obter_tamanho_canvas_principal()
        x_lupa = largura_canvas - LUPA_TAMANHO_PX - 18
        y_lupa = 42
        mouse_sobre_lupa = (
            evento.x >= x_lupa - 20
            and evento.x <= x_lupa + LUPA_TAMANHO_PX + 20
            and evento.y >= y_lupa - 40
            and evento.y <= y_lupa + LUPA_TAMANHO_PX + 50
        )
        if mouse_sobre_lupa:
            x_lupa = 18
        x_lupa = max(12, x_lupa)
        y_lupa = max(12, y_lupa)

        self.view.canvas.create_rectangle(
            x_lupa + (esquerda - recorte_x1) * escala_x,
            y_lupa + (topo - recorte_y1) * escala_y,
            x_lupa + (direita - recorte_x1) * escala_x,
            y_lupa + (base - recorte_y1) * escala_y,
            outline="#38BDF8",
            width=2,
            dash=(5, 3),
            tags=("lupa_canvas",),
        )
        self.view.canvas.tag_raise("lupa_canvas")

    def _handles_canvas(self) -> dict[str, tuple[float, float]]:
        bbox = self._bbox_area_selecionada()
        if bbox is None or len(self._area_roi_ids) < 2:
            return {}
        x1, y1, x2, y2 = bbox
        meio_x = (x1 + x2) / 2.0
        meio_y = (y1 + y2) / 2.0
        pontos = {
            "nw": (x1, y1),
            "n": (meio_x, y1),
            "ne": (x2, y1),
            "e": (x2, meio_y),
            "se": (x2, y2),
            "s": (meio_x, y2),
            "sw": (x1, y2),
            "w": (x1, meio_y),
        }
        return {
            nome: (
                self._coordenada_canvas(x, "x"),
                self._coordenada_canvas(y, "y"),
            )
            for nome, (x, y) in pontos.items()
        }

    def _handle_atingido_area(self, canvas_x: int, canvas_y: int) -> str | None:
        melhor = None
        menor = None
        for nome, (x, y) in self._handles_canvas().items():
            dx = float(canvas_x) - x
            dy = float(canvas_y) - y
            if abs(dx) > HANDLE_HIT_CANVAS_PX or abs(dy) > HANDLE_HIT_CANVAS_PX:
                continue
            distancia = dx * dx + dy * dy
            if menor is None or distancia < menor:
                melhor = nome
                menor = distancia
        return melhor

    def _ponto_dentro_selecao(self, imagem_x: int, imagem_y: int) -> bool:
        bbox = self._bbox_area_selecionada()
        if bbox is None:
            return False
        x1, y1, x2, y2 = bbox
        return x1 <= imagem_x <= x2 and y1 <= imagem_y <= y2

    def _desenhar_overlay_editor_roi(self) -> None:
        canvas = getattr(getattr(self, "view", None), "canvas", None)
        if canvas is None:
            return
        try:
            canvas.delete(ROI_EDITOR_TAG)
        except tk.TclError:
            return
        if not self._modo_edicao_roi_ativo():
            return

        self._sincronizar_preview_area()
        if (
            self._area_roi_mode == "marquee"
            and self._area_roi_press_image is not None
            and self._area_roi_current_image is not None
        ):
            x1, y1 = self._area_roi_press_image
            x2, y2 = self._area_roi_current_image
            canvas.create_rectangle(
                self._coordenada_canvas(x1, "x"),
                self._coordenada_canvas(y1, "y"),
                self._coordenada_canvas(x2, "x"),
                self._coordenada_canvas(y2, "y"),
                outline="#38BDF8",
                width=2,
                dash=(6, 3),
                tags=ROI_EDITOR_TAG,
            )
            for led in self._leds_area_selecionados():
                x = self._coordenada_canvas(led.centro_x, "x")
                y = self._coordenada_canvas(led.centro_y, "y")
                raio = max(4.0, led.raio * float(self.view.escala_exibicao))
                canvas.create_oval(
                    x - raio - 3,
                    y - raio - 3,
                    x + raio + 3,
                    y + raio + 3,
                    outline="#FBBF24",
                    width=3,
                    tags=ROI_EDITOR_TAG,
                )
            return

        selecionados = self._leds_area_selecionados()
        if not selecionados:
            return
        if len(selecionados) == 1:
            led = selecionados[0]
            x = self._coordenada_canvas(led.centro_x, "x")
            y = self._coordenada_canvas(led.centro_y, "y")
            raio = max(4.0, led.raio * float(self.view.escala_exibicao))
            canvas.create_oval(
                x - raio - 4,
                y - raio - 4,
                x + raio + 4,
                y + raio + 4,
                outline="#FBBF24",
                width=3,
                dash=(5, 3),
                tags=ROI_EDITOR_TAG,
            )
            return

        bbox = self._bbox_leds(selecionados)
        if bbox is None:
            return
        x1, y1, x2, y2 = bbox
        cx1 = self._coordenada_canvas(x1, "x")
        cy1 = self._coordenada_canvas(y1, "y")
        cx2 = self._coordenada_canvas(x2, "x")
        cy2 = self._coordenada_canvas(y2, "y")
        canvas.create_rectangle(
            cx1,
            cy1,
            cx2,
            cy2,
            outline="#FBBF24",
            width=2,
            dash=(7, 4),
            tags=ROI_EDITOR_TAG,
        )
        for nome, (x, y) in self._handles_canvas().items():
            cor = "#38BDF8" if nome in {"n", "e", "s", "w"} else "#FBBF24"
            canvas.create_rectangle(
                x - HANDLE_SIZE_CANVAS_PX,
                y - HANDLE_SIZE_CANVAS_PX,
                x + HANDLE_SIZE_CANVAS_PX,
                y + HANDLE_SIZE_CANVAS_PX,
                fill=cor,
                outline="#111827",
                width=1,
                tags=ROI_EDITOR_TAG,
            )
        canvas.create_text(
            (cx1 + cx2) / 2.0,
            max(12, cy1 - 14),
            text=f"ROIs SELECIONADAS ({len(selecionados)})",
            fill="#FBBF24",
            font=("DejaVu Sans", 8, "bold"),
            tags=ROI_EDITOR_TAG,
        )

    def _iniciar_transformacao(
        self,
        modo: str,
        imagem_x: int,
        imagem_y: int,
        handle: str | None = None,
    ) -> None:
        self._area_roi_mode = modo
        self._area_roi_handle = handle
        self._area_roi_press_image = (int(imagem_x), int(imagem_y))
        self._area_roi_snapshot_all = [
            copiar_led(led) for led in self._leds_editaveis()
        ]
        ids = set(self._area_roi_ids)
        self._area_roi_snapshot_selected = [
            copiar_led(led)
            for led in self._area_roi_snapshot_all
            if str(led.id) in ids
        ]
        self._area_roi_bbox_snapshot = self._bbox_leds(
            self._area_roi_snapshot_selected
        )

    def evento_clique_esquerdo(self, evento) -> str | None:
        if not self._modo_edicao_roi_ativo():
            self._resetar_editor_roi()
            return self._evento_clique_original(evento)
        try:
            self.view.canvas.focus_set()
        except tk.TclError:
            pass

        coordenadas = self.view.converter_canvas_para_imagem_original(
            evento.x,
            evento.y,
        )
        if coordenadas is None:
            return "break"
        imagem_x, imagem_y = coordenadas
        self._area_roi_press_canvas = (int(evento.x), int(evento.y))
        self._area_roi_press_image = (int(imagem_x), int(imagem_y))
        self._area_roi_current_image = (int(imagem_x), int(imagem_y))

        handle = self._handle_atingido_area(evento.x, evento.y)
        if handle is not None:
            modo = "scale" if handle in {"nw", "ne", "se", "sw"} else "stretch"
            self._iniciar_transformacao(
                modo,
                imagem_x,
                imagem_y,
                handle,
            )
            return "break"

        led = self._led_atingido(imagem_x, imagem_y)
        if led is not None:
            id_led = str(led.id)
            if id_led not in self._area_roi_ids:
                self._selecionar_ids([id_led], mensagem=False)
            self._iniciar_transformacao("move", imagem_x, imagem_y)
            return "break"

        if len(self._area_roi_ids) > 1 and self._ponto_dentro_selecao(
            imagem_x,
            imagem_y,
        ):
            self._iniciar_transformacao("move", imagem_x, imagem_y)
            return "break"

        self._area_roi_mode = "pending_marquee"
        self._area_roi_snapshot_all = [
            copiar_led(led) for led in self._leds_editaveis()
        ]
        return "break"

    def _atualizar_marquee(self, imagem_x: int, imagem_y: int) -> None:
        if self._area_roi_press_image is None:
            return
        self._area_roi_current_image = (int(imagem_x), int(imagem_y))
        x1, y1 = self._area_roi_press_image
        selecionados = selecionar_rois_por_area(
            self._leds_editaveis(),
            x1,
            y1,
            imagem_x,
            imagem_y,
        )
        self._area_roi_ids = {str(led.id) for led in selecionados}
        self._sincronizar_preview_area()
        self._desenhar_overlay_editor_roi()

    def _transformar_handle(self, imagem_x: int, imagem_y: int):
        origem = self._area_roi_snapshot_selected
        bbox = self._area_roi_bbox_snapshot
        handle = self._area_roi_handle
        if not origem or bbox is None or handle is None:
            return origem
        x1, y1, x2, y2 = bbox
        largura = int(getattr(self, "largura_original", 0) or 0)
        altura = int(getattr(self, "altura_original", 0) or 0)

        if self._area_roi_mode == "scale":
            opostos = {
                "nw": (x2, y2, x1, y1),
                "ne": (x1, y2, x2, y1),
                "se": (x1, y1, x2, y2),
                "sw": (x2, y1, x1, y2),
            }
            ancora_x, ancora_y, original_x, original_y = opostos[handle]
            fator_x = abs(float(imagem_x) - ancora_x) / max(1.0, abs(original_x - ancora_x))
            fator_y = abs(float(imagem_y) - ancora_y) / max(1.0, abs(original_y - ancora_y))
            return escalar_rois_por_ancora(
                origem,
                ancora_x,
                ancora_y,
                max(0.05, min(fator_x, fator_y)),
                largura,
                altura,
            )

        if handle == "e":
            eixo, ancora = "x", x1
            fator = (float(imagem_x) - ancora) / max(1.0, x2 - x1)
        elif handle == "w":
            eixo, ancora = "x", x2
            fator = (ancora - float(imagem_x)) / max(1.0, x2 - x1)
        elif handle == "s":
            eixo, ancora = "y", y1
            fator = (float(imagem_y) - ancora) / max(1.0, y2 - y1)
        else:
            eixo, ancora = "y", y2
            fator = (ancora - float(imagem_y)) / max(1.0, y2 - y1)
        return esticar_rois_em_eixo(
            origem,
            eixo,
            ancora,
            max(0.05, fator),
            largura,
            altura,
        )

    def _evento_arrastar_roi(self, evento) -> str | None:
        if not self._modo_edicao_roi_ativo():
            return None
        coordenadas = self.view.converter_canvas_para_imagem_original(
            evento.x,
            evento.y,
        )
        if coordenadas is None or self._area_roi_press_image is None:
            return "break"
        imagem_x, imagem_y = coordenadas

        if self._area_roi_mode == "pending_marquee":
            origem = self._area_roi_press_canvas
            if origem is None:
                return "break"
            if math.hypot(evento.x - origem[0], evento.y - origem[1]) < DRAG_THRESHOLD_CANVAS_PX:
                self._atualizar_lupa_dinamica(evento)
                return "break"
            self._area_roi_mode = "marquee"

        if self._area_roi_mode == "marquee":
            self._atualizar_marquee(imagem_x, imagem_y)
            self._atualizar_lupa_dinamica(evento)
            return "break"

        x0, y0 = self._area_roi_press_image
        if self._area_roi_mode == "move":
            transformados = mover_rois(
                self._area_roi_snapshot_selected,
                int(imagem_x) - int(x0),
                int(imagem_y) - int(y0),
                self.largura_original,
                self.altura_original,
            )
        elif self._area_roi_mode in {"scale", "stretch"}:
            transformados = self._transformar_handle(imagem_x, imagem_y)
        else:
            return None

        self._substituir_leds_editaveis(
            self._mesclar_transformados(transformados)
        )
        self.view.desenhar_canvas(
            self.leds_selecionados,
            self.resultados_led_atual,
        )
        self._atualizar_lupa_dinamica(evento)
        return "break"

    def _evento_soltar_roi(self, evento) -> str | None:
        if not self._modo_edicao_roi_ativo():
            return None
        modo = self._area_roi_mode

        if modo == "pending_marquee":
            self._area_roi_mode = None
            antes = {str(led.id) for led in self._leds_editaveis()}
            retorno = self._evento_clique_original(evento)
            depois = {str(led.id) for led in self._leds_editaveis()}
            novos = depois - antes
            self._selecionar_ids(novos, mensagem=False)
            self._atualizar_lupa_dinamica(evento)
            return retorno or "break"

        if modo == "marquee":
            self._area_roi_mode = None
            self._area_roi_current_image = None
            self._sincronizar_preview_area()
            self.view.desenhar_canvas(
                self.leds_selecionados,
                self.resultados_led_atual,
            )
            quantidade = len(self._area_roi_ids)
            if quantidade:
                self.view.atualizar_status(
                    f"Seleção de área concluída: {quantidade} ROI(s). "
                    "Arraste para mover; cantos redimensionam; laterais esticam; Delete remove."
                )
            else:
                self.view.atualizar_status(
                    "A área não englobou nenhuma ROI."
                )
            self._atualizar_lupa_dinamica(evento)
            return "break"

        if modo in {"move", "scale", "stretch"}:
            self._area_roi_mode = None
            self._area_roi_handle = None
            self._atualizar_pos_edicao_roi()
            textos = {
                "move": "ROI(s) movida(s)",
                "scale": "ROI(s) aumentada(s) ou reduzida(s)",
                "stretch": "ROI(s) esticada(s) ou comprimida(s)",
            }
            self.view.atualizar_status(
                f"{textos[modo]}. As funções de análise e salvamento foram mantidas."
            )
            self._atualizar_lupa_dinamica(evento)
            return "break"
        return None

    def _evento_roda_roi(self, evento) -> str | None:
        if not self._modo_edicao_roi_ativo() or not self._area_roi_ids:
            return None
        numero = getattr(evento, "num", None)
        delta = int(getattr(evento, "delta", 0) or 0)
        incremento = 1 if numero == 4 or delta > 0 else -1
        self._area_roi_snapshot_all = [
            copiar_led(led) for led in self._leds_editaveis()
        ]
        selecionados = self._leds_area_selecionados()
        transformados = ajustar_raios_rois(
            selecionados,
            incremento,
            self.largura_original,
            self.altura_original,
        )
        self._substituir_leds_editaveis(
            self._mesclar_transformados(transformados)
        )
        self._atualizar_pos_edicao_roi()
        self._atualizar_lupa_dinamica(evento)
        return "break"

    def _evento_apagar_roi(self, _evento=None) -> str | None:
        if not self._modo_edicao_roi_ativo() or not self._area_roi_ids:
            return None
        ids = set(self._area_roi_ids)
        atuais = self._leds_editaveis()
        novos = [
            copiar_led(led)
            for led in atuais
            if str(led.id) not in ids
        ]
        removidos = len(atuais) - len(novos)
        self._substituir_leds_editaveis(novos)
        self._resetar_editor_roi()
        self._atualizar_pos_edicao_roi()
        self.view.atualizar_status(
            f"{removidos} ROI(s) removida(s). A configuração permanente só muda ao salvar LEDs."
        )
        return "break"

    def _evento_cancelar_selecao_roi(self, _evento=None) -> str | None:
        if not self._modo_edicao_roi_ativo():
            return None
        self._resetar_editor_roi()
        self.view.desenhar_canvas(
            self.leds_selecionados,
            self.resultados_led_atual,
        )
        self.view.atualizar_status(
            "Seleção de área desmarcada; as posições foram mantidas."
        )
        return "break"

    def _evento_selecionar_todas_rois(self, _evento=None) -> str | None:
        if not self._modo_edicao_roi_ativo():
            return None
        self._selecionar_todas_rois()
        return "break"

    def iniciar_selecao_led(self) -> None:
        super().iniciar_selecao_led()
        if self._modo_edicao_roi_ativo():
            self.view.atualizar_status(
                "Seleção ativa. Clique no vazio para adicionar ROI; clique e arraste no vazio "
                "para selecionar uma área; clique numa ROI para editar; Ctrl+A seleciona todas."
            )
