from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import time

import src.platform.display_f3_live_diagnostic_trace as trace_module
from src.platform.display_f3_debug_toggle import debug_tecnico_ativo_display_f3


F3_PERF_DEBUG_REFRESH_MS = 1200
F3_PERF_TRACE_MAX_FRAMES = 96
F3_PERF_TRACE_DETAIL_FRAMES = 12
F3_PERF_TRACE_SAMPLE_INTERVAL_S = 0.18
F3_PERF_PROBE_PAUSE_REASON = "sonda_pausada_para_performance"


def _contexto_exige_sonda_rapida_f3(app, context: dict | None) -> bool:
    """H1 e CHECKS transitórios preservam a sonda positiva mesmo sem debug."""
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


def sonda_oculta_permitida_display_f3(app, context: dict | None = None) -> bool:
    """Controla a sonda cara sem sacrificar a captura operacional de H1/BLUE.

    Fora da produção a sonda fica sempre pausada. Durante a produção, DEBUG ON
    libera o diagnóstico completo. Com DEBUG OFF, somente H1 e CHECKS transitórios
    conservam o gabarito exato positivo necessário à captura rápida.
    """
    if not bool(getattr(app, "display_f3_ativo", False)):
        return False
    if getattr(app, "display_f3_result_after_id", None) is not None:
        return False
    if bool(getattr(app, "_display_f3_waiting_empty_rearm", False)):
        return False
    if bool(getattr(app, "_display_f3_waiting_new_board_after_empty", False)):
        return False

    try:
        if bool(app._display_auto_configuration_open()):
            return False
    except Exception:
        pass

    window = getattr(app, "display_f3_window", None)
    if window is not None and hasattr(window, "visible"):
        try:
            if not bool(window.visible):
                return False
        except Exception:
            pass

    if debug_tecnico_ativo_display_f3(app):
        return True
    return _contexto_exige_sonda_rapida_f3(app, context)


def _analise_sonda_pausada(context: dict | None) -> dict:
    return {
        "ready": False,
        "approved": None,
        "reason": F3_PERF_PROBE_PAUSE_REASON,
        "check_id": str((context or {}).get("check_id") or ""),
        "check_name": str((context or {}).get("check_name") or ""),
        "matched_mask_count": 0,
        "active_mask_count": 0,
        "mask_results": [],
        "reference_authority": "f3_probe_paused_for_ui_performance",
    }


def _mask_snapshot(item: dict) -> dict:
    return {
        "mask_id": str(item.get("mask_id", item.get("id", ""))),
        "expected": item.get("expected"),
        "classified": item.get("classified"),
        "matched": bool(item.get("matched")),
        "confidence": trace_module._safe_float(item.get("confidence")),
        "template_similarity": trace_module._safe_float(item.get("template_similarity")),
        "template_threshold": trace_module._safe_float(item.get("template_threshold")),
        "pixel_similarity": trace_module._safe_float(item.get("pixel_similarity")),
        "energy_similarity": trace_module._safe_float(item.get("energy_similarity")),
        "reference_v_mean": trace_module._safe_float(item.get("reference_v_mean")),
        "current_v_mean": trace_module._safe_float(item.get("current_v_mean")),
    }


def _context_signature(context: dict | None):
    if not isinstance(context, dict):
        return None
    return (
        str(context.get("project_name") or ""),
        str(context.get("check_id") or ""),
    )


def deve_registrar_rastro_display_f3(
    app,
    *,
    context: dict | None,
    analysis: dict | None,
    advance: dict | None,
    now_monotonic: float | None = None,
) -> bool:
    """Mantém transições importantes e amostra frames estáveis em baixa taxa."""
    now = time.monotonic() if now_monotonic is None else float(now_monotonic)
    signature = _context_signature(context)
    previous_signature = getattr(app, "_display_f3_perf_last_context_signature", None)
    if signature != previous_signature:
        return True

    if isinstance(advance, dict) and bool(advance.get("advanced")):
        return True

    approved = bool(isinstance(analysis, dict) and analysis.get("approved") is True)
    previous_approved = bool(getattr(app, "_display_f3_perf_last_probe_approved", False))
    if approved and not previous_approved:
        return True

    last = getattr(app, "_display_f3_perf_last_trace_monotonic", None)
    if last is None:
        return True
    try:
        return (now - float(last)) >= F3_PERF_TRACE_SAMPLE_INTERVAL_S
    except (TypeError, ValueError):
        return True


def _compact_analysis(analysis: dict | None) -> dict | None:
    if not isinstance(analysis, dict):
        return None
    masks = [
        _mask_snapshot(item)
        for item in (analysis.get("mask_results") or [])
        if isinstance(item, dict)
    ]
    return {
        "ready": analysis.get("ready"),
        "approved": analysis.get("approved"),
        "reason": analysis.get("reason"),
        "check_id": analysis.get("check_id"),
        "check_name": analysis.get("check_name"),
        "matched_mask_count": int(analysis.get("matched_mask_count", 0) or 0),
        "active_mask_count": int(analysis.get("active_mask_count", 0) or 0),
        "reference_authority": analysis.get("reference_authority"),
        "positive_probe_mode": analysis.get("positive_probe_mode"),
        "positive_on_mask_count": analysis.get("positive_on_mask_count"),
        "positive_on_matched_count": analysis.get("positive_on_matched_count"),
        "mask_results": masks,
    }


def registrar_rastro_compacto_display_f3(
    app,
    *,
    token,
    context: dict | None,
    analysis: dict | None,
    analysis_source: str,
    stability: dict,
    advance: dict | None,
) -> None:
    """Telemetria só existe quando o operador habilita explicitamente o debug."""
    # O token ainda precisa ser marcado para o wrapper nunca reprocessar a mesma
    # imagem. Todo o restante fica zerado quando DEBUG OFF.
    app._display_f3_live_trace_last_token = token
    if not debug_tecnico_ativo_display_f3(app):
        return

    now = time.monotonic()
    should_record = deve_registrar_rastro_display_f3(
        app,
        context=context,
        analysis=analysis,
        advance=advance,
        now_monotonic=now,
    )

    signature = _context_signature(context)
    approved = bool(isinstance(analysis, dict) and analysis.get("approved") is True)
    app._display_f3_perf_last_context_signature = signature
    app._display_f3_perf_last_probe_approved = approved

    if not should_record:
        return

    compact_analysis = _compact_analysis(analysis)
    app._display_f3_live_probe_last_analysis = compact_analysis

    history = getattr(app, "_display_f3_live_trace", None)
    if not isinstance(history, deque) or history.maxlen != F3_PERF_TRACE_MAX_FRAMES:
        history = deque(
            list(history)[-F3_PERF_TRACE_MAX_FRAMES:] if isinstance(history, deque) else [],
            maxlen=F3_PERF_TRACE_MAX_FRAMES,
        )
        app._display_f3_live_trace = history

    state = getattr(app, "_display_f3_operational_state", None)
    state_data = state if isinstance(state, dict) else {}
    masks = list((compact_analysis or {}).get("mask_results") or [])
    similarities = [
        value
        for value in (
            trace_module._safe_float(item.get("template_similarity"))
            for item in masks
        )
        if value is not None
    ]

    physical_keys = (
        "kind",
        "text",
        "allow_auto",
        "source",
        "physical_state_key",
        "score",
        "best_score",
        "ambiguous",
        "physical_transition_pending",
        "pending_physical_state_key",
        "fast_expected_check_gate",
        "comparison_mode",
    )
    reference_scores = state_data.get("reference_scores")
    record = {
        "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
        "token": token,
        "frame_id": getattr(app, "camera_ultimo_frame_id", None),
        "rotation": trace_module._rotation(app),
        "context": dict(context) if isinstance(context, dict) else None,
        "physical": {key: state_data.get(key) for key in physical_keys},
        "reference_scores": dict(reference_scores) if isinstance(reference_scores, dict) else {},
        "analysis_source": str(analysis_source),
        "probe": {
            "ready": (compact_analysis or {}).get("ready"),
            "approved": (compact_analysis or {}).get("approved"),
            "reason": (compact_analysis or {}).get("reason"),
            "matched": int((compact_analysis or {}).get("matched_mask_count", 0) or 0),
            "active": int((compact_analysis or {}).get("active_mask_count", 0) or 0),
            "similarity_min": min(similarities) if similarities else None,
            "similarity_avg": (sum(similarities) / len(similarities)) if similarities else None,
            "similarity_max": max(similarities) if similarities else None,
            "stable_frames": int(stability.get("frames", 0) or 0),
            "required_frames": int(stability.get("required", 0) or 0),
        },
        "advance": dict(advance) if isinstance(advance, dict) else advance,
        "masks": masks,
    }
    history.append(record)
    app._display_f3_perf_last_trace_monotonic = now


def instalar_guard_performance_runtime_display_f3() -> None:
    """Mantém produção leve e só paga o custo técnico quando DEBUG está ON."""
    if bool(getattr(trace_module, "_display_f3_runtime_performance_guard_installed", False)):
        return

    trace_module.F3_LIVE_DEBUG_REFRESH_MS = F3_PERF_DEBUG_REFRESH_MS
    trace_module.F3_LIVE_TRACE_MAX_FRAMES = F3_PERF_TRACE_MAX_FRAMES
    trace_module.F3_LIVE_TRACE_DETAIL_FRAMES = F3_PERF_TRACE_DETAIL_FRAMES

    original_probe = trace_module._probe_expected_check

    def probe(app, frame, context):
        if not sonda_oculta_permitida_display_f3(app, context):
            app._display_f3_live_probe_ok_frames = 0
            app._display_f3_live_probe_signature = None
            return _analise_sonda_pausada(context)
        return original_probe(app, frame, context)

    trace_module._probe_expected_check = probe
    trace_module._record_live_frame = registrar_rastro_compacto_display_f3
    trace_module._display_f3_runtime_performance_guard_installed = True
