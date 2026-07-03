from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path

from config import DATA_DIR


class ProductionLogRepository:
    """Grava e rotaciona o histórico textual das inspeções de produção."""

    MAX_REGISTROS_POR_ARQUIVO = 1000
    MAX_ARQUIVOS_LOG = 10
    MAX_REGISTROS_RECENTES = 10

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
        self._registros_recentes: deque[dict] = deque(
            maxlen=self.MAX_REGISTROS_RECENTES
        )
        self._quantidade_registros_arquivo_atual = (
            self._contar_registros(self.log_file)
        )
        self._limpar_arquivos_antigos()
        self._carregar_registros_recentes()

    def _listar_arquivos_log(self) -> list[Path]:
        pasta = self.log_file.parent
        if not pasta.exists():
            return []

        padrao = f"{self.log_file.stem}*{self.log_file.suffix}"
        arquivos = [
            caminho
            for caminho in pasta.glob(padrao)
            if caminho.is_file()
        ]
        return sorted(
            arquivos,
            key=lambda caminho: (
                caminho.stat().st_mtime,
                caminho.name,
            ),
        )

    @staticmethod
    def _contar_registros(caminho: Path) -> int:
        if not caminho.exists():
            return 0

        quantidade = 0
        try:
            with open(caminho, "r", encoding="utf-8") as arquivo:
                for linha in arquivo:
                    if linha.startswith("Configuração de LED:"):
                        quantidade += 1
        except OSError:
            return 0
        return quantidade

    def _limpar_arquivos_antigos(self) -> None:
        arquivos = self._listar_arquivos_log()
        arquivos_arquivados = [
            caminho
            for caminho in arquivos
            if caminho.resolve() != self.log_file.resolve()
        ]

        maximo_arquivados = max(0, self.MAX_ARQUIVOS_LOG - 1)
        excedentes = len(arquivos_arquivados) - maximo_arquivados
        if excedentes <= 0:
            return

        for caminho in arquivos_arquivados[:excedentes]:
            try:
                caminho.unlink()
            except OSError:
                pass

    def _criar_caminho_arquivo_rotacionado(
        self,
        momento: datetime,
    ) -> Path:
        sufixo_data = momento.strftime("%Y%m%d_%H%M%S")
        base = self.log_file.with_name(
            f"{self.log_file.stem}_{sufixo_data}{self.log_file.suffix}"
        )
        if not base.exists():
            return base

        contador = 1
        while True:
            candidato = self.log_file.with_name(
                f"{self.log_file.stem}_{sufixo_data}_{contador:02d}"
                f"{self.log_file.suffix}"
            )
            if not candidato.exists():
                return candidato
            contador += 1

    def _rotacionar_se_necessario(self, momento: datetime) -> None:
        if (
            self._quantidade_registros_arquivo_atual
            < self.MAX_REGISTROS_POR_ARQUIVO
        ):
            return

        if self.log_file.exists():
            destino = self._criar_caminho_arquivo_rotacionado(momento)
            self.log_file.replace(destino)

        self._quantidade_registros_arquivo_atual = 0
        self._limpar_arquivos_antigos()

    @staticmethod
    def _normalizar_leds_apagados(
        leds_apagados,
    ) -> tuple[str, ...]:
        resultado: list[str] = []
        for led_id in leds_apagados or ():
            nome = str(led_id or "").strip()
            if nome and nome not in resultado:
                resultado.append(nome)
        return tuple(resultado)

    @staticmethod
    def _ler_registros_arquivo(caminho: Path) -> list[dict]:
        registros: list[dict] = []
        atual: dict | None = None

        try:
            with open(caminho, "r", encoding="utf-8") as arquivo:
                for linha_original in arquivo:
                    linha = linha_original.rstrip("\r\n")

                    if linha.startswith("Configuração de LED:"):
                        if atual is not None:
                            registros.append(atual)
                        atual = {
                            "configuracao": linha.split(":", 1)[1].strip(),
                            "data": "",
                            "hora": "",
                            "status": "INDEFINIDO",
                            "leds_apagados": (),
                            "alteracao": "",
                        }
                        continue

                    if atual is None:
                        continue

                    if linha.startswith("Data:"):
                        atual["data"] = linha.split(":", 1)[1].strip()
                    elif linha.startswith("Hora:"):
                        atual["hora"] = linha.split(":", 1)[1].strip()
                    elif linha.startswith("Status:"):
                        atual["status"] = linha.split(":", 1)[1].strip()
                    elif linha.startswith("LEDs apagados:"):
                        texto = linha.split(":", 1)[1].strip()
                        if texto and texto.upper() != "NENHUM":
                            atual["leds_apagados"] = tuple(
                                item.strip()
                                for item in texto.split(",")
                                if item.strip()
                            )
                    elif linha.startswith("Alteração:"):
                        atual["alteracao"] = linha.split(":", 1)[1].strip()
        except OSError:
            return []

        if atual is not None:
            registros.append(atual)
        return registros

    def _carregar_registros_recentes(self) -> None:
        self._registros_recentes.clear()
        for caminho in self._listar_arquivos_log():
            for registro in self._ler_registros_arquivo(caminho):
                self._registros_recentes.append(registro)

    def obter_ultimas_inspecoes(self, limite: int = 10) -> list[dict]:
        limite = max(0, int(limite))
        if limite == 0:
            return []
        registros = list(self._registros_recentes)
        return [dict(registro) for registro in registros[-limite:]]

    def registrar_inspecao(
        self,
        nome_configuracao_led: str,
        status: str,
        total: int,
        ok_count: int,
        ng_count: int,
        leds_apagados=(),
        momento: datetime | None = None,
    ) -> Path:
        momento = momento or datetime.now()
        nome_configuracao = (
            str(nome_configuracao_led or "SEM PROJETO").strip()
            or "SEM PROJETO"
        )
        status_normalizado = str(status or "INDEFINIDO").strip().upper()
        leds_apagados_normalizados = self._normalizar_leds_apagados(
            leds_apagados
        )
        texto_leds_apagados = (
            ", ".join(leds_apagados_normalizados)
            if leds_apagados_normalizados
            else "NENHUM"
        )

        alteracao = (
            f"Placa {int(total)} registrada como {status_normalizado}. "
            f"Contadores da sessão atualizados para: "
            f"TOTAL {int(total)} | OK {int(ok_count)} | NG {int(ng_count)}."
        )
        registro_texto = (
            "=" * 72
            + "\n"
            + f"Configuração de LED: {nome_configuracao}\n"
            + f"Data: {momento.strftime('%d/%m/%Y')}\n"
            + f"Hora: {momento.strftime('%H:%M:%S')}\n"
            + f"Status: {status_normalizado}\n"
            + f"LEDs apagados: {texto_leds_apagados}\n"
            + f"Alteração: {alteracao}\n"
            + "\n"
        )

        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._rotacionar_se_necessario(momento)
        arquivo_novo = (
            not self.log_file.exists()
            or self.log_file.stat().st_size == 0
        )

        with open(
            self.log_file,
            "a",
            encoding="utf-8",
            newline="\n",
        ) as arquivo:
            if arquivo_novo:
                arquivo.write(self.HEADER)
            arquivo.write(registro_texto)

        self._quantidade_registros_arquivo_atual += 1
        self._registros_recentes.append(
            {
                "configuracao": nome_configuracao,
                "data": momento.strftime("%d/%m/%Y"),
                "hora": momento.strftime("%H:%M:%S"),
                "status": status_normalizado,
                "leds_apagados": leds_apagados_normalizados,
                "alteracao": alteracao,
            }
        )
        self._limpar_arquivos_antigos()
        return self.log_file
