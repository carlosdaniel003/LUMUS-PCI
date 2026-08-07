from __future__ import annotations

import cv2
import tkinter as tk


ROTACOES_VISUAIS = (0, 90, 180, 270)


def normalizar_rotacao_visual(valor) -> int:
    try:
        rotacao = int(valor) % 360
    except (TypeError, ValueError):
        return 0
    return rotacao if rotacao in ROTACOES_VISUAIS else 0


def proxima_rotacao_visual(valor) -> int:
    atual = normalizar_rotacao_visual(valor)
    indice = ROTACOES_VISUAIS.index(atual)
    return ROTACOES_VISUAIS[(indice + 1) % len(ROTACOES_VISUAIS)]


def dimensoes_visuais(
    largura_original: int,
    altura_original: int,
    rotacao: int,
) -> tuple[int, int]:
    largura = max(1, int(largura_original))
    altura = max(1, int(altura_original))
    angulo = normalizar_rotacao_visual(rotacao)
    if angulo in (90, 270):
        return altura, largura
    return largura, altura


def rotacionar_imagem_visual(imagem, rotacao: int):
    """Rotaciona somente a cópia usada na interface; não altera a fonte."""
    if imagem is None:
        return None
    angulo = normalizar_rotacao_visual(rotacao)
    if angulo == 90:
        return cv2.rotate(imagem, cv2.ROTATE_90_CLOCKWISE)
    if angulo == 180:
        return cv2.rotate(imagem, cv2.ROTATE_180)
    if angulo == 270:
        return cv2.rotate(imagem, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return imagem


def converter_ponto_original_para_visual(
    x: float,
    y: float,
    largura_original: int,
    altura_original: int,
    rotacao: int,
) -> tuple[float, float]:
    largura = max(1, int(largura_original))
    altura = max(1, int(altura_original))
    angulo = normalizar_rotacao_visual(rotacao)
    x = float(x)
    y = float(y)

    if angulo == 90:
        return float(altura - 1) - y, x
    if angulo == 180:
        return float(largura - 1) - x, float(altura - 1) - y
    if angulo == 270:
        return y, float(largura - 1) - x
    return x, y


def converter_ponto_visual_para_original(
    x: float,
    y: float,
    largura_original: int,
    altura_original: int,
    rotacao: int,
) -> tuple[float, float]:
    largura = max(1, int(largura_original))
    altura = max(1, int(altura_original))
    angulo = normalizar_rotacao_visual(rotacao)
    x = float(x)
    y = float(y)

    if angulo == 90:
        return y, float(altura - 1) - x
    if angulo == 180:
        return float(largura - 1) - x, float(altura - 1) - y
    if angulo == 270:
        return float(largura - 1) - y, x
    return x, y


def converter_delta_visual_para_original(
    delta_x_visual: int,
    delta_y_visual: int,
    rotacao: int,
) -> tuple[int, int]:
    """Converte um deslocamento visto na tela para o referencial da câmera."""
    dx = int(delta_x_visual)
    dy = int(delta_y_visual)
    angulo = normalizar_rotacao_visual(rotacao)

    if angulo == 90:
        return dy, -dx
    if angulo == 180:
        return -dx, -dy
    if angulo == 270:
        return -dy, dx
    return dx, dy


def obter_ponto_visual_view(
    self,
    x: float,
    y: float,
) -> tuple[float, float]:
    imagem = getattr(self, "imagem_canvas_original", None)
    if imagem is None:
        return float(x), float(y)
    altura, largura = imagem.shape[:2]
    return converter_ponto_original_para_visual(
        x,
        y,
        largura,
        altura,
        getattr(self, "rotacao_visual_principal", 0),
    )


def obter_ponto_canvas_view(
    self,
    x: float,
    y: float,
) -> tuple[float, float]:
    """Projeta uma coordenada real da imagem no Canvas atualmente rotacionado."""
    visual_x, visual_y = obter_ponto_visual_view(self, x, y)
    escala = max(
        0.000001,
        float(getattr(self, "escala_exibicao", 1.0)),
    )
    return (
        float(getattr(self, "deslocamento_imagem_x", 0))
        + visual_x * escala,
        float(getattr(self, "deslocamento_imagem_y", 0))
        + visual_y * escala,
    )


def obter_retangulo_canvas_view(
    self,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> tuple[float, float, float, float]:
    """Projeta um retângulo da imagem e normaliza suas bordas no Canvas."""
    pontos = (
        obter_ponto_canvas_view(self, x1, y1),
        obter_ponto_canvas_view(self, x2, y1),
        obter_ponto_canvas_view(self, x2, y2),
        obter_ponto_canvas_view(self, x1, y2),
    )
    xs = [ponto[0] for ponto in pontos]
    ys = [ponto[1] for ponto in pontos]
    return min(xs), min(ys), max(xs), max(ys)


def atualizar_botao_rotacao_principal(self) -> None:
    botao = getattr(self, "botao_rotacao_principal", None)
    if botao is None:
        return
    angulo = normalizar_rotacao_visual(
        getattr(self, "rotacao_visual_principal", 0)
    )
    try:
        botao.config(text=f"↻ {angulo}°")
    except Exception:
        pass


def _atualizar_fundo_e_imagem_canvas(self) -> None:
    canvas = getattr(self, "canvas", None)
    imagem_tk = getattr(self, "imagem_tk", None)
    if canvas is None or imagem_tk is None:
        return

    largura_canvas, altura_canvas = self.obter_tamanho_canvas_principal()
    fundos = canvas.find_withtag("fundo_canvas")
    if fundos:
        fundo = fundos[0]
        canvas.coords(fundo, 0, 0, largura_canvas, altura_canvas)
        canvas.itemconfigure(fundo, fill="#020617", outline="")
    else:
        fundo = canvas.create_rectangle(
            0,
            0,
            largura_canvas,
            altura_canvas,
            fill="#020617",
            outline="",
            tags=("fundo_canvas",),
        )

    imagens = canvas.find_withtag("imagem_canvas")
    if imagens:
        item_imagem = imagens[0]
        canvas.coords(
            item_imagem,
            self.deslocamento_imagem_x,
            self.deslocamento_imagem_y,
        )
        canvas.itemconfigure(
            item_imagem,
            image=imagem_tk,
            anchor=tk.NW,
        )
    else:
        item_imagem = canvas.create_image(
            self.deslocamento_imagem_x,
            self.deslocamento_imagem_y,
            image=imagem_tk,
            anchor=tk.NW,
            tags=("imagem_canvas",),
        )

    canvas.tag_lower(fundo)
    canvas.tag_raise(item_imagem, fundo)


def redesenhar_rotacao_visual_principal(self) -> None:
    """Redesenha imagem e marcações sem atualizar histórico/KPIs."""
    if getattr(self, "imagem_canvas_original", None) is None:
        return

    self.atualizar_imagem_principal_redimensionada()
    _atualizar_fundo_e_imagem_canvas(self)

    canvas = getattr(self, "canvas", None)
    if canvas is None:
        return

    canvas.delete("marcacoes_canvas")
    canvas.delete("lupa_canvas")

    resultados = getattr(self, "ultimo_resultado_led_atual", None)
    leds = getattr(self, "ultimo_led_selecionado", None)
    resultados_normalizados = self._normalizar_resultados_led(resultados)
    leds_normalizados = self._normalizar_leds_selecionados(leds)

    if resultados_normalizados:
        self.desenhar_resultados_led(resultados_normalizados)
    elif leds_normalizados:
        selecao_manual_camera = bool(
            getattr(self, "selecao_manual_camera_visivel", False)
        )
        if (
            getattr(self, "tela_ao_vivo_ativa", False)
            and not selecao_manual_camera
        ):
            self.desenhar_guias_leds_camera(leds_normalizados)
        else:
            self.desenhar_leds_selecionados(leds_normalizados)


def definir_rotacao_visual_principal(
    self,
    rotacao: int,
    notificar: bool = False,
) -> None:
    """Troca somente a orientação apresentada no Canvas principal."""
    angulo = normalizar_rotacao_visual(rotacao)
    if angulo == getattr(self, "rotacao_visual_principal", 0):
        atualizar_botao_rotacao_principal(self)
        return

    self.rotacao_visual_principal = angulo
    atualizar_botao_rotacao_principal(self)
    redesenhar_rotacao_visual_principal(self)

    atualizar_fullscreen = getattr(
        self,
        "atualizar_imagem_tela_cheia_se_aberta",
        None,
    )
    if callable(atualizar_fullscreen):
        atualizar_fullscreen("principal")

    if notificar:
        atualizar_status = getattr(self, "atualizar_status", None)
        if callable(atualizar_status):
            atualizar_status(
                f"Imagem principal rotacionada visualmente para {angulo}°. "
                "Câmera, análise e posições das ROIs não foram alteradas."
            )


def rotacionar_imagem_principal(self) -> None:
    if bool(getattr(self, "selecao_led_ativa", False)):
        atualizar_status = getattr(self, "atualizar_status", None)
        if callable(atualizar_status):
            atualizar_status(
                "Finalize o modo Selecionar LEDs antes de rotacionar a visualização."
            )
        return

    definir_rotacao_visual_principal(
        self,
        proxima_rotacao_visual(
            getattr(self, "rotacao_visual_principal", 0)
        ),
        notificar=True,
    )
