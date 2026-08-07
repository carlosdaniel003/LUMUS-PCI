from __future__ import annotations

from src.core.roi_geometry import (
    TIPO_ROI_SEGMENTO,
    bbox_roi,
    normalizar_tipo_roi,
    pontos_segmento,
)
from src.platform.blue_operation_window import BlueRaspberryOperationWindow


class SegmentDisplayOperationWindow(BlueRaspberryOperationWindow):
    """Prévia F2 capaz de desenhar simultaneamente círculos e segmentos."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        try:
            self.preview_legend.configure(text="AZUL: ROI APAGADA")
        except Exception:
            pass

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
