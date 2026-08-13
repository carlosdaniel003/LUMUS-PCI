from __future__ import annotations

from src.platform.live_fixed_full_hd_camera_service import LiveFixedFullHdCameraService


class VerifiedLiveCameraService(LiveFixedFullHdCameraService):
    """Confirma se o driver aceita o controle antes de liberar o ajuste."""

    def _status_verificado(self, nome, status, solicitado=None, lido=None, bloqueado=False, motivo=None):
        self._registrar_status_controle(
            nome,
            status,
            valor_solicitado=solicitado,
            valor_lido=lido,
        )
        with self._lock:
            dados = self._status_controles_camera.setdefault(nome, {})
            dados["bloqueado"] = bool(bloqueado)
            dados["motivo"] = motivo

    def _aplicar_habilitacao_manual(self, capture, nome: str, habilitado: bool) -> None:
        if not habilitado:
            return super()._aplicar_habilitacao_manual(capture, nome, False)

        propriedade = self._propriedade_manual(nome)
        baseline = self._garantir_baseline(capture, nome)
        if propriedade is None or baseline is None:
            self._status_verificado(
                nome,
                "nao_suportado",
                bloqueado=True,
                motivo="O driver não oferece leitura segura para este controle.",
            )
            return

        aceito, lido = self._definir_propriedade_capture(capture, propriedade, baseline)
        if not aceito:
            self._status_verificado(
                nome,
                "nao_suportado",
                baseline,
                lido,
                True,
                "O driver recusou este controle; o ajuste foi bloqueado.",
            )
            return

        self._status_verificado(
            nome,
            "manual_pronto",
            baseline,
            baseline if lido is None else lido,
            False,
            "Controle aceito pelo driver.",
        )

    def _aplicar_valor_manual(self, capture, nome: str, configuracoes: dict) -> None:
        if not bool(configuracoes.get(f"{nome}_enabled", False)):
            return
        propriedade = self._propriedade_manual(nome)
        if propriedade is None:
            self._status_verificado(nome, "nao_suportado", bloqueado=True)
            return
        solicitado = float(configuracoes.get(nome, 0.0))
        baseline = self._garantir_baseline(capture, nome)
        aceito, lido = self._definir_propriedade_capture(capture, propriedade, solicitado)
        if not aceito:
            self._status_verificado(
                nome,
                "nao_suportado",
                solicitado,
                lido,
                True,
                "O driver recusou o novo valor.",
            )
            return
        if lido is not None:
            with self._lock:
                self._camera_live_valores_hardware[nome] = float(lido)
        ignorado = (
            lido is not None
            and baseline is not None
            and abs(float(lido) - float(baseline)) <= 1.0
            and abs(solicitado - float(baseline)) > 1.0
        )
        self._status_verificado(
            nome,
            "ignorado_driver" if ignorado else "aplicado",
            solicitado,
            lido,
            False,
            "O driver não confirmou mudança do valor." if ignorado else None,
        )
