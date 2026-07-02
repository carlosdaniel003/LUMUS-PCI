from __future__ import annotations

from datetime import datetime
from pathlib import Path

from config import DATA_DIR


class ProductionLogRepository:
    """Grava um histórico textual simples das inspeções de produção."""

    HEADER = (
        "ODIN - LOG DE PRODUÇÃO\n"
        "Arquivo atualizado automaticamente pelo modo PRODUÇÃO.\n"
        "Cada registro representa uma placa inspecionada.\n"
        "\n"
    )

    def __init__(self, log_file: Path | None = None) -> None:
        self.log_file = log_file or (
            DATA_DIR / "logs" / "log_producao.txt"
        )

    def registrar_inspecao(
        self,
        nome_configuracao_led: str,
        status: str,
        total: int,
        ok_count: int,
        ng_count: int,
        momento: datetime | None = None,
    ) -> Path:
        momento = momento or datetime.now()
        nome_configuracao = (
            str(nome_configuracao_led or "SEM PROJETO").strip()
            or "SEM PROJETO"
        )
        status_normalizado = str(status or "INDEFINIDO").strip().upper()

        alteracao = (
            f"Placa {int(total)} registrada como {status_normalizado}. "
            f"Contadores da sessão atualizados para: "
            f"TOTAL {int(total)} | OK {int(ok_count)} | NG {int(ng_count)}."
        )
        registro = (
            "=" * 72
            + "\n"
            + f"Configuração de LED: {nome_configuracao}\n"
            + f"Data: {momento.strftime('%d/%m/%Y')}\n"
            + f"Hora: {momento.strftime('%H:%M:%S')}\n"
            + f"Status: {status_normalizado}\n"
            + f"Alteração: {alteracao}\n"
            + "\n"
        )

        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        arquivo_novo = not self.log_file.exists()

        with open(
            self.log_file,
            "a",
            encoding="utf-8",
            newline="\n",
        ) as arquivo:
            if arquivo_novo:
                arquivo.write(self.HEADER)
            arquivo.write(registro)

        return self.log_file
