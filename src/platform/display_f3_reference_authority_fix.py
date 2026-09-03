from __future__ import annotations

from pathlib import Path

import cv2

import src.platform.display_auto_check_policy as policy_module
import src.platform.display_auto_check_runtime as runtime_module
import src.platform.display_f3_operational_status as operational_module
import src.platform.display_check_presence_reference as presence_module
from src.core.classifier import ReferenceLedClassifier
from src.core.feature_extractor import extrair_features_selecao
from src.models.led_features import LedFeatures
from src.platform.display_auto_check_analyzer import (
    DISPLAY_AUTO_CLASS_LABELS,
    DISPLAY_AUTO_CLASS_LOW_LIGHT,
    DISPLAY_AUTO_FEATURE_WEIGHTS,
    display_mask_to_analysis_selection,
)
from src.platform.display_project_repository import (
    DISPLAY_CHECK_STATE_OFF,
    DISPLAY_CHECK_STATE_ON,
    normalizar_resolucao_display,
)
from src.platform.display_visual_rotation import preparar_check_visual_display


# O F3 passa a exigir margem real entre classes. O classificador comum do ODIN
# limita a confiança mínima a 0.50; usar 0.50 também como gate tornava qualquer
# leitura, inclusive uma leitura quase empatada por reflexo, automaticamente
# "confiante" no F3.
F3_REFERENCE_MIN_CONFIDENCE = 0.58

# Quando a leitura está claramente mais próxima da aparência da própria máscara
# na foto do CHECK do que da classe oposta, a referência local do CHECK prevalece.
# Isso absorve reflexos legítimos de segmentos vizinhos que já estavam presentes
# no momento em que a referência do H1/BLUE/USB/etc. foi capturada.
F3_CHECK_REFERENCE_STRONG_RATIO = 0.72

# POUCA LUZ continua sendo uma classe explícita, mas somente vence quando uma
# amostra real dessa classe estiver claramente mais próxima que ACESO/APAGADO.
F3_LOW_LIGHT_DISTANCE_RATIO = 0.82

# Distâncias muito próximas representam ambiguidade óptica. Nesse caso o F3 não
# acumula OK nem NG: mantém a busca até chegar um frame com separação suficiente.
F3_REFERENCE_AMBIGUOUS_SEPARATION = 0.16

_PRESENCE_ONLY_REASONS = {
    "referencia_visual_check_indisponivel",
    "referencia_visual_check_nao_corresponde",
}


def _feature_distance(current: LedFeatures, reference: LedFeatures) -> float:
    distance = 0.0
    for name, weight in DISPLAY_AUTO_FEATURE_WEIGHTS.items():
        distance += abs(
            float(getattr(current, name, 0.0))
            - float(getattr(reference, name, 0.0))
        ) * float(weight)
    return float(distance)


def _reference_features(entries: list[dict] | None) -> list[LedFeatures]:
    result: list[LedFeatures] = []
    for entry in entries or ():
        sample = entry.get("sample", entry) if isinstance(entry, dict) else None
        data = sample.get("features") if isinstance(sample, dict) else None
        if isinstance(data, dict) and data:
            result.append(LedFeatures.from_dict(data))
    return result


def _nearest_reference(
    current: LedFeatures,
    references: list[LedFeatures],
) -> tuple[LedFeatures | None, int | None, float | None]:
    if not references:
        return None, None, None
    distances = [
        _feature_distance(current, reference)
        for reference in references
    ]
    index = min(range(len(distances)), key=distances.__getitem__)
    return references[index], int(index), float(distances[index])


def _separation(distance_on: float, distance_off: float) -> float:
    denominator = max(1e-9, float(distance_on) + float(distance_off))
    return abs(float(distance_on) - float(distance_off)) / denominator


def classificar_mascara_com_referencias_f3(
    *,
    current: LedFeatures,
    expected: str,
    on_references: list[LedFeatures],
    off_references: list[LedFeatures],
    low_light_references: list[LedFeatures] | None = None,
    check_expected_reference: LedFeatures | None = None,
) -> dict | None:
    """Classifica uma máscara usando somente referências pertencentes ao F3.

    Prioridade:
    1. aparência da mesma máscara na foto de referência do CHECK atual;
    2. amostras F3 reais ACESO/APAGADO, individualmente, sem centróide;
    3. amostras F3 reais POUCA LUZ, quando configuradas.

    A foto do CHECK nunca é usada para dizer que o runtime está em outro CHECK.
    Ela serve somente como referência óptica local da máscara que está sendo
    analisada no CHECK lógico atual.
    """
    expected_state = str(expected or "")
    if expected_state not in (DISPLAY_CHECK_STATE_ON, DISPLAY_CHECK_STATE_OFF):
        return None

    source = "f3_state_samples"
    expected_reference_index = None

    if check_expected_reference is not None:
        source = "f3_check_mask"
        if expected_state == DISPLAY_CHECK_STATE_ON:
            on_reference = check_expected_reference
            off_reference, opposite_index, _ = _nearest_reference(
                check_expected_reference,
                off_references,
            )
            on_index = None
            off_index = opposite_index
        else:
            off_reference = check_expected_reference
            on_reference, opposite_index, _ = _nearest_reference(
                check_expected_reference,
                on_references,
            )
            on_index = opposite_index
            off_index = None
    else:
        on_reference, on_index, _ = _nearest_reference(current, on_references)
        off_reference, off_index, _ = _nearest_reference(current, off_references)

    if on_reference is None or off_reference is None:
        return None

    binary_classifier = ReferenceLedClassifier(
        features_referencia_acesa=on_reference,
        features_referencia_apagada=off_reference,
    )
    binary = binary_classifier.classificar_led_por_referencia(
        features_atual=current,
        centro_x=0,
        centro_y=0,
        raio=1,
    )

    distance_on = _feature_distance(current, on_reference)
    distance_off = _feature_distance(current, off_reference)
    state = (
        DISPLAY_CHECK_STATE_ON
        if int(getattr(binary, "valor_binario", 0) or 0) == 1
        else DISPLAY_CHECK_STATE_OFF
    )

    expected_distance = (
        distance_on
        if expected_state == DISPLAY_CHECK_STATE_ON
        else distance_off
    )
    opposite_distance = (
        distance_off
        if expected_state == DISPLAY_CHECK_STATE_ON
        else distance_on
    )

    # A mesma máscara, na mesma posição e com os mesmos reflexos de vizinhança,
    # é uma referência mais forte que um limiar genérico quando a proximidade é
    # inequívoca. Esta é a principal correção para o 27/30 <-> 30/30 observado.
    if (
        check_expected_reference is not None
        and expected_distance
        <= max(1e-9, opposite_distance) * F3_CHECK_REFERENCE_STRONG_RATIO
    ):
        state = expected_state

    distances = {
        DISPLAY_CHECK_STATE_ON: float(distance_on),
        DISPLAY_CHECK_STATE_OFF: float(distance_off),
    }

    low_reference, low_index, low_distance = _nearest_reference(
        current,
        list(low_light_references or ()),
    )
    if low_reference is not None and low_distance is not None:
        distances[DISPLAY_AUTO_CLASS_LOW_LIGHT] = float(low_distance)
        binary_best = min(distance_on, distance_off)
        if (
            binary_best > 1e-9
            and float(low_distance)
            <= binary_best * F3_LOW_LIGHT_DISTANCE_RATIO
        ):
            state = DISPLAY_AUTO_CLASS_LOW_LIGHT

    separation = _separation(distance_on, distance_off)
    binary_confidence = float(getattr(binary, "confianca", 0.50) or 0.50)

    if state == DISPLAY_AUTO_CLASS_LOW_LIGHT:
        ordered = sorted(float(value) for value in distances.values())
        best = ordered[0]
        second = ordered[1] if len(ordered) > 1 else best
        confidence = max(
            0.50,
            min(0.99, float(second / max(1e-9, best + second))),
        )
    else:
        # Similaridade com protótipo também participa da confiança. Uma máscara
        # quase idêntica à própria referência do CHECK não deve ficar presa ao
        # piso 0.50 do classificador genérico.
        prototype_confidence = 0.50 + (0.49 * separation)
        confidence = max(binary_confidence, prototype_confidence)
        confidence = min(0.99, confidence)

        # Em empate óptico real, não inventamos uma certeza. A política do F3
        # tratará < 0.58 como SEARCHING em vez de acumular OK/NG.
        if separation < F3_REFERENCE_AMBIGUOUS_SEPARATION:
            confidence = min(confidence, F3_REFERENCE_MIN_CONFIDENCE - 0.01)

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
        "reference_source": source,
        "reference_separation": round(float(separation), 4),
        "expected_reference_distance": round(float(expected_distance), 4),
        "opposite_reference_distance": round(float(opposite_distance), 4),
        "nearest_reference_indexes": nearest_indexes,
        "reference_counts": {
            DISPLAY_CHECK_STATE_ON: len(on_references),
            DISPLAY_CHECK_STATE_OFF: len(off_references),
            DISPLAY_AUTO_CLASS_LOW_LIGHT: len(low_light_references or ()),
        },
    }


class F3ReferenceAuthorityAnalyzer(presence_module.DisplayPresenceAwareAnalyzer):
    """Autoridade óptica final do F3: CHECK lógico + referências por máscara."""

    def _state_reference_sets(self, project_name: str) -> dict[str, list[LedFeatures]]:
        return {
            state: _reference_features(
                self.store.active_references(project_name, state)
            )
            for state in (
                DISPLAY_CHECK_STATE_ON,
                DISPLAY_CHECK_STATE_OFF,
                DISPLAY_AUTO_CLASS_LOW_LIGHT,
            )
        }

    def _check_reference_context(
        self,
        project_name: str,
        check_id: str,
        project: dict,
        masks: list[dict],
        visual_rotation: int,
    ) -> tuple[object | None, dict[str, dict], bool]:
        metadata = self.presence_store.get(project_name, check_id)
        if not isinstance(metadata, dict):
            return None, {}, False

        path = Path(str(metadata.get("image_path") or ""))
        image = cv2.imread(str(path), cv2.IMREAD_COLOR) if path.is_file() else None
        if image is None or getattr(image, "size", 0) == 0:
            return None, {}, True

        master_resolution = normalizar_resolucao_display(
            project.get("master_resolution")
        )
        if master_resolution is None:
            return None, {}, True

        visual_frame, _visual_resolution, visual_masks = preparar_check_visual_display(
            image,
            master_resolution,
            masks,
            visual_rotation,
        )
        if visual_frame is None or getattr(visual_frame, "size", 0) == 0:
            return None, {}, True

        mask_by_id = {
            str(mask.get("id")): mask
            for mask in visual_masks
            if isinstance(mask, dict) and mask.get("id") is not None
        }
        return visual_frame, mask_by_id, True

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

        mask_results = [
            item
            for item in (analysis.get("mask_results") or [])
            if isinstance(item, dict)
        ]
        if not mask_results:
            return analysis

        # A extensão antiga de presença podia transformar um resultado de
        # máscaras válido em indisponível/NG apenas porque o SSIM do frame inteiro
        # variou. A partir daqui esse SSIM fica somente como diagnóstico.
        if str(analysis.get("reason") or "") in _PRESENCE_ONLY_REASONS:
            analysis["ready"] = True
            analysis["approved"] = None

        if not bool(analysis.get("ready")):
            return analysis

        project = self.repository.carregar_projeto(project_name)
        check = self.repository.carregar_check(project_name, check_id)
        if project is None or check is None:
            return analysis

        masks = list(project.get("masks", []) or [])
        state_sets = self._state_reference_sets(project_name)
        on_references = state_sets[DISPLAY_CHECK_STATE_ON]
        off_references = state_sets[DISPLAY_CHECK_STATE_OFF]
        if not on_references or not off_references:
            return analysis

        reference_frame, reference_masks, reference_configured = (
            self._check_reference_context(
                project_name,
                check_id,
                project,
                masks,
                visual_rotation,
            )
        )

        recalibrated = []
        for item in mask_results:
            mask_id = str(item.get("mask_id") or "")
            expected = str(item.get("expected") or "")
            current_features_data = item.get("features")
            if not isinstance(current_features_data, dict):
                recalibrated.append(item)
                continue

            current_features = LedFeatures.from_dict(current_features_data)
            check_expected_reference = None
            visual_mask = reference_masks.get(mask_id)
            if reference_frame is not None and visual_mask is not None:
                try:
                    selection = display_mask_to_analysis_selection(visual_mask)
                    reference_features = extrair_features_selecao(
                        reference_frame,
                        selection,
                    )
                    if int(getattr(reference_features, "area_pixels", 0) or 0) > 0:
                        check_expected_reference = reference_features
                except (TypeError, ValueError):
                    check_expected_reference = None

            classified = classificar_mascara_com_referencias_f3(
                current=current_features,
                expected=expected,
                on_references=on_references,
                off_references=off_references,
                low_light_references=state_sets[DISPLAY_AUTO_CLASS_LOW_LIGHT],
                check_expected_reference=check_expected_reference,
            )
            if classified is None:
                recalibrated.append(item)
                continue

            updated = dict(item)
            updated.update(
                {
                    "classified": classified["state"],
                    "classified_label": classified["label"],
                    "matched": classified["state"] == expected,
                    "confidence": classified["confidence"],
                    "distances": classified["distances"],
                    "reference_source": classified["reference_source"],
                    "reference_separation": classified["reference_separation"],
                    "expected_reference_distance": classified[
                        "expected_reference_distance"
                    ],
                    "opposite_reference_distance": classified[
                        "opposite_reference_distance"
                    ],
                    "nearest_reference_indexes": classified[
                        "nearest_reference_indexes"
                    ],
                    "reference_counts": classified["reference_counts"],
                }
            )
            recalibrated.append(updated)

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
            "check_conforme_referencias_f3"
            if analysis["approved"]
            else "check_nao_conforme_referencias_f3"
        )
        analysis["reference_authority"] = "display_f3_masks"
        analysis["check_reference_configured"] = bool(reference_configured)
        analysis["check_reference_used"] = any(
            str(item.get("reference_source")) == "f3_check_mask"
            for item in recalibrated
        )

        presence = analysis.get("presence_reference")
        if isinstance(presence, dict):
            presence["decision_authority"] = False
            presence["role"] = "diagnostic_only"

        return analysis


def _sequence_authoritative_operational_state(
    self,
    frame,
    project_name: str,
    context: dict | None,
) -> dict:
    """Status do F3 mostra o CHECK lógico, não tenta adivinhar H1/USB pelo frame."""
    current = context if isinstance(context, dict) else {}
    check_id = str(current.get("check_id") or "")
    check_name = str(current.get("check_name") or check_id).strip().upper()

    # Durante o ciclo ativo, a sequência do próprio F3 é a única fonte do nome
    # do CHECK. Isso elimina H1 <-> USB <-> BLUE oscilando por SSIM parecido.
    if check_id and not bool(getattr(self, "_display_f3_waiting_empty_rearm", False)):
        configured = presence_module.DisplayCheckPresenceReferenceStore(
            self.display_project_repository
        ).get(project_name, check_id) is not None
        return {
            "kind": "check",
            "text": f"CHECK ATUAL • {check_name or check_id}",
            "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["check"],
            "allow_auto": True,
            "check_name": check_name,
            "check_id": check_id,
            "source": "f3_sequence",
            "current_check_reference_configured": bool(configured),
        }

    # Depois de OK/NG/descartada, a única inferência visual necessária é saber
    # se a placa realmente saiu do suporte para rearmar o próximo ciclo.
    if bool(getattr(self, "_display_f3_waiting_empty_rearm", False)):
        repository = getattr(self, "display_project_repository", None)
        if repository is None:
            return {
                "kind": "unavailable",
                "text": "REFERÊNCIA DE SUPORTE INDISPONÍVEL",
                "color": operational_module.F3_OPERATIONAL_STATUS_COLORS[
                    "unavailable"
                ],
                "allow_auto": False,
            }

        matcher = getattr(self, "_display_f3_operational_matcher", None)
        if matcher is None or getattr(matcher, "repository", None) is not repository:
            matcher = operational_module.DisplayVisualReferenceMatcher(repository)
            self._display_f3_operational_matcher = matcher

        current_small = operational_module.visual_status_module._small_image(frame)
        references = matcher.project_store.get_all(project_name)
        empty_metadata = references.get(
            operational_module.DISPLAY_PROJECT_REFERENCE_EMPTY_SUPPORT
        )
        empty_candidate = operational_module._score_candidate(
            matcher,
            current_small,
            empty_metadata,
        )
        if bool((empty_candidate or {}).get("matched")):
            return {
                "kind": "empty",
                "text": "PLACA FORA DO SUPORTE",
                "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["empty"],
                "allow_auto": False,
                "source": "f3_empty_support_reference",
            }
        return {
            "kind": "unknown",
            "text": "AGUARDANDO RETIRADA DA PLACA",
            "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["unknown"],
            "allow_auto": False,
            "source": "f3_empty_support_reference",
        }

    # Fora de um ciclo, preserva o resolvedor anterior para os estados físicos
    # gerais. Não há CHECK anterior/atual para oscilar neste caso.
    return _ORIGINAL_OPERATIONAL_STATE_BUILDER(
        self,
        frame,
        project_name,
        context,
    )


_ORIGINAL_OPERATIONAL_STATE_BUILDER = operational_module._build_operational_state
_INSTALLED = False


def instalar_autoridade_referencias_display_f3() -> None:
    """Instala a correção final exclusivamente no pipeline Display/F3."""
    global _INSTALLED
    if _INSTALLED:
        return

    # O runtime instancia este símbolo somente dentro do mixin F3.
    runtime_module.DisplayAutomaticCheckAnalyzer = F3ReferenceAuthorityAnalyzer

    # O SSIM de frame inteiro continua disponível para diagnóstico/preview, mas
    # deixa de autorizar ou impedir OK/NG. As máscaras + referências F3 decidem.
    runtime_module.decidir_analise_display_f3 = policy_module.decidir_analise_display_f3

    # Margem F3 real: reflexo/empate não é considerado evidência suficiente.
    policy_module.DISPLAY_AUTO_MIN_CONFIDENCE = F3_REFERENCE_MIN_CONFIDENCE
    runtime_module.DISPLAY_AUTO_MIN_CONFIDENCE = F3_REFERENCE_MIN_CONFIDENCE

    # O texto operacional passa a refletir a sequência lógica do F3; o matcher
    # de imagem inteira não pode mais trocar visualmente H1 por USB ou vice-versa.
    operational_module._build_operational_state = (
        _sequence_authoritative_operational_state
    )

    _INSTALLED = True
