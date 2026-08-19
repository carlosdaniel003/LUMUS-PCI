from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
import threading


_TRUE_VALUES = {"1", "true", "yes", "on", "sim"}
_LOG_LOCK = threading.RLock()


def camera_debug_enabled() -> bool:
    """Ativa diagnóstico somente no Windows e mediante variável de ambiente."""
    if not sys.platform.startswith("win"):
        return False
    valor = str(os.environ.get("ODIN_CAMERA_DEBUG", "")).strip().lower()
    return valor in _TRUE_VALUES


def _normalizar_valor(valor):
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    if isinstance(valor, (tuple, list)):
        return [_normalizar_valor(item) for item in valor]
    if isinstance(valor, dict):
        return {str(chave): _normalizar_valor(item) for chave, item in valor.items()}
    return repr(valor)


def camera_debug(evento: str, **dados) -> None:
    """Imprime uma linha curta no PowerShell e mantém cópia em arquivo.

    Não altera nenhum estado da câmera. Fora do Windows ou sem
    ``ODIN_CAMERA_DEBUG=1`` retorna imediatamente.
    """
    if not camera_debug_enabled():
        return

    agora = datetime.now().astimezone()
    payload = {
        "ts": agora.isoformat(timespec="milliseconds"),
        "thread": threading.current_thread().name,
        "event": str(evento),
    }
    for chave, valor in dados.items():
        payload[str(chave)] = _normalizar_valor(valor)

    linha = "[ODIN-CAMERA] " + json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
    )

    with _LOG_LOCK:
        print(linha, flush=True)
        try:
            pasta = Path("data") / "logs"
            pasta.mkdir(parents=True, exist_ok=True)
            with (pasta / "windows_camera_debug.log").open(
                "a",
                encoding="utf-8",
            ) as arquivo:
                arquivo.write(linha + "\n")
        except Exception:
            # Debug nunca pode interferir no funcionamento da câmera.
            pass


def camera_debug_snapshot(service, evento: str = "snapshot") -> None:
    if not camera_debug_enabled() or service is None:
        return
    try:
        snapshot = service.obter_snapshot()
    except Exception as erro:
        camera_debug(
            evento + "_erro",
            erro=type(erro).__name__,
            detalhe=str(erro),
        )
        return

    try:
        diagnostico = service.obter_diagnostico_fluxo()
    except Exception:
        diagnostico = {}

    camera_debug(
        evento,
        estado=getattr(snapshot, "estado", None),
        mensagem=getattr(snapshot, "mensagem", None),
        frame_id=getattr(snapshot, "frame_id", None),
        resolucao=getattr(snapshot, "resolucao", None),
        resolucao_solicitada=getattr(snapshot, "resolucao_solicitada", None),
        fps_real=getattr(snapshot, "fps_real", None),
        backend=diagnostico.get("backend_ativo"),
        thread_ativa=diagnostico.get("thread_ativa"),
        frames_lidos=diagnostico.get("frames_lidos_total"),
        falhas_leitura=diagnostico.get("leituras_falhas_total"),
        probe_timeouts=diagnostico.get("windows_probe_timeout_total"),
        ultimo_probe_timeout=diagnostico.get("windows_ultimo_probe_timeout"),
    )
