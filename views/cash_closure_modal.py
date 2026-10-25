"""
Modal de Fechamento de Caixa e Encerramento de Turno (PDV)
Arquivo: views/cash_closure_modal.py

Exibe o balanço financeiro consolidado do caixa no momento (Faturamento,
Lucro Líquido, Contagem de Vendas, Desdobramento por Método de Pagamento)
e permite ao operador/gerente fechar o turno, disparando a geração automática
da planilha Excel criptografada com carimbo de data e hora exclusivos.
"""

import os
import subprocess
import tkinter as tk
from datetime import datetime
from typing import Optional, Callable
import customtkinter as ctk

import theme
import database as db
import reports


class CashClosureModal(ctk.CTkToplevel):
    """Janela modal para fechamento auditado do caixa do PDV."""

    def __init__(self, parent, on_fechamento_concluido: Optional[Callable] = None):
        super().__init__(parent)
        self.parent = parent
        self.on_fechamento_concluido = on_fechamento_concluido

        self.title("🔒 Fechamento de Caixa - Encerramento de Turno")
        self.geometry("640x700")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG_COLOR)

        # Modalidade exclusiva
        self.transient(parent)
        self.grab_set()

        # Centraliza a janela perfeitamente na tela
        theme.centralizar_toplevel(self, 640, 680)

        self._criar_layout()

    def _criar_layout(self):
        # 1. Container Principal
        card = ctk.CTkFrame(self, corner_radius=14, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        card.pack(fill="both", expand=True, padx=20, pady=20)

        # 2. Cabeçalho
        head_frame = ctk.CTkFrame(card, fg_color="transparent")
        head_frame.pack(fill="x", padx=24, pady=(20, 10))

        ctk.CTkLabel(
            head_frame,
            text="🔒 Fechamento de Caixa (Encerramento de Turno)",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        agora_txt = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
        ctk.CTkLabel(
            head_frame,
            text=f"Data/Hora do Fechamento: {agora_txt} | Balcão PDV",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkFrame(card, height=1, fg_color=theme.BORDER_COLOR).pack(fill="x", padx=20, pady=(6, 12))

        # 3. Consulta métricas do caixa no banco
        self.dados_caixa = db.obter_resumo_caixa_detalhado()
        fat = self.dados_caixa["total_faturamento"]
        custo = self.dados_caixa["total_custo"]
        lucro = self.dados_caixa["total_lucro"]
        margem = self.dados_caixa["margem_lucro"]
        n_vendas = self.dados_caixa["total_vendas"]
        n_itens = self.dados_caixa["total_itens"]
        ticket = self.dados_caixa["ticket_medio"]
        formas = self.dados_caixa["formas_pagamento"]

        # 4. Grid de Indicadores Principais (KPIs)
        grid_kpis = ctk.CTkFrame(card, fg_color="transparent")
        grid_kpis.pack(fill="x", padx=20, pady=(0, 10))
        grid_kpis.grid_columnconfigure((0, 1, 2), weight=1)

        # KPI Faturamento
        card_fat = ctk.CTkFrame(grid_kpis, fg_color=theme.INNER_CARD_BG, corner_radius=10, border_width=1, border_color=theme.BORDER_COLOR)
        card_fat.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ctk.CTkLabel(card_fat, text="FATURAMENTO", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(pady=(8, 2))
        ctk.CTkLabel(card_fat, text=reports.formatar_moeda(fat), font=ctk.CTkFont(size=15, weight="bold"), text_color=theme.PRICE_COLOR).pack(pady=(0, 8))

        # KPI Lucro Real
        card_lucro = ctk.CTkFrame(grid_kpis, fg_color=theme.INNER_CARD_BG, corner_radius=10, border_width=1, border_color=theme.BORDER_COLOR)
        card_lucro.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ctk.CTkLabel(card_lucro, text="LUCRO REAL", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(pady=(8, 2))
        ctk.CTkLabel(card_lucro, text=f"{reports.formatar_moeda(lucro)} ({margem}%)", font=ctk.CTkFont(size=14, weight="bold"), text_color=theme.STOCK_COLOR[1]).pack(pady=(0, 8))

        # KPI Vendas / Ticket
        card_vendas = ctk.CTkFrame(grid_kpis, fg_color=theme.INNER_CARD_BG, corner_radius=10, border_width=1, border_color=theme.BORDER_COLOR)
        card_vendas.grid(row=0, column=2, sticky="ew", padx=4, pady=4)
        ctk.CTkLabel(card_vendas, text="VENDAS / TICKET", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(pady=(8, 2))
        ctk.CTkLabel(card_vendas, text=f"{n_vendas}x | {reports.formatar_moeda(ticket)}", font=ctk.CTkFont(size=13, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(pady=(0, 8))

        # 5. Desdobramento por Forma de Pagamento
        card_formas = ctk.CTkFrame(card, fg_color=theme.INNER_CARD_BG, corner_radius=10, border_width=1, border_color=theme.BORDER_COLOR)
        card_formas.pack(fill="x", padx=24, pady=(6, 12))

        ctk.CTkLabel(
            card_formas,
            text="💳 Apuração por Método de Pagamento:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=16, pady=(10, 6))

        itens_pgto = [
            ("💵 Dinheiro", formas.get("DINHEIRO", 0.0), "#10B981"),
            ("📱 Pix", formas.get("PIX", 0.0), "#06B6D4"),
            ("💳 Cartão de Débito", formas.get("CARTAO_DEBITO", 0.0), "#3B82F6"),
            ("💳 Cartão de Crédito", formas.get("CARTAO_CREDITO", 0.0), "#8B5CF6"),
            ("🎫 Vales / Outros", formas.get("VALE_ALIMENTACAO", 0.0) + formas.get("OUTROS", 0.0), "#F59E0B"),
        ]

        for rotulo, val, cor in itens_pgto:
            row_p = ctk.CTkFrame(card_formas, fg_color="transparent")
            row_p.pack(fill="x", padx=16, pady=2)
            pct = round((val / fat * 100), 1) if fat > 0 else 0.0
            ctk.CTkLabel(row_p, text=f"{rotulo}:", font=ctk.CTkFont(size=11), text_color=theme.TEXT_SECONDARY).pack(side="left")
            ctk.CTkLabel(row_p, text=f"{reports.formatar_moeda(val)} ({pct}%)", font=ctk.CTkFont(size=11, weight="bold"), text_color=cor).pack(side="right")

        ctk.CTkLabel(card_formas, text="", height=4).pack()

        # 6. Aviso Informativo sobre o Relatório Criptografado
        box_aviso = ctk.CTkFrame(card, fg_color="#1E293B", corner_radius=8, border_width=1, border_color="#334155")
        box_aviso.pack(fill="x", padx=24, pady=(0, 14))

        ctk.CTkLabel(
            box_aviso,
            text="📊 Cada fechamento gera uma nova planilha protegida em Excel (.xlsx)\n"
                 "com data e horário exatos, garantindo auditoria completa\n"
                 "mesmo em caso de múltiplos fechamentos diários.",
            font=ctk.CTkFont(size=11),
            text_color="#94A3B8",
            justify="center",
            wraplength=500,
        ).pack(padx=12, pady=10)

        # Container para feedback pós-fechamento
        self.box_resultado = ctk.CTkFrame(card, fg_color="transparent")
        self.box_resultado.pack(fill="x", padx=24, pady=(0, 10))

        # 7. Botões de Ação
        self.actions_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.actions_frame.pack(fill="x", side="bottom", padx=24, pady=(0, 20))

        self.btn_cancelar = ctk.CTkButton(
            self.actions_frame,
            text="Voltar ao PDV",
            width=130,
            height=42,
            corner_radius=8,
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self.destroy,
        )
        self.btn_cancelar.pack(side="left")

        self.btn_confirmar = ctk.CTkButton(
            self.actions_frame,
            text="✔ CONFIRMAR FECHAMENTO E GERAR EXCEL",
            height=42,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#D97706",
            hover_color="#B45309",
            command=self._confirmar_fechamento,
        )
        self.btn_confirmar.pack(side="right", fill="x", expand=True, padx=(12, 0))

    def _confirmar_fechamento(self):
        """Gera o relatório Excel protegido e grava o fechamento atômico."""
        self.btn_confirmar.configure(state="disabled", text="⏳ Gerando Relatório Criptografado...")
        self.btn_cancelar.configure(state="disabled")
        self.update_idletasks()

        sucesso, msg, caminho_arquivo = reports.gerar_relatorio_diario_excel(eh_fechamento_caixa=True)

        # Limpa botões de ação e exibe resultado
        for w in self.actions_frame.winfo_children():
            w.destroy()

        if sucesso:
            nome_arq = os.path.basename(caminho_arquivo)
            lbl_suc = ctk.CTkLabel(
                self.box_resultado,
                text=f"✔ Caixa fechado com sucesso!\nPlanilha diária atualizada: {nome_arq}",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=theme.STOCK_COLOR[1],
                justify="center",
            )
            lbl_suc.pack(pady=(0, 8))

            # Botão para abrir a planilha
            btn_abrir = ctk.CTkButton(
                self.actions_frame,
                text="📊 Abrir no Excel",
                height=40,
                corner_radius=8,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=theme.ACCENT_GREEN,
                hover_color=theme.ACCENT_GREEN_HOVER,
                command=lambda: self._abrir_arquivo(caminho_arquivo),
            )
            btn_abrir.pack(side="left", fill="x", expand=True, padx=(0, 6))

            # Botão para abrir a pasta
            btn_pasta = ctk.CTkButton(
                self.actions_frame,
                text="📂 Abrir Pasta",
                height=40,
                corner_radius=8,
                fg_color=theme.BTN_SECONDARY_BG,
                hover_color=theme.BTN_SECONDARY_HOVER,
                text_color=theme.BTN_SECONDARY_TEXT,
                command=lambda: self._abrir_pasta(caminho_arquivo),
            )
            btn_pasta.pack(side="left", padx=6)

            # Botão Concluir
            btn_fechar = ctk.CTkButton(
                self.actions_frame,
                text="Concluir",
                width=110,
                height=40,
                corner_radius=8,
                fg_color=theme.ACCENT_BLUE,
                hover_color=theme.ACCENT_BLUE_HOVER,
                command=self._ao_finalizar,
            )
            btn_fechar.pack(side="right", padx=(6, 0))

        else:
            lbl_err = ctk.CTkLabel(
                self.box_resultado,
                text=f"❌ {msg}",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=theme.ACCENT_RED[1],
                wraplength=520,
            )
            lbl_err.pack(pady=(0, 8))

            btn_fechar = ctk.CTkButton(
                self.actions_frame,
                text="Fechar",
                height=40,
                corner_radius=8,
                fg_color=theme.BTN_SECONDARY_BG,
                hover_color=theme.BTN_SECONDARY_HOVER,
                text_color=theme.BTN_SECONDARY_TEXT,
                command=self.destroy,
            )
            btn_fechar.pack(fill="x")

    def _abrir_arquivo(self, caminho: str):
        sucesso, msg = reports.abrir_arquivo_planilha(caminho)
        if not sucesso:
            try:
                lbl_aviso = ctk.CTkLabel(
                    self.box_resultado,
                    text=f"⚠️ {msg}",
                    font=ctk.CTkFont(size=11),
                    text_color=theme.WARNING_COLOR[1],
                    wraplength=480,
                )
                lbl_aviso.pack(pady=(4, 0))
            except Exception:
                pass

    def _abrir_pasta(self, caminho: str):
        try:
            if caminho and os.path.exists(caminho):
                subprocess.Popen(f'explorer /select,"{os.path.abspath(caminho)}"')
            else:
                pasta = os.path.dirname(os.path.abspath(caminho)) if caminho else db.get_base_dir()
                os.startfile(pasta)
        except Exception:
            try:
                pasta = db.get_base_dir()
                os.startfile(pasta)
            except Exception:
                pass

    def _ao_finalizar(self):
        if self.on_fechamento_concluido:
            try:
                self.on_fechamento_concluido()
            except Exception:
                pass
        self.destroy()
