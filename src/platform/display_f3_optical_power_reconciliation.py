from __future__ import annotations

import src.platform.display_f3_operational_status as operational_module
from src.platform.display_auto_check_policy import DISPLAY_AUTO_MIN_CONFIDENCE
from src.platform.display_project_repository import (
    DISPLAY_CHECK_STATE_OFF,
    DISPLAY_CHECK_STATE_ON,
)


def _analise_optica_corresponde_ao_contexto_f3(
    analysis: dict | None,
    context: dict | None,
) -> bool:
    if not isinstance(analysis, dict) or not isinstance(context, dict):
        return False

    return (
        str(analysis.get("project_name") or "")
        == str(context.get("project_name") or "")
        and str(analysis.get("check_id") or "")
        == str(context.get("check_id") or "")
    )


def _confidence(item: dict) -> float:
    try:
        return float(item.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _analise_tem_evidencia_optica_de_display_ligado_f3(
    analysis: dict | None,
) -> bool:
    """Detecta energia pelas máscaras sem reutilizar o gate manual estrito.

    O gate de transição manual do F3 foi endurecido para aceitar somente um CHECK
    integralmente conforme. Isso é correto para BLUE/USB/AUX, mas é rígido demais
    para responder à pergunta física mais simples: "o display está ligado?".

    Para essa pergunta usamos somente a classificação óptica das máscaras:
    - precisa existir ao menos uma máscara esperada ON reconhecida como ON;
    - a leitura precisa ter a confiança mínima já aceita pelo classificador F3;
    - se o CHECK possuir máscaras esperadas OFF, ao menos uma delas também deve
      parecer OFF, reduzindo a chance de brilho global/reflexo ser tomado por energia.
    """
    if not isinstance(analysis, dict) or not bool(analysis.get("ready")):
        return False

    results = [
        item
        for item in (analysis.get("mask_results") or [])
        if isinstance(item, dict)
        and _confidence(item) >= DISPLAY_AUTO_MIN_CONFIDENCE
    ]
    if not results:
        return False

    expected_on = [
        item for item in results if str(item.get("expected") or "") == DISPLAY_CHECK_STATE_ON
    ]
    if not expected_on:
        return False

    on_evidence = any(
        str(item.get("classified") or "") == DISPLAY_CHECK_STATE_ON
        for item in expected_on
    )
    if not on_evidence:
        return False

    expected_off = [
        item for item in results if str(item.get("expected") or "") == DISPLAY_CHECK_STATE_OFF
    ]
    if expected_off and not any(
        str(item.get("classified") or "") == DISPLAY_CHECK_STATE_OFF
        for item in expected_off
    ):
        return False

    return True


def _tem_evidencia_optica_de_display_ligado_f3(
    app,
    context: dict | None,
) -> bool:
    analysis = getattr(app, "_display_auto_last_analysis", None)
    if not _analise_optica_corresponde_ao_contexto_f3(analysis, context):
        return False
    return _analise_tem_evidencia_optica_de_display_ligado_f3(analysis)


def reconciliar_estado_operacional_com_evidencia_optica_f3(
    app,
    state: dict | None,
    context: dict | None,
) -> dict:
    """Impede a referência de placa OFF de esconder evidência óptica de CHECK ligado.

    A referência de quadro inteiro continua responsável por EMPTY/OFF. Porém, quando
    ela chama a placa de desligada e as próprias máscaras do CHECK atual já mostram
    evidência confiável de segmentos ACESOS, o estado OFF deixa de bloquear o motor.

    Isto não aprova o CHECK: apenas libera o analisador oficial do F3. Presença por
    imagem do CHECK, máscaras, estabilidade e política de OK/NG continuam sendo
    aplicadas normalmente depois deste gate.
    """
    result = dict(state or {})
    if str(result.get("kind") or "") != "off":
        return result

    # Depois de um resultado terminal, a retirada física continua obrigatória.
    # Evidência de LED nunca pode furar o latch EMPTY -> nova placa.
    if bool(getattr(app, "_display_f3_waiting_empty_rearm", False)) or bool(
        getattr(app, "_display_f3_waiting_new_board_after_empty", False)
    ):
        return result

    if not _tem_evidencia_optica_de_display_ligado_f3(app, context):
        return result

    check_id = str((context or {}).get("check_id") or "")
    check_name = str((context or {}).get("check_name") or check_id or "CHECK")
    normalized_name = check_name.strip().upper() or "CHECK"

    result.update(
        {
            "kind": "check",
            "text": f"DISPLAY LIGADO • ANALISANDO {normalized_name}",
            "color": operational_module.F3_OPERATIONAL_STATUS_COLORS["check"],
            "allow_auto": True,
            "check_id": check_id,
            "check_name": normalized_name,
            "optical_power_evidence": True,
            "physical_reference_kind": "off",
        }
    )
    return result


def instalar_reconciliacao_optica_estado_fisico_display_f3() -> None:
    """Instala a reconciliação somente no estado operacional do Display F3."""
    if bool(
        getattr(
            operational_module,
            "_display_f3_optical_power_reconciliation_installed",
            False,
        )
    ):
        return

    base_build = operational_module._build_operational_state

    def build(self, frame, project_name: str, context: dict | None):
        state = base_build(self, frame, project_name, context)
        return reconciliar_estado_operacional_com_evidencia_optica_f3(
            self,
            state,
            context,
        )

    operational_module._build_operational_state = build
    operational_module._display_f3_optical_power_reconciliation_installed = True
