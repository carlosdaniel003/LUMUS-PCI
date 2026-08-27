from __future__ import annotations

from copy import deepcopy

import src.platform.display_f3_check_transition_guard as transition_module
from src.platform.display_auto_check_analyzer import DisplayAutomaticCheckAnalyzer
from src.platform.display_auto_check_runtime import DisplayAutomaticCheckF3Mixin


F3_TRANSIENT_DISPLAY_NAMES = frozenset({"BLUE", "BLUETOOTH", "BT"})
# O BLUE pisca fisicamente. Com preview a 45 ms, 12 frames seguram o estado por
# cerca de meio segundo, suficiente para atravessar a fase escura sem chamar a
# placa de desligada. Um novo CHECK real sempre substitui o hold imediatamente.
F3_TRANSIENT_HOLD_FRAMES = 12

_LEGACY_PHYSICAL_STABILIZER = transition_module._estado_fisico_estavel


def _normalized_tokens(value: str) -> set[str]:
    normalized = " ".join(
        str(value or "").strip().upper().replace("-", " ").replace("_", " ").split()
    )
    return set(normalized.split())


def _is_transient_check_state(state: dict | None) -> bool:
    if not isinstance(state, dict) or str(state.get("kind") or "") != "check":
        return False
    name = str(state.get("check_name") or state.get("text") or "")
    return bool(_normalized_tokens(name).intersection(F3_TRANSIENT_DISPLAY_NAMES))


def _clear_transient_hold(app) -> None:
    app._display_f3_transient_hold_state = None
    app._display_f3_transient_hold_frames = 0


def _remember_immediate_check(app, raw_state: dict) -> dict:
    state = dict(raw_state)
    key = str(state.get("physical_state_key") or state.get("check_id") or "check")

    # CHECKs ligados não precisam do debounce físico de três frames: a própria
    # referência visual já confirmou o estado e a análise óptica ainda possui
    # seu debounce de OK/NG. Isto é essencial para H1 e para estados transitórios.
    app._display_f3_physical_stable_key = key
    app._display_f3_physical_stable_state = dict(state)
    app._display_f3_physical_pending_key = ""
    app._display_f3_physical_pending_frames = 0

    if _is_transient_check_state(state):
        app._display_f3_transient_hold_state = dict(state)
        app._display_f3_transient_hold_frames = F3_TRANSIENT_HOLD_FRAMES
    else:
        _clear_transient_hold(app)
    return state


def estabilizar_estado_fisico_rapido_f3(app, raw_state: dict) -> dict:
    """Debounce físico assimétrico para o Display.

    - CHECK ligado: entra imediatamente para a análise não perder H1/BLUE.
    - BLUE/BT: mantém o último estado durante a fase escura do pisca.
    - EMPTY: nunca é mascarado pelo hold; remoção física continua detectável.
    - OFF/EMPTY normais: preservam o debounce legado de três frames.
    """
    state = dict(raw_state or {})
    kind = str(state.get("kind") or "unknown")

    if kind == "check":
        return _remember_immediate_check(app, state)

    if kind == "empty":
        # Retirar a placa é um evento físico real e deve cancelar imediatamente
        # qualquer memória de BLUE, embora a confirmação EMPTY siga o debounce.
        _clear_transient_hold(app)
        return _LEGACY_PHYSICAL_STABILIZER(app, state)

    hold_frames = int(getattr(app, "_display_f3_transient_hold_frames", 0) or 0)
    hold_state = getattr(app, "_display_f3_transient_hold_state", None)
    if kind in {"off", "unknown", "unavailable"} and hold_frames > 0 and isinstance(
        hold_state, dict
    ):
        app._display_f3_transient_hold_frames = hold_frames - 1
        held = deepcopy(hold_state)
        held["transient_hold"] = True
        held["raw_kind_during_hold"] = kind
        held["hold_frames_remaining"] = hold_frames - 1
        return held

    if hold_frames <= 0:
        _clear_transient_hold(app)
    return _LEGACY_PHYSICAL_STABILIZER(app, state)


def _analysis_matches_context(analysis, context: dict) -> bool:
    return bool(
        isinstance(analysis, dict)
        and str(analysis.get("project_name") or "")
        == str(context.get("project_name") or "")
        and str(analysis.get("check_id") or "")
        == str(context.get("check_id") or "")
    )


def atualizar_classificacao_overlay_f3(app):
    """Atualiza apenas as cores da ROI, sem poder avançar/reprovar um CHECK.

    O gate físico decide se o CHECK pode ser registrado. A classificação óptica
    das máscaras é independente e continua rodando para manter verde/vermelho/
    amarelo na câmera ao vivo mesmo quando o gate está bloqueado.
    """
    if not bool(getattr(app, "display_f3_ativo", False)):
        return None

    try:
        if bool(app._display_auto_configuration_open()):
            return None
    except Exception:
        pass

    frame = getattr(app, "camera_frame_atual", None)
    if frame is None or getattr(frame, "size", 0) == 0:
        return None

    try:
        context = app._display_auto_current_context()
    except Exception:
        context = None
    if not isinstance(context, dict):
        return None

    current_analysis = getattr(app, "_display_auto_last_analysis", None)
    if _analysis_matches_context(current_analysis, context):
        return current_analysis

    try:
        frame_token = app._display_auto_frame_token(frame)
    except Exception:
        frame_token = ("object", id(frame))
    cache_key = (
        str(context.get("project_name") or ""),
        str(context.get("check_id") or ""),
        frame_token,
    )
    cached_key = getattr(app, "_display_f3_overlay_analysis_cache_key", None)
    cached_analysis = getattr(app, "_display_f3_overlay_analysis_cache", None)
    if cache_key == cached_key and _analysis_matches_context(cached_analysis, context):
        # O gate pode limpar _display_auto_last_analysis a cada frame bloqueado.
        # Reaproveitamos a classificação do mesmo frame sem recalcular tudo.
        app._display_auto_last_analysis = cached_analysis
        return cached_analysis

    repository = getattr(app, "display_project_repository", None)
    if repository is None:
        return None
    analyzer = getattr(app, "_display_auto_analyzer", None)
    if analyzer is None or getattr(analyzer, "repository", None) is not repository:
        # Não usa _rebuild_display_auto_analyzer(), pois esse método também
        # reinicia o debounce oficial. Aqui queremos somente classificação.
        analyzer = DisplayAutomaticCheckAnalyzer(repository)
        app._display_auto_analyzer = analyzer

    try:
        rotation = int(app._obter_rotacao_visual_display_f3())
    except Exception:
        rotation = 0

    analysis = analyzer.analyze(
        frame=frame,
        project_name=str(context.get("project_name") or ""),
        check_id=str(context.get("check_id") or ""),
        visual_rotation=rotation,
    )
    if not isinstance(analysis, dict):
        return None

    app._display_f3_overlay_analysis_cache_key = cache_key
    app._display_f3_overlay_analysis_cache = analysis
    app._display_auto_last_analysis = analysis
    return analysis


_DISPLAY_F3_LIVE_RUNTIME_FIX_INSTALLED = False


def instalar_runtime_ao_vivo_display_f3() -> None:
    """Instala resposta rápida/overlay exclusivamente no runtime Display F3."""
    global _DISPLAY_F3_LIVE_RUNTIME_FIX_INSTALLED
    if _DISPLAY_F3_LIVE_RUNTIME_FIX_INSTALLED:
        return

    # O guard operacional consulta esta função a cada preview. Ao substituir aqui,
    # CHECKs ligados entram imediatamente e BLUE ganha histerese de pisca.
    transition_module._estado_fisico_estavel = estabilizar_estado_fisico_rapido_f3

    cls = DisplayAutomaticCheckF3Mixin
    if not bool(getattr(cls, "_display_f3_live_runtime_fix_installed", False)):
        gated_process = cls._process_display_auto_check

        def process(self):
            result = gated_process(self)
            try:
                atualizar_classificacao_overlay_f3(self)
            except Exception:
                # Overlay nunca pode derrubar o fluxo operacional.
                pass
            return result

        cls._process_display_auto_check = process
        cls._display_f3_live_runtime_fix_installed = True

    _DISPLAY_F3_LIVE_RUNTIME_FIX_INSTALLED = True
