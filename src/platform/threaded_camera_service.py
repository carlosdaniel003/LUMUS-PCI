from __future__ import annotations

import math
import threading
import time

import cv2

from src.infra.camera_service import CameraService, CameraSnapshot
from src.platform.frame_integrity import FrameIntegrityValidator
from src.platform.raspberry_camera_service import RaspberryPi3CameraService


class ThreadedRaspberryPi3CameraService(RaspberryPi3CameraService):
    """Câmera contínua com último frame íntegro, sem bloquear o Tkinter."""

    FRAMES_CORROMPIDOS_ANTES_RECONEXAO = 3
    FRAMES_ESTAVEIS_MINIMOS = 2
    MOVIMENTO_ESTAVEL_MAXIMO = 10.0
    VARIACAO_BRILHO_ESTAVEL_MAXIMA = 8.0
    ESPERA_THREAD_PARAR_S = 1.2

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()
        self._capture_thread: threading.Thread | None = None
        self._frame_condition = threading.Condition(self._lock)
        self._validador_integridade = FrameIntegrityValidator()

        self._frames_validos_sessao = 0
        self._frames_corrompidos_consecutivos = 0
        self._frames_corrompidos_total = 0
        self._ultimo_motivo_descarte = ""
        self._miniatura_estabilidade = None
        self._brilho_estabilidade: float | None = None
        self._frames_estaveis_consecutivos = 0
        self._ultimo_frame_estavel = None
        self._ultimo_frame_estavel_id = -1
        self._controles_automaticos_travados = False

    def iniciar(self) -> None:
        if self._ativo:
            return

        self._ativo = True
        self._falhas_consecutivas = 0
        self._proxima_reconexao_em = 0.0
        self._stop_event.clear()
        self._definir_estado(
            self.ESTADO_CONECTANDO,
            "Procurando câmera disponível...",
        )
        self._capture_thread = threading.Thread(
            target=self._loop_captura,
            name="odin-camera-capture",
            daemon=True,
        )
        self._capture_thread.start()

    def parar(self) -> None:
        self._ativo = False
        self._stop_event.set()
        with self._frame_condition:
            self._frame_condition.notify_all()

        thread = self._capture_thread
        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=self.ESPERA_THREAD_PARAR_S)

        if thread is not None and thread.is_alive():
            # Fallback para backends presos em read().
            self._liberar_camera()
            thread.join(timeout=0.35)

        self._capture_thread = None
        self._liberar_camera()
        self._reiniciar_estado_fluxo()
        self._definir_estado(self.ESTADO_PARADA, "Câmera parada.")

    def atualizar_configuracoes_camera(
        self,
        configuracoes_camera: dict | None,
    ) -> None:
        # Não chama a implementação Raspberry original, pois ela acessa o driver
        # pela thread da interface. A thread de captura aplicará a configuração.
        CameraService.atualizar_configuracoes_camera(
            self,
            configuracoes_camera,
        )
        self._controles_automaticos_travados = False

    def obter_snapshot(
        self,
        ultimo_frame_id: int = -1,
    ) -> CameraSnapshot:
        with self._lock:
            frame = None
            if (
                self._ultimo_frame is not None
                and self._frame_id != ultimo_frame_id
            ):
                # O array publicado não volta a ser modificado; somente a
                # referência é substituída no próximo frame.
                frame = self._ultimo_frame

            return CameraSnapshot(
                estado=self._estado,
                mensagem=self._mensagem,
                frame_id=self._frame_id,
                frame=frame,
                resolucao=self._resolucao,
                resolucao_solicitada=self._resolucao_solicitada,
                fps_solicitado=self._fps_solicitado,
                fps_real=self._fps_real,
                formato_solicitado=self._formato_solicitado,
                formato_real=self._formato_real,
            )

    def obter_ultimo_frame_estavel(self):
        with self._lock:
            if self._ultimo_frame_estavel is None:
                return None
            return (
                int(self._ultimo_frame_estavel_id),
                self._ultimo_frame_estavel.copy(),
            )

    def aguardar_proximo_frame_estavel(
        self,
        depois_frame_id: int = -1,
        timeout_s: float = 0.30,
    ):
        limite = time.monotonic() + max(0.0, float(timeout_s))
        with self._frame_condition:
            while self._ativo and not self._stop_event.is_set():
                if (
                    self._ultimo_frame_estavel is not None
                    and self._ultimo_frame_estavel_id > int(depois_frame_id)
                ):
                    return (
                        int(self._ultimo_frame_estavel_id),
                        self._ultimo_frame_estavel.copy(),
                    )

                restante = limite - time.monotonic()
                if restante <= 0:
                    return None
                self._frame_condition.wait(timeout=restante)
        return None

    def obter_diagnostico_fluxo(self) -> dict:
        with self._lock:
            return {
                "frames_corrompidos_total": int(
                    self._frames_corrompidos_total
                ),
                "frames_corrompidos_consecutivos": int(
                    self._frames_corrompidos_consecutivos
                ),
                "ultimo_motivo_descarte": self._ultimo_motivo_descarte,
                "frames_estaveis_consecutivos": int(
                    self._frames_estaveis_consecutivos
                ),
                "ultimo_frame_estavel_id": int(
                    self._ultimo_frame_estavel_id
                ),
                "thread_ativa": bool(
                    self._capture_thread is not None
                    and self._capture_thread.is_alive()
                ),
            }

    def _reiniciar_estado_fluxo(self) -> None:
        self._validador_integridade.reset()
        self._frames_validos_sessao = 0
        self._frames_corrompidos_consecutivos = 0
        self._miniatura_estabilidade = None
        self._brilho_estabilidade = None
        self._frames_estaveis_consecutivos = 0
        with self._lock:
            self._ultimo_frame_estavel = None
            self._ultimo_frame_estavel_id = -1
        self._controles_automaticos_travados = False

    def _loop_captura(self) -> None:
        try:
            while self._ativo and not self._stop_event.is_set():
                if self._capture is None:
                    espera = self._proxima_reconexao_em - time.monotonic()
                    if espera > 0:
                        self._stop_event.wait(min(espera, 0.10))
                        continue
                    if not self._abrir_camera():
                        self._stop_event.wait(0.05)
                        continue
                    self._reiniciar_estado_fluxo()

                capture = self._capture
                if capture is None:
                    continue

                try:
                    sucesso, frame = capture.read()
                except Exception:
                    sucesso, frame = False, None

                frame = (
                    self._normalizar_frame(frame)
                    if sucesso
                    else None
                )
                if not self._frame_basico_valido(frame):
                    self._falhas_consecutivas += 1
                    if (
                        self._falhas_consecutivas
                        >= self.falhas_antes_reconexao
                    ):
                        self._agendar_reconexao(
                            "A câmera parou de entregar frames válidos."
                        )
                        self._reiniciar_estado_fluxo()
                    else:
                        self._stop_event.wait(0.005)
                    continue

                self._falhas_consecutivas = 0
                primeiro_frame = self._frames_validos_sessao == 0
                if primeiro_frame:
                    self._registrar_parametros_reais(capture, frame)
                    self._aplicar_configuracoes_hardware()
                elif self._controles_pendentes:
                    self._aplicar_configuracoes_hardware()
                    self._controles_automaticos_travados = False

                frame_processado = self._aplicar_rotacao(frame)
                integridade = self._validador_integridade.avaliar(
                    frame_processado
                )
                if not integridade.valido:
                    self._frames_corrompidos_total += 1
                    self._frames_corrompidos_consecutivos += 1
                    self._ultimo_motivo_descarte = integridade.motivo
                    if (
                        self._frames_corrompidos_consecutivos
                        >= self.FRAMES_CORROMPIDOS_ANTES_RECONEXAO
                    ):
                        self._agendar_reconexao(
                            "Frames com bandas horizontais foram descartados."
                        )
                        self._reiniciar_estado_fluxo()
                    continue

                self._frames_corrompidos_consecutivos = 0
                self._frames_validos_sessao += 1
                estavel = self._avaliar_estabilidade(frame_processado)
                self._publicar_frame_otimizado(
                    frame_processado,
                    estavel=estavel,
                )

                if (
                    not self._controles_automaticos_travados
                    and self._frames_validos_sessao
                    >= max(8, int(self.frames_aquecimento))
                    and self._frames_estaveis_consecutivos
                    >= self.FRAMES_ESTAVEIS_MINIMOS
                ):
                    self._travar_controles_automaticos_atuais()
        finally:
            self._liberar_camera()
            with self._frame_condition:
                self._frame_condition.notify_all()

    @staticmethod
    def _miniatura_cinza(frame):
        cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.resize(
            cinza,
            (160, 120),
            interpolation=cv2.INTER_AREA,
        )

    def _avaliar_estabilidade(self, frame) -> bool:
        miniatura = self._miniatura_cinza(frame)
        brilho = float(miniatura.mean())
        anterior = self._miniatura_estabilidade
        brilho_anterior = self._brilho_estabilidade
        self._miniatura_estabilidade = miniatura
        self._brilho_estabilidade = brilho

        if anterior is None or brilho_anterior is None:
            self._frames_estaveis_consecutivos = 1
            return False

        movimento = float(cv2.absdiff(miniatura, anterior).mean())
        variacao_brilho = abs(brilho - brilho_anterior)
        estavel = (
            movimento <= self.MOVIMENTO_ESTAVEL_MAXIMO
            and variacao_brilho
            <= self.VARIACAO_BRILHO_ESTAVEL_MAXIMA
        )
        if estavel:
            self._frames_estaveis_consecutivos += 1
        else:
            self._frames_estaveis_consecutivos = 0

        return (
            self._frames_estaveis_consecutivos
            >= self.FRAMES_ESTAVEIS_MINIMOS
        )

    def _publicar_frame_otimizado(self, frame, estavel: bool) -> None:
        altura, largura = frame.shape[:2]
        backend_name = getattr(self, "_backend_name", "automático")
        with self._frame_condition:
            self._ultimo_frame = frame
            self._frame_id += 1
            frame_id = int(self._frame_id)
            self._resolucao = (largura, altura)
            self._estado = self.ESTADO_CONECTADA
            self._mensagem = (
                f"Câmera {self.indice_camera} conectada via {backend_name}. "
                f"Resolução real: {largura}x{altura}."
            )
            if estavel:
                self._ultimo_frame_estavel = frame
                self._ultimo_frame_estavel_id = frame_id
            self._frame_condition.notify_all()

    @staticmethod
    def _ler_propriedade_finita(capture, propriedade: int | None):
        if propriedade is None:
            return None
        try:
            valor = float(capture.get(propriedade))
        except Exception:
            return None
        return valor if math.isfinite(valor) else None

    @staticmethod
    def _definir_propriedade(capture, propriedade: int | None, valor) -> bool:
        if propriedade is None or valor is None:
            return False
        try:
            return bool(capture.set(propriedade, float(valor)))
        except Exception:
            return False

    def _travar_controles_automaticos_atuais(self) -> None:
        """Congela valores estabilizados somente quando o driver permite."""
        capture = self._capture
        if capture is None:
            return
        configuracoes = self.obter_configuracoes_camera()

        controles = (
            (
                "exposure_auto",
                "auto_exposure",
                getattr(cv2, "CAP_PROP_AUTO_EXPOSURE", None),
                self._valor_auto_exposure(False),
                "exposure",
                getattr(cv2, "CAP_PROP_EXPOSURE", None),
            ),
            (
                "focus_auto",
                "autofocus",
                getattr(cv2, "CAP_PROP_AUTOFOCUS", None),
                0.0,
                "focus",
                getattr(cv2, "CAP_PROP_FOCUS", None),
            ),
            (
                "white_balance_auto",
                "auto_white_balance",
                getattr(cv2, "CAP_PROP_AUTO_WB", None),
                0.0,
                "white_balance",
                getattr(cv2, "CAP_PROP_WB_TEMPERATURE", None),
            ),
        )

        for (
            chave_auto,
            nome_auto,
            propriedade_auto,
            valor_auto_desligado,
            nome_manual,
            propriedade_manual,
        ) in controles:
            if not bool(configuracoes.get(chave_auto, True)):
                continue

            valor_atual = self._ler_propriedade_finita(
                capture,
                propriedade_manual,
            )
            auto_desligado = self._definir_propriedade(
                capture,
                propriedade_auto,
                valor_auto_desligado,
            )
            valor_fixado = self._definir_propriedade(
                capture,
                propriedade_manual,
                valor_atual,
            )
            self._registrar_status_controle(
                nome_auto,
                (
                    "travado_producao"
                    if auto_desligado
                    else "nao_suportado"
                ),
                valor_solicitado=valor_auto_desligado,
                valor_lido=valor_atual,
            )
            if valor_fixado:
                self._registrar_status_controle(
                    nome_manual,
                    "travado_producao",
                    valor_solicitado=valor_atual,
                    valor_lido=valor_atual,
                )

        self._controles_automaticos_travados = True
