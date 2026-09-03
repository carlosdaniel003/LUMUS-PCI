from __future__ import annotations

import src.platform.display_auto_check_runtime as auto_runtime_module
import src.platform.display_f3_live_runtime_fix as live_runtime_module
import src.platform.display_f3_optical_power_reconciliation as optical_power_module
from src.platform.display_f3_reference_authority_fix import (
    F3_REFERENCE_MIN_CONFIDENCE,
    F3ReferenceAuthorityAnalyzer,
)


_INSTALLED = False


def instalar_ponte_autoridade_referencias_display_f3() -> None:
    """Mantém preview/overlay e reconciliação óptica na mesma autoridade F3."""
    global _INSTALLED
    if _INSTALLED:
        return

    # O overlay ao vivo possui um fallback que instancia o analisador por um
    # símbolo importado diretamente. Substituímos somente esse símbolo do F3
    # para impedir retorno acidental ao classificador anterior após limpar cache.
    live_runtime_module.DisplayAutomaticCheckAnalyzer = F3ReferenceAuthorityAnalyzer

    # Este módulo também importou o limiar por valor. Mantemos o mesmo 0.58 da
    # política F3 para que uma leitura ambígua não seja usada como evidência de
    # display ligado por um caminho secundário.
    optical_power_module.DISPLAY_AUTO_MIN_CONFIDENCE = F3_REFERENCE_MIN_CONFIDENCE

    # H1, USB, AUX e demais estados estáveis precisam aparecer corretamente em
    # dois frames novos antes de avançar. Bluetooth/BLUE continua com a exceção
    # transitória já existente no runtime e pode confirmar com um único frame OK.
    auto_runtime_module.DisplayAutomaticCheckF3Mixin.DISPLAY_AUTO_OK_STABLE_FRAMES = 2

    _INSTALLED = True
