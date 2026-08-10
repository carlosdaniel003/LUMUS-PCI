import cv2
import numpy as np

from src.core.roi_geometry import (
    TIPO_ROI_SEGMENTO,
    bbox_roi,
    criar_mascara_roi_global,
    normalizar_tipo_roi,
    pontos_segmento,
)
from src.models.analysis_result import LedAnalysisResult
from src.models.led_selection import LedSelection


AlvoLed = LedAnalysisResult | LedSelection | None
AlvosLed = AlvoLed | list[LedAnalysisResult] | list[LedSelection]

STATUS_ACESO = "ACESO"
STATUS_APAGADO = "APAGADO"
STATUS_POUCA_LUZ = "POUCA_LUZ"

# Paleta visual do ODIN em BGR (OpenCV):
# ACESO = verde, APAGADO = azul, POUCA_LUZ = amarelo.
COR_ACESO_BGR = (94, 197, 34)          # #22C55E
COR_APAGADO_BGR = (248, 189, 56)      # #38BDF8
COR_POUCA_LUZ_BGR = (36, 191, 251)    # #FBBF24
COR_SELECIONADO_BGR = (248, 189, 56)  # #38BDF8


def _normalizar_alvos(alvo: AlvosLed):
    if alvo is None:
        return []
    if isinstance(alvo, (list, tuple)):
        return [item for item in alvo if item is not None]
    return [alvo]


def _obter_dados_alvo(alvo: AlvoLed):
    if alvo is None:
        return None
    return {
        "id": str(getattr(alvo, "id", "LED")),
        "centro_x": int(alvo.centro_x),
        "centro_y": int(alvo.centro_y),
        "raio": int(alvo.raio),
        "tipo_roi": normalizar_tipo_roi(getattr(alvo, "tipo_roi", None)),
        "largura": getattr(alvo, "largura", None),
        "altura": getattr(alvo, "altura", None),
        "angulo": float(getattr(alvo, "angulo", 0.0) or 0.0),
        "valor_binario": int(getattr(alvo, "valor_binario", -1)),
        "status": str(getattr(alvo, "status", "SELECIONADO")),
        "confianca": getattr(alvo, "confianca", None),
    }


def _obter_estado_visual(dados) -> str:
    if dados is None:
        return "SELECIONADO"

    status = str(dados.get("status", "")).strip().upper().replace(" ", "_")
    valor_binario = int(dados.get("valor_binario", -1))

    # O status tem precedência sobre o binário. POUCA_LUZ mantém binário 1
    # porque ainda existe emissão luminosa, mas visualmente é uma falha NG.
    if status == STATUS_POUCA_LUZ:
        return STATUS_POUCA_LUZ
    if status == STATUS_APAGADO or valor_binario == 0:
        return STATUS_APAGADO
    if status == STATUS_ACESO or valor_binario == 1:
        return STATUS_ACESO
    return "SELECIONADO"


def _obter_cor_bgr(alvo: AlvoLed):
    dados = _obter_dados_alvo(alvo)
    estado = _obter_estado_visual(dados)
    if estado == STATUS_POUCA_LUZ:
        return COR_POUCA_LUZ_BGR
    if estado == STATUS_APAGADO:
        return COR_APAGADO_BGR
    if estado == STATUS_ACESO:
        return COR_ACESO_BGR
    return COR_SELECIONADO_BGR


def _obter_numero_led(alvo: AlvoLed) -> str:
    dados = _obter_dados_alvo(alvo)
    if dados is None:
        return ""
    id_led = dados["id"]
    return id_led.split("_")[-1] if "_" in id_led else id_led


def _desenhar_forma(imagem, alvo, cor, espessura=2, preencher=False, escala=1.0):
    dados = _obter_dados_alvo(alvo)
    if dados is None:
        return imagem
    if dados["tipo_roi"] == TIPO_ROI_SEGMENTO:
        pts = np.rint(pontos_segmento(alvo, escala=escala)).astype(np.int32)
        if preencher:
            cv2.fillConvexPoly(imagem, pts, cor)
        else:
            cv2.polylines(imagem, [pts], True, cor, int(espessura), cv2.LINE_AA)
        return imagem

    raio = max(1, int(round(dados["raio"] * float(escala))))
    cv2.circle(
        imagem,
        (dados["centro_x"], dados["centro_y"]),
        raio,
        cor,
        -1 if preencher else int(espessura),
    )
    return imagem


def _desenhar_marcacao_led(imagem, alvo: AlvoLed, com_texto: bool = True):
    dados = _obter_dados_alvo(alvo)
    if dados is None:
        return imagem

    estado = _obter_estado_visual(dados)
    cor = _obter_cor_bgr(alvo)
    if estado == STATUS_APAGADO:
        espessura = 3
        escala = 1.12
    elif estado == STATUS_POUCA_LUZ:
        espessura = 3
        escala = 1.08
    else:
        espessura = 2
        escala = 1.0

    _desenhar_forma(imagem, alvo, cor, espessura=espessura, escala=escala)
    cv2.drawMarker(
        imagem,
        (dados["centro_x"], dados["centro_y"]),
        cor,
        markerType=cv2.MARKER_CROSS,
        markerSize=max(8, int(dados["raio"] * 0.65)),
        thickness=1,
    )

    numero = _obter_numero_led(alvo)
    if com_texto and numero:
        largura_texto, altura_texto = cv2.getTextSize(
            numero, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1
        )[0]
        x1, y1, x2, _ = bbox_roi(alvo)
        x_texto = max(4, int((x1 + x2 - largura_texto) / 2))
        y_texto = max(14, y1 - 6)
        cv2.rectangle(
            imagem,
            (x_texto - 3, y_texto - altura_texto - 3),
            (x_texto + largura_texto + 3, y_texto + 3),
            (3, 7, 18),
            -1,
        )
        cv2.putText(
            imagem,
            numero,
            (x_texto, y_texto),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            cor,
            1,
            cv2.LINE_AA,
        )
    return imagem


def _desenhar_marcacoes_leds(imagem, alvos: AlvosLed, com_texto: bool = True):
    for alvo in _normalizar_alvos(alvos):
        _desenhar_marcacao_led(imagem, alvo, com_texto=com_texto)
    return imagem


def criar_imagem_resultado_visual(imagem_original, resultado_led: LedAnalysisResult):
    return criar_imagem_resultados_visuais(imagem_original, [resultado_led])


def criar_imagem_resultados_visuais(imagem_original, resultados_led):
    imagem_resultado = imagem_original.copy()
    for resultado in resultados_led:
        dados = _obter_dados_alvo(resultado)
        estado = _obter_estado_visual(dados)
        cor = _obter_cor_bgr(resultado)

        if estado == STATUS_APAGADO:
            alpha = 0.35
            escala = 1.12
        elif estado == STATUS_POUCA_LUZ:
            alpha = 0.30
            escala = 1.08
        else:
            alpha = 0.12
            escala = 1.08

        camada = imagem_resultado.copy()
        _desenhar_forma(
            camada,
            resultado,
            cor,
            preencher=True,
            escala=escala,
        )
        imagem_resultado = cv2.addWeighted(
            camada, alpha, imagem_resultado, 1.0 - alpha, 0
        )
    return _desenhar_marcacoes_leds(
        imagem_resultado, resultados_led, com_texto=False
    )


def criar_imagem_canal_v(imagem_original, alvo: AlvosLed = None):
    hsv = cv2.cvtColor(imagem_original, cv2.COLOR_BGR2HSV)
    canal_v = hsv[:, :, 2]
    imagem_canal_v = cv2.cvtColor(canal_v, cv2.COLOR_GRAY2BGR)
    return _desenhar_marcacoes_leds(imagem_canal_v, alvo)


def criar_heatmap_intensidade(imagem_original, alvo: AlvosLed = None):
    hsv = cv2.cvtColor(imagem_original, cv2.COLOR_BGR2HSV)
    canal_v = cv2.GaussianBlur(hsv[:, :, 2], (5, 5), 0)
    normalizado = cv2.normalize(
        canal_v, None, 0, 255, cv2.NORM_MINMAX
    ).astype(np.uint8)
    heatmap = cv2.applyColorMap(normalizado, cv2.COLORMAP_JET)
    return _desenhar_marcacoes_leds(heatmap, alvo)


def criar_imagem_mascara(imagem_original, resultado_led: LedAnalysisResult):
    return criar_imagem_mascara_multiplos(imagem_original, [resultado_led])


def criar_imagem_mascara_multiplos(imagem_original, alvos: AlvosLed):
    altura, largura = imagem_original.shape[:2]
    mascara = np.zeros((altura, largura), dtype=np.uint8)
    for alvo in _normalizar_alvos(alvos):
        mascara = cv2.bitwise_or(
            mascara,
            criar_mascara_roi_global(alvo, largura, altura),
        )
    return mascara


def criar_imagem_mascara_visual(imagem_original, alvo: AlvosLed = None):
    alvos = _normalizar_alvos(alvo)
    altura, largura = imagem_original.shape[:2]
    imagem_mascara = cv2.convertScaleAbs(imagem_original, alpha=0.24, beta=0)

    if not alvos:
        cv2.putText(
            imagem_mascara,
            "ROI ainda nao selecionado",
            (30, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (203, 213, 225),
            2,
            cv2.LINE_AA,
        )
        return imagem_mascara

    mascara = criar_imagem_mascara_multiplos(imagem_original, alvos)
    imagem_mascara[mascara > 0] = imagem_original[mascara > 0]

    for item in alvos:
        cor = _obter_cor_bgr(item)
        _desenhar_forma(imagem_mascara, item, cor, espessura=2)
        _desenhar_forma(
            imagem_mascara, item, (255, 255, 0), espessura=1, escala=0.62
        )
        cv2.drawMarker(
            imagem_mascara,
            (int(item.centro_x), int(item.centro_y)),
            (255, 255, 255),
            cv2.MARKER_CROSS,
            14,
            1,
        )
        x1, y1, x2, _ = bbox_roi(item)
        cv2.putText(
            imagem_mascara,
            str(getattr(item, "id", "ROI")),
            (max(10, x2 + 8), max(25, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return imagem_mascara


def criar_imagem_roi_debug(imagem_original, resultado_led: AlvoLed):
    if resultado_led is None:
        return np.zeros((120, 120, 3), dtype=np.uint8)
    altura, largura = imagem_original.shape[:2]
    bx1, by1, bx2, by2 = bbox_roi(resultado_led)
    margem = max(30, int(getattr(resultado_led, "raio", 10)) * 2)
    x1 = max(0, bx1 - margem)
    y1 = max(0, by1 - margem)
    x2 = min(largura, bx2 + margem + 1)
    y2 = min(altura, by2 + margem + 1)
    roi_debug = imagem_original[y1:y2, x1:x2].copy()
    if roi_debug.size == 0:
        return np.zeros((120, 120, 3), dtype=np.uint8)

    # Cria proxy local para reutilizar a mesma geometria sem mutar o alvo.
    proxy = LedSelection(
        id=str(getattr(resultado_led, "id", "ROI")),
        centro_x=int(resultado_led.centro_x) - x1,
        centro_y=int(resultado_led.centro_y) - y1,
        raio=int(resultado_led.raio),
        tipo_roi=getattr(resultado_led, "tipo_roi", "circulo"),
        largura=getattr(resultado_led, "largura", None),
        altura=getattr(resultado_led, "altura", None),
        angulo=float(getattr(resultado_led, "angulo", 0.0) or 0.0),
    )
    cor = _obter_cor_bgr(resultado_led)
    _desenhar_forma(roi_debug, proxy, cor, espessura=2)
    _desenhar_forma(roi_debug, proxy, (255, 255, 0), espessura=1, escala=0.62)
    cv2.drawMarker(
        roi_debug,
        (proxy.centro_x, proxy.centro_y),
        cor,
        cv2.MARKER_CROSS,
        12,
        1,
    )
    cv2.putText(
        roi_debug,
        proxy.id,
        (5, 18),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        cor,
        1,
        cv2.LINE_AA,
    )
    return roi_debug


def criar_imagem_roi_debug_sem_alvo(imagem_original):
    imagem_debug = imagem_original.copy()
    cv2.rectangle(
        imagem_debug,
        (18, 18),
        (min(imagem_debug.shape[1] - 18, 620), 102),
        (3, 7, 18),
        -1,
    )
    cv2.putText(
        imagem_debug,
        "ROI ainda nao selecionado",
        (30, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (56, 189, 248),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        imagem_debug,
        "Selecione uma ROI para exibir a lupa tecnica",
        (30, 82),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (203, 213, 225),
        1,
        cv2.LINE_AA,
    )
    return imagem_debug


def _redimensionar_preservando_proporcao(
    imagem,
    largura_maxima: int,
    altura_maxima: int,
    ampliar: bool = True,
):
    altura, largura = imagem.shape[:2]
    if largura <= 0 or altura <= 0:
        return imagem
    escala = min(largura_maxima / largura, altura_maxima / altura)
    if not ampliar:
        escala = min(escala, 1.0)
    largura_final = max(1, int(round(largura * escala)))
    altura_final = max(1, int(round(altura * escala)))
    interpolacao = cv2.INTER_NEAREST if escala >= 1.0 else cv2.INTER_AREA
    return cv2.resize(
        imagem,
        (largura_final, altura_final),
        interpolation=interpolacao,
    )


def criar_imagem_roi_debug_ampliado(
    imagem_original,
    alvo: AlvoLed = None,
    fator_escala: int = 5,
):
    dados = _obter_dados_alvo(alvo)
    if dados is None:
        return criar_imagem_roi_debug_sem_alvo(imagem_original)

    imagem_debug = imagem_original.copy()
    altura, largura = imagem_debug.shape[:2]
    cor = _obter_cor_bgr(alvo)
    _desenhar_marcacao_led(imagem_debug, alvo, com_texto=True)
    roi_debug = criar_imagem_roi_debug(imagem_original, alvo)
    if roi_debug.size == 0:
        return imagem_debug

    largura_maxima = max(
        120,
        min(int(largura * 0.42), roi_debug.shape[1] * max(1, fator_escala)),
    )
    altura_maxima = max(
        100,
        min(int(altura * 0.42), roi_debug.shape[0] * max(1, fator_escala)),
    )
    lupa = _redimensionar_preservando_proporcao(
        roi_debug, largura_maxima, altura_maxima, ampliar=True
    )
    altura_lupa, largura_lupa = lupa.shape[:2]
    margem = max(8, int(min(largura, altura) * 0.02))
    x1 = margem if dados["centro_x"] >= largura / 2 else max(
        margem, largura - largura_lupa - margem
    )
    y1 = margem + 24
    if y1 + altura_lupa + margem > altura:
        y1 = max(margem, altura - altura_lupa - margem)
    x2 = min(largura, x1 + largura_lupa)
    y2 = min(altura, y1 + altura_lupa)
    lupa = lupa[: y2 - y1, : x2 - x1]

    cv2.rectangle(
        imagem_debug,
        (max(0, x1 - 5), max(0, y1 - 25)),
        (min(largura - 1, x2 + 5), min(altura - 1, y2 + 5)),
        (3, 7, 18),
        -1,
    )
    imagem_debug[y1:y2, x1:x2] = lupa
    cv2.rectangle(
        imagem_debug,
        (x1, y1),
        (max(x1, x2 - 1), max(y1, y2 - 1)),
        cor,
        2,
    )
    cv2.putText(
        imagem_debug,
        f"LUPA {dados['id']}",
        (x1, max(16, y1 - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        cor,
        1,
        cv2.LINE_AA,
    )
    return imagem_debug


def _obter_ultimo_alvo(alvo: AlvosLed):
    alvos = _normalizar_alvos(alvo)
    return alvos[-1] if alvos else None


def criar_pacote_renderizacoes_visuais(imagem_original, alvo: AlvosLed = None) -> dict:
    ultimo = _obter_ultimo_alvo(alvo)
    alvos = _normalizar_alvos(alvo)
    renderizacoes = {
        "canal_v": criar_imagem_canal_v(imagem_original, alvos),
        "heatmap": criar_heatmap_intensidade(imagem_original, alvos),
        "mascara": criar_imagem_mascara_visual(imagem_original, alvos),
        "roi_debug": (
            criar_imagem_roi_debug_ampliado(imagem_original, ultimo)
            if ultimo is not None
            else criar_imagem_roi_debug_sem_alvo(imagem_original)
        ),
    }
    renderizacoes["overlay"] = (
        criar_imagem_resultados_visuais(imagem_original, alvos)
        if alvos and all(isinstance(item, LedAnalysisResult) for item in alvos)
        else None
    )
    return renderizacoes
