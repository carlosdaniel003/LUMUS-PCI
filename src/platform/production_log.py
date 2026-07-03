from __future__ import annotations

from datetime import datetime
import tkinter as tk

from src.infra.production_log_repository import (
    ProductionLogRepository,
)


class ProductionLogMixin:
    """Registra cada resultado sem atrasar a renderização da produção."""

    def __init__(self, *args, **kwargs) -> None:
        self.production_log_repository = ProductionLogRepository()
        self.ultimo_erro_log_producao: str | None = None
        super().__init__(*args, **kwargs)
        self._atualizar_painel_log_producao()

    def _obter_nome_configuracao_log(self) -> str:
        nome = str(
            getattr(self, "projeto_led_ativo", "") or ""
        ).strip()
        if nome:
            return nome

        try:
            nome = str(
                self.config_repository.obter_projeto_led_ativo()
                or ""
            ).strip()
        except Exception:
            nome = ""

        return nome or "SEM PROJETO"

    def _atualizar_painel_log_producao(self) -> None:
        try:
            registros = (
                self.production_log_repository.obter_ultimas_inspecoes(10)
            )
            self.view.atualizar_log_producao(registros)
        except Exception:
            pass

    def _gravar_registro_producao(
        self,
        nome_configuracao: str,
        status: str,
        total: int,
        ok_count: int,
        ng_count: int,
        leds_apagados: tuple[str, ...],
        momento: datetime,
    ) -> None:
        try:
            self.production_log_repository.registrar_inspecao(
                nome_configuracao_led=nome_configuracao,
                status=status,
                total=total,
                ok_count=ok_count,
                ng_count=ng_count,
                leds_apagados=leds_apagados,
                momento=momento,
            )
            self.ultimo_erro_log_producao = None
            self._atualizar_painel_log_producao()
        except Exception as erro:
            # Uma falha de escrita nunca pode interromper a inspeção.
            self.ultimo_erro_log_producao = (
                f"{type(erro).__name__}: {erro}"
            )

    def disparar_inspecao_operacao(self) -> None:
        total_anterior = int(self.operacao_total)
        ok_anterior = int(self.operacao_ok)
        ng_anterior = int(self.operacao_ng)

        super().disparar_inspecao_operacao()

        if int(self.operacao_total) <= total_anterior:
            return

        status = (
            "OK"
            if int(self.operacao_ok) > ok_anterior
            else "NG"
        )
        resultado = getattr(
            self,
            "ultimo_resultado_operacao",
            None,
        )
        leds_apagados = tuple(
            getattr(resultado, "failed_led_ids", ()) or ()
        )
        nome_configuracao = self._obter_nome_configuracao_log()
        total = int(self.operacao_total)
        ok_count = int(self.operacao_ok)
        ng_count = int(self.operacao_ng)
        momento = datetime.now()

        try:
            # Timer curto: a interface termina de renderizar antes da escrita.
            # Diferente de after_idle, não é executado por update_idletasks().
            self.root.after(
                1,
                lambda: self._gravar_registro_producao(
                    nome_configuracao=nome_configuracao,
                    status=status,
                    total=total,
                    ok_count=ok_count,
                    ng_count=ng_count,
                    leds_apagados=leds_apagados,
                    momento=momento,
                ),
            )
        except tk.TclError:
            self._gravar_registro_producao(
                nome_configuracao=nome_configuracao,
                status=status,
                total=total,
                ok_count=ok_count,
                ng_count=ng_count,
                leds_apagados=leds_apagados,
                momento=momento,
            )
