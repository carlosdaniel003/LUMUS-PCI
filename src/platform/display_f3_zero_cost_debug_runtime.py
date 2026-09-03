from __future__ import annotations

"""Remove o custo diagnóstico do loop F3 quando DEBUG TÉCNICO está OFF.

O rastreio ao vivo original permanece intacto para DEBUG ON. Com DEBUG OFF,
USB/AUX e demais CHECKS estáveis usam diretamente o runtime produtivo anterior
ao rastreio. H1/BLUE preservam apenas a sonda positiva mínima necessária para
não perder estados transitórios.
"""

import src.platform.display_f3_live_diagnostic_trace as trace_module
from src.platform.display_auto_check_runtime import DisplayAutomaticCheckF3Mixin
from src.platform.display_f3_debug_toggle import debug_tecnico_ativo_display_f3


F3_DEBUG_OFF_RUNTIME_SOURCE = "f3_debug_off_zero_cost_runtime"


def extrair_runtime_produtivo_antes_do_debug(func):
    """Obtém o `original_process` capturado pelo wrapper de rastreio ao vivo."""
    closure = getattr(func, "__closure__", None) or ()
    freevars = tuple(getattr(getattr(func, "__code__", None), "co_freevars", ()) or ())
    for name, cell in zip(freevars, closure):
        if name != "original_process":
            continue
        try:
            candidate = cell.cell_contents
        except Exception:
            continue
        if callable(candidate):
            return candidate
    return None


def _contexto_sem_copia(app):
    try:
        value = app._display_auto_current_context()
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _contexto_exige_sonda_operacional(app, context: dict | None) -> bool:
    if not isinstance(context, dict):
        return False
    try:
        if bool(app._display_auto_is_reference_gate(context)):
            return True
    except Exception:
        pass
    try:
        if bool(app._display_auto_is_transient_check(context)):
            return True
    except Exception:
        pass
    return False


def processar_frame_debug_off_display_f3(app, runtime_produtivo, frame, context):
    """Executa H1/BLUE sem histórico, deepcopy ou provider técnico por frame."""
    token = trace_module._frame_token(app, frame)
    result = runtime_produtivo(app)

    if not isinstance(context, dict):
        return result

    core_token = getattr(app, "_display_auto_last_frame_token", None)
    core_analysis = getattr(app, "_display_auto_last_analysis", None)
    if (
        core_token == token
        and isinstance(core_analysis, dict)
        and str(core_analysis.get("check_id") or "")
        == str(context.get("check_id") or "")
    ):
        # Usa a própria estrutura do core sem deepcopy: DEBUG OFF não persiste
        # esse objeto e portanto não precisa duplicá-lo.
        analysis = core_analysis
    else:
        analysis = trace_module._probe_expected_check(app, frame, context)

    stability = trace_module._update_positive_probe_stability(app, context, analysis)
    trace_module._advance_positive_probe_if_needed(
        app,
        context,
        analysis,
        stability,
    )
    # O token apenas evita reaproveitamento acidental se o operador ligar o
    # debug no mesmo frame. Não há histórico nem snapshot associado.
    app._display_f3_live_trace_last_token = token
    return result


_INSTALLED = False


def instalar_runtime_debug_off_custo_zero_display_f3() -> None:
    """Última camada: DEBUG OFF sai totalmente do caminho de telemetria."""
    global _INSTALLED
    if _INSTALLED:
        return

    cls = DisplayAutomaticCheckF3Mixin
    if bool(getattr(cls, "_display_f3_zero_cost_debug_runtime_installed", False)):
        _INSTALLED = True
        return

    diagnostic_process = cls._process_display_auto_check
    runtime_produtivo = extrair_runtime_produtivo_antes_do_debug(diagnostic_process)
    if runtime_produtivo is None:
        # Falha segura: não substitui o runtime se a cadeia não tiver a forma
        # esperada. Isso evita remover acidentalmente uma camada operacional.
        cls._display_f3_zero_cost_debug_runtime_unavailable = True
        _INSTALLED = True
        return

    def process(self):
        if not bool(getattr(self, "display_f3_ativo", False)):
            return runtime_produtivo(self)

        if debug_tecnico_ativo_display_f3(self):
            return diagnostic_process(self)

        # DEBUG OFF: para CHECK estável não existe qualquer trabalho de debug.
        context = _contexto_sem_copia(self)
        if not _contexto_exige_sonda_operacional(self, context):
            return runtime_produtivo(self)

        frame = getattr(self, "camera_frame_atual", None)
        if frame is None or getattr(frame, "size", 0) == 0:
            return runtime_produtivo(self)

        return processar_frame_debug_off_display_f3(
            self,
            runtime_produtivo,
            frame,
            context,
        )

    cls._process_display_auto_check = process
    cls._display_f3_zero_cost_debug_runtime_installed = True
    cls._display_f3_zero_cost_debug_runtime_source = F3_DEBUG_OFF_RUNTIME_SOURCE
    _INSTALLED = True
