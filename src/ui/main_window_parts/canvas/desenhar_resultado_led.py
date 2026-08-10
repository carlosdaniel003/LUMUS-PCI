import tkinter as tk

from src.models.analysis_result import LedAnalysisResult
from src.ui.main_window_parts.canvas.roi_shape_canvas import (
    desenhar_forma_roi_canvas,
    ponto_original_para_canvas,
)


TAG_MARCACOES = "marcacoes_canvas"
COR_NG_AZUL = "#38BDF8"
FUNDO_NG_AZUL = "#061A33"
COR_POUCA_LUZ = "#FBBF24"
FUNDO_POUCA_LUZ = "#3A2103"
STATUS_POUCA_LUZ = "POUCA_LUZ"


def desenhar_resultado_led(
    self,
    resultado_led_atual: LedAnalysisResult,
) -> None:
    status = str(getattr(resultado_led_atual, "status", "")).upper()
    pouca_luz = status == STATUS_POUCA_LUZ
    apagado = status == "APAGADO" or resultado_led_atual.valor_binario == 0

    if pouca_luz:
        cor = COR_POUCA_LUZ
    elif apagado:
        cor = COR_NG_AZUL
    else:
        cor = self.COR_VERDE_CLARO

    centro_x, centro_y = ponto_original_para_canvas(
        self,
        resultado_led_atual.centro_x,
        resultado_led_atual.centro_y,
    )
    id_led = str(getattr(resultado_led_atual, "id", "LED"))
    numero_led = id_led.split("_")[-1] if "_" in id_led else id_led

    falha = pouca_luz or apagado
    largura_linha = 4 if falha else 2
    escala_forma = 1.08 if pouca_luz else (1.12 if apagado else 1.0)
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

    if falha:
        texto = f"{numero_led} POUCA LUZ" if pouca_luz else f"{numero_led} NG"
        fundo = FUNDO_POUCA_LUZ if pouca_luz else FUNDO_NG_AZUL
        largura_aproximada = max(52, len(texto) * 7)
        self.canvas.create_rectangle(
            x_label - 4,
            y_label - 16,
            x_label + largura_aproximada,
            y_label + 2,
            fill=fundo,
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
