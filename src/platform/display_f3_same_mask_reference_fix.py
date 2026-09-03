from __future__ import annotations

from pathlib import Path

import src.platform.display_auto_check_runtime as runtime_module
import src.platform.display_f3_live_runtime_fix as live_runtime_module
from src.models.led_features import LedFeatures
from src.core.feature_extractor import extrair_features_selecao
from src.platform.display_auto_check_analyzer import (
    DISPLAY_AUTO_CLASS_LABELS,
    DISPLAY_AUTO_CLASS_LOW_LIGHT,
    display_mask_to_analysis_selection,
)
from src.platform.display_f3_reference_authority_fix import (
    F3_LOW_LIGHT_DISTANCE_RATIO,
    F3_REFERENCE_AMBIGUOUS_SEPARATION,
    F3_REFERENCE_MIN_CONFIDENCE,
    F3ReferenceAuthorityAnalyzer,
    _nearest_reference,
    _separation,
    classificar_mascara_com_referencias_f3,
)
from src.platform.display_project_repository import (
    DISPLAY_CHECK_STATE_OFF,
    DISPLAY_CHECK_STATE_ON,
)


F3_SAME_MASK_REFERENCE_SOURCE = "f3_same_mask_checks"
F3_STATE_SAMPLE_FALLBACK_SOURCE = "f3_state_samples_no_check_photo"


def classificar_mascara_por_referencias_locais_f3(
    *,
    current: LedFeatures,
    on_references: list[LedFeatures],
    off_references: list[LedFeatures],
    low_light_references: list[LedFeatures] | None = None,
) -> dict | None:
    """Classifica uma máscara comparando somente o mesmo segmento físico.

    ACESO e APAGADO são obtidos de fotos de CHECKS do próprio Projeto Display
    nas quais esta mesma máscara estava configurada em cada estado. O estado
    esperado do CHECK atual não participa da decisão, evitando aprovação por
    antecipação. A classe é definida exclusivamente pela referência mais próxima.
    """
    _on_reference, on_index, distance_on = _nearest_reference(
        current,
        list(on_references or ()),
    )
    _off_reference, off_index, distance_off = _nearest_reference(
        current,
        list(off_references or ()),
    )
    if distance_on is None or distance_off is None:
        return None

    state = (
        DISPLAY_CHECK_STATE_ON
        if float(distance_on) < float(distance_off)
        else DISPLAY_CHECK_STATE_OFF
    )
    distances = {
        DISPLAY_CHECK_STATE_ON: float(distance_on),
        DISPLAY_CHECK_STATE_OFF: float(distance_off),
    }

    _low_reference, low_index, low_distance = _nearest_reference(
        current,
        list(low_light_references or ()),
    )
    if low_distance is not None:
        distances[DISPLAY_AUTO_CLASS_LOW_LIGHT] = float(low_distance)
        binary_best = min(float(distance_on), float(distance_off))
        if (
            binary_best > 1e-9
            and float(low_distance)
            <= binary_best * F3_LOW_LIGHT_DISTANCE_RATIO
        ):
            state = DISPLAY_AUTO_CLASS_LOW_LIGHT

    separation = _separation(float(distance_on), float(distance_off))
    if state == DISPLAY_AUTO_CLASS_LOW_LIGHT:
        ordered = sorted(float(value) for value in distances.values())
        best = ordered[0]
        second = ordered[1] if len(ordered) > 1 else best
        confidence = max(
            0.50,
            min(0.99, second / max(1e-9, best + second)),
        )
    else:
        confidence = min(0.99, 0.50 + (0.49 * separation))
        if separation < F3_REFERENCE_AMBIGUOUS_SEPARATION:
            confidence = min(
                confidence,
                F3_REFERENCE_MIN_CONFIDENCE - 0.01,
            )

    nearest_indexes = {
        DISPLAY_CHECK_STATE_ON: on_index,
        DISPLAY_CHECK_STATE_OFF: off_index,
    }
    if low_index is not None:
        nearest_indexes[DISPLAY_AUTO_CLASS_LOW_LIGHT] = low_index

    return {
        "state": state,
        "label": DISPLAY_AUTO_CLASS_LABELS[state],
        "confidence": round(float(confidence), 4),
        "distances": {
            key: round(float(value), 4)
            for key, value in distances.items()
        },
        "reference_source": F3_SAME_MASK_REFERENCE_SOURCE,
        "reference_separation": round(float(separation), 4),
        "nearest_reference_indexes": nearest_indexes,
        "reference_counts": {
            DISPLAY_CHECK_STATE_ON: len(on_references or ()),
            DISPLAY_CHECK_STATE_OFF: len(off_references or ()),
            DISPLAY_AUTO_CLASS_LOW_LIGHT: len(low_light_references or ()),
        },
    }


class F3SameMaskReferenceAnalyzer(F3ReferenceAuthorityAnalyzer):
    """Autoridade final do F3 usando referências do mesmo segmento físico."""

    def __init__(self, repository) -> None:
        super().__init__(repository)
        self._same_mask_cache_key = None
        self._same_mask_cache = None

    def _same_mask_signature(
        self,
        project_name: str,
        project: dict,
        visual_rotation: int,
    ):
        checks_signature = []
        for check in self.repository.listar_checks(project_name):
            check_id = str(check.get("id") or "")
            states = check.get("mask_states", {})
            states_signature = tuple(
                sorted(
                    (str(mask_id), str(state))
                    for mask_id, state in (
                        states.items() if isinstance(states, dict) else ()
                    )
                )
            )
            metadata = self.presence_store.get(project_name, check_id)
            image_signature = ("", 0, 0)
            if isinstance(metadata, dict):
                path = Path(str(metadata.get("image_path") or ""))
                try:
                    stat = path.stat()
                    image_signature = (
                        str(path),
                        int(stat.st_mtime_ns),
                        int(stat.st_size),
                    )
                except OSError:
                    image_signature = (str(path), 0, 0)
            checks_signature.append(
                (check_id, states_signature, image_signature)
            )

        return (
            str(project_name),
            int(visual_rotation),
            str(project.get("updated_at") or ""),
            tuple(checks_signature),
        )

    def _build_same_mask_profiles(
        self,
        project_name: str,
        project: dict,
        masks: list[dict],
        visual_rotation: int,
    ) -> dict[str, dict]:
        profiles: dict[str, dict] = {
            str(mask.get("id")): {
                DISPLAY_CHECK_STATE_ON: [],
                DISPLAY_CHECK_STATE_OFF: [],
                "sources": {
                    DISPLAY_CHECK_STATE_ON: [],
                    DISPLAY_CHECK_STATE_OFF: [],
                },
            }
            for mask in masks
            if isinstance(mask, dict) and mask.get("id") is not None
        }

        for check in self.repository.listar_checks(project_name):
            check_id = str(check.get("id") or "")
            if not check_id:
                continue
            states = (
                check.get("mask_states", {})
                if isinstance(check.get("mask_states"), dict)
                else {}
            )
            reference_frame, reference_masks, _configured = (
                self._check_reference_context(
                    project_name,
                    check_id,
                    project,
                    masks,
                    visual_rotation,
                )
            )
            if reference_frame is None:
                continue

            check_name = str(check.get("name") or check_id)
            for mask_id, profile in profiles.items():
                state = str(states.get(mask_id) or "")
                if state not in (
                    DISPLAY_CHECK_STATE_ON,
                    DISPLAY_CHECK_STATE_OFF,
                ):
                    continue
                visual_mask = reference_masks.get(mask_id)
                if visual_mask is None:
                    continue
                try:
                    selection = display_mask_to_analysis_selection(visual_mask)
                    features = extrair_features_selecao(
                        reference_frame,
                        selection,
                    )
                except (TypeError, ValueError):
                    continue
                if int(getattr(features, "area_pixels", 0) or 0) <= 0:
                    continue

                profile[state].append(features)
                profile["sources"][state].append(
                    {
                        "check_id": check_id,
                        "check_name": check_name,
                    }
                )

        return profiles

    def _same_mask_profiles(
        self,
        project_name: str,
        project: dict,
        masks: list[dict],
        visual_rotation: int,
    ) -> dict[str, dict]:
        cache_key = self._same_mask_signature(
            project_name,
            project,
            visual_rotation,
        )
        if cache_key == self._same_mask_cache_key:
            return self._same_mask_cache or {}

        profiles = self._build_same_mask_profiles(
            project_name,
            project,
            masks,
            visual_rotation,
        )
        self._same_mask_cache_key = cache_key
        self._same_mask_cache = profiles
        return profiles

    @staticmethod
    def _source_for_index(profile: dict, state: str, index):
        try:
            source_index = int(index)
        except (TypeError, ValueError):
            return None
        sources = (
            profile.get("sources", {}).get(state, [])
            if isinstance(profile, dict)
            else []
        )
        if source_index < 0 or source_index >= len(sources):
            return None
        return dict(sources[source_index])

    @staticmethod
    def _apply_classification(
        item: dict,
        classified: dict,
        *,
        reference_source: str,
        reference_checks: dict | None = None,
    ) -> dict:
        updated = dict(item)
        updated.update(
            {
                "classified": classified["state"],
                "classified_label": classified["label"],
                "matched": (
                    classified["state"]
                    == str(item.get("expected") or "")
                ),
                "confidence": classified["confidence"],
                "distances": classified["distances"],
                "reference_source": reference_source,
                "reference_separation": classified.get(
                    "reference_separation"
                ),
                "nearest_reference_indexes": classified.get(
                    "nearest_reference_indexes",
                    {},
                ),
                "reference_counts": classified.get(
                    "reference_counts",
                    {},
                ),
            }
        )
        if reference_checks is not None:
            updated["reference_checks"] = reference_checks
        else:
            updated.pop("reference_checks", None)
        return updated

    def analyze(
        self,
        frame,
        project_name: str,
        check_id: str,
        visual_rotation: int = 0,
    ) -> dict:
        analysis = super().analyze(
            frame=frame,
            project_name=project_name,
            check_id=check_id,
            visual_rotation=visual_rotation,
        )
        if not bool(analysis.get("ready")):
            return analysis

        results = [
            item
            for item in (analysis.get("mask_results") or [])
            if isinstance(item, dict)
        ]
        if not results:
            return analysis

        project = self.repository.carregar_projeto(project_name)
        if project is None:
            return analysis
        masks = list(project.get("masks", []) or [])
        profiles = self._same_mask_profiles(
            project_name,
            project,
            masks,
            visual_rotation,
        )
        state_sets = self._state_reference_sets(project_name)
        generic_on = list(state_sets.get(DISPLAY_CHECK_STATE_ON, []) or [])
        generic_off = list(state_sets.get(DISPLAY_CHECK_STATE_OFF, []) or [])
        low_light_references = list(
            state_sets.get(DISPLAY_AUTO_CLASS_LOW_LIGHT, []) or []
        )

        recalibrated = []
        local_used_count = 0
        fallback_used_count = 0
        complete_pair_count = 0
        missing_pair_ids = []

        for item in results:
            mask_id = str(item.get("mask_id") or "")
            expected = str(item.get("expected") or "")
            features_data = item.get("features")
            if not isinstance(features_data, dict):
                recalibrated.append(item)
                continue
            current_features = LedFeatures.from_dict(features_data)

            profile = profiles.get(mask_id, {})
            local_on = list(profile.get(DISPLAY_CHECK_STATE_ON, []) or [])
            local_off = list(profile.get(DISPLAY_CHECK_STATE_OFF, []) or [])

            if local_on and local_off:
                complete_pair_count += 1
                classified = classificar_mascara_por_referencias_locais_f3(
                    current=current_features,
                    on_references=local_on,
                    off_references=local_off,
                    low_light_references=low_light_references,
                )
                if classified is not None:
                    nearest = classified["nearest_reference_indexes"]
                    reference_checks = {
                        DISPLAY_CHECK_STATE_ON: self._source_for_index(
                            profile,
                            DISPLAY_CHECK_STATE_ON,
                            nearest.get(DISPLAY_CHECK_STATE_ON),
                        ),
                        DISPLAY_CHECK_STATE_OFF: self._source_for_index(
                            profile,
                            DISPLAY_CHECK_STATE_OFF,
                            nearest.get(DISPLAY_CHECK_STATE_OFF),
                        ),
                    }
                    recalibrated.append(
                        self._apply_classification(
                            item,
                            classified,
                            reference_source=F3_SAME_MASK_REFERENCE_SOURCE,
                            reference_checks=reference_checks,
                        )
                    )
                    local_used_count += 1
                    continue

            # Sem um par local completo, não reutilizamos a classificação do pai,
            # pois ela contém a foto do CHECK atual como referência esperada. Foi
            # exatamente essa mistura (foto local + estado oposto genérico) que
            # produziu o padrão sistemático de baixa conformidade no BLUE.
            missing_pair_ids.append(mask_id)
            fallback = classificar_mascara_com_referencias_f3(
                current=current_features,
                expected=expected,
                on_references=generic_on,
                off_references=generic_off,
                low_light_references=low_light_references,
                check_expected_reference=None,
            )
            if fallback is None:
                recalibrated.append(item)
                continue

            recalibrated.append(
                self._apply_classification(
                    item,
                    fallback,
                    reference_source=F3_STATE_SAMPLE_FALLBACK_SOURCE,
                )
            )
            fallback_used_count += 1

        analysis["mask_results"] = recalibrated
        analysis["active_mask_count"] = len(recalibrated)
        analysis["matched_mask_count"] = sum(
            1 for item in recalibrated if bool(item.get("matched"))
        )
        analysis["approved"] = bool(recalibrated) and all(
            bool(item.get("matched"))
            for item in recalibrated
        )
        analysis["reason"] = (
            "check_conforme_referencias_mesma_mascara_f3"
            if analysis["approved"]
            else "check_nao_conforme_referencias_mesma_mascara_f3"
        )
        analysis["reference_authority"] = F3_SAME_MASK_REFERENCE_SOURCE
        analysis["same_mask_reference_pair_count"] = int(complete_pair_count)
        analysis["same_mask_reference_used_count"] = int(local_used_count)
        analysis["state_sample_fallback_used_count"] = int(fallback_used_count)
        analysis["same_mask_reference_missing_ids"] = missing_pair_ids
        return analysis


_INSTALLED = False


def instalar_referencias_por_mesma_mascara_display_f3() -> None:
    """Instala a autoridade por segmento apenas no analisador Display F3."""
    global _INSTALLED
    if _INSTALLED:
        return

    runtime_module.DisplayAutomaticCheckAnalyzer = F3SameMaskReferenceAnalyzer
    live_runtime_module.DisplayAutomaticCheckAnalyzer = F3SameMaskReferenceAnalyzer
    _INSTALLED = True
