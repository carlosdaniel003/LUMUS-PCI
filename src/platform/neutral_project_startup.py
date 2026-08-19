from __future__ import annotations


class NeutralProjectStartupMixin:
    """Mantém o início do ODIN neutro até um projeto ser escolhido.

    O repositório pode continuar persistindo ``active_led_project`` para
    organização/compatibilidade, mas esse valor não representa mais um projeto
    carregado na sessão atual. Uma resolução mestre só pode influenciar a
    câmera depois que o operador escolher explicitamente um projeto em
    ``Carregar LEDs`` (ou salvar um projeto na sessão atual).
    """

    def __init__(self, *args, **kwargs) -> None:
        # Precisa existir antes do restante da cadeia de __init__. O
        # ProjectMasterResolutionMixin consulta a resolução ao retornar do
        # super(); com a sessão vazia a consulta não pode cair no último
        # active_led_project persistido.
        self._projeto_led_sessao_carregado = ""
        super().__init__(*args, **kwargs)
        self._limpar_contexto_projeto_no_inicio()

    def _nome_projeto_sessao(self, projeto: str | None = None) -> str:
        nome_sessao = str(
            getattr(self, "_projeto_led_sessao_carregado", "") or ""
        ).strip()
        if nome_sessao:
            return nome_sessao

        # Um nome recebido durante a seleção/salvamento só é aceito quando o
        # fluxo explicitamente marcou a sessão. Isso impede que chamadas
        # internas com projeto_led_ativo persistido reativem o último projeto.
        return ""

    def _limpar_referencias_projeto_runtime(self) -> None:
        grupos = getattr(self, "_referencias_ativas_por_tipo", None)
        if isinstance(grupos, dict):
            for chave in tuple(grupos.keys()):
                grupos[chave] = []

        for atributo, valor in (
            ("imagem_referencia_acesa", None),
            ("imagem_referencia_apagada", None),
            ("imagem_referencia_pouca_luz", None),
            ("caminho_referencia_acesa", None),
            ("caminho_referencia_apagada", None),
            ("caminho_referencia_pouca_luz", None),
            ("features_referencia_acesa", None),
            ("features_referencia_apagada", None),
            ("features_referencia_pouca_luz", None),
            ("referencias_acesas_ativas", []),
            ("referencias_apagadas_ativas", []),
            ("referencias_pouca_luz_ativas", []),
        ):
            if hasattr(self, atributo):
                setattr(self, atributo, valor)

    def _limpar_contexto_projeto_no_inicio(self) -> None:
        self._projeto_led_sessao_carregado = ""
        self.projeto_led_ativo = ""

        # O ODINApp legado carrega fixed_leds do projeto persistido no __init__.
        # Para uma sessão nova isso deve ser somente dado armazenado, não estado
        # operacional já carregado.
        if hasattr(self, "leds_fixos_configurados"):
            self.leds_fixos_configurados = []
        if hasattr(self, "leds_selecionados"):
            self.leds_selecionados = []
        if hasattr(self, "resultados_led_atual"):
            self.resultados_led_atual = []

        self._resolucao_mestra_projeto_ativa = None
        self._resolucao_mestra_projeto_nome = ""
        self._resolucao_mestra_producao = None
        self._limpar_referencias_projeto_runtime()

        view = getattr(self, "view", None)
        label_placa = getattr(view, "label_meta_placa", None)
        if label_placa is not None:
            try:
                label_placa.configure(text="MANUAL")
            except Exception:
                pass

        atualizar_painel = getattr(self, "atualizar_painel_inicial", None)
        if callable(atualizar_painel):
            try:
                atualizar_painel()
            except Exception:
                pass

    def _atualizar_resolucao_mestra_projeto_ativa(
        self,
        projeto: str | None = None,
    ):
        nome = self._nome_projeto_sessao(projeto)
        if not nome:
            self._resolucao_mestra_projeto_nome = ""
            self._resolucao_mestra_projeto_ativa = None
            return None
        return super()._atualizar_resolucao_mestra_projeto_ativa(nome)

    def _aplicar_resolucao_mestra_projeto(
        self,
        projeto: str | None = None,
        reiniciar_se_necessario: bool = True,
    ) -> bool:
        nome = self._nome_projeto_sessao(projeto)
        if not nome:
            # Sem projeto carregado não existe resolução mestre operacional.
            # Se houver um serviço reaproveitado, remova somente a trava de
            # projeto; nenhuma resolução é escrita e nenhum restart é feito.
            service = getattr(self, "camera_service", None)
            destravar = getattr(service, "definir_resolucao_travada", None)
            if callable(destravar):
                try:
                    destravar(None, None)
                except Exception:
                    pass
            self._resolucao_mestra_projeto_ativa = None
            self._resolucao_mestra_projeto_nome = ""
            return False

        return super()._aplicar_resolucao_mestra_projeto(
            nome,
            reiniciar_se_necessario=reiniciar_se_necessario,
        )

    def _projeto_referencia_ativo(self) -> str:
        # Não consultar obter_projeto_led_ativo() enquanto a sessão estiver
        # vazia: essa API representa o último projeto persistido, não uma ação
        # explícita do operador nesta execução.
        return str(
            getattr(self, "_projeto_led_sessao_carregado", "") or ""
        ).strip()

    def _selecionar_projeto_led_existente(self, projetos: list[str]):
        selecionado = super()._selecionar_projeto_led_existente(projetos)
        nome = str(selecionado or "").strip()
        if nome:
            self._projeto_led_sessao_carregado = nome
            self.projeto_led_ativo = nome
        return selecionado

    def _salvar_leds_no_projeto(
        self,
        nome_projeto: str,
        parent=None,
        confirmar_substituicao: bool = True,
    ) -> bool:
        salvo = super()._salvar_leds_no_projeto(
            nome_projeto,
            parent=parent,
            confirmar_substituicao=confirmar_substituicao,
        )
        if not salvo:
            return False

        nome = str(nome_projeto or "").strip()
        if nome:
            self._projeto_led_sessao_carregado = nome
            self.projeto_led_ativo = nome
            self._atualizar_resolucao_mestra_projeto_ativa(nome)
            self._aplicar_resolucao_mestra_projeto(
                nome,
                reiniciar_se_necessario=False,
            )
        return True

    def iniciar_tela_ao_vivo(self) -> None:
        resultado = super().iniciar_tela_ao_vivo()

        # O ODINApp base recarrega fixed_leds do espelho persistido sempre que
        # a câmera é iniciada. Sem projeto escolhido na sessão, remova essa
        # carga antes do primeiro callback de frame do Tkinter.
        if not self._projeto_led_sessao_carregado:
            self.leds_fixos_configurados = []
            self._resolucao_mestra_projeto_ativa = None
            self._resolucao_mestra_projeto_nome = ""
        return resultado
