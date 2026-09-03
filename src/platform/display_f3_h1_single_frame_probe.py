from __future__ import annotations

import src.platform.display_auto_check_runtime as runtime_module
import src.platform.display_f3_live_diagnostic_trace as trace_module
import src.platform.display_f3_live_runtime_fix as live_runtime_module
from src.platform.display_auto_check_analyzer import (
    DisplayAutomaticCheckAnalyzer as LearnedDisplayAutomaticCheckAnalyzer,
)
from src.platform.display_f3_exact_check_template import F3_EXACT_TEMPLATE_SOURCE
from src.platform.display_project_repository import DISPLAY_CHECK_STATE_ON


F3_POSITIVE_PROBE_MODE_ON_MASKS = "expected_on_exact_template"


def frames_necessarios_sonda_positiva_f3(app, context: dict | None) -> int:
    """H1 e BLUE são capturados no primeiro frame positivo confiável.

    Esta regra vale somente para a sonda positiva. Ela nunca gera NG. Demais
    CHECKS estáveis mantêm dois frames para evitar avanço por leitura isolada.
    """
    if not isinstance(context, dict):
        return 2

    try:
        if app._display_auto_is_reference_gate(context):
            return 1
    except Exception:
        pass

    try:
        if app._display_auto_is_transient_check(context):
            return 1
    except Exception:
        pass

    return 2


def _contexto_sonda_positiva_rapida_f3(app, context: dict | None) -> bool:
    if not isinstance(context, dict):
        return False

    try:
        if app._display_auto_is_reference_gate(context):
            return True
    except Exception:
        pass

    try:
        return bool(app._display_auto_is_transient_check(context))
    except Exception:
        return False


def avaliar_sonda_positiva_f3(
    app,
    context: dict | None,
    analysis: dict | None,
) -> dict:
    """Define a autoridade positiva sem transformar diferença de foto em defeito.

    O gabarito exato é excelente para provar rapidamente que os segmentos que
    deveriam estar ACESOS apareceram. Ele não é, porém, um classificador de
    ACESO/APAGADO: uma região APAGADA ficar mais clara/escura que na fotografia
    de referência não significa que o segmento mudou de estado.

    Para H1 e CHECK transitório (BLUE), quando a análise veio especificamente do
    gabarito exato, a captura positiva exige que TODAS as máscaras esperadas
    ACESAS estejam conformes. As máscaras esperadas APAGADAS continuam no debug
    como diagnóstico fotométrico, mas não bloqueiam essa confirmação positiva.

    Qualquer análise semântica normal continua exigindo ``approved=True``; logo
    um verdadeiro ACESO onde deveria estar APAGADO não é ignorado pelo runtime.
    """
    if not isinstance(analysis, dict) or not bool(analysis.get("ready")):
        return {
            "approved": False,
            "mode": "unavailable",
            "on_total": 0,
            "on_matched": 0,
            "off_template_mismatches": 0,
        }

    original_approved = analysis.get("approved") is True
    exact_probe = (
        str(analysis.get("reference_authority") or "")
        == F3_EXACT_TEMPLATE_SOURCE
    )
    fast_context = _contexto_sonda_positiva_rapida_f3(app, context)

    results = [
        item
        for item in (analysis.get("mask_results") or [])
        if isinstance(item, dict)
    ]
    on_results = [
        item
        for item in results
        if str(item.get("expected") or "") == DISPLAY_CHECK_STATE_ON
    ]
    on_matched = sum(1 for item in on_results if bool(item.get("matched")))
    off_template_mismatches = sum(
        1
        for item in results
        if str(item.get("expected") or "") != DISPLAY_CHECK_STATE_ON
        and not bool(item.get("matched"))
    )

    use_on_only_positive_gate = bool(
        exact_probe
        and fast_context
        and on_results
    )
    approved = (
        on_matched == len(on_results)
        if use_on_only_positive_gate
        else original_approved
    )

    return {
        "approved": bool(approved),
        "mode": (
            F3_POSITIVE_PROBE_MODE_ON_MASKS
            if use_on_only_positive_gate
            else "full_analysis"
        ),
        "on_total": len(on_results),
        "on_matched": int(on_matched),
        "off_template_mismatches": int(off_template_mismatches),
        "exact_probe": bool(exact_probe),
        "fast_context": bool(fast_context),
        "original_approved": bool(original_approved),
    }


def atualizar_estabilidade_sonda_positiva_f3(
    app,
    context: dict | None,
    analysis: dict | None,
) -> dict:
    """Debounce da sonda positiva com semântica própria para H1/BLUE."""
    signature = None
    if isinstance(context, dict):
        signature = (
            str(context.get("project_name") or ""),
            str(context.get("check_id") or ""),
        )

    evidence = avaliar_sonda_positiva_f3(app, context, analysis)
    approved = bool(evidence.get("approved"))

    # Mantém a telemetria legível no DEBUG AO VIVO. Para a sonda exata rápida,
    # ``approved`` passa a significar somente confirmação positiva do estado;
    # preservamos explicitamente o resultado fotográfico de todas as máscaras.
    if isinstance(analysis, dict):
        analysis["exact_all_masks_approved"] = bool(
            evidence.get("original_approved")
        )
        analysis["positive_probe_approved"] = approved
        analysis["positive_probe_mode"] = str(evidence.get("mode") or "")
        analysis["positive_on_mask_count"] = int(evidence.get("on_total", 0) or 0)
        analysis["positive_on_matched_count"] = int(
            evidence.get("on_matched", 0) or 0
        )
        analysis["off_template_mismatch_count"] = int(
            evidence.get("off_template_mismatches", 0) or 0
        )
        if str(evidence.get("mode") or "") == F3_POSITIVE_PROBE_MODE_ON_MASKS:
            analysis["approved"] = approved
            if approved:
                analysis["reason"] = (
                    "sonda_positiva_segmentos_acesos_conformes_"
                    f"{evidence.get('on_matched', 0)}_de_{evidence.get('on_total', 0)}"
                )
            else:
                analysis["reason"] = (
                    "sonda_positiva_aguardando_segmentos_acesos_"
                    f"{evidence.get('on_matched', 0)}_de_{evidence.get('on_total', 0)}"
                )

    previous_signature = getattr(app, "_display_f3_live_probe_signature", None)
    frames = int(getattr(app, "_display_f3_live_probe_ok_frames", 0) or 0)
    required = frames_necessarios_sonda_positiva_f3(app, context)

    if signature is None or not approved:
        app._display_f3_live_probe_signature = signature
        app._display_f3_live_probe_ok_frames = 0
        return {
            "approved": approved,
            "frames": 0,
            "required": required,
            "confirm": False,
            "mode": evidence.get("mode"),
            "on_total": evidence.get("on_total", 0),
            "on_matched": evidence.get("on_matched", 0),
        }

    frames = frames + 1 if previous_signature == signature else 1
    app._display_f3_live_probe_signature = signature
    app._display_f3_live_probe_ok_frames = frames
    return {
        "approved": True,
        "frames": frames,
        "required": required,
        "confirm": frames >= required,
        "mode": evidence.get("mode"),
        "on_total": evidence.get("on_total", 0),
        "on_matched": evidence.get("on_matched", 0),
    }


def restaurar_analisador_semantico_runtime_f3() -> None:
    """NG volta a usar aprendizado ACESO/APAGADO/POUCA LUZ, não diferença de foto.

    A foto exata continua instalada como referência física e como sonda positiva
    invisível. Já a decisão oficial de máscara precisa vir do classificador
    aprendido, pois só ele possui estados semânticos reais e POUCA LUZ.
    """
    runtime_module.DisplayAutomaticCheckAnalyzer = LearnedDisplayAutomaticCheckAnalyzer
    live_runtime_module.DisplayAutomaticCheckAnalyzer = LearnedDisplayAutomaticCheckAnalyzer


_INSTALLED = False


def instalar_captura_h1_um_frame_display_f3() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    trace_module._probe_required_frames = frames_necessarios_sonda_positiva_f3
    trace_module._update_positive_probe_stability = (
        atualizar_estabilidade_sonda_positiva_f3
    )
    restaurar_analisador_semantico_runtime_f3()
    _INSTALLED = True
