import base64
from datetime import datetime
import tkinter as tk
from tkinter import ttk

import cv2

from src.models.analysis_result import LedAnalysisResult
from src.models.led_selection import LedSelection


def limpar_renderizacoes_visuais(self) -> None:
        self.imagens_auxiliares_originais.clear()
        self.desenhar_placeholders_laterais()
        chave = getattr(self, "chave_imagem_tela_cheia", None)
        if chave and chave != "principal":
            self.atualizar_imagem_tela_cheia_se_aberta(chave)
