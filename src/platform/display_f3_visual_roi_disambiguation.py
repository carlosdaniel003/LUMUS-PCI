from __future__ import annotations

"""Desempate informativo da ANÁLISE VISUAL do Display F3.

Um score de CHECK calculado somente contra sua própria foto pode permanecer alto
quando a placa está desligada, porque fundo, placa e fixture dominam a semelhança.
Esta camada resolve somente o status visual comparando, NA MESMA ROI desenhada do
CHECK, o frame atual contra:

1) a foto daquele CHECK;
2) a foto da placa desligada.

Se a foto desligada vencer com margem clara, o CHECK é retirado apenas da disputa
da ANÁLISE VISUAL. Não usa máscaras, não consulta o CHECK lógico esperado, não
muda OK/NG, avanço, debounce, rearmamento nem qualquer função do F2.
"""

from copy import deepcopy

import src.platform.display_f3_snapshot_debug_lightweight_ui as debug_ui
import src.platform.display_f3_visual_analysis_relative_fallback as visual_module
from src.platform.display_visual_reference_status import (
    DISPLAY_PROJECT_REFERENCE_BOARD_OFF,
)


F3_VISUAL_CHECK_OFF_SAME_ROI_MIN_SCORE = 0.60
F3_VISUAL_CHECK_OFF_SAME_ROI_MIN_MARGIN = 0.035


def _safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _score_off_on_check_roi(frame, off_metadata: dict, check_roi: dict) -> float | None:
    """Pontua a foto OFF usando exatamente a ROI desenhada para o CHECK."""
    forced = deepcopy(off_metadata)
    forced["roi"] = deepcopy(check_roi)
    try:
        return visual_module._score_reference_full_roi(frame, forced)
    except Exception:
        return None


def _extend_collect_visual_candidates(original):
    def collect(matcher, frame, project_name: str, score_overrides=None):
        candidates = original(
            matcher,
            frame,
            project_name,
            score_overrides=score_overrides,
        )
        if not isinstance(candidates, dict):
            return candidates

        for item in candidates.values():
            if isinstance(item, dict):
                item.setdefault("decision_eligible", True)

        try:
            project_refs = matcher.project_store.get_all(project_name)
        except Exception:
            return candidates
        off_metadata = project_refs.get(DISPLAY_PROJECT_REFERENCE_BOARD_OFF)
        if not isinstance(off_metadata, dict):
            return candidates

        for item in candidates.values():
            if not isinstance(item, dict) or str(item.get("kind") or "") != "check":
                continue
            roi = item.get("roi")
            if not isinstance(roi, dict) or not roi:
                item["same_roi_off_comparison_available"] = False
                continue

            check_score = _safe_float(item.get("score"))
            off_same_roi_score = _score_off_on_check_roi(frame, off_metadata, roi)
            if check_score is None or off_same_roi_score is None:
                item["same_roi_off_comparison_available"] = False
                continue

            check_advantage = float(check_score) - float(off_same_roi_score)
            off_advantage = -check_advantage
            suppress = bool(
                float(off_same_roi_score) >= F3_VISUAL_CHECK_OFF_SAME_ROI_MIN_SCORE
                and off_advantage >= F3_VISUAL_CHECK_OFF_SAME_ROI_MIN_MARGIN
            )

            item["same_roi_off_comparison_available"] = True
            item["same_roi_check_score"] = round(float(check_score), 6)
            item["same_roi_off_score"] = round(float(off_same_roi_score), 6)
            item["same_roi_check_advantage"] = round(check_advantage, 6)
            item["same_roi_off_advantage"] = round(off_advantage, 6)
            item["same_roi_off_min_score"] = F3_VISUAL_CHECK_OFF_SAME_ROI_MIN_SCORE
            item["same_roi_off_min_margin"] = F3_VISUAL_CHECK_OFF_SAME_ROI_MIN_MARGIN
            item["suppressed_by_off_same_roi"] = suppress
            item["decision_eligible"] = not suppress
            item["roi_disambiguation_mode"] = "check_roi_against_check_photo_and_board_off_photo"
        return candidates

    return collect


def _extend_visual_resolver(original):
    def resolve(candidates):
        source = candidates if isinstance(candidates, dict) else {}
        eligible = {
            key: value
            for key, value in source.items()
            if isinstance(value, dict) and value.get("decision_eligible") is not False
        }
        decision = original(eligible)
        if not isinstance(decision, dict):
            return decision

        suppressed = [
            str(value.get("check_id") or key)
            for key, value in source.items()
            if isinstance(value, dict)
            and str(value.get("kind") or "") == "check"
            and bool(value.get("suppressed_by_off_same_roi"))
        ]
        decision["roi_same_region_disambiguation"] = True
        decision["suppressed_checks_by_off_same_roi"] = suppressed
        decision["suppressed_check_count"] = len(suppressed)
        decision["candidate_count_before_roi_gate"] = len(source)
        decision["candidate_count_after_roi_gate"] = len(eligible)
        return decision

    return resolve


def _extend_debug_report(original):
    def report(snapshot: dict) -> str:
        base = original(snapshot)
        visual = snapshot.get("visual_analysis") if isinstance(snapshot, dict) else None
        if not base or not isinstance(visual, dict):
            return base
        candidates = visual.get("candidates")
        if not isinstance(candidates, dict):
            return base

        lines = [
            "",
            "[DESAMBIGUAÇÃO VISUAL CHECK x PLACA DESLIGADA - MESMA ROI]",
            "Somente status informativo. Não usa máscaras e não altera julgamento.",
        ]
        found = False
        for key, item in candidates.items():
            if not isinstance(item, dict) or str(item.get("kind") or "") != "check":
                continue
            if not bool(item.get("same_roi_off_comparison_available")):
                continue
            found = True
            lines.append(
                "visual_same_roi "
                f"| key={key} "
                f"| name={item.get('name', '--')} "
                f"| check_score={item.get('same_roi_check_score', '--')} "
                f"| off_same_roi_score={item.get('same_roi_off_score', '--')} "
                f"| check_advantage={item.get('same_roi_check_advantage', '--')} "
                f"| off_advantage={item.get('same_roi_off_advantage', '--')} "
                f"| suppressed_by_off={item.get('suppressed_by_off_same_roi', False)} "
                f"| decision_eligible={item.get('decision_eligible', True)} "
                f"| roi={item.get('roi', '--')}"
            )
        if not found:
            lines.append("visual_same_roi | comparação indisponível")
        return f"{base}\n" + "\n".join(lines)

    return report


_INSTALLED = False


def instalar_desambiguacao_roi_analise_visual_display_f3() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    if not bool(getattr(visual_module, "_display_f3_visual_same_roi_gate_installed", False)):
        visual_module._collect_visual_candidates = _extend_collect_visual_candidates(
            visual_module._collect_visual_candidates
        )
        visual_module.resolver_analise_visual_candidatos_f3 = _extend_visual_resolver(
            visual_module.resolver_analise_visual_candidatos_f3
        )
        visual_module._display_f3_visual_same_roi_gate_installed = True

    if not bool(getattr(debug_ui, "_display_f3_visual_same_roi_report_installed", False)):
        debug_ui._visual_report_block = _extend_debug_report(debug_ui._visual_report_block)
        debug_ui._display_f3_visual_same_roi_report_installed = True

    _INSTALLED = True
