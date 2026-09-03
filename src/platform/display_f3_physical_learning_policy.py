from __future__ import annotations

from copy import deepcopy

import src.platform.display_auto_check_runtime as auto_runtime_module
import src.platform.display_f3_check_transition_guard as transition_module
import src.platform.display_f3_live_runtime_fix as live_runtime_module
import src.platform.display_f3_mask_status as mask_status_module
import src.platform.display_f3_operational_status as operational_module
import src.platform.display_f3_same_mask_reference_fix as learning_module
import src.platform.display_live_roi_overlay as overlay_module


F3_STATUS_BOARD_OFF = "PLACA NO SUPORTE • DESLIGADA • LEDS DESLIGADOS"
F3_STATUS_BOARD_ON_PREFIX = "PLACA NO SUPORTE • LIGADA"
F3_STATUS_EMPTY = "PLACA FORA DO SUPORTE"


_ORIGINAL_CHECK_PHOTO_CLASSIFIER = (
    learning_module.classificar_mascara_por_referencias_locais_f3
)


def classificar_mascara_binaria_pelas_fotos_dos_checks_f3(
    *,
    current,
    on_references,
    off_references,
    low_light_references=None,
    detect_low_light: bool = True,
):
    """F3 operacional usa somente ACESO/APAGADO até existir rótulo POUCA LUZ.

    As fotos dos CHECKS já são o aprendizado real: cada máscara marcada ACESO ou
    APAGADO fornece uma amostra rotulada. Como o editor de CHECKS atualmente não
    possui um estado POUCA LUZ, o runtime não pode inferir essa classe sozinho.
    """
    del low_light_references, detect_low_light
    return _ORIGINAL_CHECK_PHOTO_CLASSIFIER(
        current=current,
        on_references=on_references,
        off_references=off_references,
        low_light_references=None,
        detect_low_light=False,
    )


def aplicar_contexto_ao_estado_fisico_f3(
    state: dict | None,
    *,
    current_check_id: str = "",
) -> dict:
    """Transforma a classificação física em status e gate do CHECK esperado."""
    result = deepcopy(state) if isinstance(state, dict) else {}
    kind = str(result.get("kind") or "unknown")
    expected_id = str(current_check_id or "")

    if kind == "empty":
        result["text"] = F3_STATUS_EMPTY
        result["allow_auto"] = False
        return result

    if kind == "off":
        result["text"] = F3_STATUS_BOARD_OFF
        result["allow_auto"] = False
        return result

    if kind == "check":
        physical_id = str(result.get("check_id") or "")
        physical_name = str(
            result.get("check_name")
            or result.get("name")
            or physical_id
            or "CHECK"
        ).strip().upper()
        result["check_name"] = physical_name
        result["text"] = f"{F3_STATUS_BOARD_ON_PREFIX} • DISPLAY EM {physical_name}"
        result["expected_check_id"] = expected_id
        result["physical_matches_expected_check"] = bool(
            expected_id and physical_id == expected_id
        )
        result["allow_auto"] = bool(result["physical_matches_expected_check"])
        return result

    result["allow_auto"] = False
    return result


def _build_physical_operational_state(
    self,
    frame,
    project_name: str,
    context: dict | None,
) -> dict:
    """Estado físico é autoridade antes do sequenciador e das máscaras."""
    repository = getattr(self, "display_project_repository", None)
    if repository is None:
        return {
            "kind": "unavailable",
            "text": "PROJETO DISPLAY NÃO DISPONÍVEL",
            "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["unavailable"],
            "allow_auto": False,
        }

    matcher = getattr(self, "_display_f3_operational_matcher", None)
    if matcher is None or getattr(matcher, "repository", None) is not repository:
        matcher = operational_module.DisplayVisualReferenceMatcher(repository)
        self._display_f3_operational_matcher = matcher

    raw_state = transition_module.classificar_estado_fisico_referencias_f3(
        matcher,
        frame,
        project_name,
    )
    state = transition_module._estado_fisico_estavel(self, raw_state)
    current_check_id = str((context or {}).get("check_id") or "")
    state = aplicar_contexto_ao_estado_fisico_f3(
        state,
        current_check_id=current_check_id,
    )

    current_metadata = (
        matcher.check_store.get(project_name, current_check_id)
        if current_check_id
        else None
    )
    state["current_check_reference_configured"] = isinstance(current_metadata, dict)

    # Rearmamento terminal continua exigindo suporte vazio, mas não altera a
    # prioridade normal: EMPTY/OFF/CHECK físico sempre é determinado primeiro.
    state = live_runtime_module.aplicar_gate_rearme_ciclo_f3(self, state)
    return state


def _clear_blocked_analysis(self, state: dict, context: dict | None) -> None:
    self._display_auto_last_analysis = None
    self._display_f3_overlay_analysis_cache_key = None
    self._display_f3_overlay_analysis_cache = None

    reset = getattr(self, "_reset_display_auto_stability", None)
    if callable(reset):
        try:
            reset(transition=False)
        except TypeError:
            reset()
        except Exception:
            pass

    window = getattr(self, "display_f3_window", None)
    if window is None:
        return

    kind = str(state.get("kind") or "unknown")
    expected_name = str(
        (context or {}).get("check_name")
        or (context or {}).get("check_id")
        or "CHECK"
    ).strip().upper()

    if kind == "off":
        mask_text = "MÁSCARAS • INATIVAS • PLACA DESLIGADA"
        preview_text = "AUTO • placa desligada • aguardando display ligado"
    elif kind == "empty":
        mask_text = "MÁSCARAS • INATIVAS • PLACA FORA DO SUPORTE"
        preview_text = "AUTO • aguardando placa no suporte"
    elif kind == "check":
        physical_name = str(state.get("check_name") or "CHECK").strip().upper()
        mask_text = f"MÁSCARAS • {expected_name}: AGUARDANDO ESTADO FÍSICO"
        preview_text = (
            f"AUTO • aguardando {expected_name} • display físico em {physical_name}"
        )
    else:
        mask_text = "MÁSCARAS • INATIVAS • IDENTIFICANDO ESTADO FÍSICO"
        preview_text = "AUTO • identificando presença e estado físico da placa"

    try:
        window.set_mask_analysis_status(
            mask_text,
            mask_status_module.F3_MASK_STATUS_COLORS["waiting"],
        )
    except Exception:
        pass

    try:
        self._display_auto_set_preview_status(preview_text, "#FDE68A")
    except Exception:
        pass


def _install_physical_gate() -> None:
    cls = auto_runtime_module.DisplayAutomaticCheckF3Mixin
    if bool(getattr(cls, "_display_f3_physical_learning_policy_installed", False)):
        return

    original_process = cls._process_display_auto_check

    def process(self):
        if not bool(getattr(self, "display_f3_ativo", False)):
            return original_process(self)

        frame = getattr(self, "camera_frame_atual", None)
        repository = getattr(self, "display_project_repository", None)
        window = getattr(self, "display_f3_window", None)
        if (
            frame is None
            or getattr(frame, "size", 0) == 0
            or repository is None
            or window is None
        ):
            return original_process(self)

        try:
            project_name = str(repository.obter_projeto_ativo() or "")
        except Exception:
            project_name = ""
        if not project_name:
            return original_process(self)

        try:
            context = self._display_auto_current_context()
        except Exception:
            context = None

        state = _build_physical_operational_state(
            self,
            frame,
            project_name,
            context,
        )
        self._display_f3_operational_state = dict(state)

        try:
            window.set_operational_reference_status(
                str(state.get("text") or "IDENTIFICANDO..."),
                str(
                    state.get("color")
                    or operational_module.F3_OPERATIONAL_STATUS_COLORS["unknown"]
                ),
            )
        except Exception:
            pass

        if not bool(state.get("allow_auto")):
            _clear_blocked_analysis(self, state, context)
            return None

        return original_process(self)

    cls._process_display_auto_check = process
    cls._display_f3_physical_learning_policy_installed = True


_INSTALLED = False


def instalar_politica_fisica_e_aprendizado_display_f3() -> None:
    """Instala a política final somente no F3, depois de todas as extensões."""
    global _INSTALLED
    if _INSTALLED:
        return

    # A última autoridade visual volta a ser o estado físico, não o CHECK lógico.
    operational_module._build_operational_state = _build_physical_operational_state

    # Sem rótulo explícito POUCA LUZ no Gerenciar CHECKS, não existe essa classe.
    learning_module.classificar_mascara_por_referencias_locais_f3 = (
        classificar_mascara_binaria_pelas_fotos_dos_checks_f3
    )
    overlay_module.DISPLAY_ROI_OVERLAY_LEGEND = (
        "VERDE: ACESO  •  VERMELHO: APAGADO"
    )

    _install_physical_gate()
    _INSTALLED = True
