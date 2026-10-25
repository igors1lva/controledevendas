"""
Módulo da Tela de Descanso Inteligente (Screensaver)
Arquivo: views/screensaver_overlay.py

Exibe uma tela de descanso elegante em tela cheia quando o operador
permanece sem interação no sistema pelo período configurado.
Suporta dois modos:
  1. Padrão: Identidade AstridSoft com logo cósmico estilizado e relógio digital em tempo real.
  2. Personalizado: Banner ou imagem promocional definida pelo próprio lojista.
Qualquer interação (teclado, clique ou movimento de mouse) desativa instantaneamente a tela.
"""

import os
import sys
from datetime import datetime
from typing import Optional, Callable
import customtkinter as ctk

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

import database as db


def obter_caminho_recurso(caminho_relativo: str) -> str:
    """Retorna o caminho absoluto do recurso, compatível com PyInstaller e dev."""
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, caminho_relativo)


class ScreensaverOverlay(ctk.CTkFrame):
    """
    Overlay fullscreen cobrindo 100% da janela principal da aplicação
    quando a inatividade for detectada.
    """

    def __init__(self, master, on_dismiss: Optional[Callable] = None):
        super().__init__(
            master,
            fg_color="#0A0F1D",  # Fundo escuro tecnológico imersivo
            corner_radius=0,
            border_width=0,
        )
        self.master_window = master
        self.on_dismiss = on_dismiss
        self.ativo = False
        self._relogio_timer = None
        self._pos_mouse_inicial = None

        self._criar_conteudo()

        # Vincula eventos no próprio overlay e subwidgets para desbloqueio imediato ao menor toque
        widgets_para_vincular = [
            self,
            self.container_conteudo,
            self.lbl_imagem,
            self.lbl_hora,
            self.lbl_data,
            self.lbl_aviso,
        ]
        for w in widgets_para_vincular:
            w.bind("<Button-1>", self._ao_interagir)
            w.bind("<Button-2>", self._ao_interagir)
            w.bind("<Button-3>", self._ao_interagir)
            w.bind("<Key>", self._ao_interagir)
            w.bind("<Motion>", self._ao_verificar_movimento_mouse)

    def _criar_conteudo(self):
        """Constrói a estrutura interna do protetor de tela."""
        self.container_conteudo = ctk.CTkFrame(self, fg_color="transparent")
        self.container_conteudo.place(relx=0.5, rely=0.5, anchor="center")

        # Imagem / Logotipo de Descanso
        self.lbl_imagem = ctk.CTkLabel(self.container_conteudo, text="")
        self.lbl_imagem.pack(pady=(0, 20))

        # Relógio Digital em Destaque
        self.lbl_hora = ctk.CTkLabel(
            self.container_conteudo,
            text="00:00:00",
            font=ctk.CTkFont(family="Segoe UI", size=56, weight="bold"),
            text_color="#38BDF8",  # Azul neon / Sky 400
        )
        self.lbl_hora.pack(pady=(0, 4))

        # Data por Extenso
        self.lbl_data = ctk.CTkLabel(
            self.container_conteudo,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=16),
            text_color="#94A3B8",
        )
        self.lbl_data.pack(pady=(0, 25))

        # Instrução suave de desbloqueio
        self.lbl_aviso = ctk.CTkLabel(
            self.container_conteudo,
            text="Pressione qualquer tecla ou toque no mouse para continuar",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#64748B",
        )
        self.lbl_aviso.pack(pady=(0, 5))

    def recarregar_midia(self):
        """Recarrega a imagem conforme o modo ativo: Padrão (AstridSoft) ou Customizado (Lojista)."""
        modo = db.obter_config("screensaver_mode", "DEFAULT")
        caminho_custom = db.obter_config("screensaver_custom_path", "")

        caminho_img = None
        if modo == "CUSTOM" and caminho_custom and os.path.exists(caminho_custom):
            caminho_img = caminho_custom
        else:
            caminho_img = obter_caminho_recurso(os.path.join("assets", "astridsoft_screensaver.png"))
            if not os.path.exists(caminho_img):
                caminho_img = obter_caminho_recurso(os.path.join("assets", "astridsoft_logo.png"))

        if PIL_AVAILABLE and caminho_img and os.path.exists(caminho_img):
            try:
                with Image.open(caminho_img) as f_img:
                    pil_img = f_img.copy()
                # Se for imagem personalizada (banner), dimensiona com largura maior
                if modo == "CUSTOM":
                    max_w = min(680, max(360, self.master_window.winfo_width() - 80))
                    max_h = min(380, max(240, self.master_window.winfo_height() - 250))
                    orig_w, orig_h = pil_img.size
                    ratio = min(max_w / orig_w, max_h / orig_h)
                    alvo_w = int(orig_w * ratio)
                    alvo_h = int(orig_h * ratio)
                else:
                    # Modo Padrão AstridSoft
                    alvo_w = 260
                    alvo_h = int(pil_img.height * alvo_w / pil_img.width)

                ctk_img = ctk.CTkImage(
                    light_image=pil_img,
                    dark_image=pil_img,
                    size=(alvo_w, alvo_h),
                )
                self.lbl_imagem.configure(image=ctk_img)
                self.lbl_imagem.image = ctk_img
            except Exception:
                self.lbl_imagem.configure(image=None, text="AstridSoft")
        else:
            self.lbl_imagem.configure(image=None, text="AstridSoft")

    def _atualizar_relogio(self):
        """Atualiza dinamicamente a hora e a data no protetor de tela a cada 1 segundo."""
        if not self.ativo:
            return

        agora = datetime.now()
        self.lbl_hora.configure(text=agora.strftime("%H:%M:%S"))

        meses = [
            "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
        ]
        dias_semana = [
            "Segunda-feira", "Terça-feira", "Quarta-feira",
            "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"
        ]
        dia_sem = dias_semana[agora.weekday()]
        mes_nome = meses[agora.month - 1]
        data_extenso = f"{dia_sem}, {agora.day:02d} de {mes_nome} de {agora.year}"
        self.lbl_data.configure(text=data_extenso)

        self._relogio_timer = self.after(1000, self._atualizar_relogio)

    def _ao_verificar_movimento_mouse(self, event):
        """Detecta movimento intencional do mouse, evitando disparos acidentais por microvibrações."""
        if not self.ativo:
            return
        if self._pos_mouse_inicial is None:
            self._pos_mouse_inicial = (event.x_root, event.y_root)
            return

        dx = abs(event.x_root - self._pos_mouse_inicial[0])
        dy = abs(event.y_root - self._pos_mouse_inicial[1])
        if dx > 8 or dy > 8:
            self.fechar_screensaver()

    def _ao_interagir(self, event=None):
        """Desativa o screensaver imediatamente ao clicar ou pressionar tecla."""
        self.fechar_screensaver()

    def mostrar(self):
        """Exibe o overlay cobrindo 100% da janela."""
        if self.ativo:
            return
        self.ativo = True
        self._pos_mouse_inicial = None
        self.recarregar_midia()
        self._atualizar_relogio()

        # Posiciona cobrindo todo o master
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        self.focus_set()

    def fechar_screensaver(self):
        """Oculta o overlay e restaura a visão da aplicação."""
        if not self.ativo:
            return
        self.ativo = False
        if self._relogio_timer:
            try:
                self.after_cancel(self._relogio_timer)
            except Exception:
                pass
            self._relogio_timer = None

        self.place_forget()
        if self.on_dismiss:
            self.on_dismiss()
