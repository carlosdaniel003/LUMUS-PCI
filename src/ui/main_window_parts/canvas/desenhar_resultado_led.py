import tkinter as tk

from src.models.analysis_result import LedAnalysisResult
from src.ui.main_window_parts.canvas.roi_shape_canvas import (
    desenhar_forma_roi_canvas,
    ponto_original_para_canvas,
)


TAG_MARCACOES = "marcacoes_canvas"
COR_NG_AZUL = "#3B82F6"
FUNDO_NG_AZUL = "#061A33"


def desenhar_resultado_led(
    self,
    resultado_led_atual: LedAnalysisResult,
) -> None:
    cor = (
        self.COR_VERDE_CLARO
        if resultado_led_atual.valor_binario == 1
        else COR_NG_AZUL
    )
    centro_x, centro_y = ponto_original_para_canvas(
        self,
        resultado_led_atual.centro_x,
        resultado_led_atual.centro_y,
    )
    id_led = str(getattr(resultado_led_atual, "id", "LED"))
    numero_led = id_led.split("_")[-1] if "_" in id_led else id_led
    largura_linha = 2 if resultado_led_atual.valor_binario == 1 else 4
    escala_forma = 1.0 if resultado_led_atual.valor_binario == 1 else 1.12
    tags = (TAG_MARCACOES,)

    desenhar_forma_roi_canvas(
        self,
        resultado_led_atual,
        cor,
        largura_linha=largura_linha,
        tags=tags,
        escala_forma=escala_forma,
    )

    raio_visual = max(
        6,
        int(resultado_led_atual.raio * self.escala_exibicao * escala_forma),
    )
    x_label = centro_x + raio_visual + 4
    y_label = centro_y - raio_visual - 4

    if resultado_led_atual.valor_binario == 0:
        texto = f"{numero_led} NG"
        largura_aproximada = max(42, len(texto) * 7)
        self.canvas.create_rectangle(
            x_label - 4,
            y_label - 16,
            x_label + largura_aproximada,
            y_label + 2,
            fill=FUNDO_NG_AZUL,
            outline=cor,
            width=1,
            tags=tags,
        )
        self.canvas.create_text(
            x_label,
            y_label - 8,
            text=texto,
            fill=cor,
            font=("Segoe UI", 8, "bold"),
            anchor=tk.W,
            tags=tags,
        )
        return

    self.canvas.create_oval(
        centro_x - 8,
        centro_y - 8,
        centro_x + 8,
        centro_y + 8,
        fill="#03120A",
        outline=cor,
        width=1,
        tags=tags,
    )
    self.canvas.create_text(
        centro_x,
        centro_y,
        text=numero_led,
        fill=cor,
        font=("Segoe UI", 6, "bold"),
        tags=tags,
    )
