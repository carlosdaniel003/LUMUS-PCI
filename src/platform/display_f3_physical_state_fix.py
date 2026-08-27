from __future__ import annotations

from copy import deepcopy

import cv2
import numpy as np

import src.platform.display_f3_check_transition_guard as transition_module
import src.platform.display_live_roi_overlay as overlay_module
import src.platform.display_visual_reference_status as visual_status_module
from src.platform.display_project_repository import (
    DISPLAY_CHECK_STATE_OFF,
    DISPLAY_CHECK_STATE_ON,
    normalizar_resolucao_display,
)
from src.platform.display_reference_roi import normalizar_roi_referencia
from src.platform.display_visual_rotation import preparar_check_visual_display


F3_PHYSICAL_PAIR_DELTA = 8.0
F3_PHYSICAL_PAIR_ERROR_MARGIN = 1.5
F3_PHYSICAL_PAIR_MIN_DIFFERENT_RATIO = 0.0015


def _as_bgr(image):
    if image is None or getattr(image, "size", 0) == 0:
        return None
    result = image
    if result.ndim == 2:
        result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
    elif result.ndim == 3 and result.shape[2] == 4:
        result = cv2.cvtColor(result, cv2.COLOR_BGRA2BGR)
    elif result.ndim != 3 or result.shape[2] != 3:
        return None
    return result


def _resize_like(image, target):
    if image is None or target is None:
        return None
    height, width = target.shape[:2]
    if image.shape[:2] == (height, width):
        return image
    return cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)


def _roi_boolean_mask(shape, left_metadata: dict, right_metadata: dict):
    height, width = int(shape[0]), int(shape[1])
    left_roi = normalizar_roi_referencia((left_metadata or {}).get("roi"))
    right_roi = normalizar_roi_referencia((right_metadata or {}).get("roi"))

    # Se uma das referências foi explicitamente configurada para IMAGEM TODA,
    # a região comum também é a imagem toda. O filtro de diferença abaixo ainda
    # elimina as partes que são visualmente iguais entre as duas referências.
    if left_roi is None or right_roi is None:
        return np.ones((height, width), dtype=bool)

    result = np.zeros((height, width), dtype=bool)
    for roi in (left_roi, right_roi):
        x1 = max(0, min(width - 1, int(round(float(roi["x"]) * width))))
        y1 = max(0, min(height - 1, int(round(float(roi["y"]) * height))))
        x2 = max(
            x1 + 1,
            min(width, int(round((float(roi["x"]) + float(roi["width"])) * width))),
        )
        y2 = max(
            y1 + 1,
            min(height, int(round((float(roi["y"]) + float(roi["height"])) * height))),
        )
        result[y1:y2, x1:x2] = True
    return result


def comparar_referencias_no_mesmo_dominio_f3(
    observed,
    left_reference,
    right_reference,
    left_metadata: dict,
    right_metadata: dict,
) -> dict:
    """Compara duas referências no mesmo conjunto de pixels.

    Scores calculados em ROIs diferentes não são comparáveis. Esta função usa
    a união das ROIs das duas referências e, dentro dela, dá peso somente aos
    pixels que realmente diferenciam os dois estados físicos.
    """
    observed = _as_bgr(observed)
    left = _as_bgr(left_reference)
    right = _as_bgr(right_reference)
    if observed is None or left is None or right is None:
        return {"available": False, "winner": "tie"}

    left = _resize_like(left, observed)
    right = _resize_like(right, observed)
    if left is None or right is None:
        return {"available": False, "winner": "tie"}

    observed_f = observed.astype(np.float32)
    left_f = left.astype(np.float32)
    right_f = right.astype(np.float32)
    domain = _roi_boolean_mask(observed.shape[:2], left_metadata, right_metadata)

    delta = np.mean(np.abs(left_f - right_f), axis=2)
    difference = (delta >= F3_PHYSICAL_PAIR_DELTA) & domain
    different_pixels = int(np.count_nonzero(difference))
    domain_pixels = max(1, int(np.count_nonzero(domain)))
    minimum = max(16, int(domain_pixels * F3_PHYSICAL_PAIR_MIN_DIFFERENT_RATIO))

    if different_pixels < minimum:
        # Referências quase idênticas dentro da área escolhida: não inventa um
        # vencedor. O estado fica ambíguo em vez de avançar para outro CHECK.
        return {
            "available": True,
            "winner": "tie",
            "different_pixels": different_pixels,
        }

    left_error_map = np.mean(np.abs(observed_f - left_f), axis=2)
    right_error_map = np.mean(np.abs(observed_f - right_f), axis=2)
    left_error = float(np.mean(left_error_map[difference]))
    right_error = float(np.mean(right_error_map[difference]))

    if left_error + F3_PHYSICAL_PAIR_ERROR_MARGIN < right_error:
        winner = "left"
    elif right_error + F3_PHYSICAL_PAIR_ERROR_MARGIN < left_error:
        winner = "right"
    else:
        winner = "tie"

    return {
        "available": True,
        "winner": winner,
        "left_error": left_error,
        "right_error": right_error,
        "different_pixels": different_pixels,
    }


def _prepare_candidates(matcher, frame, project_name: str) -> tuple[list[dict], object, bool]:
    current_small = visual_status_module._small_image(frame)
    observed = _as_bgr(current_small)
    project_references = matcher.project_store.get_all(project_name)
    board_complete = all(
        kind in project_references
        for kind in transition_module.DISPLAY_PROJECT_REFERENCE_TYPES
    )
    if observed is None:
        return [], None, board_complete

    prepared: list[dict] = []
    for candidate in transition_module._reference_candidates(matcher, project_name):
        metadata = candidate.get("metadata")
        if not isinstance(metadata, dict):
            continue
        reference = _as_bgr(matcher._reference_image(metadata))
        if reference is None:
            continue
        reference = _resize_like(reference, observed)
        score = matcher._score(current_small, metadata)
        if score is None:
            continue
        item = dict(candidate)
        item["reference"] = reference
        item["score"] = float(score)
        item["threshold"] = float(matcher._threshold(metadata))
        item["matched"] = float(score) >= float(item["threshold"])
        prepared.append(item)
    return prepared, observed, board_complete


def _state_from_candidate(candidate: dict, board_complete: bool, configured_count: int) -> dict:
    kind = str(candidate.get("kind") or "unknown")
    state = {
        "kind": kind,
        "allow_auto": False,
        "board_references_complete": bool(board_complete),
        "configured_count": int(configured_count),
        "physical_state_key": str(candidate.get("key") or kind),
        "score": float(candidate.get("score", 0.0) or 0.0),
    }
    colors = transition_module.operational_module.F3_OPERATIONAL_STATUS_COLORS
    if kind == "empty":
        state.update(text="PLACA FORA DO SUPORTE", color=colors["empty"])
    elif kind == "off":
        state.update(text="PLACA NO SUPORTE • DESLIGADA", color=colors["off"])
    else:
        name = str(candidate.get("name") or "CHECK").strip().upper()
        state.update(
            text=f"DISPLAY EM {name}",
            color=colors["check"],
            check_id=str(candidate.get("check_id") or ""),
            check_name=name,
        )
    return state


def classificar_estado_fisico_hierarquico_f3(matcher, frame, project_name: str) -> dict:
    """Resolve primeiro suporte/placa desligada e só depois estados ligados."""
    prepared, observed, board_complete = _prepare_candidates(
        matcher,
        frame,
        project_name,
    )
    colors = transition_module.operational_module.F3_OPERATIONAL_STATUS_COLORS
    if observed is None:
        return {
            "kind": "unknown",
            "text": "AGUARDANDO CÂMERA",
            "color": colors["unknown"],
            "allow_auto": False,
            "board_references_complete": board_complete,
            "configured_count": len(prepared),
        }
    if not prepared:
        return {
            "kind": "unavailable",
            "text": "REFERÊNCIAS VISUAIS NÃO CONFIGURADAS",
            "color": colors["unavailable"],
            "allow_auto": False,
            "board_references_complete": board_complete,
            "configured_count": 0,
        }

    by_key = {str(item.get("key")): item for item in prepared}
    empty = by_key.get("empty")
    off = by_key.get("off")
    checks = [item for item in prepared if str(item.get("kind")) == "check"]
    eligible_checks = [item for item in checks if bool(item.get("matched"))]

    # 1) Suporte vazio só vence se a referência vazia estiver válida e vencer
    # diretamente a placa desligada. Em empate, não arriscamos dizer "fora".
    if isinstance(empty, dict) and bool(empty.get("matched")):
        physical_rivals = []
        if isinstance(off, dict) and bool(off.get("matched")):
            physical_rivals.append(off)
        physical_rivals.extend(eligible_checks)
        if physical_rivals:
            results = [
                comparar_referencias_no_mesmo_dominio_f3(
                    observed,
                    empty["reference"],
                    rival["reference"],
                    empty["metadata"],
                    rival["metadata"],
                )
                for rival in physical_rivals
            ]
            if results and all(result.get("winner") == "left" for result in results):
                return _state_from_candidate(empty, board_complete, len(prepared))
        elif off is None:
            return _state_from_candidate(empty, board_complete, len(prepared))

    # 2) Placa desligada tem prioridade física sobre qualquer CHECK. Ela só
    # deixa de ser OFF quando uma referência de estado ligado a vence de forma
    # direta na mesma região discriminante. Percentuais de ROIs distintas nunca
    # decidem essa disputa.
    if isinstance(off, dict) and bool(off.get("matched")):
        if isinstance(empty, dict) and bool(empty.get("matched")):
            empty_vs_off = comparar_referencias_no_mesmo_dominio_f3(
                observed,
                off["reference"],
                empty["reference"],
                off["metadata"],
                empty["metadata"],
            )
            if empty_vs_off.get("winner") != "left":
                # Se o vazio venceu, a etapa anterior já teria retornado EMPTY.
                # Em empate, mantém estado indefinido para não inventar presença.
                if empty_vs_off.get("winner") == "tie":
                    return {
                        "kind": "unknown",
                        "text": "IDENTIFICANDO...",
                        "color": colors["unknown"],
                        "allow_auto": False,
                        "board_references_complete": board_complete,
                        "configured_count": len(prepared),
                    }

        powered_winners = []
        for check in eligible_checks:
            comparison = comparar_referencias_no_mesmo_dominio_f3(
                observed,
                off["reference"],
                check["reference"],
                off["metadata"],
                check["metadata"],
            )
            if comparison.get("winner") == "right":
                powered_winners.append(check)
        if not powered_winners:
            return _state_from_candidate(off, board_complete, len(prepared))

    # 3) A partir daqui a cena é tratada como placa ligada. Escolhemos o CHECK
    # pela disputa direta entre as referências elegíveis, sem comparar scores
    # produzidos em recortes diferentes.
    if eligible_checks:
        ranking = []
        for candidate in eligible_checks:
            wins = 0
            losses = 0
            error_total = 0.0
            comparisons = 0
            for rival in eligible_checks:
                if rival is candidate:
                    continue
                result = comparar_referencias_no_mesmo_dominio_f3(
                    observed,
                    candidate["reference"],
                    rival["reference"],
                    candidate["metadata"],
                    rival["metadata"],
                )
                if not result.get("available"):
                    continue
                comparisons += 1
                error_total += float(result.get("left_error", 0.0) or 0.0)
                if result.get("winner") == "left":
                    wins += 1
                elif result.get("winner") == "right":
                    losses += 1
            average_error = error_total / max(1, comparisons)
            ranking.append((wins - losses, wins, -average_error, candidate))
        ranking.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        winner = ranking[0][3]
        if len(ranking) >= 2 and ranking[0][:2] == ranking[1][:2]:
            return {
                "kind": "unknown",
                "text": "IDENTIFICANDO...",
                "color": colors["unknown"],
                "allow_auto": False,
                "board_references_complete": board_complete,
                "configured_count": len(prepared),
                "ambiguous": True,
            }
        return _state_from_candidate(winner, board_complete, len(prepared))

    return {
        "kind": "unknown",
        "text": "IDENTIFICANDO...",
        "color": colors["unknown"],
        "allow_auto": False,
        "board_references_complete": board_complete,
        "configured_count": len(prepared),
    }


def overlay_contexto_independente_da_analise(window, visual_rotation: int):
    """Mantém a geometria das ROIs visível mesmo quando o automático está bloqueado."""
    app = overlay_module._app_from_window(window)
    if app is None:
        return None
    repository = getattr(app, "display_project_repository", None)
    if repository is None:
        return None
    try:
        project_name = str(repository.obter_projeto_ativo() or "")
    except Exception:
        project_name = ""
    current_check_id = overlay_module._current_check_id(app)
    if not project_name or not current_check_id:
        return None

    cache_key = (
        project_name,
        current_check_id,
        int(visual_rotation),
        overlay_module._config_signature(repository),
    )
    if cache_key != getattr(window, "_display_roi_overlay_cache_key", None):
        project = repository.carregar_projeto(project_name)
        if not isinstance(project, dict):
            return None
        resolution = normalizar_resolucao_display(project.get("master_resolution"))
        if resolution is None:
            return None
        check = next(
            (
                item
                for item in (project.get("checks", []) or [])
                if isinstance(item, dict)
                and str(item.get("id") or "") == current_check_id
            ),
            None,
        )
        if not isinstance(check, dict):
            return None
        states = check.get("mask_states", {}) if isinstance(check.get("mask_states"), dict) else {}
        active_masks = [
            deepcopy(mask)
            for mask in (project.get("masks", []) or [])
            if isinstance(mask, dict)
            and states.get(str(mask.get("id")))
            in (DISPLAY_CHECK_STATE_ON, DISPLAY_CHECK_STATE_OFF)
        ]
        _, visual_resolution, visual_masks = preparar_check_visual_display(
            None,
            resolution,
            active_masks,
            visual_rotation,
        )
        window._display_roi_overlay_cache_key = cache_key
        window._display_roi_overlay_resolution = tuple(visual_resolution)
        window._display_roi_overlay_masks = tuple(visual_masks)

    classifications = {}
    analysis = getattr(app, "_display_auto_last_analysis", None)
    if isinstance(analysis, dict):
        analysis_project = str(analysis.get("project_name") or "")
        analysis_check = str(analysis.get("check_id") or "")
        if analysis_project == project_name and analysis_check == current_check_id:
            for item in analysis.get("mask_results", []) or []:
                if not isinstance(item, dict):
                    continue
                mask_id = str(item.get("mask_id") or "")
                if mask_id:
                    classifications[mask_id] = str(item.get("classified") or "unknown")

    return {
        "resolution": getattr(window, "_display_roi_overlay_resolution", None),
        "masks": getattr(window, "_display_roi_overlay_masks", ()),
        "classifications": classifications,
    }


_DISPLAY_F3_PHYSICAL_STATE_FIX_INSTALLED = False


def instalar_correcao_estado_fisico_display_f3() -> None:
    """Corrige estado físico e overlay apenas no runtime Display/F3."""
    global _DISPLAY_F3_PHYSICAL_STATE_FIX_INSTALLED
    if _DISPLAY_F3_PHYSICAL_STATE_FIX_INSTALLED:
        return
    transition_module.classificar_estado_fisico_referencias_f3 = (
        classificar_estado_fisico_hierarquico_f3
    )
    overlay_module._overlay_context = overlay_contexto_independente_da_analise
    _DISPLAY_F3_PHYSICAL_STATE_FIX_INSTALLED = True
