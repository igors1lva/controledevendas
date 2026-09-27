"""
views/admin_auth_modal.py
Modal de Autorização de Administrador.

Exige a senha do administrador cadastrada no painel OU a senha padrão 'Central@2026'
para autorizar operações críticas, como a alternância entre os regimes
Fiscal (NFC-e SEFAZ) e Não-Fiscal (Controle Interno).
"""

from typing import Callable, Optional
import tkinter as tk
import customtkinter as ctk

import database as db
import theme


class AdminAuthModal(ctk.CTkToplevel):
    """Modal para autenticação de administrador com senha do painel ou senha padrão."""

    def __init__(
        self,
        parent,
        titulo: str = "🔐 Confirmação de Administrador",
        motivo: str = "Confirme a senha para autorizar a alteração de regime operacional:",
        on_confirm_callback: Optional[Callable[[], None]] = None,
        on_cancel_callback: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.on_confirm_callback = on_confirm_callback
        self.on_cancel_callback = on_cancel_callback
        self.confirmado = False
        self.mostrar_senha = False

        self.title(titulo)
        self.geometry("520x330")
        self.resizable(False, False)
        self.configure(fg_color=theme.MODAL_BG)

        # Configura comportamento modal exclusivo
        self.transient(parent)
        self.grab_set()

        self._centralizar()
        self._criar_widgets(titulo, motivo)

        # Atalhos de teclado
        self.bind("<Return>", lambda e: self._confirmar())
        self.bind("<Escape>", lambda e: self._cancelar())
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

        # Foco imediato no campo de senha
        self.after(100, lambda: self.entry_senha.focus_set())

    def _centralizar(self):
        self.update_idletasks()
        w = 520
        h = 330
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _criar_widgets(self, titulo: str, motivo: str):
        card = ctk.CTkFrame(
            self,
            corner_radius=14,
            fg_color=theme.CARD_BG,
            border_width=1,
            border_color=theme.BORDER_COLOR,
        )
        card.pack(fill="both", expand=True, padx=16, pady=16)

        # Cabeçalho com Ícone de Segurança
        head_row = ctk.CTkFrame(card, fg_color="transparent")
        head_row.pack(fill="x", padx=20, pady=(16, 8))

        badge = ctk.CTkFrame(head_row, width=42, height=42, corner_radius=10, fg_color=theme.ACCENT_BLUE)
        badge.pack_propagate(False)
        badge.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(badge, text="🔒", font=ctk.CTkFont(size=20)).pack(expand=True)

        col_tit = ctk.CTkFrame(head_row, fg_color="transparent")
        col_tit.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            col_tit,
            text=titulo,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            col_tit,
            text="Autenticação de segurança para controle de emissão fiscal.",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(1, 0))

        # Divisor
        ctk.CTkFrame(card, height=1, fg_color=theme.BORDER_COLOR).pack(fill="x", padx=20, pady=(6, 12))

        # Mensagem / Motivo
        ctk.CTkLabel(
            card,
            text=motivo,
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_PRIMARY,
            wraplength=460,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 10))

        # Campo de Senha com Botão de Exibir/Ocultar
        box_senha = ctk.CTkFrame(card, fg_color="transparent")
        box_senha.pack(fill="x", padx=20, pady=(0, 6))

        self.entry_senha = ctk.CTkEntry(
            box_senha,
            height=38,
            placeholder_text="Digite a senha do administrador ou Central@2026...",
            font=ctk.CTkFont(size=13),
            show="*",
        )
        self.entry_senha.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_olho = ctk.CTkButton(
            box_senha,
            text="👁️ Exibir",
            width=85,
            height=38,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._toggle_senha,
        )
        self.btn_olho.pack(side="right")

        # Rótulo de Erro / Feedback
        self.lbl_status = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.ACCENT_RED[1],
        )
        self.lbl_status.pack(anchor="w", padx=20, pady=(2, 6))

        # Botões de Ação
        botoes_row = ctk.CTkFrame(card, fg_color="transparent")
        botoes_row.pack(fill="x", padx=20, pady=(6, 14), side="bottom")

        btn_cancelar = ctk.CTkButton(
            botoes_row,
            text="Cancelar (Esc)",
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(size=12),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._cancelar,
        )
        btn_cancelar.pack(side="left", padx=(0, 8), fill="x", expand=True)

        btn_confirmar = ctk.CTkButton(
            botoes_row,
            text="Confirmar (Enter)",
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            command=self._confirmar,
        )
        btn_confirmar.pack(side="right", padx=(8, 0), fill="x", expand=True)

    def _toggle_senha(self):
        self.mostrar_senha = not self.mostrar_senha
        if self.mostrar_senha:
            self.entry_senha.configure(show="")
            self.btn_olho.configure(text="🔒 Ocultar")
        else:
            self.entry_senha.configure(show="*")
            self.btn_olho.configure(text="👁️ Exibir")

    def _confirmar(self):
        digitada = self.entry_senha.get().strip()
        if not digitada:
            self.lbl_status.configure(text="⚠️ Por favor, digite a senha de administrador.")
            return

        # Validação contra a senha mestra padrão ou a senha configurada no painel
        if db.validar_senha_admin_ou_padrao(digitada):
            self.confirmado = True
            self.destroy()
            if self.on_confirm_callback:
                self.on_confirm_callback()
        else:
            self.lbl_status.configure(
                text="❌ Senha incorreta! Digite a senha cadastrada ou a padrão Central@2026."
            )
            self.entry_senha.delete(0, tk.END)
            self.entry_senha.focus_set()

    def _cancelar(self):
        self.destroy()
        if not self.confirmado and self.on_cancel_callback:
            self.on_cancel_callback()
