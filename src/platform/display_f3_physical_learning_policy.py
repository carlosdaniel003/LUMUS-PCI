from __future__ import annotations

from copy import deepcopy
from math import ceil
from pathlib import Path

import cv2

import src.platform.display_auto_check_runtime as auto_runtime_module
import src.platform.display_f3_check_transition_guard as transition_module
import src.platform.display_f3_live_runtime_fix as live_runtime_module
import src.platform.display_f3_mask_status as mask_status_module
import src.platform.display_f3_operational_status as operational_module
import src.platform.display_f3_same_mask_reference_fix as learning_module
import src.platform.display_live_roi_overlay as overlay_module
from src.core.feature_extractor import extrair_features_selecao
from src.platform.display_auto_check_analyzer import (
    DISPLAY_AUTO_FEATURE_WEIGHTS,
    display_mask_to_analysis_selection,
)
from src.platform.display_project_repository import (
    DISPLAY_CHECK_STATE_ON,
    normalizar_resolucao_display,
)
from src.platform.display_visual_reference_status import (
    DISPLAY_PROJECT_REFERENCE_BOARD_OFF,
)


F3_STATUS_BOARD_OFF = "PLACA NO SUPORTE • DESLIGADA • LEDS DESLIGADOS"
F3_STATUS_BOARD_ON_PREFIX = "PLACA NO SUPORTE • LIGADA"
F3_STATUS_EMPTY = "PLACA FORA DO SUPORTE"

# Antes de aceitar qualquer CHECK ligado, as máscaras que deveriam estar ACESAS
# precisam parecer mais com a foto desse CHECK do que com a foto PLACA DESLIGADA.
# A cena inteira continua útil para presença/posição, mas não pode sozinha dizer
# que H1/BLUE/USB/AUX está ligado quando os segmentos estão visualmente apagados.
F3_POWER_MASK_MIN_SEPARATION = 0.14
F3_POWER_MASK_OFF_RATIO = 0.70
F3_POWER_MASK_MIN_OFF_VOTES = 2


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


def _feature_distance(left, right) -> float:
    distance = 0.0
    for name, weight in DISPLAY_AUTO_FEATURE_WEIGHTS.items():
        distance += abs(
            float(getattr(left, name, 0.0))
            - float(getattr(right, name, 0.0))
        ) * float(weight)
    return float(distance)


def _prepare_reference_image(metadata: dict | None, resolution: tuple[int, int]):
    if not isinstance(metadata, dict):
        return None
    path = Path(str(metadata.get("image_path") or ""))
    if not path.is_file():
        return None
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None or getattr(image, "size", 0) == 0:
        return None
    width, height = int(resolution[0]), int(resolution[1])
    if image.shape[:2] != (height, width):
        image = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    return image


def _prepare_live_image(frame, resolution: tuple[int, int]):
    if frame is None or getattr(frame, "size", 0) == 0:
        return None
    image = frame.copy()
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.ndim == 3 and image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    elif image.ndim != 3 or image.shape[2] != 3:
        return None
    width, height = int(resolution[0]), int(resolution[1])
    if image.shape[:2] != (height, width):
        interpolation = (
            cv2.INTER_AREA
            if image.shape[1] > width or image.shape[0] > height
            else cv2.INTER_LINEAR
        )
        image = cv2.resize(image, (width, height), interpolation=interpolation)
    return image


def decidir_placa_desligada_por_votos_mascaras_f3(
    *,
    off_votes: int,
    powered_votes: int,
    valid_votes: int,
) -> bool:
    """Decide OFF só quando a maioria forte das máscaras ACESAS aponta OFF."""
    valid = max(0, int(valid_votes or 0))
    off_count = max(0, int(off_votes or 0))
    powered_count = max(0, int(powered_votes or 0))
    if valid <= 0:
        return False

    minimum_votes = 1 if valid == 1 else max(
        F3_POWER_MASK_MIN_OFF_VOTES,
        int(ceil(valid * F3_POWER_MASK_OFF_RATIO)),
    )
    return bool(
        off_count >= minimum_votes
        and off_count > powered_count
    )


def avaliar_evidencia_energia_check_pelas_mascaras_f3(
    *,
    repository,
    matcher,
    frame,
    project_name: str,
    check_id: str,
) -> dict:
    """Compara somente segmentos que o CHECK diz que deveriam estar ACESOS.

    Para cada máscara esperada ACESA, o frame atual disputa entre a aparência
    real daquela mesma região na foto PLACA DESLIGADA e na foto do CHECK.
    Assim suporte, fundo, placa e demais pixels iguais deixam de dominar a decisão.
    """
    project = repository.carregar_projeto(project_name)
    check = repository.carregar_check(project_name, check_id)
    if not isinstance(project, dict) or not isinstance(check, dict):
        return {"available": False, "off_confirmed": False, "reason": "contexto_invalido"}

    resolution = normalizar_resolucao_display(project.get("master_resolution"))
    if resolution is None:
        return {"available": False, "off_confirmed": False, "reason": "resolucao_ausente"}

    states = check.get("mask_states", {}) if isinstance(check.get("mask_states"), dict) else {}
    on_masks = [
        mask
        for mask in (project.get("masks", []) or [])
        if isinstance(mask, dict)
        and states.get(str(mask.get("id") or "")) == DISPLAY_CHECK_STATE_ON
    ]
    if not on_masks:
        return {"available": False, "off_confirmed": False, "reason": "check_sem_mascara_acesa"}

    project_refs = matcher.project_store.get_all(project_name)
    off_metadata = project_refs.get(DISPLAY_PROJECT_REFERENCE_BOARD_OFF)
    check_metadata = matcher.check_store.get(project_name, check_id)
    off_image = _prepare_reference_image(off_metadata, resolution)
    check_image = _prepare_reference_image(check_metadata, resolution)
    live_image = _prepare_live_image(frame, resolution)
    if off_image is None or check_image is None or live_image is None:
        return {
            "available": False,
            "off_confirmed": False,
            "reason": "referencias_energia_indisponiveis",
        }

    off_votes = 0
    powered_votes = 0
    ties = 0
    details = []

    for mask in on_masks:
        mask_id = str(mask.get("id") or "")
        try:
            selection = display_mask_to_analysis_selection(mask)
            current_features = extrair_features_selecao(live_image, selection)
            off_features = extrair_features_selecao(off_image, selection)
            check_features = extrair_features_selecao(check_image, selection)
        except (TypeError, ValueError):
            continue

        if min(
            int(getattr(current_features, "area_pixels", 0) or 0),
            int(getattr(off_features, "area_pixels", 0) or 0),
            int(getattr(check_features, "area_pixels", 0) or 0),
        ) <= 0:
            continue

        # Se nem a própria foto do CHECK difere da foto desligada nessa máscara,
        # ela não possui poder discriminante e não participa da votação.
        reference_span = _feature_distance(off_features, check_features)
        if reference_span <= 1e-6:
            continue

        distance_off = _feature_distance(current_features, off_features)
        distance_check = _feature_distance(current_features, check_features)
        separation = abs(distance_off - distance_check) / max(
            1e-9,
            distance_off + distance_check,
        )

        winner = "tie"
        if separation >= F3_POWER_MASK_MIN_SEPARATION:
            if distance_off < distance_check:
                off_votes += 1
                winner = "off"
            else:
                powered_votes += 1
                winner = "check"
        else:
            ties += 1

        details.append(
            {
                "mask_id": mask_id,
                "distance_off": round(float(distance_off), 4),
                "distance_check": round(float(distance_check), 4),
                "reference_span": round(float(reference_span), 4),
                "separation": round(float(separation), 4),
                "winner": winner,
            }
        )

    valid_votes = off_votes + powered_votes
    off_confirmed = decidir_placa_desligada_por_votos_mascaras_f3(
        off_votes=off_votes,
        powered_votes=powered_votes,
        valid_votes=valid_votes,
    )
    return {
        "available": bool(details),
        "off_confirmed": bool(off_confirmed),
        "check_id": str(check_id),
        "expected_on_mask_count": len(on_masks),
        "off_votes": int(off_votes),
        "powered_votes": int(powered_votes),
        "tie_votes": int(ties),
        "valid_votes": int(valid_votes),
        "details": details,
    }


def corrigir_falso_check_ligado_pelas_mascaras_f3(
    *,
    repository,
    matcher,
    frame,
    project_name: str,
    state: dict | None,
) -> dict:
    """Um CHECK ligado só sobrevive se suas máscaras ACESAS tiverem energia real."""
    result = deepcopy(state) if isinstance(state, dict) else {}
    if str(result.get("kind") or "") != "check":
        return result

    check_id = str(result.get("check_id") or "")
    if not check_id:
        return result

    evidence = avaliar_evidencia_energia_check_pelas_mascaras_f3(
        repository=repository,
        matcher=matcher,
        frame=frame,
        project_name=project_name,
        check_id=check_id,
    )
    result["power_mask_evidence"] = evidence
    if not bool(evidence.get("off_confirmed")):
        return result

    return {
        "kind": "off",
        "text": F3_STATUS_BOARD_OFF,
        "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["off"],
        "allow_auto": False,
        "physical_state_key": "off",
        "source": "f3_expected_on_masks_vs_board_off",
        "power_mask_evidence": evidence,
        "board_references_complete": bool(result.get("board_references_complete")),
        "configured_count": int(result.get("configured_count", 0) or 0),
    }


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

    # A comparação global pode confundir OFF com H1 porque quase toda a cena é
    # igual. Antes do debounce, confirmamos o suposto CHECK usando somente as
    # máscaras que na foto dele deveriam estar realmente ACESAS.
    raw_state = corrigir_falso_check_ligado_pelas_mascaras_f3(
        repository=repository,
        matcher=matcher,
        frame=frame,
        project_name=project_name,
        state=raw_state,
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
