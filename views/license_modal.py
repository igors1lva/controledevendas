"""
Módulo de Interface: Modal de Ativação de Licença Comercial
Arquivo: views/license_modal.py

Janela modal moderna para inserção, validação matemática e ativação da chave de licença (Ed25519).
Exibe o Identificador do Computador (Machine ID) para vinculação de hardware e proteção do software.
"""

import os
import sys
import json
import base64
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional
import customtkinter as ctk

import license_manager as lm
import clipboard_utils as clip
import edicao_config
import theme


class LicenseActivationModal(ctk.CTkToplevel):
    """Janela modal para ativação e renovação da licença comercial do sistema."""

    def __init__(self, parent, on_activated_callback: Callable, em_modo_bloqueio: bool = True, mensagem_inicial: str = ""):
        super().__init__(parent)
        self.parent = parent
        self.on_activated_callback = on_activated_callback
        self.em_modo_bloqueio = em_modo_bloqueio
        self.ativado = False

        self.title("🔐 Licença & Ativação - Central de Vendas")
        self.geometry("660x690")
        self.resizable(False, False)
        self.configure(fg_color=theme.MODAL_BG)

        self.transient(parent)
        self.grab_set()

        # Intercepta fechamento da janela
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        self.after(10, self._centralizar)
        self._criar_widgets(mensagem_inicial)

    def _centralizar(self):
        theme.centralizar_toplevel(self, 660, 690)

    def _criar_widgets(self, mensagem_inicial: str):
        card = ctk.CTkFrame(self, corner_radius=14, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        card.pack(fill="both", expand=True, padx=20, pady=16)

        # Cabeçalho
        head_row = ctk.CTkFrame(card, fg_color="transparent")
        head_row.pack(fill="x", padx=24, pady=(16, 8))

        badge_icon = ctk.CTkFrame(head_row, width=48, height=48, corner_radius=10, fg_color=theme.ACCENT_BLUE)
        badge_icon.pack_propagate(False)
        badge_icon.pack(side="left", padx=(0, 14))
        ctk.CTkLabel(badge_icon, text="🔐", font=ctk.CTkFont(size=22)).pack(expand=True)

        col_tit = ctk.CTkFrame(head_row, fg_color="transparent")
        col_tit.pack(side="left", fill="x", expand=True)

        ed_nome = edicao_config.obter_nome_edicao()
        ctk.CTkLabel(
            col_tit,
            text="Central de Vendas - Ativação Comercial",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            col_tit,
            text=f"Edição instalada: {ed_nome}",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        # Divisor
        ctk.CTkFrame(card, height=1, fg_color=theme.BORDER_COLOR).pack(fill="x", padx=20, pady=(6, 10))

        # Motivo de bloqueio se houver
        if mensagem_inicial:
            aviso_box = ctk.CTkFrame(card, fg_color=("#FEE2E2", "#450A0A"), corner_radius=8, border_width=1, border_color=theme.ACCENT_RED)
            aviso_box.pack(fill="x", padx=24, pady=(0, 10))
            ctk.CTkLabel(
                aviso_box,
                text=f"⚠️ {mensagem_inicial}",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=theme.ACCENT_RED,
                wraplength=540,
                justify="left",
            ).pack(padx=12, pady=8)

        # Card de Identificação da Máquina (Machine ID)
        card_mid = ctk.CTkFrame(card, fg_color=theme.INNER_CARD_BG, corner_radius=8, border_width=1, border_color=theme.BORDER_COLOR)
        card_mid.pack(fill="x", padx=24, pady=(0, 10))

        row_mid = ctk.CTkFrame(card_mid, fg_color="transparent")
        row_mid.pack(fill="x", padx=12, pady=8)

        col_mid_info = ctk.CTkFrame(row_mid, fg_color="transparent")
        col_mid_info.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            col_mid_info,
            text="💻 Identificador Único deste Computador (Machine ID):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        self.mid_atual = lm.obter_machine_id()
        ctk.CTkLabel(
            col_mid_info,
            text=self.mid_atual,
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            text_color=theme.PRICE_COLOR[1],
        ).pack(anchor="w", pady=(2, 0))

        btn_copiar_mid = ctk.CTkButton(
            row_mid,
            text="📋 Copiar ID",
            width=100,
            height=30,
            corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._copiar_mid,
        )
        btn_copiar_mid.pack(side="right", padx=(8, 0))

        # Campo de Inserção da Chave
        ctk.CTkLabel(
            card,
            text="Cole sua Chave de Ativação (Token Assinado):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=24, pady=(4, 4))

        self.txt_chave = ctk.CTkTextbox(
            card,
            height=110,
            corner_radius=8,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
            border_width=1,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="char",
        )
        self.txt_chave.pack(fill="x", padx=24, pady=(0, 6))

        # Habilita menu de contexto (botão direito) e atalhos Ctrl+V / Ctrl+A no campo
        clip.habilitar_menu_e_atalhos(self.txt_chave, callback_ao_colar=self._ao_colar_chave)

        # Barra de Ações Rápidas da Chave (Colar, Carregar Arquivo, Limpar)
        btn_colar_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_colar_frame.pack(fill="x", padx=24, pady=(0, 4))

        ctk.CTkLabel(
            btn_colar_frame,
            text="Inicia com 'LIC-'. Clique com botão direito ou use os botões ao lado:",
            font=ctk.CTkFont(size=10),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left")

        btn_limpar = ctk.CTkButton(
            btn_colar_frame,
            text="🧹 Limpar",
            width=70,
            height=28,
            corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._limpar_campo,
        )
        btn_limpar.pack(side="right", padx=(6, 0))

        btn_arquivo = ctk.CTkButton(
            btn_colar_frame,
            text="📁 Carregar de Arquivo",
            width=145,
            height=28,
            corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._carregar_de_arquivo,
        )
        btn_arquivo.pack(side="right", padx=(6, 0))

        btn_colar = ctk.CTkButton(
            btn_colar_frame,
            text="📋 Colar Chave",
            width=110,
            height=28,
            corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            text_color="#FFFFFF",
            command=self._colar_clipboard,
        )
        btn_colar.pack(side="right")

        # Botão Principal de Ativação
        self.btn_ativar = ctk.CTkButton(
            card,
            text="✔ ATIVAR SISTEMA AGORA",
            height=46,
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            command=self._processar_ativacao,
        )
        self.btn_ativar.pack(fill="x", padx=24, pady=(8, 10))

        # Banner de Feedback
        self.lbl_feedback = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.ACCENT_GREEN[1],
            wraplength=520,
        )
        self.lbl_feedback.pack(padx=24, pady=(0, 10))

        # Rodapé do Modal
        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=24, pady=(0, 14))

        ctk.CTkLabel(
            footer,
            text="Planos suportados: Mensal, Trimestral, Anual e Vitalícia.\nProteção de integridade por criptografia assimétrica de curva elíptica.",
            font=ctk.CTkFont(size=10),
            text_color=theme.TEXT_MUTED,
            justify="left",
        ).pack(side="left")

        if self.em_modo_bloqueio:
            btn_sair = ctk.CTkButton(
                footer,
                text="Sair do Software",
                width=110,
                height=32,
                corner_radius=6,
                fg_color=theme.ACCENT_RED,
                hover_color=theme.ACCENT_RED_HOVER,
                command=self._sair_aplicacao,
            )
            btn_sair.pack(side="right")
        else:
            btn_fechar = ctk.CTkButton(
                footer,
                text="Fechar",
                width=100,
                height=32,
                corner_radius=6,
                fg_color=theme.BTN_SECONDARY_BG,
                hover_color=theme.BTN_SECONDARY_HOVER,
                text_color=theme.BTN_SECONDARY_TEXT,
                command=self.destroy,
            )
            btn_fechar.pack(side="right")

    def _copiar_mid(self):
        clip.definir_texto_clipboard(self.mid_atual, self)
        self.lbl_feedback.configure(
            text="📋 ID da Máquina copiado com persistência! Envie este código para a emissão da chave.",
            text_color=theme.PRICE_COLOR[1],
        )

    def _ao_colar_chave(self, texto_inserido: str):
        """Callback executado ao colar texto via atalho (Ctrl+V) ou menu de contexto."""
        limpo = clip.sanitizar_chave(texto_inserido)
        if limpo.startswith("LIC-"):
            self.lbl_feedback.configure(
                text="📋 Chave inserida! Clique em 'ATIVAR SISTEMA AGORA'.",
                text_color=theme.PRICE_COLOR[1],
            )

    def _colar_clipboard(self):
        """Lê o texto da área de transferência do Windows e preenche o campo da chave."""
        texto = clip.obter_texto_clipboard(self)
        texto_limpo = clip.sanitizar_chave(texto)
        if texto_limpo:
            self.txt_chave.delete("1.0", "end")
            self.txt_chave.insert("1.0", texto_limpo)
            if texto_limpo.startswith("LIC-"):
                self.lbl_feedback.configure(
                    text="📋 Chave colada com sucesso! Clique em 'ATIVAR SISTEMA AGORA'.",
                    text_color=theme.PRICE_COLOR[1],
                )
            else:
                self.lbl_feedback.configure(
                    text="📋 Texto colado. Verifique se a chave inicia com 'LIC-'.",
                    text_color=theme.WARNING_COLOR[1],
                )
        else:
            self.lbl_feedback.configure(
                text="⚠️ Área de transferência vazia! Copie a chave no Gerador (Keygen) ou use 'Carregar de Arquivo'.",
                text_color=theme.WARNING_COLOR[1],
            )

    def _carregar_de_arquivo(self):
        """Permite selecionar um arquivo license.dat ou .txt gerado pelo Keygen."""
        from tkinter import filedialog
        caminho = filedialog.askopenfilename(
            parent=self,
            title="Selecionar Arquivo de Chave ou Licença",
            filetypes=[
                ("Arquivos de Licença / Texto", "*.dat;*.txt"),
                ("Arquivo de Licença (*.dat)", "*.dat"),
                ("Arquivo de Texto (*.txt)", "*.txt"),
                ("Todos os Arquivos", "*.*"),
            ],
        )
        if not caminho:
            return

        try:
            with open(caminho, "rb") as f:
                conteudo_bytes = f.read()

            token_extraido = ""
            # Tenta ler como license.dat (JSON ofuscado em Base64)
            try:
                dec = base64.b64decode(conteudo_bytes).decode("utf-8")
                dados = json.loads(dec)
                if isinstance(dados, dict) and "token" in dados:
                    token_extraido = dados["token"]
            except Exception:
                pass

            # Fallback para texto comum (.txt)
            if not token_extraido:
                try:
                    token_extraido = conteudo_bytes.decode("utf-8")
                except Exception:
                    token_extraido = conteudo_bytes.decode("latin1", errors="replace")

            token_limpo = clip.sanitizar_chave(token_extraido)
            if token_limpo:
                self.txt_chave.delete("1.0", "end")
                self.txt_chave.insert("1.0", token_limpo)
                nome_arq = os.path.basename(caminho)
                self.lbl_feedback.configure(
                    text=f"📁 Chave carregada de '{nome_arq}'! Clique em 'ATIVAR SISTEMA AGORA'.",
                    text_color=theme.PRICE_COLOR[1],
                )
            else:
                self.lbl_feedback.configure(
                    text="⚠️ O arquivo selecionado está vazio ou não contém uma chave legível.",
                    text_color=theme.ACCENT_RED[1],
                )
        except Exception as e:
            self.lbl_feedback.configure(
                text=f"Erro ao carregar arquivo: {str(e)}",
                text_color=theme.ACCENT_RED[1],
            )

    def _limpar_campo(self):
        """Limpa a caixa de texto da chave e reseta o feedback."""
        self.txt_chave.delete("1.0", "end")
        self.lbl_feedback.configure(text="")

    def _processar_ativacao(self):
        chave_bruta = self.txt_chave.get("1.0", "end")
        chave = clip.sanitizar_chave(chave_bruta)
        if not chave:
            self.lbl_feedback.configure(
                text="Por favor, cole, digite ou carregue a chave de ativação.",
                text_color=theme.ACCENT_RED[1],
            )
            return

        sucesso, msg = lm.ativar_licenca(chave)

        if sucesso:
            self.ativado = True
            self.lbl_feedback.configure(text=f"✔ {msg} Acessando o sistema...", text_color=theme.ACCENT_GREEN[1])
            self.btn_ativar.configure(state="disabled")
            self.after(700, self._concluir_ativacao)
        else:
            self.lbl_feedback.configure(text=f"Erro de ativação: {msg}", text_color=theme.ACCENT_RED[1])

    def _concluir_ativacao(self):
        self.destroy()
        if self.on_activated_callback:
            self.on_activated_callback()

    def _ao_fechar(self):
        if self.em_modo_bloqueio and not self.ativado:
            resp = messagebox.askyesno(
                "Sair do Sistema",
                "O sistema não pode ser iniciado sem uma licença ativa válida.\nDeseja realmente encerrar a aplicação?",
                parent=self,
            )
            if resp:
                self.parent.destroy()
                sys.exit(0)
        else:
            self.destroy()

    def _sair_aplicacao(self):
        self.parent.destroy()
        sys.exit(0)
