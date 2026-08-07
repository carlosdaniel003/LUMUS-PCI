from src.models.led_selection import LedSelection
from src.ui.main_window_parts.image.rotacao_visual_principal import (
    obter_ponto_visual_view,
)


TAG_MARCACOES = "marcacoes_canvas"


def desenhar_led_selecionado(
    self,
    led_selecionado: LedSelection,
) -> None:
    centro_x_visual, centro_y_visual = obter_ponto_visual_view(
        self,
        led_selecionado.centro_x,
        led_selecionado.centro_y,
    )
    centro_x_canvas = (
        self.deslocamento_imagem_x
        + int(centro_x_visual * self.escala_exibicao)
    )
    centro_y_canvas = (
        self.deslocamento_imagem_y
        + int(centro_y_visual * self.escala_exibicao)
    )
    raio_canvas = max(
        3,
        int(
            led_selecionado.raio
            * self.escala_exibicao
        ),
    )

    id_led = getattr(led_selecionado, "id", "LED")
    numero_led = (
        id_led.split("_")[-1]
        if "_" in id_led
        else id_led
    )
    led_em_edicao_id = getattr(
        self,
        "led_em_edicao_id",
        None,
    )
    esta_selecionado = (
        led_em_edicao_id is not None
        and str(led_em_edicao_id) == str(id_led)
    )
    cor_marcacao = (
        self.COR_AMARELO
        if esta_selecionado
        else self.COR_AZUL
    )
    largura_linha = 3 if esta_selecionado else 2

    tags = (TAG_MARCACOES,)

    if esta_selecionado:
        margem_selecao = 5
        self.canvas.create_oval(
            centro_x_canvas - raio_canvas - margem_selecao,
            centro_y_canvas - raio_canvas - margem_selecao,
            centro_x_canvas + raio_canvas + margem_selecao,
            centro_y_canvas + raio_canvas + margem_selecao,
            outline=cor_marcacao,
            width=1,
            dash=(4, 3),
            tags=tags,
        )

    self.canvas.create_oval(
        centro_x_canvas - raio_canvas,
        centro_y_canvas - raio_canvas,
        centro_x_canvas + raio_canvas,
        centro_y_canvas + raio_canvas,
        outline=cor_marcacao,
        width=largura_linha,
        tags=tags,
    )

    self.canvas.create_line(
        centro_x_canvas - raio_canvas,
        centro_y_canvas,
        centro_x_canvas + raio_canvas,
        centro_y_canvas,
        fill=cor_marcacao,
        width=1,
        tags=tags,
    )

    self.canvas.create_line(
        centro_x_canvas,
        centro_y_canvas - raio_canvas,
        centro_x_canvas,
        centro_y_canvas + raio_canvas,
        fill=cor_marcacao,
        width=1,
        tags=tags,
    )

    self.canvas.create_oval(
        centro_x_canvas - 8,
        centro_y_canvas - 8,
        centro_x_canvas + 8,
        centro_y_canvas + 8,
        fill="#020617",
        outline=cor_marcacao,
        width=largura_linha,
        tags=tags,
    )

    self.canvas.create_text(
        centro_x_canvas,
        centro_y_canvas,
        text=numero_led,
        fill=cor_marcacao,
        font=("Segoe UI", 6, "bold"),
        tags=tags,
    )
