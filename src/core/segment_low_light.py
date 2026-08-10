from __future__ import annotations

from dataclasses import dataclass

from src.core.roi_geometry import TIPO_ROI_SEGMENTO, normalizar_tipo_roi


STATUS_ACESO = "ACESO"
STATUS_APAGADO = "APAGADO"
STATUS_POUCA_LUZ = "POUCA_LUZ"

# Perfil óptico calibrado para o display vermelho de 7 segmentos usado na
# branch display. Segmentos saudáveis aparecem muito claros/quase saturados;
# quando perdem intensidade, a emissão vermelha volta a ficar evidente.
# Os limites abaixo foram escolhidos para separar os exemplos J23/J25/J27/
# J28/J29 sem reclassificar o SEG_015, que possui brilho global baixo por
# enquadramento da ROI mas não apresenta a assinatura cromática vermelha.
LIMITE_SATURACAO_POUCA_LUZ = 120.0
LIMITE_HUE_VERMELHO_BAIXO = 12.0
LIMITE_HUE_VERMELHO_ALTO = 145.0
LIMITE_V_MEAN_SAUDAVEL = 248.0
LIMITE_GLOW_SAUDAVEL = 230.0
LIMITE_PERCENT_HOT_250_SAUDAVEL = 0.80
MIN_EVIDENCIAS_OPTICAS = 2
MIN_SCORE_FALHA = 0.85


@dataclass(frozen=True)
class SegmentLowLightEvaluation:
    falha: bool
    indice_luminosidade: float
    score_falha: float
    evidencias_opticas: int
    assinatura_vermelha: bool
    motivo: str


def _limitar_01(valor: float) -> float:
    return max(0.0, min(1.0, float(valor)))


def _hue_em_faixa_vermelha(h_mean: float) -> bool:
    # OpenCV usa Hue no intervalo 0..179; vermelho cruza as duas extremidades.
    hue = float(h_mean) % 180.0
    return hue <= LIMITE_HUE_VERMELHO_BAIXO or hue >= LIMITE_HUE_VERMELHO_ALTO


def avaliar_pouca_luz_segmento(features) -> SegmentLowLightEvaluation:
    v_mean = float(getattr(features, "v_mean", 0.0))
    s_mean = float(getattr(features, "s_mean", 0.0))
    h_mean = float(getattr(features, "h_mean", 0.0))
    glow = float(getattr(features, "glow_score", 0.0))
    hot_250 = float(getattr(features, "percent_hot_250", 0.0))

    assinatura_vermelha = (
        s_mean >= LIMITE_SATURACAO_POUCA_LUZ
        and _hue_em_faixa_vermelha(h_mean)
    )

    brilho_reduzido = v_mean < LIMITE_V_MEAN_SAUDAVEL
    glow_reduzido = glow < LIMITE_GLOW_SAUDAVEL
    area_quente_reduzida = hot_250 < LIMITE_PERCENT_HOT_250_SAUDAVEL
    evidencias_opticas = sum(
        1
        for evidencia in (
            brilho_reduzido,
            glow_reduzido,
            area_quente_reduzida,
        )
        if evidencia
    )

    # Índice 0..1 de intensidade em relação ao perfil mínimo considerado
    # saudável. É apenas diagnóstico; a classe é decidida pela combinação das
    # evidências ópticas com a assinatura cromática.
    indice_luminosidade = (
        _limitar_01(v_mean / LIMITE_V_MEAN_SAUDAVEL) * 0.35
        + _limitar_01(glow / LIMITE_GLOW_SAUDAVEL) * 0.30
        + _limitar_01(hot_250 / LIMITE_PERCENT_HOT_250_SAUDAVEL) * 0.35
    )

    score_falha = 0.0
    if s_mean >= LIMITE_SATURACAO_POUCA_LUZ:
        score_falha += 0.25
    if _hue_em_faixa_vermelha(h_mean):
        score_falha += 0.30
    if brilho_reduzido:
        score_falha += 0.15
    if glow_reduzido:
        score_falha += 0.15
    if area_quente_reduzida:
        score_falha += 0.15
    score_falha = _limitar_01(score_falha)

    falha = (
        assinatura_vermelha
        and evidencias_opticas >= MIN_EVIDENCIAS_OPTICAS
        and score_falha >= MIN_SCORE_FALHA
    )

    if falha:
        motivo = (
            "segmento aceso com baixa luminosidade: emissão vermelha preservada "
            f"e {evidencias_opticas}/3 indicadores ópticos abaixo do perfil saudável"
        )
    else:
        motivo = "luminosidade do segmento dentro do perfil saudável"

    return SegmentLowLightEvaluation(
        falha=bool(falha),
        indice_luminosidade=round(float(indice_luminosidade), 4),
        score_falha=round(float(score_falha), 4),
        evidencias_opticas=int(evidencias_opticas),
        assinatura_vermelha=bool(assinatura_vermelha),
        motivo=motivo,
    )


def aplicar_diagnostico_pouca_luz(resultado, tipo_roi=None):
    """Converte ACESO em POUCA_LUZ somente para ROIs do tipo segmento.

    ``valor_binario`` permanece 1 porque existe emissão luminosa. O status é
    que passa a carregar a falha de qualidade; por isso produção e NG devem
    considerar ``status != ACESO`` como falha.
    """
    tipo = normalizar_tipo_roi(
        tipo_roi if tipo_roi is not None else getattr(resultado, "tipo_roi", None)
    )

    if tipo != TIPO_ROI_SEGMENTO or str(getattr(resultado, "status", "")) != STATUS_ACESO:
        resultado.falha_luminosidade = False
        resultado.indice_luminosidade = 1.0 if str(getattr(resultado, "status", "")) == STATUS_ACESO else 0.0
        resultado.score_falha_luminosidade = 0.0
        return resultado

    avaliacao = avaliar_pouca_luz_segmento(resultado.features)
    resultado.falha_luminosidade = bool(avaliacao.falha)
    resultado.indice_luminosidade = float(avaliacao.indice_luminosidade)
    resultado.score_falha_luminosidade = float(avaliacao.score_falha)

    if avaliacao.falha:
        resultado.status = STATUS_POUCA_LUZ
        resultado.valor_binario = 1
        motivos = list(getattr(resultado, "motivos", []) or [])
        motivos.append(avaliacao.motivo)
        resultado.motivos = motivos

    return resultado
