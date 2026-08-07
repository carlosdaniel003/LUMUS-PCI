from __future__ import annotations

from types import SimpleNamespace
import tkinter as tk

from src.platform.area_roi_editor_v4 import AreaRoiEditorV4Mixin
from src.platform.bulk_roi_editor import ROI_EDITOR_TAG, copiar_led, mover_rois
from src.ui.main_window_parts.image.rotacao_visual_principal import (
    atualizar_botao_rotacao_principal,
    converter_delta_visual_para_original,
    normalizar_rotacao_visual,
    obter_ponto_canvas_view,
    obter_retangulo_canvas_view,
    redesenhar_rotacao_visual_principal,
)


HANDLE_SIZE_CANVAS_PX = 7


class RotatedAreaRoiEditorMixin(AreaRoiEditorV4Mixin):
    """Mantém seleção e edição coerentes com a rotação visual do Canvas.

    As ROIs continuam armazenadas no referencial original da câmera. Somente a
    projeção para a tela e os comandos direcionais são transformados. Assim, a
    rotação nunca regrava nem desloca as máscaras permanentes.
    """

    def _ponto_canvas_rotacionado(
        self,
        imagem_x: float,
        imagem_y: float,
    ) -> tuple[float, float]:
        return obter_ponto_canvas_view(
            self.view,
            imagem_x,
            imagem_y,
        )

    def _retangulo_canvas_rotacionado(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> tuple[float, float, float, float]:
        return obter_retangulo_canvas_view(
            self.view,
            x1,
            y1,
            x2,
            y2,
        )

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
            nome: self._ponto_canvas_rotacionado(x, y)
            for nome, (x, y) in pontos.items()
        }

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
            cx1, cy1, cx2, cy2 = self._retangulo_canvas_rotacionado(
                x1,
                y1,
                x2,
                y2,
            )
            canvas.create_rectangle(
                cx1,
                cy1,
                cx2,
                cy2,
                outline="#38BDF8",
                width=2,
                dash=(6, 3),
                tags=ROI_EDITOR_TAG,
            )
            for led in self._leds_area_selecionados():
                x, y = self._ponto_canvas_rotacionado(
                    led.centro_x,
                    led.centro_y,
                )
                raio = max(
                    4.0,
                    led.raio * float(self.view.escala_exibicao),
                )
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
            x, y = self._ponto_canvas_rotacionado(
                led.centro_x,
                led.centro_y,
            )
            raio = max(
                4.0,
                led.raio * float(self.view.escala_exibicao),
            )
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
        cx1, cy1, cx2, cy2 = self._retangulo_canvas_rotacionado(
            x1,
            y1,
            x2,
            y2,
        )
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
            cor = (
                "#38BDF8"
                if nome in {"n", "e", "s", "w"}
                else "#FBBF24"
            )
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

    def _evento_preview_teclado(self):
        view = getattr(self, "view", None)
        if view is None:
            return None

        ultima_posicao = getattr(
            view,
            "_lupa_ultima_posicao_canvas",
            None,
        )
        if ultima_posicao is not None:
            return SimpleNamespace(
                x=int(ultima_posicao[0]),
                y=int(ultima_posicao[1]),
            )

        selecionados = self._leds_area_selecionados()
        bbox = self._bbox_leds(selecionados)
        if bbox is None:
            return None

        x1, y1, x2, y2 = bbox
        centro_x = (x1 + x2) / 2.0
        centro_y = (y1 + y2) / 2.0
        canvas_x, canvas_y = self._ponto_canvas_rotacionado(
            centro_x,
            centro_y,
        )
        return SimpleNamespace(
            x=int(round(canvas_x)),
            y=int(round(canvas_y)),
        )

    @staticmethod
    def _direcao_visual_teclado(keysym: str):
        return {
            "Left": (-1, 0, "esquerda"),
            "Right": (1, 0, "direita"),
            "Up": (0, -1, "cima"),
            "Down": (0, 1, "baixo"),
        }.get(str(keysym))

    def _evento_mover_roi_teclado(self, evento) -> str | None:
        if not self._modo_edicao_roi_ativo():
            return None
        if not self._area_roi_ids:
            return None
        if self._area_roi_mode is not None:
            return "break"

        direcao = self._direcao_visual_teclado(
            getattr(evento, "keysym", "")
        )
        if direcao is None:
            return None

        visual_dx, visual_dy, nome_direcao = direcao
        rotacao = normalizar_rotacao_visual(
            getattr(self.view, "rotacao_visual_principal", 0)
        )
        deslocamento_x, deslocamento_y = (
            converter_delta_visual_para_original(
                visual_dx,
                visual_dy,
                rotacao,
            )
        )

        todos = [copiar_led(led) for led in self._leds_editaveis()]
        ids = set(self._area_roi_ids)
        selecionados = [
            copiar_led(led)
            for led in todos
            if str(led.id) in ids
        ]
        if not selecionados:
            return None

        movidos = mover_rois(
            selecionados,
            deslocamento_x,
            deslocamento_y,
            int(getattr(self, "largura_original", 0) or 0),
            int(getattr(self, "altura_original", 0) or 0),
        )
        houve_movimento = any(
            antes.centro_x != depois.centro_x
            or antes.centro_y != depois.centro_y
            for antes, depois in zip(selecionados, movidos)
        )

        self._area_roi_snapshot_all = todos
        self._substituir_leds_editaveis(
            self._mesclar_transformados(movidos)
        )
        self._atualizar_pos_edicao_roi()
        self._atualizar_preview_apos_teclado()

        quantidade = len(selecionados)
        if houve_movimento:
            self.view.atualizar_status(
                f"{quantidade} ROI(s) movida(s) 1 px para {nome_direcao} "
                f"na visualização em {rotacao}°."
            )
        else:
            self.view.atualizar_status(
                f"Movimento para {nome_direcao} bloqueado pelo limite da imagem."
            )
        return "break"

    def iniciar_selecao_led(self) -> None:
        view = getattr(self, "view", None)
        rotacao_antes = normalizar_rotacao_visual(
            getattr(view, "rotacao_visual_principal", 0)
            if view is not None
            else 0
        )

        super().iniciar_selecao_led()

        view = getattr(self, "view", None)
        if view is None:
            return

        rotacao_depois = normalizar_rotacao_visual(
            getattr(view, "rotacao_visual_principal", 0)
        )
        if rotacao_depois != rotacao_antes:
            view.rotacao_visual_principal = rotacao_antes
            atualizar_botao_rotacao_principal(view)
            redesenhar_rotacao_visual_principal(view)

        if self._modo_edicao_roi_ativo():
            view.atualizar_status(
                "Seleção ativa mantendo a rotação visual em "
                f"{rotacao_antes}°. Clique numa ROI ou arraste no vazio para "
                "selecionar uma área; as coordenadas reais das máscaras permanecem intactas."
            )
