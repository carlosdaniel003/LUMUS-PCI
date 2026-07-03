import tkinter as tk


def atualizar_log_producao(self, registros: list[dict]) -> None:
    texto = getattr(self, "texto_log_producao", None)
    if texto is None:
        return

    texto.configure(state=tk.NORMAL)
    texto.delete("1.0", tk.END)

    if not registros:
        texto.insert(
            tk.END,
            "Nenhuma análise de produção registrada.",
        )
        texto.configure(state=tk.DISABLED)
        return

    for indice, registro in enumerate(reversed(registros)):
        data = str(registro.get("data", "")).strip()
        hora = str(registro.get("hora", "")).strip()
        configuracao = str(
            registro.get("configuracao", "SEM PROJETO")
        ).strip()
        status = str(registro.get("status", "INDEFINIDO")).strip()
        leds_apagados = tuple(registro.get("leds_apagados", ()) or ())
        apagados = ", ".join(str(item) for item in leds_apagados) or "—"

        linha = (
            f"{data} {hora} | {configuracao} | {status}"
            f" | Apagados: {apagados}"
        )
        texto.insert(tk.END, linha)
        if indice < len(registros) - 1:
            texto.insert(tk.END, "\n")

    texto.configure(state=tk.DISABLED)
    texto.see("1.0")
