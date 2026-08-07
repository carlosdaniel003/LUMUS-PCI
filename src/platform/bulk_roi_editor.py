from __future__ import annotations

import math
import time
import tkinter as tk
from typing import Iterable

from config import MAX_RADIUS_PX, MIN_RADIUS_PX
from src.core.roi_geometry import (
    TIPO_ROI_SEGMENTO,
    bbox_roi,
    normalizar_tipo_roi,
    ponto_dentro_roi,
    raio_compatibilidade_segmento,
    roi_dentro_imagem,
)
from src.models.led_selection import LedSelection


ROI_EDITOR_TAG = "roi_bulk_editor"
LONG_PRESS_MS = 320
DRAG_THRESHOLD_CANVAS_PX = 5
HANDLE_SIZE_CANVAS_PX = 9
HANDLE_HIT_CANVAS_PX = 15


def copiar_led(led: LedSelection) -> LedSelection:
    """Copia toda a geometria absoluta da ROI circular ou de segmento."""
    return LedSelection(
        id=str(led.id),
        centro_x=int(led.centro_x),
        centro_y=int(led.centro_y),
        raio=int(led.raio),
        tipo_roi=getattr(led, "tipo_roi", "circulo"),
        largura=getattr(led, "largura", None),
        altura=getattr(led, "altura", None),
        angulo=float(getattr(led, "angulo", 0.0) or 0.0),
    )


def limitar_deslocamento_rois(
    leds: Iterable[LedSelection],
    deslocamento_x: int,
    deslocamento_y: int,
    largura: int,
    altura: int,
) -> tuple[int, int]:
    itens = list(leds)
    if not itens or largura <= 0 or altura <= 0:
        return 0, 0

    caixas = [bbox_roi(led) for led in itens]
    minimo_x = max(-x1 for x1, _, _, _ in caixas)
    maximo_x = min(int(largura) - 1 - x2 for _, _, x2, _ in caixas)
    minimo_y = max(-y1 for _, y1, _, _ in caixas)
    maximo_y = min(int(altura) - 1 - y2 for _, _, _, y2 in caixas)

    dx = min(maximo_x, max(minimo_x, int(round(deslocamento_x))))
    dy = min(maximo_y, max(minimo_y, int(round(deslocamento_y))))
    return dx, dy


def mover_rois(
    leds: Iterable[LedSelection],
    deslocamento_x: int,
    deslocamento_y: int,
    largura: int,
    altura: int,
) -> list[LedSelection]:
    itens = [copiar_led(led) for led in leds]
    dx, dy = limitar_deslocamento_rois(
        itens, deslocamento_x, deslocamento_y, largura, altura
    )
    resultado = []
    for led in itens:
        novo = copiar_led(led)
        novo.centro_x += dx
        novo.centro_y += dy
        resultado.append(novo)
    return resultado


def _rois_validas(
    leds: Iterable[LedSelection],
    largura: int,
    altura: int,
) -> bool:
    for led in leds:
        if normalizar_tipo_roi(getattr(led, "tipo_roi", None)) != TIPO_ROI_SEGMENTO:
            if led.raio < MIN_RADIUS_PX or led.raio > MAX_RADIUS_PX:
                return False
        if not roi_dentro_imagem(led, largura, altura):
            return False
    return True


def _criar_rois_escaladas(
    leds: Iterable[LedSelection],
    centro_grupo_x: float,
    centro_grupo_y: float,
    escala: float,
) -> list[LedSelection]:
    resultado = []
    for origem in leds:
        led = copiar_led(origem)
        led.centro_x = int(round(
            centro_grupo_x + (int(origem.centro_x) - centro_grupo_x) * escala
        ))
        led.centro_y = int(round(
            centro_grupo_y + (int(origem.centro_y) - centro_grupo_y) * escala
        ))
        if normalizar_tipo_roi(getattr(led, "tipo_roi", None)) == TIPO_ROI_SEGMENTO:
            led.largura = max(8, int(round(int(led.largura or 48) * escala)))
            led.altura = max(4, int(round(int(led.altura or 14) * escala)))
            led.raio = raio_compatibilidade_segmento(led.largura, led.altura)
        else:
            led.raio = int(round(int(led.raio) * escala))
        resultado.append(led)
    return resultado


def escalar_rois_uniformemente(
    leds: Iterable[LedSelection],
    centro_grupo_x: float,
    centro_grupo_y: float,
    escala_desejada: float,
    largura: int,
    altura: int,
) -> list[LedSelection]:
    origem = [copiar_led(led) for led in leds]
    if not origem or largura <= 0 or altura <= 0:
        return origem

    circulos = [
        led for led in origem
        if normalizar_tipo_roi(getattr(led, "tipo_roi", None)) != TIPO_ROI_SEGMENTO
    ]
    escala_minima = max(
        [MIN_RADIUS_PX / max(1, int(led.raio)) for led in circulos] + [0.05]
    )
    escala_maxima = min(
        [MAX_RADIUS_PX / max(1, int(led.raio)) for led in circulos] + [20.0]
    )
    escala = min(escala_maxima, max(escala_minima, float(escala_desejada)))

    candidato = _criar_rois_escaladas(
        origem, centro_grupo_x, centro_grupo_y, escala
    )
    if _rois_validas(candidato, largura, altura):
        return candidato
    if escala <= 1.0:
        return origem

    inferior = 1.0
    superior = escala
    melhor = origem
    for _ in range(28):
        meio = (inferior + superior) / 2.0
        tentativa = _criar_rois_escaladas(
            origem, centro_grupo_x, centro_grupo_y, meio
        )
        if _rois_validas(tentativa, largura, altura):
            melhor = tentativa
            inferior = meio
        else:
            superior = meio
    return melhor


def ajustar_raios_rois(
    leds: Iterable[LedSelection],
    incremento: int,
    largura: int,
    altura: int,
) -> list[LedSelection]:
    """A roda altera somente círculos; segmentos usam alças de largura/altura."""
    resultado = []
    for item in leds:
        led = copiar_led(item)
        if normalizar_tipo_roi(getattr(led, "tipo_roi", None)) == TIPO_ROI_SEGMENTO:
            resultado.append(led)
            continue
        limite_borda = min(
            led.centro_x,
            led.centro_y,
            largura - 1 - led.centro_x,
            altura - 1 - led.centro_y,
        )
        raio_maximo = max(
            MIN_RADIUS_PX,
            min(MAX_RADIUS_PX, int(limite_borda)),
        )
        led.raio = min(
            raio_maximo,
            max(MIN_RADIUS_PX, led.raio + int(incremento)),
        )
        resultado.append(led)
    return resultado


class BulkRoiEditorMixin:
    MODOS_EDICAO = {
        "selecionar_leds_analise",
        "configurar_leds_fixos",
        "selecionar_leds_camera",
    }

    def __init__(self, *args, **kwargs) -> None:
        self._roi_editor_selection = None
        self._roi_editor_single_id = None
        self._roi_editor_drag_mode = None
        self._roi_editor_press_canvas = None
        self._roi_editor_press_image = None
        self._roi_editor_snapshot = []
        self._roi_editor_scale_center = None
        self._roi_editor_scale_distance = 1.0
        self._roi_editor_long_press_after_id = None
        self._roi_editor_moved = False
        self._roi_editor_installed = False
        super().__init__(*args, **kwargs)
        self._instalar_editor_roi()

    def _modo_edicao_roi_ativo(self) -> bool:
        return str(getattr(self, "modo_atual", "")) in self.MODOS_EDICAO

    def _leds_editaveis(self) -> list[LedSelection]:
        if str(getattr(self, "modo_atual", "")) == "selecionar_leds_camera":
            return list(getattr(self, "leds_manuais_camera", []) or ())
        return list(getattr(self, "leds_selecionados", []) or ())

    def _substituir_leds_editaveis(self, leds: Iterable[LedSelection]) -> None:
        novos = [copiar_led(led) for led in leds]
        if str(getattr(self, "modo_atual", "")) == "selecionar_leds_camera":
            self.leds_manuais_camera = [copiar_led(led) for led in novos]
            self.leds_selecionados = [copiar_led(led) for led in novos]
            self.guias_leds_fixos_visiveis = False
            self.view.selecao_manual_camera_visivel = bool(novos)
        else:
            self.leds_selecionados = novos
        self.resultados_led_atual = []

    def _instalar_editor_roi(self) -> None:
        if self._roi_editor_installed:
            return
        canvas = getattr(getattr(self, "view", None), "canvas", None)
        if canvas is None:
            return
        self._roi_editor_installed = True
        canvas.bind("<B1-Motion>", self._evento_arrastar_roi, add="+")
        canvas.bind("<ButtonRelease-1>", self._evento_soltar_roi, add="+")
        canvas.bind("<MouseWheel>", self._evento_roda_roi, add="+")
        canvas.bind("<Button-4>", self._evento_roda_roi, add="+")
        canvas.bind("<Button-5>", self._evento_roda_roi, add="+")
        canvas.bind("<Delete>", self._evento_apagar_roi, add="+")
        canvas.bind("<BackSpace>", self._evento_apagar_roi, add="+")
        canvas.bind("<Escape>", self._evento_cancelar_selecao_roi, add="+")
        self.root.bind("<Control-a>", self._evento_selecionar_todas_rois, add="+")
        self.root.bind("<Control-A>", self._evento_selecionar_todas_rois, add="+")

        original = self.view.desenhar_canvas
        def desenhar_canvas_com_editor(*args, **kwargs):
            retorno = original(*args, **kwargs)
            self._desenhar_overlay_editor_roi()
            return retorno
        self.view.desenhar_canvas = desenhar_canvas_com_editor

    def _cancelar_long_press_roi(self) -> None:
        after_id = self._roi_editor_long_press_after_id
        self._roi_editor_long_press_after_id = None
        if after_id is None:
            return
        try:
            self.root.after_cancel(after_id)
        except Exception:
            pass

    def _resetar_editor_roi(self) -> None:
        self._cancelar_long_press_roi()
        self._roi_editor_selection = None
        self._roi_editor_single_id = None
        self._roi_editor_drag_mode = None
        self._roi_editor_press_canvas = None
        self._roi_editor_press_image = None
        self._roi_editor_snapshot = []
        self._roi_editor_scale_center = None
        self._roi_editor_scale_distance = 1.0
        self._roi_editor_moved = False
        canvas = getattr(getattr(self, "view", None), "canvas", None)
        if canvas is not None:
            try:
                canvas.delete(ROI_EDITOR_TAG)
            except tk.TclError:
                pass

    def _coordenada_canvas(self, valor: float, eixo: str) -> float:
        escala = max(0.000001, float(getattr(self.view, "escala_exibicao", 1.0)))
        deslocamento = float(getattr(
            self.view,
            "deslocamento_imagem_x" if eixo == "x" else "deslocamento_imagem_y",
            0,
        ))
        return deslocamento + float(valor) * escala

    def _bbox_grupo_imagem(self, leds=None):
        itens = list(leds if leds is not None else self._leds_editaveis())
        if not itens:
            return None
        caixas = [bbox_roi(led) for led in itens]
        return (
            min(c[0] for c in caixas),
            min(c[1] for c in caixas),
            max(c[2] for c in caixas),
            max(c[3] for c in caixas),
        )

    def _handles_grupo_canvas(self) -> list[tuple[float, float]]:
        bbox = self._bbox_grupo_imagem()
        if bbox is None:
            return []
        x1, y1, x2, y2 = bbox
        return [
            (self._coordenada_canvas(x1, "x"), self._coordenada_canvas(y1, "y")),
            (self._coordenada_canvas(x2, "x"), self._coordenada_canvas(y1, "y")),
            (self._coordenada_canvas(x1, "x"), self._coordenada_canvas(y2, "y")),
            (self._coordenada_canvas(x2, "x"), self._coordenada_canvas(y2, "y")),
        ]

    def _handle_atingido(self, canvas_x: int, canvas_y: int) -> bool:
        if self._roi_editor_selection != "all":
            return False
        return any(
            abs(float(canvas_x) - hx) <= HANDLE_HIT_CANVAS_PX
            and abs(float(canvas_y) - hy) <= HANDLE_HIT_CANVAS_PX
            for hx, hy in self._handles_grupo_canvas()
        )

    def _led_atingido(self, imagem_x: int, imagem_y: int) -> LedSelection | None:
        melhor = None
        melhor_distancia = None
        for led in self._leds_editaveis():
            if not ponto_dentro_roi(led, imagem_x, imagem_y):
                continue
            dx = int(imagem_x) - int(led.centro_x)
            dy = int(imagem_y) - int(led.centro_y)
            distancia = dx * dx + dy * dy
            if melhor_distancia is None or distancia < melhor_distancia:
                melhor = led
                melhor_distancia = distancia
        return melhor

    def _ponto_dentro_grupo(self, imagem_x: int, imagem_y: int) -> bool:
        bbox = self._bbox_grupo_imagem()
        if bbox is None:
            return False
        x1, y1, x2, y2 = bbox
        return x1 <= imagem_x <= x2 and y1 <= imagem_y <= y2

    def _selecionar_todas_rois(self, mensagem: bool = True) -> bool:
        leds = self._leds_editaveis()
        if not leds:
            return False
        self._roi_editor_selection = "all"
        self._roi_editor_single_id = None
        self._desenhar_overlay_editor_roi()
        if mensagem:
            self.view.atualizar_status(
                f"{len(leds)} ROIs selecionadas. Arraste para mover; cantos escalam; "
                "Delete apaga o conjunto."
            )
        return True

    def _selecionar_roi_individual(self, led: LedSelection) -> None:
        self._roi_editor_selection = "single"
        self._roi_editor_single_id = str(led.id)
        self._desenhar_overlay_editor_roi()
        self.view.atualizar_status(
            f"{led.id} selecionado. Arraste para mover; Delete remove."
        )

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
        leds = self._leds_editaveis()
        if not leds:
            return

        if self._roi_editor_selection == "single":
            led = next((x for x in leds if str(x.id) == self._roi_editor_single_id), None)
            if led is None:
                return
            x1, y1, x2, y2 = bbox_roi(led)
            cx1 = self._coordenada_canvas(x1, "x")
            cy1 = self._coordenada_canvas(y1, "y")
            cx2 = self._coordenada_canvas(x2, "x")
            cy2 = self._coordenada_canvas(y2, "y")
            canvas.create_rectangle(
                cx1 - 4, cy1 - 4, cx2 + 4, cy2 + 4,
                outline="#FBBF24", width=3, dash=(5, 3), tags=ROI_EDITOR_TAG,
            )
            canvas.create_text(
                (cx1 + cx2) / 2, max(12, cy1 - 14),
                text=f"EDITAR {led.id}", fill="#FBBF24",
                font=("DejaVu Sans", 8, "bold"), tags=ROI_EDITOR_TAG,
            )
            return

        if self._roi_editor_selection != "all":
            return
        bbox = self._bbox_grupo_imagem(leds)
        if bbox is None:
            return
        x1, y1, x2, y2 = bbox
        cx1 = self._coordenada_canvas(x1, "x")
        cy1 = self._coordenada_canvas(y1, "y")
        cx2 = self._coordenada_canvas(x2, "x")
        cy2 = self._coordenada_canvas(y2, "y")
        canvas.create_rectangle(
            cx1, cy1, cx2, cy2,
            outline="#FBBF24", width=2, dash=(7, 4), tags=ROI_EDITOR_TAG,
        )
        for hx, hy in self._handles_grupo_canvas():
            canvas.create_rectangle(
                hx - HANDLE_SIZE_CANVAS_PX, hy - HANDLE_SIZE_CANVAS_PX,
                hx + HANDLE_SIZE_CANVAS_PX, hy + HANDLE_SIZE_CANVAS_PX,
                fill="#FBBF24", outline="#111827", width=1, tags=ROI_EDITOR_TAG,
            )
        canvas.create_text(
            (cx1 + cx2) / 2.0, max(12, cy1 - 14),
            text=f"TODAS AS ROIs ({len(leds)})", fill="#FBBF24",
            font=("DejaVu Sans", 8, "bold"), tags=ROI_EDITOR_TAG,
        )

    def _iniciar_arrasto(self, modo: str, imagem_x: int, imagem_y: int) -> None:
        self._roi_editor_drag_mode = modo
        self._roi_editor_press_image = (int(imagem_x), int(imagem_y))
        self._roi_editor_snapshot = [copiar_led(led) for led in self._leds_editaveis()]
        self._roi_editor_moved = False
        if modo == "scale_all":
            bbox = self._bbox_grupo_imagem(self._roi_editor_snapshot)
            if bbox is None:
                return
            x1, y1, x2, y2 = bbox
            centro_x = (x1 + x2) / 2.0
            centro_y = (y1 + y2) / 2.0
            self._roi_editor_scale_center = (centro_x, centro_y)
            self._roi_editor_scale_distance = max(
                1.0, math.hypot(imagem_x - centro_x, imagem_y - centro_y)
            )

    def evento_clique_esquerdo(self, evento) -> str | None:
        if not self._modo_edicao_roi_ativo():
            self._resetar_editor_roi()
            return super().evento_clique_esquerdo(evento)
        try:
            self.view.canvas.focus_set()
        except tk.TclError:
            pass
        coordenadas = self.view.converter_canvas_para_imagem_original(evento.x, evento.y)
        if coordenadas is None:
            return "break"
        imagem_x, imagem_y = coordenadas
        self._roi_editor_press_canvas = (int(evento.x), int(evento.y))
        self._roi_editor_press_image = (int(imagem_x), int(imagem_y))
        self._roi_editor_moved = False

        if self._handle_atingido(evento.x, evento.y):
            self._cancelar_long_press_roi()
            self._iniciar_arrasto("scale_all", imagem_x, imagem_y)
            return "break"
        led = self._led_atingido(imagem_x, imagem_y)
        if led is not None:
            self._cancelar_long_press_roi()
            self._selecionar_roi_individual(led)
            self._iniciar_arrasto("move_single", imagem_x, imagem_y)
            return "break"
        if self._roi_editor_selection == "all" and self._ponto_dentro_grupo(imagem_x, imagem_y):
            self._cancelar_long_press_roi()
            self._iniciar_arrasto("move_all", imagem_x, imagem_y)
            return "break"

        estado = int(getattr(evento, "state", 0) or 0)
        shift = bool(estado & 0x0001)
        control = bool(estado & 0x0004)
        leds = self._leds_editaveis()
        if control or not leds:
            self._resetar_editor_roi()
            return super().evento_clique_esquerdo(evento)
        if shift:
            self._selecionar_todas_rois()
            self._iniciar_arrasto("move_all", imagem_x, imagem_y)
            return "break"

        self._roi_editor_drag_mode = "pending_all"
        self._roi_editor_snapshot = [copiar_led(item) for item in leds]
        self._cancelar_long_press_roi()
        self._roi_editor_long_press_after_id = self.root.after(
            LONG_PRESS_MS,
            lambda: self._ativar_selecao_total_por_long_press(imagem_x, imagem_y),
        )
        return "break"

    def _ativar_selecao_total_por_long_press(self, imagem_x: int, imagem_y: int) -> None:
        self._roi_editor_long_press_after_id = None
        if self._roi_editor_drag_mode != "pending_all":
            return
        if self._selecionar_todas_rois():
            self._iniciar_arrasto("move_all", imagem_x, imagem_y)

    def _evento_arrastar_roi(self, evento) -> str | None:
        if not self._modo_edicao_roi_ativo():
            return None
        coordenadas = self.view.converter_canvas_para_imagem_original(evento.x, evento.y)
        if coordenadas is None or self._roi_editor_press_image is None:
            return "break"
        imagem_x, imagem_y = coordenadas

        if self._roi_editor_drag_mode == "pending_all":
            origem_canvas = self._roi_editor_press_canvas
            if origem_canvas is None:
                return "break"
            distancia = math.hypot(evento.x - origem_canvas[0], evento.y - origem_canvas[1])
            if distancia < DRAG_THRESHOLD_CANVAS_PX:
                return "break"
            self._cancelar_long_press_roi()
            if not self._selecionar_todas_rois():
                return "break"
            origem_x, origem_y = self._roi_editor_press_image
            self._iniciar_arrasto("move_all", origem_x, origem_y)

        origem_x, origem_y = self._roi_editor_press_image
        dx = int(imagem_x) - int(origem_x)
        dy = int(imagem_y) - int(origem_y)
        largura = int(getattr(self, "largura_original", 0) or 0)
        altura = int(getattr(self, "altura_original", 0) or 0)

        if self._roi_editor_drag_mode == "move_all":
            novos = mover_rois(self._roi_editor_snapshot, dx, dy, largura, altura)
        elif self._roi_editor_drag_mode == "move_single":
            novos = [copiar_led(led) for led in self._roi_editor_snapshot]
            indice = next((i for i, led in enumerate(novos) if str(led.id) == self._roi_editor_single_id), None)
            if indice is None:
                return "break"
            novos[indice] = mover_rois([novos[indice]], dx, dy, largura, altura)[0]
        elif self._roi_editor_drag_mode == "scale_all":
            if self._roi_editor_scale_center is None:
                return "break"
            centro_x, centro_y = self._roi_editor_scale_center
            distancia = max(1.0, math.hypot(imagem_x - centro_x, imagem_y - centro_y))
            escala = distancia / max(1.0, self._roi_editor_scale_distance)
            novos = escalar_rois_uniformemente(
                self._roi_editor_snapshot, centro_x, centro_y, escala, largura, altura
            )
        else:
            return None

        self._roi_editor_moved = True
        self._substituir_leds_editaveis(novos)
        self.view.desenhar_canvas(self.leds_selecionados, self.resultados_led_atual)
        return "break"

    def _evento_soltar_roi(self, evento) -> str | None:
        if not self._modo_edicao_roi_ativo():
            return None
        modo = self._roi_editor_drag_mode
        self._cancelar_long_press_roi()
        if modo == "pending_all":
            self._roi_editor_drag_mode = None
            self._roi_editor_selection = None
            self._roi_editor_single_id = None
            retorno = super().evento_clique_esquerdo(evento)
            self._desenhar_overlay_editor_roi()
            return retorno or "break"
        if modo in {"move_all", "move_single", "scale_all"}:
            self._roi_editor_drag_mode = None
            self._atualizar_pos_edicao_roi()
            acao = {
                "move_all": "conjunto de ROIs movido",
                "move_single": "ROI movida",
                "scale_all": "conjunto de ROIs escalado",
            }[modo]
            self.view.atualizar_status(f"{acao}. Análise e salvamento foram mantidos.")
            return "break"
        return None

    def _atualizar_pos_edicao_roi(self) -> None:
        self.resultados_led_atual = []
        self.view.desenhar_canvas(self.leds_selecionados, self.resultados_led_atual)
        if getattr(self, "camera_ativa", False):
            self.atualizar_renderizacoes_camera_se_necessario(forcar=True)
        else:
            self.atualizar_renderizacoes_visuais(self.leds_selecionados)
        self.view.atualizar_faixa_resultado()
        self.atualizar_painel_inicial()

    def _evento_roda_roi(self, evento) -> str | None:
        if not self._modo_edicao_roi_ativo():
            return None
        if self._roi_editor_selection not in {"single", "all"}:
            return None
        numero = getattr(evento, "num", None)
        delta = int(getattr(evento, "delta", 0) or 0)
        incremento = 1 if numero == 4 or delta > 0 else -1
        leds = self._leds_editaveis()
        if self._roi_editor_selection == "all":
            novos = ajustar_raios_rois(leds, incremento, self.largura_original, self.altura_original)
        else:
            novos = [copiar_led(led) for led in leds]
            for indice, led in enumerate(novos):
                if str(led.id) == self._roi_editor_single_id:
                    novos[indice] = ajustar_raios_rois(
                        [led], incremento, self.largura_original, self.altura_original
                    )[0]
                    break
        self._substituir_leds_editaveis(novos)
        self._atualizar_pos_edicao_roi()
        return "break"

    def _evento_apagar_roi(self, _evento=None) -> str | None:
        if not self._modo_edicao_roi_ativo():
            return None
        if self._roi_editor_selection not in {"single", "all"}:
            return None
        leds = self._leds_editaveis()
        if self._roi_editor_selection == "all":
            removidos, novos = len(leds), []
        else:
            novos = [copiar_led(led) for led in leds if str(led.id) != self._roi_editor_single_id]
            removidos = len(leds) - len(novos)
        self._substituir_leds_editaveis(novos)
        self._resetar_editor_roi()
        self._atualizar_pos_edicao_roi()
        self.view.atualizar_status(
            f"{removidos} ROI(s) removida(s) da seleção atual. A configuração salva só muda ao salvar LEDs."
        )
        return "break"

    def _evento_cancelar_selecao_roi(self, _evento=None) -> str | None:
        if not self._modo_edicao_roi_ativo():
            return None
        self._resetar_editor_roi()
        self.view.desenhar_canvas(self.leds_selecionados, self.resultados_led_atual)
        self.view.atualizar_status("Edição de ROI desmarcada; posições mantidas.")
        return "break"

    def _evento_selecionar_todas_rois(self, _evento=None) -> str | None:
        if not self._modo_edicao_roi_ativo():
            return None
        self._selecionar_todas_rois()
        return "break"

    def iniciar_selecao_led(self) -> None:
        ativando_camera = bool(
            getattr(self, "camera_ativa", False)
            and not getattr(self, "selecao_manual_camera_ativa", False)
        )
        if ativando_camera:
            atuais = list(getattr(self, "leds_selecionados", []) or ())
            if atuais and not getattr(self, "leds_manuais_camera", []):
                self.leds_manuais_camera = [copiar_led(led) for led in atuais]
        self._resetar_editor_roi()
        super().iniciar_selecao_led()
        if self._modo_edicao_roi_ativo():
            self.view.atualizar_status(
                "Seleção de ROIs ativa. Clique numa ROI para editar; selecione por área; Ctrl+A seleciona o conjunto."
            )

    def configurar_leds_fixos(self) -> None:
        self._resetar_editor_roi()
        super().configurar_leds_fixos()

    def carregar_imagem(self) -> None:
        self._resetar_editor_roi()
        super().carregar_imagem()

    def carregar_leds_fixos(self) -> None:
        self._resetar_editor_roi()
        super().carregar_leds_fixos()

    def limpar_tela(self) -> None:
        self._resetar_editor_roi()
        super().limpar_tela()
