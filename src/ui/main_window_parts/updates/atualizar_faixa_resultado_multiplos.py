from src.models.analysis_result import LedAnalysisResult


STATUS_POUCA_LUZ = "POUCA_LUZ"


def atualizar_faixa_resultado_multiplos(
    self,
    resultados_led: list[LedAnalysisResult],
) -> None:
    if not resultados_led:
        self.atualizar_faixa_resultado()
        return

    total_leds = len(resultados_led)
    leds_acesos = sum(
        1
        for resultado in resultados_led
        if str(getattr(resultado, "status", "")).upper() == "ACESO"
    )
    leds_pouca_luz = sum(
        1
        for resultado in resultados_led
        if str(getattr(resultado, "status", "")).upper() == STATUS_POUCA_LUZ
    )
    leds_apagados = sum(
        1
        for resultado in resultados_led
        if str(getattr(resultado, "status", "")).upper() == "APAGADO"
    )

    if leds_apagados > 0:
        cor_fundo = self.COR_VERMELHO
        cor_resultado = self.COR_VERMELHO_CLARO
        titulo = "ANÁLISE COM FALHA"
        texto = (
            f"ANÁLISE COM FALHA | acesos {leds_acesos} | "
            f"pouca luz {leds_pouca_luz} | apagados {leds_apagados}"
        )
    elif leds_pouca_luz > 0:
        cor_fundo = "#92400E"
        cor_resultado = "#F59E0B"
        titulo = "SEGMENTO COM POUCA LUZ"
        texto = (
            f"FALHA DE LUMINOSIDADE | acesos {leds_acesos} | "
            f"pouca luz {leds_pouca_luz} | apagados 0"
        )
    else:
        cor_fundo = self.COR_VERDE
        cor_resultado = self.COR_VERDE_CLARO
        texto = f"TODOS OS LEDS ACESOS | total {total_leds}"
        titulo = "TODOS ACESOS"

    self.frame_faixa_resultado.config(bg=cor_fundo)
    self.label_faixa_resultado.config(text=texto, bg=cor_fundo)
    self.label_resultado_grande.config(text=titulo, fg=cor_resultado)

    confianca_media = sum(
        float(resultado.confianca) for resultado in resultados_led
    ) / total_leds
    self.label_confianca.config(
        text=f"Confiança média\n{round(confianca_media, 4)}"
    )
    self.desenhar_barra_confianca(float(confianca_media), cor_resultado)
