def obter_tamanho_canvas_principal(self) -> tuple[int, int]:
    self.root.update_idletasks()

    largura_canvas = int(self.canvas.winfo_width())
    altura_canvas = int(self.canvas.winfo_height())

    # Nunca devolve uma área maior que o Canvas real. O comportamento anterior
    # impunha 320x220 mesmo quando o painel havia sido comprimido, fazendo a
    # imagem ser renderizada maior que a área visível e, portanto, cortada.
    if largura_canvas <= 1:
        largura_canvas = max(
            1,
            int(self.frame_painel_principal.winfo_width()) - 24,
        )

    if altura_canvas <= 1:
        altura_canvas = max(
            1,
            int(self.frame_painel_principal.winfo_height()) - 120,
        )

    return max(1, largura_canvas), max(1, altura_canvas)
