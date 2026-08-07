from src.core.roi_geometry import TIPO_ROI_SEGMENTO, normalizar_tipo_roi
from src.models.led_selection import LedSelection
from src.ui.main_window_parts.canvas.roi_shape_canvas import (
    desenhar_forma_roi_canvas,
    ponto_original_para_canvas,
)


TAG_MARCACOES = "marcacoes_canvas"


def desenhar_led_selecionado(
    self,
    led_selecionado: LedSelection,
) -> None:
    centro_x_canvas, centro_y_canvas = ponto_original_para_canvas(
        self,
        led_selecionado.centro_x,
        led_selecionado.centro_y,
    )
    id_led = str(getattr(led_selecionado, "id", "LED"))
    numero_led = id_led.split("_")[-1] if "_" in id_led else id_led
    esta_selecionado = (
        getattr(self, "led_em_edicao_id", None) is not None
        and str(self.led_em_edicao_id) == id_led
    )
    cor = self.COR_AMARELO if esta_selecionado else self.COR_AZUL
    largura_linha = 3 if esta_selecionado else 2
    tags = (TAG_MARCACOES,)

    if esta_selecionado:
        desenhar_forma_roi_canvas(
            self,
            led_selecionado,
            cor,
            largura_linha=1,
            dash=(4, 3),
            tags=tags,
            escala_forma=1.10,
        )

    desenhar_forma_roi_canvas(
        self,
        led_selecionado,
        cor,
        largura_linha=largura_linha,
        tags=tags,
    )

    if normalizar_tipo_roi(getattr(led_selecionado, "tipo_roi", None)) != TIPO_ROI_SEGMENTO:
        raio = max(3, int(led_selecionado.raio * self.escala_exibicao))
        self.canvas.create_line(
            centro_x_canvas - raio,
            centro_y_canvas,
            centro_x_canvas + raio,
            centro_y_canvas,
            fill=cor,
            width=1,
            tags=tags,
        )
        self.canvas.create_line(
            centro_x_canvas,
            centro_y_canvas - raio,
            centro_x_canvas,
            centro_y_canvas + raio,
            fill=cor,
            width=1,
            tags=tags,
        )

    self.canvas.create_oval(
        centro_x_canvas - 8,
        centro_y_canvas - 8,
        centro_x_canvas + 8,
        centro_y_canvas + 8,
        fill="#020617",
        outline=cor,
        width=largura_linha,
        tags=tags,
    )
    self.canvas.create_text(
        centro_x_canvas,
        centro_y_canvas,
        text=numero_led,
        fill=cor,
        font=("Segoe UI", 6, "bold"),
        tags=tags,
    )
