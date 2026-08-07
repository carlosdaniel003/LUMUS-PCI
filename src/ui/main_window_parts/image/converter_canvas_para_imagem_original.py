from src.ui.main_window_parts.image.rotacao_visual_principal import (
    converter_ponto_visual_para_original,
)


def converter_canvas_para_imagem_original(self, canvas_x: int, canvas_y: int):
    if self.imagem_canvas_original is None:
        return None

    x_relativo = canvas_x - self.deslocamento_imagem_x
    y_relativo = canvas_y - self.deslocamento_imagem_y

    if x_relativo < 0 or y_relativo < 0:
        return None

    if (
        x_relativo >= self.largura_imagem_exibida
        or y_relativo >= self.altura_imagem_exibida
    ):
        return None

    if self.escala_exibicao <= 0:
        return None

    x_visual = float(x_relativo) / self.escala_exibicao
    y_visual = float(y_relativo) / self.escala_exibicao

    altura_original, largura_original = self.imagem_canvas_original.shape[:2]
    centro_x, centro_y = converter_ponto_visual_para_original(
        x_visual,
        y_visual,
        largura_original,
        altura_original,
        getattr(self, "rotacao_visual_principal", 0),
    )

    centro_x = min(largura_original - 1, max(0, int(round(centro_x))))
    centro_y = min(altura_original - 1, max(0, int(round(centro_y))))
    return centro_x, centro_y
