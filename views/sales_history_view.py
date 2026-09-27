"""
Módulo de Visualização: Histórico de Vendas de Hoje
Arquivo: views/sales_history_view.py

Tela dedicada exclusivamente à consulta detalhada de todas as vendas
realizadas na data atual, com filtros, métricas de faturamento e listagem completa.
"""

from typing import Optional, Callable
from tkinter import messagebox
import customtkinter as ctk

import database as db
import theme


def formatar_moeda(valor: float) -> str:
    """Formata valor numérico para padrão monetário brasileiro R$ 0,00."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class SalesHistoryView(ctk.CTkFrame):
    """Tela dedicada à exibição e análise do histórico de vendas do dia."""

    def __init__(
        self,
        parent,
        on_goto_nova_venda: Optional[Callable] = None,
        on_venda_cancelada: Optional[Callable] = None,
    ):
        super().__init__(parent, fg_color="transparent")
        self.on_goto_nova_venda = on_goto_nova_venda
        self.on_venda_cancelada = on_venda_cancelada

        self._criar_layout()
        self.recarregar_dados()

    def _criar_layout(self):
        # 1. Cabeçalho
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(16, 12))

        col_tit = ctk.CTkFrame(header_frame, fg_color="transparent")
        col_tit.pack(side="left")

        lbl_titulo = ctk.CTkLabel(
            col_tit,
            text="🕒 Histórico Detalhado de Vendas de Hoje",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        lbl_titulo.pack(anchor="w")

        lbl_subtitulo = ctk.CTkLabel(
            col_tit,
            text="Acompanhe todas as transações finalizadas no caixa na data de hoje em ordem cronológica.",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        )
        lbl_subtitulo.pack(anchor="w")

        if self.on_goto_nova_venda:
            btn_vender = ctk.CTkButton(
                header_frame,
                text="⚡ Realizar Nova Venda",
                font=ctk.CTkFont(size=12, weight="bold"),
                height=38,
                corner_radius=8,
                fg_color=theme.ACCENT_GREEN,
                hover_color=theme.ACCENT_GREEN_HOVER,
                command=self.on_goto_nova_venda,
            )
            btn_vender.pack(side="right")

        # 2. Grid de Cards com Indicadores Rápidos do Dia
        kpi_grid = ctk.CTkFrame(self, fg_color="transparent")
        kpi_grid.pack(fill="x", padx=24, pady=(0, 14))

        # Card 1: Faturamento Hoje
        c1 = ctk.CTkFrame(kpi_grid, corner_radius=10, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        c1.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ctk.CTkLabel(c1, text="FATURAMENTO DO DIA", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(pady=(10, 2))
        self.lbl_faturamento = ctk.CTkLabel(c1, text="R$ 0,00", font=ctk.CTkFont(size=18, weight="bold"), text_color=theme.STOCK_COLOR)
        self.lbl_faturamento.pack(pady=(0, 10))

        # Card 2: Peças Vendidas
        c2 = ctk.CTkFrame(kpi_grid, corner_radius=10, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        c2.pack(side="left", fill="both", expand=True, padx=4)
        ctk.CTkLabel(c2, text="ITENS VENDIDOS", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(pady=(10, 2))
        self.lbl_itens = ctk.CTkLabel(c2, text="0 un", font=ctk.CTkFont(size=18, weight="bold"), text_color=theme.PRICE_COLOR)
        self.lbl_itens.pack(pady=(0, 10))

        # Card 3: Transações
        c3 = ctk.CTkFrame(kpi_grid, corner_radius=10, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        c3.pack(side="left", fill="both", expand=True, padx=4)
        ctk.CTkLabel(c3, text="OPERAÇÕES / VENDAS", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(pady=(10, 2))
        self.lbl_vendas = ctk.CTkLabel(c3, text="0", font=ctk.CTkFont(size=18, weight="bold"), text_color=theme.TEXT_PRIMARY)
        self.lbl_vendas.pack(pady=(0, 10))

        # Card 4: Ticket Médio
        c4 = ctk.CTkFrame(kpi_grid, corner_radius=10, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        c4.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ctk.CTkLabel(c4, text="TICKET MÉDIO", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(pady=(10, 2))
        self.lbl_ticket = ctk.CTkLabel(c4, text="R$ 0,00", font=ctk.CTkFont(size=18, weight="bold"), text_color=theme.WARNING_COLOR)
        self.lbl_ticket.pack(pady=(0, 10))

        # 3. Card da Tabela de Transações
        table_card = ctk.CTkFrame(self, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        table_card.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        # Barra de Pesquisa e Atualização
        filter_bar = ctk.CTkFrame(table_card, fg_color="transparent")
        filter_bar.pack(fill="x", padx=16, pady=12)

        self.entry_busca = ctk.CTkEntry(
            filter_bar,
            placeholder_text="🔍 Filtrar histórico por nome do produto...",
            height=36,
            corner_radius=8,
            fg_color=theme.ENTRY_BG,
            border_color=theme.ENTRY_BORDER,
            text_color=theme.ENTRY_TEXT,
        )
        self.entry_busca.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry_busca.bind("<KeyRelease>", lambda event: self.recarregar_dados())

        ctk.CTkButton(
            filter_bar,
            text="Atualizar",
            width=100,
            height=36,
            corner_radius=8,
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self.recarregar_dados,
        ).pack(side="right")

        # Cabeçalho da Tabela
        header_grid = ctk.CTkFrame(table_card, height=36, fg_color=theme.INNER_CARD_BG, corner_radius=6, border_width=1, border_color=theme.BORDER_COLOR)
        header_grid.pack(fill="x", padx=16, pady=(0, 6))

        col_configs = [
            ("ID", 55, "center"),
            ("Horário", 80, "center"),
            ("Produto Vendido", 240, "w"),
            ("Qtd", 65, "center"),
            ("Unitário", 110, "e"),
            ("Total", 120, "e"),
            ("Status", 120, "center"),
            ("Ação", 110, "center"),
        ]

        for nome_col, largura, alinhamento in col_configs:
            lbl = ctk.CTkLabel(
                header_grid,
                text=nome_col,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=theme.TEXT_SECONDARY,
                width=largura,
            )
            if alinhamento == "w":
                lbl.pack(side="left", fill="x", expand=True, padx=8)
            else:
                lbl.pack(side="left", padx=4)

        # Scrollable Frame de Vendas
        self.scroll_frame = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=(0, 14))

    def recarregar_dados(self):
        """Atualiza a lista com base nas vendas do dia e nos filtros."""
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        resumo = db.obter_resumo_dia()
        fat = resumo["total_faturamento"]
        itens = resumo["total_itens"]
        vendas_count = resumo["total_vendas"]
        ticket = (fat / vendas_count) if vendas_count > 0 else 0.0

        self.lbl_faturamento.configure(text=formatar_moeda(fat))
        self.lbl_itens.configure(text=f"{itens} un")
        self.lbl_vendas.configure(text=str(vendas_count))
        self.lbl_ticket.configure(text=formatar_moeda(ticket))

        # Lista vendas recentes do dia
        todas_vendas = db.obter_vendas_recentes_do_dia(limite=500)
        termo = self.entry_busca.get().strip().lower() if hasattr(self, "entry_busca") else ""

        if termo:
            vendas = [v for v in todas_vendas if termo in v["produto_nome"].lower()]
        else:
            vendas = todas_vendas

        if not vendas:
            lbl_vazio = ctk.CTkLabel(
                self.scroll_frame,
                text="Nenhuma venda encontrada para os filtros selecionados.",
                font=ctk.CTkFont(size=12, slant="italic"),
                text_color=theme.TEXT_MUTED,
            )
            lbl_vazio.pack(pady=40)
            return

        for v in vendas:
            is_cancelada = (v.get("status") == "CANCELADA")
            cor_linha = theme.INNER_CARD_BG
            cor_texto = theme.TEXT_MUTED if is_cancelada else theme.TEXT_PRIMARY
            cor_preco = theme.TEXT_MUTED if is_cancelada else theme.PRICE_COLOR
            cor_total = theme.TEXT_MUTED if is_cancelada else theme.STOCK_COLOR

            linha = ctk.CTkFrame(
                self.scroll_frame,
                height=42,
                fg_color=cor_linha,
                corner_radius=6,
                border_width=1,
                border_color=theme.BORDER_COLOR,
            )
            linha.pack(fill="x", pady=2)

            # ID
            ctk.CTkLabel(
                linha,
                text=f"#{v['id']}",
                font=ctk.CTkFont(size=11),
                text_color=theme.TEXT_SECONDARY,
                width=55,
            ).pack(side="left", padx=4)

            # Horário
            hora_str = v["data_hora"].split(" ")[-1] if " " in v["data_hora"] else v["data_hora"]
            ctk.CTkLabel(
                linha,
                text=hora_str,
                font=ctk.CTkFont(size=11),
                text_color=cor_texto,
                width=80,
            ).pack(side="left", padx=4)

            # Nome do Produto
            lbl_prod = ctk.CTkLabel(
                linha,
                text=v["produto_nome"],
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=cor_texto,
                anchor="w",
            )
            lbl_prod.pack(side="left", fill="x", expand=True, padx=8)

            # Quantidade
            ctk.CTkLabel(
                linha,
                text=f"{v['quantidade']} un",
                font=ctk.CTkFont(size=11),
                text_color=cor_texto,
                width=65,
            ).pack(side="left", padx=4)

            # Preço Unitário
            ctk.CTkLabel(
                linha,
                text=formatar_moeda(v["preco_unitario"]),
                font=ctk.CTkFont(size=11),
                text_color=cor_preco,
                width=110,
                anchor="e",
            ).pack(side="left", padx=4)

            # Total da Venda
            ctk.CTkLabel(
                linha,
                text=formatar_moeda(v["valor_total"]),
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=cor_total,
                width=120,
                anchor="e",
            ).pack(side="left", padx=4)

            # Badge de Status
            status_box = ctk.CTkFrame(linha, width=120, height=26, fg_color="transparent")
            status_box.pack(side="left", padx=4)
            status_box.pack_propagate(False)

            if is_cancelada:
                lbl_status = ctk.CTkLabel(
                    status_box,
                    text="🔴 CANCELADA",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=theme.ACCENT_RED,
                )
            else:
                lbl_status = ctk.CTkLabel(
                    status_box,
                    text="🟢 CONCLUÍDA",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=theme.STOCK_COLOR,
                )
            lbl_status.pack(expand=True)

            # Botão de Ação / Cancelamento
            acao_box = ctk.CTkFrame(linha, width=110, height=28, fg_color="transparent")
            acao_box.pack(side="left", padx=4)
            acao_box.pack_propagate(False)

            if is_cancelada:
                btn_acao = ctk.CTkButton(
                    acao_box,
                    text="Cancelada",
                    font=ctk.CTkFont(size=10),
                    state="disabled",
                    fg_color=theme.ENTRY_BG,
                    text_color=theme.TEXT_MUTED,
                    corner_radius=6,
                )
            else:
                btn_acao = ctk.CTkButton(
                    acao_box,
                    text="❌ Cancelar",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    fg_color=theme.ACCENT_RED,
                    hover_color=theme.ACCENT_RED_HOVER,
                    text_color="#FFFFFF",
                    corner_radius=6,
                    command=lambda vid=v["id"], pnome=v["produto_nome"], qtd=v["quantidade"]: self._confirmar_cancelamento(vid, pnome, qtd),
                )
            btn_acao.pack(fill="both", expand=True)

    def _confirmar_cancelamento(self, venda_id: int, produto_nome: str, quantidade: int):
        """Exibe diálogo de confirmação e realiza o cancelamento da venda no banco."""
        confirma = messagebox.askyesno(
            "Confirmar Cancelamento",
            f"Deseja realmente CANCELAR a venda #{venda_id} de '{produto_nome}'?\n\n"
            f"• Quantidade a devolver ao estoque: {quantidade} un\n"
            f"• O valor será estornado do faturamento diário.\n\n"
            f"Esta operação não pode ser desfeita. Confirmar?",
            icon="warning",
        )
        if not confirma:
            return

        sucesso, msg = db.cancelar_venda(venda_id)
        if sucesso:
            messagebox.showinfo("Venda Cancelada", msg)
            self.recarregar_dados()
            if self.on_venda_cancelada:
                self.on_venda_cancelada()
        else:
            messagebox.showerror("Erro ao Cancelar", msg)

    def focar_busca(self):
        """Foca no campo de busca de vendas."""
        self.entry_busca.focus_set()
