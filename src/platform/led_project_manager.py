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

    def _selecionar_projeto_led_existente(
        self,
        projetos: list[str],
    ) -> str | None:
        if not projetos:
            return None

        resultado = {"nome": None}
        janela = tk.Toplevel(self.root)
        janela.title("Selecionar projeto de LEDs")
        janela.configure(bg="#07111F")
        janela.transient(self.root)
        janela.resizable(False, False)
        janela.grab_set()

        largura = 430
        altura = 410
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
            text="Projeto da placa",
            font=("Segoe UI", 16, "bold"),
            fg="#F9FAFB",
            bg="#07111F",
        ).pack(anchor="w", padx=22, pady=(20, 4))

        tk.Label(
            janela,
            text=(
                "Selecione a configuração de máscaras que será carregada "
                "e usada pelo modo de produção."
            ),
            font=("Segoe UI", 9),
            fg="#94A3B8",
            bg="#07111F",
            justify=tk.LEFT,
            wraplength=380,
        ).pack(anchor="w", padx=22, pady=(0, 12))

        frame_lista = tk.Frame(
            janela,
            bg="#122033",
            highlightthickness=1,
            highlightbackground="#1E293B",
        )
        frame_lista.pack(fill=tk.BOTH, expand=True, padx=22, pady=(0, 16))

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
        )
        lista.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        for projeto in projetos:
            lista.insert(tk.END, projeto)

        projeto_atual = self.projeto_led_ativo
        indice_inicial = 0
        if projeto_atual in projetos:
            indice_inicial = projetos.index(projeto_atual)
        lista.selection_set(indice_inicial)
        lista.activate(indice_inicial)
        lista.see(indice_inicial)

        def confirmar(_evento=None) -> str:
            selecao = lista.curselection()
            if not selecao:
                return "break"
            resultado["nome"] = str(lista.get(selecao[0]))
            janela.destroy()
            return "break"

        def cancelar(_evento=None) -> str:
            janela.destroy()
            return "break"

        frame_botoes = tk.Frame(janela, bg="#07111F")
        frame_botoes.pack(fill=tk.X, padx=22, pady=(0, 20))

        tk.Button(
            frame_botoes,
            text="Cancelar",
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
        if self.imagem_original is None:
            super().carregar_leds_fixos()
            return

        projetos = self.config_repository.listar_projetos_led()
        if not projetos:
            super().carregar_leds_fixos()
            return

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
