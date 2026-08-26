from __future__ import annotations

import cv2
import numpy as np

import src.platform.display_f3_operational_status as operational_module
import src.platform.display_visual_reference_status as visual_status_module


F3_CHECK_TRANSITION_STABLE_FRAMES = 4
F3_CHECK_TRANSITION_GLOBAL_SCORE_MARGIN = 0.05
F3_CHECK_TRANSITION_REFERENCE_DELTA = 8.0
F3_CHECK_TRANSITION_ERROR_MARGIN = 1.5
F3_CHECK_TRANSITION_ERROR_RATIO = 0.82


def _as_color_image(image):
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


def avaliar_preferencia_transicao_referencias_f3(
    matcher,
    current_small,
    last_metadata: dict | None,
    current_metadata: dict | None,
) -> dict:
    """Compara somente as regiões que diferenciam dois CHECKS consecutivos.

    A imagem inteira do Display muda pouco entre BLUE/USB/AUX. Por isso a
    similaridade global pode dizer que USB parece válido enquanto o Display
    ainda está em BLUE. Esta comparação cria uma máscara a partir dos pixels
    que realmente mudam entre as duas referências e exige que o frame atual
    esteja mais próximo da nova referência justamente nessas regiões.
    """
    if not isinstance(last_metadata, dict) or not isinstance(current_metadata, dict):
        return {"current_preferred": False, "available": False}

    last_reference = _as_color_image(matcher._reference_image(last_metadata))
    current_reference = _as_color_image(matcher._reference_image(current_metadata))
    observed = _as_color_image(current_small)
    if last_reference is None or current_reference is None or observed is None:
        return {"current_preferred": False, "available": False}

    target_height, target_width = current_reference.shape[:2]
    if last_reference.shape[:2] != (target_height, target_width):
        last_reference = cv2.resize(
            last_reference,
            (target_width, target_height),
            interpolation=cv2.INTER_AREA,
        )
    if observed.shape[:2] != (target_height, target_width):
        observed = cv2.resize(
            observed,
            (target_width, target_height),
            interpolation=cv2.INTER_AREA,
        )

    current_score = matcher._score(current_small, current_metadata)
    last_score = matcher._score(current_small, last_metadata)
    current_threshold = matcher._threshold(current_metadata)
    last_threshold = matcher._threshold(last_metadata)
    if current_score is None or last_score is None:
        return {"current_preferred": False, "available": False}

    current_score = float(current_score)
    last_score = float(last_score)
    current_matched = current_score >= float(current_threshold)
    last_matched = last_score >= float(last_threshold)

    current_f = current_reference.astype(np.float32)
    last_f = last_reference.astype(np.float32)
    observed_f = observed.astype(np.float32)

    reference_delta = np.mean(np.abs(current_f - last_f), axis=2)
    difference_mask = reference_delta >= F3_CHECK_TRANSITION_REFERENCE_DELTA
    different_pixels = int(np.count_nonzero(difference_mask))
    minimum_pixels = max(32, int(reference_delta.size * 0.002))

    if different_pixels < minimum_pixels:
        preferred = bool(
            current_matched
            and (
                not last_matched
                or current_score
                >= last_score + F3_CHECK_TRANSITION_GLOBAL_SCORE_MARGIN
            )
        )
        return {
            "current_preferred": preferred,
            "available": True,
            "mode": "global_fallback",
            "current_score": current_score,
            "last_score": last_score,
            "different_pixels": different_pixels,
        }

    current_error_map = np.mean(np.abs(observed_f - current_f), axis=2)
    last_error_map = np.mean(np.abs(observed_f - last_f), axis=2)
    current_error = float(np.mean(current_error_map[difference_mask]))
    last_error = float(np.mean(last_error_map[difference_mask]))

    if last_error <= 1e-6:
        error_ratio = float("inf") if current_error > 0 else 1.0
    else:
        error_ratio = current_error / last_error

    preferred = bool(
        current_matched
        and current_error + F3_CHECK_TRANSITION_ERROR_MARGIN < last_error
        and error_ratio <= F3_CHECK_TRANSITION_ERROR_RATIO
    )
    return {
        "current_preferred": preferred,
        "available": True,
        "mode": "difference_mask",
        "current_score": current_score,
        "last_score": last_score,
        "current_error": current_error,
        "last_error": last_error,
        "error_ratio": error_ratio,
        "different_pixels": different_pixels,
    }


def decidir_transicao_estavel_f3(
    *,
    current_check_id: str,
    preferred: bool,
    pending_check_id: str = "",
    pending_frames: int = 0,
) -> dict:
    """Exige vários frames consecutivos antes de trocar o status do CHECK."""
    check_id = str(current_check_id or "")
    if not check_id or not bool(preferred):
        return {
            "promote": False,
            "pending_check_id": "",
            "pending_frames": 0,
        }

    previous_id = str(pending_check_id or "")
    frames = int(pending_frames or 0) + 1 if previous_id == check_id else 1
    return {
        "promote": frames >= F3_CHECK_TRANSITION_STABLE_FRAMES,
        "pending_check_id": check_id,
        "pending_frames": frames,
    }


def _hold_last_check_state(last_check_id: str, last_check_name: str, evidence=None) -> dict:
    name = str(last_check_name or last_check_id or "CHECK").strip().upper()
    return {
        # `unknown` é intencional: o gate operacional já bloqueia o CHECK atual
        # quando as referências estão configuradas, mas o texto continua mostrando
        # ao operador o último estado físico realmente confirmado.
        "kind": "unknown",
        "text": f"DISPLAY EM {name}",
        "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["check"],
        "allow_auto": False,
        "transition_hold": True,
        "check_id": str(last_check_id or ""),
        "check_name": name,
        "transition_evidence": dict(evidence or {}),
    }


def _install_transition_guard() -> None:
    if bool(getattr(operational_module, "_display_f3_check_transition_guard_installed", False)):
        return

    base_build = operational_module._build_operational_state

    def guarded_build(self, frame, project_name: str, context: dict | None):
        base_state = base_build(self, frame, project_name, context)
        kind = str(base_state.get("kind") or "unknown")

        if kind in {"empty", "off"}:
            self._display_f3_transition_pending_check_id = ""
            self._display_f3_transition_pending_frames = 0
            return base_state

        current_check_id = str((context or {}).get("check_id") or "")
        current_check_name = str(
            (context or {}).get("check_name") or current_check_id
        )
        last_check_id = str(
            getattr(self, "_display_f3_last_recognized_check_id", "") or ""
        )
        last_check_name = str(
            getattr(self, "_display_f3_last_recognized_check_name", "")
            or last_check_id
        )

        # Primeiro CHECK da placa: não há estado anterior a proteger.
        if (
            not current_check_id
            or not last_check_id
            or current_check_id == last_check_id
        ):
            self._display_f3_transition_pending_check_id = ""
            self._display_f3_transition_pending_frames = 0
            return base_state

        matcher = getattr(self, "_display_f3_operational_matcher", None)
        if matcher is None:
            return base_state

        last_metadata = matcher.check_store.get(project_name, last_check_id)
        current_metadata = matcher.check_store.get(project_name, current_check_id)
        if not isinstance(last_metadata, dict) or not isinstance(current_metadata, dict):
            return base_state

        current_small = visual_status_module._small_image(frame)
        evidence = avaliar_preferencia_transicao_referencias_f3(
            matcher,
            current_small,
            last_metadata,
            current_metadata,
        )
        self._display_f3_transition_evidence = dict(evidence)

        transition = decidir_transicao_estavel_f3(
            current_check_id=current_check_id,
            preferred=bool(evidence.get("current_preferred")),
            pending_check_id=str(
                getattr(self, "_display_f3_transition_pending_check_id", "") or ""
            ),
            pending_frames=int(
                getattr(self, "_display_f3_transition_pending_frames", 0) or 0
            ),
        )
        self._display_f3_transition_pending_check_id = str(
            transition["pending_check_id"]
        )
        self._display_f3_transition_pending_frames = int(
            transition["pending_frames"]
        )

        if not bool(transition["promote"]):
            return _hold_last_check_state(
                last_check_id,
                last_check_name,
                evidence,
            )

        self._display_f3_transition_pending_check_id = ""
        self._display_f3_transition_pending_frames = 0
        return {
            "kind": "check",
            "text": f"DISPLAY EM {current_check_name.strip().upper()}",
            "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["check"],
            "allow_auto": True,
            "check_id": current_check_id,
            "check_name": current_check_name.strip().upper(),
            "score": evidence.get("current_score"),
            "current_check_reference_configured": True,
            "board_references_complete": bool(
                base_state.get("board_references_complete", True)
            ),
            "transition_confirmed": True,
        }

    operational_module._build_operational_state = guarded_build
    operational_module._display_f3_check_transition_guard_installed = True


_DISPLAY_F3_CHECK_TRANSITION_GUARD_INSTALLED = False


def instalar_guard_transicao_check_display_f3() -> None:
    """Impede BLUE→USB (e demais passos) antes da mudança física real."""
    global _DISPLAY_F3_CHECK_TRANSITION_GUARD_INSTALLED
    if _DISPLAY_F3_CHECK_TRANSITION_GUARD_INSTALLED:
        return
    _install_transition_guard()
    _DISPLAY_F3_CHECK_TRANSITION_GUARD_INSTALLED = True
