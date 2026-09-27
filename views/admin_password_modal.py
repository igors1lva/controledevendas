"""
Módulo de Interface: Modal de Gerenciamento de Senha do Administrador
Arquivo: views/admin_password_modal.py

Janela modal para definição, alteração e recuperação da senha mestra
do administrador, utilizada para proteção e bloqueio contra adulterações
nas planilhas de fechamento diário do sistema.
"""

from typing import Callable, Optional
import customtkinter as ctk

import database as db
import theme


class AdminPasswordModal(ctk.CTkToplevel):
    """Janela modal para cadastrar, alterar ou redefinir a senha do administrador."""

    def __init__(self, parent, on_success_callback: Optional[Callable] = None):
        super().__init__(parent)
        self.parent = parent
        self.on_success_callback = on_success_callback
        self.ja_existe_senha = db.existe_senha_admin()
        self.modo_recuperacao = False
        self.mostrar_senhas = False

        self.title("🔐 Senha do Administrador - Proteção de Fechamentos")
        self.geometry("560x540")
        self.resizable(False, False)
        self.configure(fg_color=theme.MODAL_BG)

        self.transient(parent)
        self.grab_set()

        self.after(10, self._centralizar)
        self._criar_widgets()

    def _centralizar(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 560) // 2
        y = (self.winfo_screenheight() - 540) // 2
        self.geometry(f"+{x}+{y}")

    def _criar_widgets(self):
        card = ctk.CTkFrame(self, corner_radius=14, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        card.pack(fill="both", expand=True, padx=20, pady=20)

        # Cabeçalho
        head_row = ctk.CTkFrame(card, fg_color="transparent")
        head_row.pack(fill="x", padx=22, pady=(16, 10))

        badge_icon = ctk.CTkFrame(head_row, width=44, height=44, corner_radius=10, fg_color=theme.ACCENT_BLUE)
        badge_icon.pack_propagate(False)
        badge_icon.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(badge_icon, text="🔒", font=ctk.CTkFont(size=20)).pack(expand=True)

        col_tit = ctk.CTkFrame(head_row, fg_color="transparent")
        col_tit.pack(side="left", fill="x", expand=True)

        titulo_texto = "Alterar Senha do Administrador" if self.ja_existe_senha else "Definir Senha do Administrador"
        self.lbl_head_tit = ctk.CTkLabel(
            col_tit,
            text=titulo_texto,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        self.lbl_head_tit.pack(anchor="w")

        ctk.CTkLabel(
            col_tit,
            text="Proteja seus relatórios diários de vendas contra alterações indevidas no Excel.",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(1, 0))

        # Divisor
        ctk.CTkFrame(card, height=1, fg_color=theme.BORDER_COLOR).pack(fill="x", padx=22, pady=(4, 12))

        # Área de formulário
        self.form_container = ctk.CTkFrame(card, fg_color="transparent")
        self.form_container.pack(fill="both", expand=True, padx=22)

        self._renderizar_campos()

    def _renderizar_campos(self):
        for w in self.form_container.winfo_children():
            w.destroy()

        if self.ja_existe_senha:
            # Alternador de modo (Senha Atual vs Recuperar por Chave de Licença)
            tab_frame = ctk.CTkFrame(self.form_container, fg_color=theme.INNER_CARD_BG, corner_radius=8)
            tab_frame.pack(fill="x", pady=(0, 12))

            btn_com_senha = ctk.CTkButton(
                tab_frame,
                text="Com Senha Atual",
                height=30,
                corner_radius=6,
                fg_color=theme.ACCENT_BLUE if not self.modo_recuperacao else "transparent",
                text_color=theme.TEXT_PRIMARY,
                hover_color=theme.ACCENT_BLUE_HOVER,
                command=lambda: self._alternar_modo(False),
            )
            btn_com_senha.pack(side="left", fill="x", expand=True, padx=3, pady=3)

            btn_com_licenca = ctk.CTkButton(
                tab_frame,
                text="🔑 Esqueci (Chave de Licença)",
                height=30,
                corner_radius=6,
                fg_color=theme.ACCENT_BLUE if self.modo_recuperacao else "transparent",
                text_color=theme.TEXT_PRIMARY,
                hover_color=theme.ACCENT_BLUE_HOVER,
                command=lambda: self._alternar_modo(True),
            )
            btn_com_licenca.pack(side="left", fill="x", expand=True, padx=3, pady=3)

            if not self.modo_recuperacao:
                # Campo: Senha Atual
                ctk.CTkLabel(
                    self.form_container,
                    text="Senha Atual do Administrador:",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=theme.TEXT_PRIMARY,
                ).pack(anchor="w", pady=(0, 3))

                self.entry_atual = ctk.CTkEntry(
                    self.form_container,
                    placeholder_text="Digite sua senha atual...",
                    height=36,
                    show="*" if not self.mostrar_senhas else "",
                    corner_radius=8,
                )
                self.entry_atual.pack(fill="x", pady=(0, 10))
            else:
                # Campo: Chave de Licença para Recuperação
                ctk.CTkLabel(
                    self.form_container,
                    text="Chave de Licença da Loja (LIC-...):",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=theme.TEXT_PRIMARY,
                ).pack(anchor="w", pady=(0, 3))

                self.entry_licenca = ctk.CTkEntry(
                    self.form_container,
                    placeholder_text="Cole sua chave de licença de ativação...",
                    height=36,
                    corner_radius=8,
                )
                self.entry_licenca.pack(fill="x", pady=(0, 10))
        else:
            # Banner informativo de primeira configuração
            info_banner = ctk.CTkFrame(
                self.form_container,
                fg_color=theme.INNER_CARD_BG,
                corner_radius=8,
                border_width=1,
                border_color=theme.ACCENT_BLUE,
            )
            info_banner.pack(fill="x", pady=(0, 12))
            ctk.CTkLabel(
                info_banner,
                text="ℹ️ Nenhuma senha personalizada foi definida ainda.\nAo definir sua senha, todas as novas planilhas de fechamento serão travadas com esta chave.",
                font=ctk.CTkFont(size=11),
                text_color=theme.TEXT_PRIMARY,
                justify="left",
            ).pack(padx=12, pady=10)

        # Campo: Nova Senha
        ctk.CTkLabel(
            self.form_container,
            text="Nova Senha do Administrador (mínimo 4 caracteres):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 3))

        self.entry_nova = ctk.CTkEntry(
            self.form_container,
            placeholder_text="Digite a nova senha...",
            height=36,
            show="*" if not self.mostrar_senhas else "",
            corner_radius=8,
        )
        self.entry_nova.pack(fill="x", pady=(0, 10))

        # Campo: Confirmar Nova Senha
        ctk.CTkLabel(
            self.form_container,
            text="Confirmar Nova Senha:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 3))

        self.entry_confirma = ctk.CTkEntry(
            self.form_container,
            placeholder_text="Repita a nova senha...",
            height=36,
            show="*" if not self.mostrar_senhas else "",
            corner_radius=8,
        )
        self.entry_confirma.pack(fill="x", pady=(0, 8))

        # Opção de mostrar/ocultar senha
        self.chk_mostrar = ctk.CTkCheckBox(
            self.form_container,
            text="Mostrar senhas digitadas",
            font=ctk.CTkFont(size=11),
            command=self._ao_alternar_mostrar_senha,
        )
        self.chk_mostrar.pack(anchor="w", pady=(0, 10))

        # Label de status / erro
        self.lbl_feedback = ctk.CTkLabel(
            self.form_container,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=theme.ACCENT_RED[1],
            wraplength=480,
            justify="center",
        )
        self.lbl_feedback.pack(fill="x", pady=(0, 10))

        # Rodapé com Botões de Ação
        btn_row = ctk.CTkFrame(self.form_container, fg_color="transparent")
        btn_row.pack(fill="x", side="bottom", pady=(0, 6))

        btn_cancelar = ctk.CTkButton(
            btn_row,
            text="Cancelar",
            width=110,
            height=38,
            corner_radius=8,
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self.destroy,
        )
        btn_cancelar.pack(side="left")

        btn_salvar = ctk.CTkButton(
            btn_row,
            text="💾 Salvar Senha do Administrador",
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            command=self._salvar_senha,
        )
        btn_salvar.pack(side="right", fill="x", expand=True, padx=(10, 0))

    def _alternar_modo(self, modo_recuperacao: bool):
        self.modo_recuperacao = modo_recuperacao
        self._renderizar_campos()

    def _ao_alternar_mostrar_senha(self):
        self.mostrar_senhas = bool(self.chk_mostrar.get())
        char_show = "" if self.mostrar_senhas else "*"
        if hasattr(self, "entry_atual"):
            self.entry_atual.configure(show=char_show)
        if hasattr(self, "entry_nova"):
            self.entry_nova.configure(show=char_show)
        if hasattr(self, "entry_confirma"):
            self.entry_confirma.configure(show=char_show)

    def _salvar_senha(self):
        nova = self.entry_nova.get().strip()
        confirma = self.entry_confirma.get().strip()

        if len(nova) < 4:
            self.lbl_feedback.configure(
                text="A nova senha deve ter no mínimo 4 caracteres.",
                text_color=theme.ACCENT_RED[1],
            )
            return

        if nova != confirma:
            self.lbl_feedback.configure(
                text="A confirmação de senha não confere com a nova senha digitada.",
                text_color=theme.ACCENT_RED[1],
            )
            return

        senha_atual = None
        token_rec = None

        if self.ja_existe_senha:
            if not self.modo_recuperacao:
                senha_atual = self.entry_atual.get().strip()
                if not senha_atual:
                    self.lbl_feedback.configure(
                        text="Por favor, informe sua senha atual para autorizar a troca.",
                        text_color=theme.ACCENT_RED[1],
                    )
                    return
            else:
                token_rec = self.entry_licenca.get().strip()
                if not token_rec:
                    self.lbl_feedback.configure(
                        text="Por favor, informe a chave de licença da loja para redefinir.",
                        text_color=theme.ACCENT_RED[1],
                    )
                    return

        sucesso, msg = db.definir_senha_admin(
            nova_senha=nova,
            senha_atual=senha_atual,
            token_recuperacao=token_rec,
        )

        if sucesso:
            self.lbl_feedback.configure(
                text=f"✔ {msg}",
                text_color=theme.STOCK_COLOR[1],
            )
            if self.on_success_callback:
                self.on_success_callback()
            self.after(1200, self.destroy)
        else:
            self.lbl_feedback.configure(
                text=msg,
                text_color=theme.ACCENT_RED[1],
            )
