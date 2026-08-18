from __future__ import annotations

import tkinter as tk

from src.ui.main_window_parts.settings.camera_live_ui_behavior import (
    abrir_janela_configuracoes_sem_saltos,
)


_CONTROLES = {
    "Panorâmica manual": "pan",
    "Inclinação manual": "tilt",
    "Contraste manual": "contrast",
    "Nitidez manual": "sharpness",
    "Saturação manual": "saturation",
    "Exposição manual": "exposure",
    "Ganho manual": "gain",
    "Foco manual": "focus",
    "Balanço de branco manual": "white_balance",
    "Brilho manual": "brightness",
    "Gamma manual": "gamma",
}

_AUTOMATICOS = {
    "Exposição automática": "auto_exposure",
    "Foco automático": "autofocus",
    "Balanço de branco automático": "auto_white_balance",
}

_STATUS = {
    "manual_pronto": "Pronto para ajuste",
    "aplicado": "Aplicado ao vivo",
    "aplicado_sem_leitura": "Aplicado; leitura indisponível",
    "ignorado_driver": "Driver não confirmou alteração",
    "ajustado_driver": "Limitado pelo driver",
    "nao_suportado": "Não suportado pelo driver/backend",
    "restaurado": "Restaurado",
    "automatico": "Automático",
    "manual_disponivel": "Manual disponível",
    "padrao_driver": "Padrão do driver",
    "padrao_driver_windows": "Padrão do Windows",
    "aguardando_camera": "Aguardando câmera",
}


def _widgets(widget):
    for filho in widget.winfo_children():
        yield filho
        yield from _widgets(filho)


def _nova_janela(root, anteriores):
    novas = [
        item for item in root.winfo_children()
        if isinstance(item, tk.Toplevel)
        and item not in anteriores
        and item.winfo_exists()
    ]
    return novas[-1] if novas else None


def _label_texto(root, texto):
    for item in _widgets(root):
        if not isinstance(item, tk.Label):
            continue
        try:
            if str(item.cget("text")) == texto:
                return item
        except tk.TclError:
            pass
    return None


def _primeiro(root, classe):
    for item in _widgets(root):
        if isinstance(item, classe):
            return item
    return None


def _aplicar_perfil_real(janela, perfil: dict | None) -> None:
    """Mostra o stream real sem sobrescrever o perfil solicitado pelo usuário."""
    perfil = perfil if isinstance(perfil, dict) else {}
    resolucao = perfil.get("resolucao")
    if not resolucao or len(resolucao) != 2:
        return

    largura, altura = int(resolucao[0]), int(resolucao[1])
    fps = perfil.get("fps")
    formato = str(perfil.get("formato") or "").strip()
    backend = str(perfil.get("backend") or "").strip()

    label_titulo = _label_texto(janela, "Perfil de captura")
    if label_titulo is None:
        return
    card = label_titulo.master
    corpo = None
    for item in card.winfo_children():
        if isinstance(item, tk.Frame):
            corpo = item
    if corpo is None:
        return

    partes = [f"{largura}x{altura}"]
    if fps is not None:
        try:
            partes.append(f"{float(fps):.1f} FPS")
        except (TypeError, ValueError):
            pass
    if formato:
        partes.append(formato)
    if backend:
        partes.append(backend)

    resumo = tk.Label(
        corpo,
        text="ATUAL  •  " + "  •  ".join(partes),
        font=("Segoe UI", 9, "bold"),
        fg="#BBF7D0",
        bg="#0F3D24",
        anchor="w",
        padx=9,
        pady=6,
    )
    resumo.pack(
        fill=tk.X,
        padx=12,
        pady=(0, 8),
        before=corpo.winfo_children()[0],
    )

    # A faixa acima informa o que o hardware está entregando agora. O seletor
    # "Resolução" abaixo continua mostrando o perfil configurado (por exemplo,
    # 1920x1080). Antes ele era sobrescrito com "640x480 (atual)" e, ao salvar,
    # esse texto não correspondia a nenhum preset, fazendo a UI cair em AUTO.


def _mapear_controles(janela):
    resultado = {}
    automaticos = {}
    for item in _widgets(janela):
        if not isinstance(item, tk.Checkbutton):
            continue
        try:
            texto = str(item.cget("text"))
        except tk.TclError:
            continue
        nome = _CONTROLES.get(texto)
        if nome:
            linha = item.master.master
            resultado[nome] = {
                "check": item,
                "scale": _primeiro(linha, tk.Scale),
                "linha": linha,
                "aviso": None,
            }
        auto = _AUTOMATICOS.get(texto)
        if auto:
            automaticos[auto] = item
    return resultado, automaticos


def abrir_janela_configuracoes_com_status_real(
    self,
    *args,
    perfil_camera_real=None,
    callback_status_camera_ao_vivo=None,
    **kwargs,
) -> None:
    anteriores = {
        item for item in self.root.winfo_children()
        if isinstance(item, tk.Toplevel)
    }
    abrir_janela_configuracoes_sem_saltos(
        self,
        *args,
        callback_status_camera_ao_vivo=callback_status_camera_ao_vivo,
        **kwargs,
    )
    janela = _nova_janela(self.root, anteriores)
    if janela is None:
        return

    _aplicar_perfil_real(janela, perfil_camera_real)
    controles, automaticos = _mapear_controles(janela)

    def atualizar() -> None:
        if callback_status_camera_ao_vivo is None:
            return
        try:
            if not janela.winfo_exists():
                return
            status = callback_status_camera_ao_vivo() or {}
        except Exception:
            status = {}

        for nome, widgets in controles.items():
            dados = status.get(nome, {})
            if not isinstance(dados, dict):
                continue
            bloqueado = bool(dados.get("bloqueado", False))
            estado = str(dados.get("status") or "")
            motivo = str(dados.get("motivo") or "").strip()
            check = widgets["check"]
            scale = widgets["scale"]

            if bloqueado:
                try:
                    check.config(state=tk.DISABLED)
                    if scale is not None:
                        scale.config(state=tk.DISABLED)
                except tk.TclError:
                    pass

            texto = _STATUS.get(estado, estado)
            if texto or motivo:
                aviso = widgets.get("aviso")
                mensagem = texto
                if motivo:
                    mensagem = f"{texto}: {motivo}" if texto else motivo
                if aviso is None:
                    aviso = tk.Label(
                        widgets["linha"],
                        font=("Segoe UI", 8, "bold"),
                        fg="#FCA5A5" if bloqueado else "#FDE68A",
                        bg="#1E293B",
                        anchor="w",
                        justify=tk.LEFT,
                        wraplength=610,
                    )
                    aviso.pack(fill=tk.X, pady=(2, 0))
                    widgets["aviso"] = aviso
                try:
                    aviso.config(
                        text=mensagem,
                        fg="#FCA5A5" if bloqueado else "#FDE68A",
                    )
                except tk.TclError:
                    pass

        for chave_status, check in automaticos.items():
            dados = status.get(chave_status, {})
            if (
                isinstance(dados, dict)
                and dados.get("status") == "nao_suportado"
            ):
                try:
                    check.config(state=tk.DISABLED)
                except tk.TclError:
                    pass

        try:
            janela.after(220, atualizar)
        except tk.TclError:
            pass

    atualizar()
