from __future__ import annotations

import tkinter as tk

import cv2
import numpy as np

from src.core.roi_geometry import (
    TIPO_ROI_SEGMENTO,
    bbox_roi,
    normalizar_tipo_roi,
    pontos_segmento,
)
from src.platform.blue_operation_window import BlueRaspberryOperationWindow


F2_LIVE_ROI_OVERLAY_ALPHA = 0.14
F2_LIVE_ROI_COLORS_BGR = {
    "ACESO": (94, 197, 34),
    "APAGADO": (68, 68, 239),
    "POUCA_LUZ": (21, 204, 250),
    "POUCA LUZ": (21, 204, 250),
    "UNKNOWN": (184, 163, 148),
}
F2_LIVE_ROI_LEGEND = (
    "VERDE: ACESO  •  VERMELHO: APAGADO  •  AMARELO: POUCA LUZ"
)

F2_ANALYZED_WAITING_TEXT = "PLACA JÁ ANALISADA\nCOLOQUE OUTRA PLACA"
F2_ANALYZED_WAITING_FONT_MAX = 28
F2_ANALYZED_WAITING_FONT_MIN = 14

F2_BOARD_STATUS_UI = {
    "board_on": ("PLACA PRESENTE — LIGADA", "#86EFAC"),
    "board_off": ("PLACA PRESENTE — DESLIGADA", "#FBBF24"),
    "empty_support": ("PLACA AUSENTE", "#94A3B8"),
    "unknown": ("IDENTIFICANDO...", "#CBD5E1"),
    "unavailable": ("REFERÊNCIAS DE PRESENÇA NÃO CONFIGURADAS", "#FBBF24"),
    "analyzed_ok": ("JÁ ANALISADA — RESULTADO: OK", "#86EFAC"),
    "analyzed_ng": ("JÁ ANALISADA — RESULTADO: NG", "#FCA5A5"),
}


def tamanho_fonte_status_analisado_f2(panel_width: int) -> int:
    """Dimensiona o aviso em duas linhas para não cortar em telas estreitas."""
    try:
        width = int(panel_width)
    except (TypeError, ValueError):
        width = 640

    usable_width = max(160, max(220, width) - 72)
    longest_line = max(len(line) for line in F2_ANALYZED_WAITING_TEXT.splitlines())
    # Aproxima a largura de texto em DejaVu Sans Bold de forma conservadora.
    estimated = int(usable_width / max(1.0, longest_line * 0.90))
    return max(
        F2_ANALYZED_WAITING_FONT_MIN,
        min(F2_ANALYZED_WAITING_FONT_MAX, estimated),
    )


def renderizar_overlay_rois_f2(frame, leds, states: dict[str, str] | None):
    """Desenha uma cópia translúcida das ROIs sem alterar o frame da câmera."""
    if frame is None or getattr(frame, "size", 0) == 0:
        return frame

    result = frame.copy()
    tint = result.copy()
    outlines: list[tuple[str, object, tuple[int, int, int]]] = []
    state_map = {
        str(key): str(value).strip().upper()
        for key, value in dict(states or {}).items()
    }

    for led in tuple(leds or ()):
        led_id = str(getattr(led, "id", ""))
        status = state_map.get(led_id, "UNKNOWN")
        color = F2_LIVE_ROI_COLORS_BGR.get(
            status,
            F2_LIVE_ROI_COLORS_BGR["UNKNOWN"],
        )
        tipo = normalizar_tipo_roi(getattr(led, "tipo_roi", None))

        if tipo == TIPO_ROI_SEGMENTO:
            points = np.asarray(
                [(int(round(x)), int(round(y))) for x, y in pontos_segmento(led)],
                dtype=np.int32,
            )
            if len(points) < 3:
                continue
            polygon = points.reshape((-1, 1, 2))
            cv2.fillPoly(tint, [polygon], color, lineType=cv2.LINE_AA)
            outlines.append(("segment", polygon, color))
        else:
            center = (
                int(getattr(led, "centro_x", 0)),
                int(getattr(led, "centro_y", 0)),
            )
            radius = max(2, int(getattr(led, "raio", 2)))
            cv2.circle(tint, center, radius, color, -1, cv2.LINE_AA)
            outlines.append(("circle", (center, radius), color))

    cv2.addWeighted(
        tint,
        F2_LIVE_ROI_OVERLAY_ALPHA,
        result,
        1.0 - F2_LIVE_ROI_OVERLAY_ALPHA,
        0.0,
        dst=result,
    )

    for kind, geometry, color in outlines:
        if kind == "segment":
            cv2.polylines(
                result,
                [geometry],
                True,
                color,
                2,
                cv2.LINE_AA,
            )
        else:
            center, radius = geometry
            cv2.circle(result, center, radius, color, 2, cv2.LINE_AA)

    return result


class SegmentDisplayOperationWindow(BlueRaspberryOperationWindow):
    """Prévia F2 capaz de desenhar simultaneamente círculos e segmentos."""

    def __init__(self, *args, **kwargs) -> None:
        self._live_roi_states: dict[str, str] = {}
        self._live_roi_overlay_enabled = False
        self._board_presence_status = "unknown"
        self._f2_analyzed_waiting_active = False
        super().__init__(*args, **kwargs)
        try:
            self.preview_legend.configure(text="AZUL: ROI APAGADA")
        except Exception:
            pass

        self.board_presence_label = tk.Label(
            self.preview_header,
            text="STATUS DA PLACA: IDENTIFICANDO...",
            font=("DejaVu Sans", 10, "bold"),
            bg=self.PREVIEW_PANEL,
            fg="#CBD5E1",
            anchor="w",
            justify="left",
        )
        self.board_presence_label.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(7, 0),
        )
        self.board_presence_label.grid_remove()

    def _set_state(
        self,
        background: str,
        foreground: str,
        status: str,
        detail: str,
    ) -> None:
        """Restaura uma linha antes de cada estado normal exclusivo do F2."""
        self._f2_analyzed_waiting_active = False
        label = getattr(self, "status_label", None)
        if label is not None:
            try:
                label.configure(height=1, wraplength=0, pady=0)
            except Exception:
                pass
        super()._set_state(
            background=background,
            foreground=foreground,
            status=status,
            detail=detail,
        )

    def _aplicar_status_pos_analise_f2(self, panel_width: int | None = None) -> None:
        if panel_width is None:
            try:
                panel_width = int(self.analysis_panel.winfo_width())
            except Exception:
                panel_width = 640
        if int(panel_width or 0) <= 2:
            panel_width = 640

        font_size = tamanho_fonte_status_analisado_f2(int(panel_width))
        self.status_label.configure(
            text=F2_ANALYZED_WAITING_TEXT,
            font=("DejaVu Sans", font_size, "bold"),
            height=2,
            pady=0,
            justify="center",
            anchor="center",
            wraplength=0,
        )

    def show_waiting(
        self,
        led_count: int,
        total: int,
        ok_count: int,
        ng_count: int,
    ) -> None:
        """Após resultado, orienta a troca da placa sem alterar o ciclo F2."""
        super().show_waiting(
            led_count=led_count,
            total=total,
            ok_count=ok_count,
            ng_count=ng_count,
        )
        if not (
            bool(getattr(self, "_has_led_result", False))
            and getattr(self, "_last_result_ok", None) is not None
        ):
            return
        self._f2_analyzed_waiting_active = True
        self._aplicar_status_pos_analise_f2()

    def _on_analysis_resize(self, event) -> None:
        super()._on_analysis_resize(event)
        if bool(getattr(self, "_f2_analyzed_waiting_active", False)):
            try:
                width = int(event.width)
            except (TypeError, ValueError, AttributeError):
                width = 640
            self._aplicar_status_pos_analise_f2(width)

    def set_board_presence_status(
        self,
        status: str | None,
        enabled: bool = True,
    ) -> None:
        """Mostra o estado físico da placa somente no F2 automático."""
        if not enabled:
            try:
                self.board_presence_label.grid_remove()
            except Exception:
                pass
            return

        normalized = str(status or "unknown").strip().lower()
        if normalized not in F2_BOARD_STATUS_UI:
            normalized = "unknown"
        self._board_presence_status = normalized
        text, color = F2_BOARD_STATUS_UI[normalized]
        try:
            self.board_presence_label.configure(
                text=f"STATUS DA PLACA: {text}",
                fg=color,
            )
            self.board_presence_label.grid()
        except Exception:
            pass

    def set_live_roi_states(
        self,
        states: dict[str, str] | None,
        enabled: bool = True,
    ) -> None:
        """Liga o overlay somente quando a análise automática F2 está ativa."""
        self._live_roi_states = {
            str(key): str(value).strip().upper()
            for key, value in dict(states or {}).items()
        }
        self._live_roi_overlay_enabled = bool(enabled)
        try:
            self.preview_legend.configure(
                text=(F2_LIVE_ROI_LEGEND if enabled else "AZUL: ROI APAGADA")
            )
        except Exception:
            pass

        if enabled:
            self.set_board_presence_status(
                self._board_presence_status,
                enabled=True,
            )
        else:
            self.set_board_presence_status(None, enabled=False)

    def update_preview(self, frame, leds=()) -> bool:
        if not self._live_roi_overlay_enabled:
            return super().update_preview(frame, leds)

        decorated = renderizar_overlay_rois_f2(
            frame,
            leds,
            self._live_roi_states,
        )
        # As ROIs já estão desenhadas no frame com transparência; não sobrepor
        # as guias legadas azul/ciano do modo manual.
        return super().update_preview(decorated, leds=())

    def _draw_guides(
        self,
        leds,
        frame_width: int,
        frame_height: int,
        scale: float,
        offset_x: int,
        offset_y: int,
    ) -> None:
        led_list = list(leds or ())
        if not led_list:
            return

        left = offset_x + int(frame_width * scale)
        top = offset_y + int(frame_height * scale)
        right = offset_x
        bottom = offset_y

        for led in led_list:
            led_id = str(getattr(led, "id", ""))
            center_x = offset_x + int(round(int(getattr(led, "centro_x", 0)) * scale))
            center_y = offset_y + int(round(int(getattr(led, "centro_y", 0)) * scale))
            failed = led_id in self._failed_led_ids
            color = self.PREVIEW_FAILED if failed else self.PREVIEW_GUIDE
            line_width = 3 if failed else 1
            tipo = normalizar_tipo_roi(getattr(led, "tipo_roi", None))

            bx1, by1, bx2, by2 = bbox_roi(led)
            left = min(left, offset_x + int(round(bx1 * scale)))
            top = min(top, offset_y + int(round(by1 * scale)))
            right = max(right, offset_x + int(round(bx2 * scale)))
            bottom = max(bottom, offset_y + int(round(by2 * scale)))

            if tipo == TIPO_ROI_SEGMENTO:
                coords = []
                for x, y in pontos_segmento(led):
                    coords.extend(
                        (
                            offset_x + float(x) * scale,
                            offset_y + float(y) * scale,
                        )
                    )
                self.preview_canvas.create_polygon(
                    *coords,
                    fill="",
                    outline=color,
                    width=line_width,
                    tags=("preview_guide",),
                )
                label_y = offset_y + int(round(by1 * scale)) - 9
            else:
                radius = max(
                    3,
                    int(round(int(getattr(led, "raio", 1)) * scale)),
                )
                self.preview_canvas.create_oval(
                    center_x - radius,
                    center_y - radius,
                    center_x + radius,
                    center_y + radius,
                    outline=color,
                    width=line_width,
                    tags=("preview_guide",),
                )
                label_y = center_y - radius - 9

            if failed:
                dot_radius = max(3, int(round(4 * max(1.0, scale))))
                self.preview_canvas.create_oval(
                    center_x - dot_radius,
                    center_y - dot_radius,
                    center_x + dot_radius,
                    center_y + dot_radius,
                    fill=self.PREVIEW_FAILED,
                    outline="#FFFFFF",
                    width=1,
                    tags=("preview_guide",),
                )
                self.preview_canvas.create_text(
                    center_x,
                    max(offset_y + 12, label_y),
                    text=f"{led_id} APAGADO",
                    fill="#FFFFFF",
                    font=("DejaVu Sans", 9, "bold"),
                    anchor="s",
                    tags=("preview_guide",),
                )

        margin = max(6, int(round(8 * scale)))
        self.preview_canvas.create_rectangle(
            left - margin,
            top - margin,
            right + margin,
            bottom + margin,
            outline=self.PREVIEW_BOARD_GUIDE,
            width=2,
            dash=(6, 4),
            tags=("preview_guide",),
        )