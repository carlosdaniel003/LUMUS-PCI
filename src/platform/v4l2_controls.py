from __future__ import annotations

from dataclasses import dataclass
import re
import shutil
import subprocess
from typing import Callable


@dataclass(frozen=True)
class V4L2ControlResult:
    aplicado: bool
    valor: int | None = None
    mensagem: str = ""


class V4L2ControlManager:
    """Acesso pontual aos controles UVC sem custo no loop de captura."""

    def __init__(
        self,
        dispositivo: str,
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ) -> None:
        self.dispositivo = str(dispositivo)
        self._runner = runner
        self.disponivel = bool(shutil.which("v4l2-ctl"))

    def _executar(self, *argumentos: str) -> V4L2ControlResult:
        if not self.disponivel:
            return V4L2ControlResult(
                False,
                mensagem="v4l2-ctl indisponível",
            )
        try:
            processo = self._runner(
                ["v4l2-ctl", "-d", self.dispositivo, *argumentos],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False,
            )
        except Exception as erro:
            return V4L2ControlResult(
                False,
                mensagem=type(erro).__name__,
            )

        texto = f"{processo.stdout}\n{processo.stderr}".strip()
        if int(processo.returncode) != 0:
            return V4L2ControlResult(False, mensagem=texto)

        correspondencia = re.search(r":\s*(-?\d+)\b", texto)
        valor = (
            int(correspondencia.group(1))
            if correspondencia
            else None
        )
        return V4L2ControlResult(
            True,
            valor=valor,
            mensagem=texto,
        )

    def obter(self, nome: str) -> V4L2ControlResult:
        return self._executar(f"--get-ctrl={nome}")

    def definir(
        self,
        nome: str,
        valor: int | float,
    ) -> V4L2ControlResult:
        valor_inteiro = int(round(float(valor)))
        resultado = self._executar(
            f"--set-ctrl={nome}={valor_inteiro}"
        )
        if resultado.aplicado and resultado.valor is None:
            return V4L2ControlResult(
                True,
                valor=valor_inteiro,
                mensagem=resultado.mensagem,
            )
        return resultado

    def congelar_automaticos(
        self,
        configuracoes: dict,
    ) -> dict[str, V4L2ControlResult]:
        resultados: dict[str, V4L2ControlResult] = {}
        pares = (
            (
                "exposure_auto",
                "exposure_absolute",
                "exposure_auto",
                1,
            ),
            (
                "focus_auto",
                "focus_absolute",
                "focus_auto",
                0,
            ),
            (
                "white_balance_auto",
                "white_balance_temperature",
                "white_balance_temperature_auto",
                0,
            ),
        )

        for (
            chave_config,
            controle_manual,
            controle_auto,
            valor_manual,
        ) in pares:
            if not bool(configuracoes.get(chave_config, True)):
                continue

            leitura = self.obter(controle_manual)
            desligamento = self.definir(
                controle_auto,
                valor_manual,
            )
            resultados[controle_auto] = desligamento

            if leitura.aplicado and leitura.valor is not None:
                resultados[controle_manual] = self.definir(
                    controle_manual,
                    leitura.valor,
                )

        return resultados
