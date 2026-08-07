from __future__ import annotations

import math
import tkinter as tk

from src.core.roi_geometry import (
    SEGMENTO_ALTURA_PADRAO,
    SEGMENTO_ALTURA_MINIMA,
    SEGMENTO_LARGURA_PADRAO,
    SEGMENTO_LARGURA_MINIMA,
    TIPO_ROI_CIRCULO,
    TIPO_ROI_SEGMENTO,
    bbox_roi,
    normalizar_angulo_segmento,
    normalizar_tipo_roi,
    pontos_segmento,
    raio_compatibilidade_segmento,
    roi_dentro_imagem,
    todos_pontos_dentro_area,
)
from src.models.led_selection import LedSelection
from src.platform.bulk_roi_editor import (
    ROI_EDITOR_TAG,
    copiar_led,
    escalar_rois_uniformemente,
    mover_rois,
)
from src.platform.rotated_preview_roi_editor import (
    RotatedPreviewAreaRoiEditorMixin,
)


HANDLE_SIZE = 7
ROTATE_HANDLE_OFFSET = 24


def criar_segmento_por_arrasto(
    inicio_x: int,
    inicio_y: int,
    fim_x: int,
    fim_y: int,
    altura_segmento: int = SEGMENTO_ALTURA_PADRAO,
    id_roi: str = "SEG_001",
) -> LedSelection:
    dx = float(fim_x) - float(inicio_x)
    dy = float(fim_y) - float(inicio_y)
    comprimento = math.hypot(dx, dy)

    if comprimento < SEGMENTO_LARGURA_MINIMA:
        centro_x = int(round(inicio_x))
        centro_y = int(round(inicio_y))
        largura = SEGMENTO_LARGURA_PADRAO
        angulo = 0.0
    else:
        centro_x = int(round((float(inicio_x) + float(fim_x)) / 2.0))
        centro_y = int(round((float(inicio_y) + float(fim_y)) / 2.0))
        largura = max(SEGMENTO_LARGURA_MINIMA, int(round(comprimento)))
        angulo = math.degrees(math.atan2(dy, dx))

    altura = max(SEGMENTO_ALTURA_MINIMA, int(altura_segmento))
    return LedSelection(
        id=str(id_roi),
        centro_x=centro_x,
        centro_y=centro_y,
        raio=raio_compatibilidade_segmento(largura, altura),
        tipo_roi=TIPO_ROI_SEGMENTO,
        largura=largura,
        altura=altura,
        angulo=angulo,
    )


def _ponto_local_para_imagem(
    led: LedSelection,
    local_x: float,
    local_y: float,
) -> tuple[float, float]:
    angulo = math.radians(float(led.angulo))
    cos_a = math.cos(angulo)
    sin_a = math.sin(angulo)
    return (
        float(led.centro_x) + local_x * cos_a - local_y * sin_a,
        float(led.centro_y) + local_x * sin_a + local_y * cos_a,
    )


def _ponto_imagem_para_local(
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


def redimensionar_segmento_por_handle(
    led: LedSelection,
    handle: str,
    imagem_x: float,
    imagem_y: float,
) -> LedSelection:
    resultado = copiar_led(led)
    local_x, local_y = _ponto_imagem_para_local(
        resultado, imagem_x, imagem_y
    )

    if handle == "rotate":
        dx = float(imagem_x) - resultado.centro_x
        dy = float(imagem_y) - resultado.centro_y
        resultado.angulo = normalizar_angulo_segmento(
            math.degrees(math.atan2(dy, dx)) + 90.0
        )
        return resultado

    if handle in {"e", "w", "ne", "nw", "se", "sw"}:
        resultado.largura = max(
            SEGMENTO_LARGURA_MINIMA,
            int(round(abs(local_x) * 2.0)),
        )
    if handle in {"n", "s", "ne", "nw", "se", "sw"}:
        resultado.altura = max(
            SEGMENTO_ALTURA_MINIMA,
            int(round(abs(local_y) * 2.0)),
        )

    resultado.raio = raio_compatibilidade_segmento(
        int(resultado.largura or SEGMENTO_LARGURA_PADRAO),
        int(resultado.altura or SEGMENTO_ALTURA_PADRAO),
    )
    return resultado


class SegmentDisplayRoiEditorMixin(RotatedPreviewAreaRoiEditorMixin):
    """Editor misto: círculo legado + segmento chanfrado para displays."""

    def __init__(self, *args, **kwargs) -> None:
        self.tipo_roi_edicao = TIPO_ROI_SEGMENTO
        self.segmento_altura_padrao = SEGMENTO_ALTURA_PADRAO
        self._segmento_criacao_atual: LedSelection | None = None
        super().__init__(*args, **kwargs)

    def definir_tipo_roi_edicao(self, tipo: str) -> None:
        self.tipo_roi_edicao = normalizar_tipo_roi(tipo)
        atualizar = getattr(self, "_atualizar_botoes_tipo_roi", None)
        if callable(atualizar):
            atualizar()
        nome = "Segmento" if self.tipo_roi_edicao == TIPO_ROI_SEGMENTO else "Círculo"
        self.view.atualizar_status(
            f"Forma da próxima ROI: {nome}. "
            + (
                "Arraste no vazio para definir comprimento e ângulo."
                if self.tipo_roi_edicao == TIPO_ROI_SEGMENTO
                else "Clique no vazio para criar uma ROI circular."
            )
        )

    def _proximo_id_segmento(self) -> str:
        existentes = {str(led.id) for led in self._leds_editaveis()}
        indice = 1
        while f"SEG_{indice:03d}" in existentes:
            indice += 1
        return f"SEG_{indice:03d}"

    @staticmethod
    def _bbox_leds(leds):
        itens = list(leds)
        if not itens:
            return None
        caixas = [bbox_roi(led) for led in itens]
        return (
            min(c[0] for c in caixas),
            min(c[1] for c in caixas),
            max(c[2] for c in caixas),
            max(c[3] for c in caixas),
        )

    def _atualizar_marquee(self, imagem_x: int, imagem_y: int) -> None:
        if self._area_roi_press_image is None:
            return
        self._area_roi_current_image = (int(imagem_x), int(imagem_y))
        x1, y1 = self._area_roi_press_image
        esquerda, direita = sorted((int(x1), int(imagem_x)))
        topo, base = sorted((int(y1), int(imagem_y)))
        selecionados = [
            copiar_led(led)
            for led in self._leds_editaveis()
            if todos_pontos_dentro_area(
                led, esquerda, topo, direita, base
            )
        ]
        self._area_roi_ids = {str(led.id) for led in selecionados}
        self._sincronizar_preview_area()
        self._desenhar_overlay_editor_roi()

    def _segmento_unico_selecionado(self) -> LedSelection | None:
        selecionados = self._leds_area_selecionados()
        if len(selecionados) != 1:
            return None
        led = selecionados[0]
        return (
            led
            if normalizar_tipo_roi(getattr(led, "tipo_roi", None)) == TIPO_ROI_SEGMENTO
            else None
        )

    def _handles_segmento_imagem(self, led: LedSelection):
        largura = float(led.largura or SEGMENTO_LARGURA_PADRAO)
        altura = float(led.altura or SEGMENTO_ALTURA_PADRAO)
        hx, hy = largura / 2.0, altura / 2.0
        locais = {
            "nw": (-hx, -hy),
            "n": (0.0, -hy),
            "ne": (hx, -hy),
            "e": (hx, 0.0),
            "se": (hx, hy),
            "s": (0.0, hy),
            "sw": (-hx, hy),
            "w": (-hx, 0.0),
            "rotate": (0.0, -hy - max(ROTATE_HANDLE_OFFSET, altura)),
        }
        return {
            nome: _ponto_local_para_imagem(led, x, y)
            for nome, (x, y) in locais.items()
        }

    def _handles_canvas(self):
        led = self._segmento_unico_selecionado()
        if led is None:
            return super()._handles_canvas()
        return {
            nome: self._ponto_canvas_rotacionado(x, y)
            for nome, (x, y) in self._handles_segmento_imagem(led).items()
        }

    def _desenhar_segmento_canvas(
        self,
        led: LedSelection,
        cor: str,
        largura_linha: int = 2,
        dash=None,
        tags=ROI_EDITOR_TAG,
    ) -> None:
        pontos = []
        for x, y in pontos_segmento(led):
            cx, cy = self._ponto_canvas_rotacionado(float(x), float(y))
            pontos.extend((cx, cy))
        self.view.canvas.create_polygon(
            *pontos,
            fill="",
            outline=cor,
            width=largura_linha,
            dash=dash,
            tags=tags,
        )

    def _desenhar_overlay_editor_roi(self) -> None:
        super()._desenhar_overlay_editor_roi()
        canvas = getattr(getattr(self, "view", None), "canvas", None)
        if canvas is None or not self._modo_edicao_roi_ativo():
            return

        if self._area_roi_mode == "create_segment" and self._segmento_criacao_atual is not None:
            self._desenhar_segmento_canvas(
                self._segmento_criacao_atual,
                "#38BDF8",
                largura_linha=3,
                dash=(6, 3),
            )
            return

        led = self._segmento_unico_selecionado()
        if led is None or self._area_roi_mode == "marquee":
            return

        # Substitui o círculo de seleção herdado por uma seleção coerente com
        # a geometria real do segmento.
        canvas.delete(ROI_EDITOR_TAG)
        self._desenhar_segmento_canvas(
            led, "#FBBF24", largura_linha=3, dash=(5, 3)
        )
        handles = self._handles_canvas()
        for nome, (x, y) in handles.items():
            if nome == "rotate":
                centro = self._ponto_canvas_rotacionado(led.centro_x, led.centro_y)
                n = handles.get("n")
                if n is not None:
                    canvas.create_line(
                        n[0], n[1], x, y,
                        fill="#A78BFA", width=1, dash=(3, 3), tags=ROI_EDITOR_TAG,
                    )
                canvas.create_oval(
                    x - HANDLE_SIZE, y - HANDLE_SIZE,
                    x + HANDLE_SIZE, y + HANDLE_SIZE,
                    fill="#A78BFA", outline="#111827", width=1, tags=ROI_EDITOR_TAG,
                )
                continue
            cor = "#38BDF8" if nome in {"n", "e", "s", "w"} else "#FBBF24"
            canvas.create_rectangle(
                x - HANDLE_SIZE, y - HANDLE_SIZE,
                x + HANDLE_SIZE, y + HANDLE_SIZE,
                fill=cor, outline="#111827", width=1, tags=ROI_EDITOR_TAG,
            )
        x1, y1, x2, y2 = bbox_roi(led)
        cx1, cy1, cx2, _ = self._retangulo_canvas_rotacionado(x1, y1, x2, y2)
        canvas.create_text(
            (cx1 + cx2) / 2.0,
            max(14, cy1 - 16),
            text=(
                f"{led.id} • {int(led.largura or 0)}×{int(led.altura or 0)} px "
                f"• {float(led.angulo):.1f}°"
            ),
            fill="#FBBF24",
            font=("DejaVu Sans", 8, "bold"),
            tags=ROI_EDITOR_TAG,
        )

    def evento_clique_esquerdo(self, evento) -> str | None:
        retorno = super().evento_clique_esquerdo(evento)
        if not self._modo_edicao_roi_ativo():
            return retorno

        if self._area_roi_mode in {"scale", "stretch"}:
            if self._area_roi_handle == "rotate":
                self._area_roi_mode = "rotate"
            return retorno

        if (
            self.tipo_roi_edicao == TIPO_ROI_SEGMENTO
            and self._area_roi_mode == "pending_marquee"
        ):
            estado = int(getattr(evento, "state", 0) or 0)
            if estado & 0x0001:  # Shift mantém o seletor de área.
                return retorno
            self._area_roi_mode = "create_segment"
            self._segmento_criacao_atual = criar_segmento_por_arrasto(
                self._area_roi_press_image[0],
                self._area_roi_press_image[1],
                self._area_roi_press_image[0],
                self._area_roi_press_image[1],
                self.segmento_altura_padrao,
                self._proximo_id_segmento(),
            )
            self._desenhar_overlay_editor_roi()
        return retorno

    def _transformar_handle(self, imagem_x: int, imagem_y: int):
        origem = self._area_roi_snapshot_selected
        if len(origem) == 1:
            led = origem[0]
            if normalizar_tipo_roi(getattr(led, "tipo_roi", None)) == TIPO_ROI_SEGMENTO:
                candidato = redimensionar_segmento_por_handle(
                    led,
                    str(self._area_roi_handle),
                    imagem_x,
                    imagem_y,
                )
                if roi_dentro_imagem(
                    candidato,
                    int(getattr(self, "largura_original", 0) or 0),
                    int(getattr(self, "altura_original", 0) or 0),
                ):
                    return [candidato]
                return [copiar_led(led)]

        # Em seleção múltipla, os cantos escalam posição e geometria de todos.
        bbox = self._area_roi_bbox_snapshot
        handle = self._area_roi_handle
        if not origem or bbox is None or handle is None:
            return origem
        x1, y1, x2, y2 = bbox
        largura_frame = int(getattr(self, "largura_original", 0) or 0)
        altura_frame = int(getattr(self, "altura_original", 0) or 0)

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
            return escalar_rois_uniformemente(
                origem,
                ancora_x,
                ancora_y,
                max(0.05, min(fator_x, fator_y)),
                largura_frame,
                altura_frame,
            )

        # Laterais esticam somente o espaçamento do grupo, sem deformar cada ROI.
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

        resultado = []
        for original in origem:
            led = copiar_led(original)
            if eixo == "x":
                led.centro_x = int(round(
                    ancora + (original.centro_x - ancora) * max(0.05, fator)
                ))
            else:
                led.centro_y = int(round(
                    ancora + (original.centro_y - ancora) * max(0.05, fator)
                ))
            resultado.append(led)
        if all(roi_dentro_imagem(x, largura_frame, altura_frame) for x in resultado):
            return resultado
        return [copiar_led(x) for x in origem]

    def _evento_arrastar_roi(self, evento) -> str | None:
        if self._area_roi_mode == "create_segment":
            coordenadas = self.view.converter_canvas_para_imagem_original(
                evento.x, evento.y
            )
            if coordenadas is None or self._area_roi_press_image is None:
                return "break"
            imagem_x, imagem_y = coordenadas
            x0, y0 = self._area_roi_press_image
            self._area_roi_current_image = (int(imagem_x), int(imagem_y))
            self._segmento_criacao_atual = criar_segmento_por_arrasto(
                x0,
                y0,
                imagem_x,
                imagem_y,
                self.segmento_altura_padrao,
                self._proximo_id_segmento(),
            )
            self._desenhar_overlay_editor_roi()
            self._atualizar_lupa_dinamica(evento)
            return "break"

        if self._area_roi_mode == "rotate":
            coordenadas = self.view.converter_canvas_para_imagem_original(
                evento.x, evento.y
            )
            if coordenadas is None:
                return "break"
            transformados = self._transformar_handle(*coordenadas)
            self._substituir_leds_editaveis(
                self._mesclar_transformados(transformados)
            )
            self.view.desenhar_canvas(
                self.leds_selecionados,
                self.resultados_led_atual,
            )
            self._atualizar_lupa_dinamica(evento)
            return "break"

        return super()._evento_arrastar_roi(evento)

    def _evento_soltar_roi(self, evento) -> str | None:
        if self._area_roi_mode == "create_segment":
            candidato = self._segmento_criacao_atual
            self._area_roi_mode = None
            self._segmento_criacao_atual = None
            if candidato is None:
                return "break"

            candidato = mover_rois(
                [candidato],
                0,
                0,
                int(getattr(self, "largura_original", 0) or 0),
                int(getattr(self, "altura_original", 0) or 0),
            )[0]
            if not roi_dentro_imagem(
                candidato,
                int(getattr(self, "largura_original", 0) or 0),
                int(getattr(self, "altura_original", 0) or 0),
            ):
                self.view.atualizar_status(
                    "Segmento não criado: a geometria ultrapassa os limites da imagem."
                )
                self._desenhar_overlay_editor_roi()
                return "break"

            novos = [copiar_led(x) for x in self._leds_editaveis()]
            novos.append(candidato)
            self._substituir_leds_editaveis(novos)
            self._selecionar_ids([candidato.id], mensagem=False)
            self._atualizar_pos_edicao_roi()
            self.view.atualizar_status(
                f"{candidato.id} criado: {candidato.largura}×{candidato.altura}px, "
                f"ângulo {candidato.angulo:.1f}°. Arraste alças para ajustar; "
                "a alça violeta rotaciona."
            )
            return "break"

        if self._area_roi_mode == "rotate":
            self._area_roi_mode = None
            self._area_roi_handle = None
            self._atualizar_pos_edicao_roi()
            self.view.atualizar_status("Rotação do segmento concluída.")
            return "break"

        return super()._evento_soltar_roi(evento)

    def iniciar_selecao_led(self) -> None:
        super().iniciar_selecao_led()
        if self._modo_edicao_roi_ativo():
            self.view.atualizar_status(
                "Editor de display ativo. ROI padrão: Segmento. Arraste no vazio para "
                "criar uma barra; Shift+arraste seleciona área; escolha Círculo para LEDs "
                "redondos/ponto decimal."
            )
