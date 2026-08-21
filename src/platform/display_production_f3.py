from __future__ import annotations

import tkinter as tk

from src.platform.display_production_f3_window import DisplayProductionF3Window
from src.platform.display_project_config import DisplayProjectConfigWindow
from src.platform.display_project_repository import (
    DisplayProjectRepository,
    normalizar_resolucao_display,
)
from src.platform.display_visual_rotation import obter_rotacao_visual_display
from src.platform.raspberry_pi3_settings import (
    OPERATION_PREVIEW_HEIGHT,
    OPERATION_PREVIEW_WIDTH,
)


class DisplayProductionF3Mixin:
    """Runtime do F3 isolado do fluxo de Produção F2.

    Fase 3 mantém Projeto Display, resolução, máscaras e CHECKS em persistência
    própria. Ainda não existe análise automática, engine de CHECK ou resultado
    OK/NG: esta fase configura somente a sequência e a expectativa das máscaras.
    """

    DISPLAY_F3_PREVIEW_INTERVAL_MS = 90
    DISPLAY_F3_BUTTON_BG = "#0E7490"
    DISPLAY_F3_BUTTON_ACTIVE_BG = "#0891B2"

    def __init__(self, *args, **kwargs) -> None:
        self.display_f3_window: DisplayProductionF3Window | None = None
        self.display_f3_ativo = False
        self.display_f3_after_id = None
        self.display_project_repository: DisplayProjectRepository | None = None
        self._display_project_config_window: DisplayProjectConfigWindow | None = None
        super().__init__(*args, **kwargs)
        self.display_project_repository = DisplayProjectRepository()
        self._instalar_modo_display_f3()
        self._atualizar_resumo_projeto_display_f3()

    def _criar_janela_producao_display_f3(self) -> DisplayProductionF3Window:
        return DisplayProductionF3Window(
            root=self.root,
            on_close=self.fechar_tela_producao_display_f3,
            on_configure=self.abrir_configuracao_projeto_display,
            preview_width=max(480, int(OPERATION_PREVIEW_WIDTH)),
            preview_height=max(360, int(OPERATION_PREVIEW_HEIGHT)),
        )

    def _f2_esta_aberto(self) -> bool:
        if bool(getattr(self, "operacao_ativa", False)):
            return True
        janela = getattr(self, "operacao_window", None)
        if janela is None:
            return False
        try:
            return bool(janela.visible)
        except Exception:
            return False

    def _instalar_modo_display_f3(self) -> None:
        self.display_f3_window = self._criar_janela_producao_display_f3()

        self.root.bind(
            "<F3>",
            lambda _event: self.abrir_tela_producao_display_f3(),
            add="+",
        )

        parent = getattr(self.view, "frame_topo_direita", self.root)
        self.botao_operacao_display_f3 = tk.Button(
            parent,
            text="DISPLAY  F3",
            command=self.abrir_tela_producao_display_f3,
            font=("DejaVu Sans", 10, "bold"),
            bg=self.DISPLAY_F3_BUTTON_BG,
            fg="#FFFFFF",
            activebackground=self.DISPLAY_F3_BUTTON_ACTIVE_BG,
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
        )

        if parent is self.root:
            self.botao_operacao_display_f3.place(
                relx=1.0,
                x=-188,
                y=16,
                anchor="ne",
            )
            self.botao_operacao_display_f3.lift()
        else:
            self.botao_operacao_display_f3.pack(
                side=tk.RIGHT,
                padx=(0, 8),
                pady=18,
            )

    def _obter_rotacao_visual_display_f3(self) -> int:
        """Herda somente a orientação visual atual da tela principal."""
        return obter_rotacao_visual_display(getattr(self, "view", None))

    def _obter_frame_para_configuracao_display(self):
        frame = getattr(self, "camera_frame_atual", None)
        if frame is None or getattr(frame, "size", 0) == 0:
            return None
        try:
            return frame.copy()
        except Exception:
            return frame

    def _ao_fechar_configuracao_projeto_display(self) -> None:
        self._display_project_config_window = None
        janela = self.display_f3_window
        if janela is not None and self.display_f3_ativo:
            try:
                janela.container.focus_force()
            except Exception:
                pass

    def abrir_configuracao_projeto_display(self) -> None:
        """Abre somente a configuração persistente pertencente ao F3."""
        existente = self._display_project_config_window
        if existente is not None and existente.visible:
            try:
                existente.window.lift()
                existente.window.focus_force()
            except Exception:
                pass
            return

        repository = self.display_project_repository
        if repository is None:
            repository = DisplayProjectRepository()
            self.display_project_repository = repository

        self._display_project_config_window = DisplayProjectConfigWindow(
            root=self.root,
            repository=repository,
            frame_provider=self._obter_frame_para_configuracao_display,
            on_change=self._atualizar_resumo_projeto_display_f3,
            on_close=self._ao_fechar_configuracao_projeto_display,
        )

    def _atualizar_resumo_projeto_display_f3(self) -> None:
        repository = self.display_project_repository
        janela = self.display_f3_window
        if repository is None or janela is None:
            return

        nome = repository.obter_projeto_ativo()
        projeto = repository.carregar_projeto(nome) if nome else None
        if projeto is None:
            try:
                janela.set_project_info(None, None, 0, 0)
            except Exception:
                pass
            return

        resolucao = normalizar_resolucao_display(
            projeto.get("master_resolution")
        )
        mascaras = projeto.get("masks", [])
        checks = projeto.get("checks", [])
        try:
            janela.set_project_info(
                projeto.get("name"),
                resolucao,
                len(mascaras) if isinstance(mascaras, list) else 0,
                len(checks) if isinstance(checks, list) else 0,
            )
        except Exception:
            pass

    def _ativar_tela_producao_display_f3(self) -> bool:
        """Mostra somente a camada F3; não cria nem altera runtime de F2."""
        self.display_f3_ativo = True
        self._atualizar_resumo_projeto_display_f3()
        janela = self.display_f3_window
        if janela is not None:
            janela.show_waiting_camera()
            janela.show()
        self._agendar_preview_display_f3(0)
        return True

    def _abrir_f3_apos_escolha_camera(self, _indice: int) -> None:
        """Continua o F3 usando o handoff de câmera já existente no ODIN."""
        if self._f2_esta_aberto():
            return
        try:
            self.iniciar_tela_ao_vivo()
        except Exception:
            pass
        self._ativar_tela_producao_display_f3()

    def abrir_tela_producao_display_f3(self) -> bool:
        """Abre F3 sem inicializar engine, trigger, contadores ou estado F2."""
        if self.display_f3_ativo:
            janela = self.display_f3_window
            if janela is not None:
                try:
                    janela.show()
                except Exception:
                    pass
            return True

        if self._f2_esta_aberto():
            try:
                self.view.atualizar_status(
                    "Feche a Produção F2 antes de abrir a Produção Display F3."
                )
            except Exception:
                pass
            return False

        if not bool(getattr(self, "camera_ativa", False)):
            abrir_seletor = getattr(self, "abrir_seletor_camera", None)
            if callable(abrir_seletor):
                abrir_seletor(
                    ao_selecionar=self._abrir_f3_apos_escolha_camera,
                )
                return True

            try:
                self.iniciar_tela_ao_vivo()
            except Exception:
                pass

        return self._ativar_tela_producao_display_f3()

    def fechar_tela_producao_display_f3(self) -> None:
        """Fecha somente a camada F3; a câmera e o F2 não são parados."""
        self.display_f3_ativo = False

        if self.display_f3_after_id is not None:
            try:
                self.root.after_cancel(self.display_f3_after_id)
            except Exception:
                pass
            self.display_f3_after_id = None

        configuracao = self._display_project_config_window
        if configuracao is not None and configuracao.visible:
            try:
                configuracao.close()
            except Exception:
                pass
        self._display_project_config_window = None

        janela = self.display_f3_window
        if janela is not None:
            try:
                janela.hide()
            except Exception:
                pass

        try:
            self.root.after_idle(self.root.focus_force)
        except Exception:
            pass

    def _agendar_preview_display_f3(
        self,
        atraso_ms: int | None = None,
    ) -> None:
        if not self.display_f3_ativo or self.display_f3_after_id is not None:
            return
        atraso = (
            self.DISPLAY_F3_PREVIEW_INTERVAL_MS
            if atraso_ms is None
            else max(0, int(atraso_ms))
        )
        try:
            self.display_f3_after_id = self.root.after(
                atraso,
                self._atualizar_preview_display_f3,
            )
        except Exception:
            self.display_f3_after_id = None

    def _atualizar_preview_display_f3(self) -> None:
        self.display_f3_after_id = None
        if not self.display_f3_ativo:
            return

        janela = self.display_f3_window
        frame = getattr(self, "camera_frame_atual", None)
        if janela is not None:
            try:
                janela.update_camera_preview(
                    frame,
                    visual_rotation=self._obter_rotacao_visual_display_f3(),
                )
            except Exception:
                pass

        self._agendar_preview_display_f3()

    @staticmethod
    def responsabilidades_f3() -> tuple[str, ...]:
        """Contrato imutável aprovado na Fase 1."""
        return (
            "janela_f3",
            "atalho_f3",
            "preview_camera_somente_leitura",
            "ciclo_abertura_fechamento_f3",
        )

    @staticmethod
    def responsabilidades_f3_fase2() -> tuple[str, ...]:
        return (
            "projeto_display_persistente",
            "resolucao_mestra_display",
            "mascaras_display_persistentes",
        )

    @staticmethod
    def responsabilidades_f3_fase3() -> tuple[str, ...]:
        return (
            "checks_display_persistentes",
            "ordem_checks_configuravel",
            "estado_mascara_por_check",
            "editor_visual_checks",
        )
