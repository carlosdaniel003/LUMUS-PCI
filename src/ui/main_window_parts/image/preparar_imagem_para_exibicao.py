def preparar_imagem_para_exibicao(self, imagem_canvas) -> None:
    if imagem_canvas is None:
        return

    self.imagem_canvas_original = imagem_canvas

    altura_canvas_original, largura_canvas_original = imagem_canvas.shape[:2]
    resolucao = f"{largura_canvas_original} x {altura_canvas_original}"
    if getattr(self, "resolucao_atual", None) != resolucao:
        self.resolucao_atual = resolucao
        self.label_meta_resolucao.config(text=resolucao)

    self.atualizar_imagem_principal_redimensionada()
    self.atualizar_imagem_tela_cheia_se_aberta("principal")
