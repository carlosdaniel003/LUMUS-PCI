from __future__ import annotations

from collections import Counter
from dataclasses import replace

from src.core.operation_engine import OperationResult


CapturaOperacao = tuple[int, object, OperationResult]


def _ids_falhos(resultado: OperationResult) -> frozenset[str]:
    return frozenset(str(item) for item in resultado.failed_led_ids)


def dois_resultados_confirmam_ng(
    primeiro: OperationResult,
    segundo: OperationResult,
) -> bool:
    """Permite finalizar cedo quando dois frames concordam exatamente no NG."""
    falhos_primeiro = _ids_falhos(primeiro)
    falhos_segundo = _ids_falhos(segundo)
    return bool(falhos_primeiro) and falhos_primeiro == falhos_segundo


def consolidar_capturas_operacao(
    capturas: list[CapturaOperacao],
) -> tuple[int, object, OperationResult]:
    """Consolida até três frames por maioria de votos por LED.

    Cada LED é considerado NG quando aparece como falho na maioria das capturas.
    O frame retornado é o mais recente que melhor representa os LEDs finais.
    """
    if not capturas:
        raise ValueError("Nenhuma captura de operação foi fornecida.")

    if len(capturas) == 1:
        return capturas[0]

    votos: Counter[str] = Counter()
    ids_ordenados: list[str] = []
    vistos: set[str] = set()

    for _frame_id, _frame, resultado in capturas:
        for item in resultado.results:
            led_id = str(getattr(item, "id", ""))
            if led_id and led_id not in vistos:
                vistos.add(led_id)
                ids_ordenados.append(led_id)
        votos.update(_ids_falhos(resultado))

    maioria = (len(capturas) // 2) + 1
    falhos_finais = tuple(
        led_id
        for led_id in ids_ordenados
        if votos.get(led_id, 0) >= maioria
    )
    conjunto_falhos = frozenset(falhos_finais)

    def pontuar(captura: CapturaOperacao) -> tuple[int, int]:
        frame_id, _frame, resultado = captura
        falhos = _ids_falhos(resultado)
        concordantes = len(falhos & conjunto_falhos)
        divergentes = len(falhos ^ conjunto_falhos)
        return (concordantes * 10 - divergentes, int(frame_id))

    frame_id_representativo, frame_representativo, resultado_representativo = max(
        capturas,
        key=pontuar,
    )

    resultados_por_captura = [
        {
            str(getattr(item, "id", "")): item
            for item in resultado.results
        }
        for _frame_id, _frame, resultado in capturas
    ]

    resultados_consolidados = []
    for led_id in ids_ordenados:
        deve_falhar = led_id in conjunto_falhos
        candidato = None

        for mapa in reversed(resultados_por_captura):
            item = mapa.get(led_id)
            if item is None:
                continue
            item_falha = int(getattr(item, "valor_binario", 1)) == 0
            if item_falha == deve_falhar:
                candidato = item
                break
            if candidato is None:
                candidato = item

        if candidato is None:
            continue

        resultados_consolidados.append(
            replace(
                candidato,
                status="APAGADO" if deve_falhar else "ACESO",
                valor_binario=0 if deve_falhar else 1,
            )
        )

    tempo_total = sum(
        float(resultado.elapsed_seconds)
        for _frame_id, _frame, resultado in capturas
    )
    consolidado = OperationResult(
        ok=not falhos_finais,
        failed_led_ids=falhos_finais,
        results=tuple(resultados_consolidados),
        elapsed_seconds=tempo_total,
    )
    return frame_id_representativo, frame_representativo, consolidado
