"""
Módulo de Interface: Modal de Gerenciamento de Cópia de Segurança e Backups
Arquivo: views/backup_modal.py

Interface visual moderna para:
1. Criação imediata de cópias de segurança (backup manual com escolha de pasta ou pendrive).
2. Monitoramento do status da rotina de backup automático diário.
3. Restauração segura de backups anteriores com confirmação de senha administrativa.
4. Acesso rápido à pasta de backups.
"""

import os
import subprocess
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional, Callable
import customtkinter as ctk

import database as db
import backup_manager as bm
import theme
from views.admin_auth_modal import AdminAuthModal


class BackupModal(ctk.CTkToplevel):
    """Modal para criação, visualização e restauração de cópias de segurança do sistema."""

    def __init__(self, parent, on_restored_callback: Optional[Callable] = None):
        super().__init__(parent)
        self.parent = parent
        self.on_restored_callback = on_restored_callback

        self.title("🛡️ Cópias de Segurança & Backups - Proteção de Dados")
        self.geometry("680x560")
        self.resizable(False, False)
        self.configure(fg_color=theme.MODAL_BG)

        self.transient(parent)
        self.grab_set()

        self.after(10, self._centralizar)
        self._criar_layout()
        self._atualizar_lista_backups()

    def _centralizar(self):
        theme.centralizar_toplevel(self, 680, 560)

    def _criar_layout(self):
        card = ctk.CTkFrame(self, corner_radius=14, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        card.pack(fill="both", expand=True, padx=20, pady=20)

        # 1. Cabeçalho
        head_row = ctk.CTkFrame(card, fg_color="transparent")
        head_row.pack(fill="x", padx=22, pady=(16, 10))

        badge = ctk.CTkFrame(head_row, width=44, height=44, corner_radius=10, fg_color=theme.ACCENT_BLUE)
        badge.pack_propagate(False)
        badge.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(badge, text="🛡️", font=ctk.CTkFont(size=20)).pack(expand=True)

        col_tit = ctk.CTkFrame(head_row, fg_color="transparent")
        col_tit.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            col_tit,
            text="Central de Cópias de Segurança (Backup)",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            col_tit,
            text="Garante a proteção total dos seus produtos, histórico de vendas e fechamentos.",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w")

        ctk.CTkFrame(card, height=1, fg_color=theme.BORDER_COLOR).pack(fill="x", padx=20, pady=(4, 12))

        # 2. Card de Status do Backup Automático
        card_status = ctk.CTkFrame(card, fg_color=theme.INNER_CARD_BG, corner_radius=10, border_width=1, border_color=theme.BORDER_COLOR)
        card_status.pack(fill="x", padx=22, pady=(0, 12))

        row_status = ctk.CTkFrame(card_status, fg_color="transparent")
        row_status.pack(fill="x", padx=16, pady=12)

        col_st_txt = ctk.CTkFrame(row_status, fg_color="transparent")
        col_st_txt.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            col_st_txt,
            text="Rotina de Backup Automático Diário:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        ult_data = db.obter_config("ultimo_backup_automatico_data", "Nenhum backup registrado hoje")
        self.lbl_ult_backup = ctk.CTkLabel(
            col_st_txt,
            text=f"Último backup automático: {ult_data}",
            font=ctk.CTkFont(size=11),
            text_color=theme.STOCK_COLOR[1] if "Nenhum" not in ult_data else theme.WARNING_COLOR[1],
        )
        self.lbl_ult_backup.pack(anchor="w", pady=(2, 0))

        # 3. Botões de Ação Principal
        row_botoes = ctk.CTkFrame(card, fg_color="transparent")
        row_botoes.pack(fill="x", padx=22, pady=(0, 14))

        self.btn_criar_agora = ctk.CTkButton(
            row_botoes,
            text="💾 Fazer Backup Agora",
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            command=self._criar_backup_agora,
        )
        self.btn_criar_agora.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_exportar_pendrive = ctk.CTkButton(
            row_botoes,
            text="📂 Exportar para Pendrive / Pasta...",
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._exportar_para_pasta,
        )
        self.btn_exportar_pendrive.pack(side="left", fill="x", expand=True, padx=(6, 6))

        self.btn_restaurar = ctk.CTkButton(
            row_botoes,
            text="🔄 Restaurar Backup...",
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=theme.PRICE_COLOR[1],
            hover_color="#0284C7",
            command=self._iniciar_restauracao,
        )
        self.btn_restaurar.pack(side="left", fill="x", expand=True, padx=(6, 0))

        # 4. Histórico de Backups Disponíveis
        ctk.CTkLabel(
            card,
            text="Backups Disponíveis na Pasta Local:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=22, pady=(0, 6))

        self.scroll_backups = ctk.CTkScrollableFrame(card, height=180, fg_color=theme.INNER_CARD_BG, corner_radius=8)
        self.scroll_backups.pack(fill="both", expand=True, padx=22, pady=(0, 12))

        # 5. Rodapé
        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.pack(fill="x", padx=22, pady=(0, 10))

        ctk.CTkButton(
            footer,
            text="📁 Abrir Pasta de Backups",
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._abrir_pasta_backups,
        ).pack(side="left")

        ctk.CTkButton(
            footer,
            text="Fechar",
            width=100,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self.destroy,
        ).pack(side="right")

    def _atualizar_lista_backups(self):
        for widget in self.scroll_backups.winfo_children():
            widget.destroy()

        backups = bm.listar_backups_locais()
        if not backups:
            lbl_vazio = ctk.CTkLabel(
                self.scroll_backups,
                text="Nenhum arquivo de backup encontrado ainda.\nClique em 'Fazer Backup Agora' para criar o primeiro.",
                font=ctk.CTkFont(size=11),
                text_color=theme.TEXT_MUTED,
            )
            lbl_vazio.pack(pady=30)
        else:
            for bkp in backups:
                item_frame = ctk.CTkFrame(self.scroll_backups, fg_color=theme.CARD_BG, corner_radius=6)
                item_frame.pack(fill="x", padx=4, pady=3)

                col_esq = ctk.CTkFrame(item_frame, fg_color="transparent")
                col_esq.pack(side="left", padx=10, pady=8)

                nome_curto = bkp["arquivo"]
                ctk.CTkLabel(
                    col_esq,
                    text=f"📦 {nome_curto}",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=theme.TEXT_PRIMARY,
                ).pack(anchor="w")

                ctk.CTkLabel(
                    col_esq,
                    text=f"{bkp['tipo']} • {bkp['data_hora']} • {bkp['tamanho_mb']} MB",
                    font=ctk.CTkFont(size=10),
                    text_color=theme.TEXT_SECONDARY,
                ).pack(anchor="w")

        self.update_idletasks()
        try:
            self.scroll_backups._parent_canvas.yview_moveto(0.0)
        except Exception:
            pass

    def _criar_backup_agora(self):
        sucesso, msg, caminho = bm.criar_backup(prefixo="backup_manual")
        if sucesso:
            agora_str = datetime.now().strftime("%d/%m/%Y %H:%M")
            db.salvar_config("ultimo_backup_automatico_data", agora_str)
            self.lbl_ult_backup.configure(
                text=f"Último backup: {agora_str} (Manual)",
                text_color=theme.STOCK_COLOR[1],
            )
            self._atualizar_lista_backups()
            self.update_idletasks()
            self.update()
            messagebox.showinfo("Sucesso", f"Backup gerado com sucesso!\n\nSalvo em:\n{caminho}", parent=self)
            self._atualizar_lista_backups()
        else:
            messagebox.showerror("Erro", f"Não foi possível criar o backup:\n\n{msg}", parent=self)

    def _exportar_para_pasta(self):
        pasta = filedialog.askdirectory(title="Selecione o Pendrive ou Pasta para salvar a cópia de segurança", parent=self)
        if not pasta:
            return

        sucesso, msg, caminho = bm.criar_backup(destino_dir=pasta, prefixo="backup_externo")
        if sucesso:
            self._atualizar_lista_backups()
            messagebox.showinfo("Sucesso", f"Cópia de segurança exportada com sucesso!\n\nDestino:\n{caminho}", parent=self)
            self._atualizar_lista_backups()
        else:
            messagebox.showerror("Erro", f"Falha ao exportar backup:\n\n{msg}", parent=self)

    def _iniciar_restauracao(self):
        caminho_zip = filedialog.askopenfilename(
            title="Selecione o arquivo ZIP de Backup para restaurar",
            filetypes=[("Arquivo de Backup ZIP", "*.zip")],
            parent=self,
        )
        if not caminho_zip:
            return

        def _executar_restauro():
            sucesso, msg = bm.restaurar_backup(caminho_zip)
            if sucesso:
                messagebox.showinfo("Restauração Concluída", f"{msg}\n\nA tela será atualizada.", parent=self)
                self._atualizar_lista_backups()
                if self.on_restored_callback:
                    self.on_restored_callback()
            else:
                messagebox.showerror("Erro na Restauração", f"Falha ao restaurar banco:\n\n{msg}", parent=self)

        AdminAuthModal(
            parent=self,
            titulo="🔐 Autorização para Restauração de Dados",
            motivo="Atenção: A restauração substituirá os dados atuais pelo conteúdo do backup.\nConfirme a senha do administrador para prosseguir:",
            on_confirm_callback=_executar_restauro,
        )

    def _abrir_pasta_backups(self):
        pasta = bm._garantir_diretorio_backups()
        try:
            if sys.platform.startswith("win"):
                os.startfile(pasta)
            else:
                subprocess.Popen(["xdg-open", pasta])
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível abrir a pasta:\n{str(e)}", parent=self)
