import base64

import cv2
import tkinter as tk


def _codificar_ppm_bgr(imagem_bgr) -> bytes:
    altura, largura = imagem_bgr.shape[:2]
    imagem_rgb = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2RGB)
    cabecalho = f"P6\n{largura} {altura}\n255\n".encode("ascii")
    return cabecalho + imagem_rgb.tobytes()


def _atualizar_photoimage_ppm(self, dados_ppm: bytes) -> bool:
    largura = int(self.largura_imagem_exibida)
    altura = int(self.altura_imagem_exibida)
    imagem_existente = getattr(self, "imagem_tk", None)
    mesma_resolucao = (
        imagem_existente is not None
        and getattr(self, "_imagem_tk_largura", None) == largura
        and getattr(self, "_imagem_tk_altura", None) == altura
    )

    try:
        if mesma_resolucao:
            imagem_existente.configure(
                data=dados_ppm,
                format="PPM",
            )
        else:
            self.imagem_tk = tk.PhotoImage(
                data=dados_ppm,
                format="PPM",
            )
            self._imagem_tk_largura = largura
            self._imagem_tk_altura = altura
        return True
    except tk.TclError:
        return False


def atualizar_imagem_principal_redimensionada(self) -> None:
    if self.imagem_canvas_original is None:
        return

    altura_canvas_original, largura_canvas_original = (
        self.imagem_canvas_original.shape[:2]
    )
    largura_disponivel, altura_disponivel = (
        self.obter_tamanho_canvas_principal()
    )

    escala_largura = largura_disponivel / largura_canvas_original
    escala_altura = altura_disponivel / altura_canvas_original
    self.escala_exibicao = min(escala_largura, escala_altura, 1.0)

    self.largura_imagem_exibida = max(
        1,
        int(largura_canvas_original * self.escala_exibicao),
    )
    self.altura_imagem_exibida = max(
        1,
        int(altura_canvas_original * self.escala_exibicao),
    )

    self.deslocamento_imagem_x = max(
        0,
        int(
            (largura_disponivel - self.largura_imagem_exibida) / 2
        ),
    )
    self.deslocamento_imagem_y = max(
        0,
        int(
            (altura_disponivel - self.altura_imagem_exibida) / 2
        ),
    )

    self.imagem_exibicao = cv2.resize(
        self.imagem_canvas_original,
        (
            self.largura_imagem_exibida,
            self.altura_imagem_exibida,
        ),
        interpolation=cv2.INTER_AREA,
    )

    # PPM evita compactação PNG e base64 a cada frame. Quando a resolução da
    # prévia não muda, o mesmo PhotoImage é atualizado em vez de ser recriado,
    # reduzindo as piscadas e o uso de CPU no modo de desenvolvimento.
    dados_ppm = _codificar_ppm_bgr(self.imagem_exibicao)
    if _atualizar_photoimage_ppm(self, dados_ppm):
        return

    # Fallback compatível para instalações Tk antigas que rejeitem PPM binário.
    sucesso, buffer = cv2.imencode(
        ".png",
        self.imagem_exibicao,
        [cv2.IMWRITE_PNG_COMPRESSION, 1],
    )
    if not sucesso:
        return

    imagem_base64 = base64.b64encode(buffer).decode("ascii")
    self.imagem_tk = tk.PhotoImage(data=imagem_base64)
    self._imagem_tk_largura = self.largura_imagem_exibida
    self._imagem_tk_altura = self.altura_imagem_exibida
