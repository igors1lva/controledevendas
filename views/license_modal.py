"""
Módulo de Interface: Modal de Ativação de Licença
Arquivo: views/license_modal.py

Janela modal moderna para inserção, validação e ativação da chave de licença (Ed25519).
"""

import sys
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional
import customtkinter as ctk

import license_manager as lm
import theme


class LicenseActivationModal(ctk.CTkToplevel):
    """Janela modal para ativação e renovação da licença do sistema."""

    def __init__(self, parent, on_activated_callback: Callable, em_modo_bloqueio: bool = True, mensagem_inicial: str = ""):
        super().__init__(parent)
        self.parent = parent
        self.on_activated_callback = on_activated_callback
        self.em_modo_bloqueio = em_modo_bloqueio
        self.ativado = False

        self.title("🔐 Licença & Conformidade - Central de Vendas")
        self.geometry("640x670")
        self.resizable(False, False)
        self.configure(fg_color=theme.MODAL_BG)

        self.transient(parent)
        self.grab_set()

        # Intercepta fechamento da janela
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        # Centraliza
        self.after(10, self._centralizar)

        self._criar_widgets(mensagem_inicial)

    def _centralizar(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 640) // 2
        y = (self.winfo_screenheight() - 670) // 2
        self.geometry(f"+{x}+{y}")

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

        ctk.CTkLabel(
            col_tit,
            text="Central de Vendas - Ativação de Licença",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            col_tit,
            text="Insira a chave criptográfica fornecida pelo administrador para liberar o uso.",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        # Divisor
        ctk.CTkFrame(card, height=1, fg_color=theme.BORDER_COLOR).pack(fill="x", padx=20, pady=(6, 10))

        # Aviso / Motivo de bloqueio se houver
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

        # Aviso Legal e Informativo: Módulo Não-Fiscal / Controle Interno
        aviso_legal_card = ctk.CTkFrame(card, fg_color=theme.INNER_CARD_BG, corner_radius=8, border_width=1, border_color=theme.BORDER_COLOR)
        aviso_legal_card.pack(fill="x", padx=24, pady=(0, 10))

        ctk.CTkLabel(
            aviso_legal_card,
            text="⚖️ Módulo de Controle Interno e Gestão Operacional (Não-Fiscal)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=12, pady=(6, 2))

        ctk.CTkLabel(
            aviso_legal_card,
            text=(
                "Esta aplicação destina-se exclusivamente à gestão operacional de estoque, precificação "
                "e controle interno de vendas. Não substitui emissores fiscais regulamentados (NFC-e / SAT / ECF) "
                "perante a SEFAZ. O cumprimento das obrigações fiscais é responsabilidade da empresa contratante."
            ),
            font=ctk.CTkFont(size=10),
            text_color=theme.TEXT_SECONDARY,
            wraplength=540,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 6))

        # Campo de Inserção da Chave
        ctk.CTkLabel(
            card,
            text="Cole sua Chave de Ativação (Token):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=24, pady=(2, 4))

        self.txt_chave = ctk.CTkTextbox(
            card,
            height=100,
            corner_radius=8,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
            border_width=1,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="char",
        )
        self.txt_chave.pack(fill="x", padx=24, pady=(0, 8))

        # Botão Colar do Clipboard
        btn_colar_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_colar_frame.pack(fill="x", padx=24, pady=(0, 14))

        ctk.CTkLabel(
            btn_colar_frame,
            text="A chave começa com 'LIC-' e contém assinatura digital Ed25519.",
            font=ctk.CTkFont(size=10),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left")

        ctk.CTkButton(
            btn_colar_frame,
            text="📋 Colar da Área de Transferência",
            width=210,
            height=28,
            corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._colar_clipboard,
        ).pack(side="right")

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
        self.btn_ativar.pack(fill="x", padx=24, pady=(4, 10))

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
            text="Planos suportados: 30, 60, 90 dias e Vitalícia.\nChaves geradas via keygen.py com criptografia assimétrica.",
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

    def _colar_clipboard(self):
        try:
            texto = self.clipboard_get().strip()
            if texto:
                self.txt_chave.delete("1.0", "end")
                self.txt_chave.insert("1.0", texto)
        except Exception:
            pass

    def _processar_ativacao(self):
        chave = self.txt_chave.get("1.0", "end").strip()
        if not chave:
            self.lbl_feedback.configure(text="Por favor, cole ou digite a chave de ativação.", text_color=theme.ACCENT_RED[1])
            return

        sucesso, msg = lm.ativar_licenca(chave)

        if sucesso:
            self.ativado = True
            self.lbl_feedback.configure(text=f"✔ {msg} Acessando o sistema...", text_color=theme.ACCENT_GREEN[1])
            self.btn_ativar.configure(state="disabled")
            self.after(800, self._concluir_ativacao)
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
