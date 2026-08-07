import tkinter as tk

from src.models.led_selection import LedSelection
from src.ui.main_window_parts.canvas.roi_shape_canvas import (
    desenhar_forma_roi_canvas,
    ponto_original_para_canvas,
)


TAG_MARCACOES = "marcacoes_canvas"


def desenhar_guias_leds_camera(
    self,
    leds_selecionados: list[LedSelection],
) -> None:
    tags = (TAG_MARCACOES,)

    for led in leds_selecionados:
        centro_x, centro_y = ponto_original_para_canvas(
            self,
            led.centro_x,
            led.centro_y,
        )
        id_led = str(getattr(led, "id", "LED"))
        numero_led = id_led.split("_")[-1] if "_" in id_led else id_led

        desenhar_forma_roi_canvas(
            self,
            led,
            self.COR_AMARELO,
            largura_linha=2,
            dash=(5, 4),
            tags=tags,
        )
        self.canvas.create_oval(
            centro_x - 4,
            centro_y - 4,
            centro_x + 4,
            centro_y + 4,
            fill=self.COR_AMARELO,
            outline="",
            tags=tags,
        )
        self.canvas.create_text(
            centro_x,
            centro_y - max(14, int(led.raio * self.escala_exibicao) + 8),
            text=numero_led,
            fill=self.COR_AMARELO,
            font=("Segoe UI", 7, "bold"),
            anchor=tk.CENTER,
            tags=tags,
        )
