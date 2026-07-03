from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog

from src.platform.led_project_repository import (
    normalizar_nome_projeto_led,
)


class LedProjectManagerMixin:
    """Gerencia seleção e salvamento das máscaras por modelo de placa."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.projeto_led_ativo = (
            self.config_repository.obter_projeto_led_ativo()
        )
        self._atualizar_projeto_led_na_interface()

    def _atualizar_projeto_led_na_interface(self) -> None:
        nome = self.projeto_led_ativo or "SEM PROJETO"
        label = getattr(self.view, "label_meta_placa", None)
        if label is not None:
            label.configure(text=nome)

    def _sincronizar_projeto_ativo_apos_gestao(
        self,
        carregar_mascaras: bool = False,
    ) -> None:
        self.projeto_led_ativo = (
            self.config_repository.obter_projeto_led_ativo()
        )
        self._atualizar_projeto_led_na_interface()

        if not carregar_mascaras:
            return

        if not self.projeto_led_ativo:
            self.leds_fixos_configurados = []
            self.leds_selecionados = []
            self.resultados_led_atual = []
            self.guias_leds_fixos_visiveis = False
            self.selecao_manual_camera_ativa = False
            self.leds_manuais_camera = []
            self.view.selecao_manual_camera_visivel = False
            self.view.atualizar_estado_selecao_led(False)
            self.view.atualizar_faixa_resultado()
            if self.imagem_original is not None:
                self.view.preparar_imagem_para_exibicao(
                    self.imagem_original
                )
                self.view.desenhar_canvas([], [])
            return

        if self.imagem_original is None:
            self.leds_fixos_configurados = (
                self.config_repository.carregar_leds_fixos()
            )
            return

        super().carregar_leds_fixos()

    def _selecionar_projeto_led_existente(
        self,
        projetos: list[str],
    ) -> str | None:
        resultado = {"nome": None}
        janela = tk.Toplevel(self.root)
        janela.title("Gerenciar configurações de LEDs")
        janela.configure(bg="#07111F")
        janela.transient(self.root)
        janela.resizable(False, False)
        janela.grab_set()

        largura = 650
        altura = 470
        pos_x = self.root.winfo_rootx() + max(
            0,
            (self.root.winfo_width() - largura) // 2,
        )
        pos_y = self.root.winfo_rooty() + max(
            0,
            (self.root.winfo_height() - altura) // 2,
        )
        janela.geometry(f"{largura}x{altura}+{pos_x}+{pos_y}")

        tk.Label(
            janela,
            text="Configurações de LEDs",
            font=("Segoe UI", 16, "bold"),
            fg="#F9FAFB",
            bg="#07111F",
        ).pack(anchor="w", padx=22, pady=(18, 3))

        tk.Label(
            janela,
            text=(
                "Selecione, adicione, renomeie, remova ou reorganize os "
                "projetos usados no modo de produção."
            ),
            font=("Segoe UI", 9),
            fg="#94A3B8",
            bg="#07111F",
            justify=tk.LEFT,
            wraplength=600,
        ).pack(anchor="w", padx=22, pady=(0, 10))

        frame_conteudo = tk.Frame(janela, bg="#07111F")
        frame_conteudo.pack(
            fill=tk.BOTH,
            expand=True,
            padx=22,
            pady=(0, 12),
        )

        frame_lista = tk.Frame(
            frame_conteudo,
            bg="#122033",
            highlightthickness=1,
            highlightbackground="#1E293B",
        )
        frame_lista.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(frame_lista, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        lista = tk.Listbox(
            frame_lista,
            exportselection=False,
            selectmode=tk.BROWSE,
            font=("Segoe UI", 11, "bold"),
            bg="#020617",
            fg="#F9FAFB",
            selectbackground="#0F3D24",
            selectforeground="#BBF7D0",
            activestyle="none",
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
        )
        lista.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1, pady=1)
        scrollbar.configure(command=lista.yview)

        frame_acoes = tk.Frame(frame_conteudo, bg="#07111F", width=185)
        frame_acoes.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        frame_acoes.pack_propagate(False)

        label_resumo = tk.Label(
            janela,
            text="",
            font=("Segoe UI", 8, "bold"),
            fg="#94A3B8",
            bg="#07111F",
            anchor="w",
        )
        label_resumo.pack(fill=tk.X, padx=22, pady=(0, 8))

        def obter_selecionado() -> str | None:
            selecao = lista.curselection()
            if not selecao:
                return None
            return str(lista.get(selecao[0]))

        def atualizar_resumo() -> None:
            ativo = (
                self.config_repository.obter_projeto_led_ativo()
                or "SEM PROJETO"
            )
            quantidade = lista.size()
            label_resumo.configure(
                text=(
                    f"Projeto ativo: {ativo}    |    "
                    f"Configurações cadastradas: {quantidade}"
                )
            )

        def recarregar_lista(preferido: str | None = None) -> None:
            nomes = self.config_repository.listar_projetos_led()
            lista.delete(0, tk.END)
            for nome in nomes:
                lista.insert(tk.END, nome)

            if not nomes:
                atualizar_resumo()
                return

            alvo = preferido or self.projeto_led_ativo
            indice = nomes.index(alvo) if alvo in nomes else 0
            lista.selection_set(indice)
            lista.activate(indice)
            lista.see(indice)
            atualizar_resumo()

        def adicionar() -> None:
            nome_digitado = simpledialog.askstring(
                "Adicionar configuração",
                (
                    "Informe o nome do novo modelo/projeto.\n\n"
                    "A nova configuração será criada sem máscaras."
                ),
                parent=janela,
            )
            if nome_digitado is None:
                return

            nome = normalizar_nome_projeto_led(nome_digitado)
            if not nome:
                messagebox.showwarning(
                    "Nome inválido",
                    "Informe um nome para a configuração de LEDs.",
                    parent=janela,
                )
                return

            if nome in self.config_repository.listar_projetos_led():
                messagebox.showwarning(
                    "Configuração existente",
                    f"Já existe uma configuração chamada {nome}.",
                    parent=janela,
                )
                return

            if not self.config_repository.adicionar_projeto_led(nome):
                messagebox.showerror(
                    "Falha ao adicionar",
                    "Não foi possível criar a configuração de LEDs.",
                    parent=janela,
                )
                return

            self._sincronizar_projeto_ativo_apos_gestao()
            recarregar_lista(nome)

        def renomear() -> None:
            atual = obter_selecionado()
            if atual is None:
                messagebox.showwarning(
                    "Seleção necessária",
                    "Selecione uma configuração para renomear.",
                    parent=janela,
                )
                return

            nome_digitado = simpledialog.askstring(
                "Renomear configuração",
                "Informe o novo nome:",
                initialvalue=atual,
                parent=janela,
            )
            if nome_digitado is None:
                return

            novo = normalizar_nome_projeto_led(nome_digitado)
            if not novo:
                messagebox.showwarning(
                    "Nome inválido",
                    "Informe um nome válido para a configuração.",
                    parent=janela,
                )
                return

            existentes = self.config_repository.listar_projetos_led()
            if novo != atual and novo in existentes:
                messagebox.showwarning(
                    "Configuração existente",
                    f"Já existe uma configuração chamada {novo}.",
                    parent=janela,
                )
                return

            if not self.config_repository.renomear_projeto_led(
                atual,
                novo,
            ):
                messagebox.showerror(
                    "Falha ao renomear",
                    "Não foi possível renomear a configuração.",
                    parent=janela,
                )
                return

            self._sincronizar_projeto_ativo_apos_gestao()
            recarregar_lista(novo)

        def remover() -> None:
            nome = obter_selecionado()
            if nome is None:
                messagebox.showwarning(
                    "Seleção necessária",
                    "Selecione uma configuração para remover.",
                    parent=janela,
                )
                return

            quantidade_leds = len(
                self.config_repository.carregar_leds_fixos(
                    projeto=nome
                )
            )
            confirmar = messagebox.askyesno(
                "Remover configuração",
                (
                    f"Remover definitivamente a configuração {nome}?\n\n"
                    f"Máscaras cadastradas: {quantidade_leds}\n\n"
                    "Essa ação não poderá ser desfeita."
                ),
                parent=janela,
            )
            if not confirmar:
                return

            era_ativo = nome == self.config_repository.obter_projeto_led_ativo()
            if not self.config_repository.remover_projeto_led(nome):
                messagebox.showerror(
                    "Falha ao remover",
                    "Não foi possível remover a configuração.",
                    parent=janela,
                )
                return

            self._sincronizar_projeto_ativo_apos_gestao(
                carregar_mascaras=era_ativo
            )
            recarregar_lista(self.projeto_led_ativo)

        def mover(direcao: int) -> None:
            selecao = lista.curselection()
            if not selecao:
                messagebox.showwarning(
                    "Seleção necessária",
                    "Selecione uma configuração para reorganizar.",
                    parent=janela,
                )
                return

            indice_atual = int(selecao[0])
            indice_novo = indice_atual + direcao
            if indice_novo < 0 or indice_novo >= lista.size():
                return

            nomes = [str(lista.get(i)) for i in range(lista.size())]
            nomes[indice_atual], nomes[indice_novo] = (
                nomes[indice_novo],
                nomes[indice_atual],
            )

            if not self.config_repository.reordenar_projetos_led(nomes):
                messagebox.showerror(
                    "Falha ao reorganizar",
                    "Não foi possível salvar a nova ordem.",
                    parent=janela,
                )
                return

            recarregar_lista(nomes[indice_novo])

        def confirmar(_evento=None) -> str:
            nome = obter_selecionado()
            if nome is None:
                messagebox.showwarning(
                    "Nenhuma configuração",
                    "Adicione ou selecione uma configuração de LEDs.",
                    parent=janela,
                )
                return "break"
            resultado["nome"] = nome
            janela.destroy()
            return "break"

        def cancelar(_evento=None) -> str:
            janela.destroy()
            return "break"

        def criar_botao_acao(
            texto: str,
            comando,
            cor_fundo: str = "#132033",
            cor_texto: str = "#E5E7EB",
        ) -> None:
            tk.Button(
                frame_acoes,
                text=texto,
                command=comando,
                font=("Segoe UI", 9, "bold"),
                bg=cor_fundo,
                fg=cor_texto,
                activebackground="#1E293B",
                activeforeground="#FFFFFF",
                relief=tk.FLAT,
                padx=12,
                pady=8,
                cursor="hand2",
                anchor="w",
            ).pack(fill=tk.X, pady=(0, 7))

        criar_botao_acao(
            "＋  Adicionar",
            adicionar,
            cor_fundo="#0F3D24",
            cor_texto="#BBF7D0",
        )
        criar_botao_acao("✎  Renomear", renomear)
        criar_botao_acao(
            "×  Remover",
            remover,
            cor_fundo="#3F1519",
            cor_texto="#FECACA",
        )

        tk.Frame(
            frame_acoes,
            bg="#1E293B",
            height=1,
        ).pack(fill=tk.X, pady=(4, 11))

        criar_botao_acao("↑  Mover para cima", lambda: mover(-1))
        criar_botao_acao("↓  Mover para baixo", lambda: mover(1))

        frame_botoes = tk.Frame(janela, bg="#07111F")
        frame_botoes.pack(fill=tk.X, padx=22, pady=(0, 18))

        tk.Button(
            frame_botoes,
            text="Fechar",
            command=cancelar,
            font=("Segoe UI", 9, "bold"),
            bg="#1F2937",
            fg="#E5E7EB",
            activebackground="#374151",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            padx=16,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.RIGHT)

        tk.Button(
            frame_botoes,
            text="Carregar projeto",
            command=confirmar,
            font=("Segoe UI", 9, "bold"),
            bg="#16A34A",
            fg="#FFFFFF",
            activebackground="#15803D",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            padx=16,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=(0, 8))

        lista.bind("<Double-Button-1>", confirmar)
        lista.bind("<Return>", confirmar)
        janela.bind("<Escape>", cancelar)
        recarregar_lista(
            self.projeto_led_ativo
            if self.projeto_led_ativo in projetos
            else None
        )
        lista.focus_force()
        self.root.wait_window(janela)
        return resultado["nome"]

    def salvar_leds_fixos(self) -> None:
        if not self.leds_selecionados:
            super().salvar_leds_fixos()
            return

        projetos = self.config_repository.listar_projetos_led()
        sugestao = self.projeto_led_ativo or ""
        nome_digitado = simpledialog.askstring(
            "Salvar configuração de LEDs",
            (
                "Informe o modelo/projeto da placa.\n\n"
                "Exemplos: TW-10, TW-42"
            ),
            initialvalue=sugestao,
            parent=self.root,
        )

        if nome_digitado is None:
            return

        nome = normalizar_nome_projeto_led(nome_digitado)
        if not nome:
            messagebox.showwarning(
                "Projeto inválido",
                "Informe um nome para o modelo da placa.",
                parent=self.root,
            )
            return

        if nome in projetos:
            substituir = messagebox.askyesno(
                "Atualizar projeto",
                (
                    f"O projeto {nome} já existe.\n\n"
                    "Deseja substituir as máscaras salvas pelas posições "
                    "que estão atualmente na tela?"
                ),
                parent=self.root,
            )
            if not substituir:
                return

        self.config_repository.definir_projeto_led_ativo(
            nome,
            criar=True,
        )
        self.projeto_led_ativo = nome
        super().salvar_leds_fixos()
        self._atualizar_projeto_led_na_interface()
        self.view.atualizar_status(
            f"Projeto {nome}: {len(self.leds_fixos_configurados)} LEDs salvos."
        )

    def carregar_leds_fixos(self) -> None:
        projetos = self.config_repository.listar_projetos_led()
        nome = self._selecionar_projeto_led_existente(projetos)
        if nome is None:
            return

        if not self.config_repository.definir_projeto_led_ativo(nome):
            messagebox.showwarning(
                "Projeto não encontrado",
                f"A configuração do projeto {nome} não foi encontrada.",
                parent=self.root,
            )
            return

        self.projeto_led_ativo = nome
        self._atualizar_projeto_led_na_interface()

        if self.imagem_original is None:
            self.leds_fixos_configurados = (
                self.config_repository.carregar_leds_fixos()
            )
            self.view.atualizar_status(
                f"Projeto {nome} ativado com "
                f"{len(self.leds_fixos_configurados)} LEDs. "
                "As máscaras serão exibidas quando a câmera ou uma imagem "
                "estiver disponível."
            )
            return

        super().carregar_leds_fixos()

        if self.leds_selecionados:
            self.view.atualizar_status(
                f"Projeto {nome} carregado com "
                f"{len(self.leds_selecionados)} LEDs."
            )

    def configurar_leds_fixos(self) -> None:
        super().configurar_leds_fixos()
        if (
            self.modo_atual == "configurar_leds_fixos"
            and self.projeto_led_ativo
        ):
            self.view.atualizar_status(
                f"Editando o projeto {self.projeto_led_ativo}. "
                "Mova, exclua ou adicione máscaras e salve para atualizar."
            )
