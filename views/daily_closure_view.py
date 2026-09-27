"""
Módulo de Visualização: Fechamento do Dia
Arquivo: views/daily_closure_view.py

Tela dedicada ao balanço financeiro e fechamento de caixa do dia,
com dados consolidados por produto, indicadores executivos e totalizadores.
"""

from datetime import datetime
from typing import Optional, Callable
import customtkinter as ctk

import database as db
import theme
from views.admin_password_modal import AdminPasswordModal


def formatar_moeda(valor: float) -> str:
    """Formata valor numérico para padrão monetário brasileiro R$ 0,00."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class DailyClosureView(ctk.CTkFrame):
    """Tela executiva para conferência e fechamento diário do caixa."""

    def __init__(self, parent, on_goto_exportar: Optional[Callable] = None):
        super().__init__(parent, fg_color="transparent")
        self.on_goto_exportar = on_goto_exportar

        self._criar_layout()
        self.recarregar_dados()

    def _criar_layout(self):
        # 1. Cabeçalho
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(16, 12))

        col_tit = ctk.CTkFrame(header_frame, fg_color="transparent")
        col_tit.pack(side="left")

        hoje_str = datetime.now().strftime("%d/%m/%Y")
        lbl_titulo = ctk.CTkLabel(
            col_tit,
            text=f"📋 Fechamento Consolidado do Dia ({hoje_str})",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        lbl_titulo.pack(anchor="w")

        lbl_subtitulo = ctk.CTkLabel(
            col_tit,
            text="Balanço analítico das vendas agrupadas por produto para prestação de contas e conciliação.",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        )
        lbl_subtitulo.pack(anchor="w")

        if self.on_goto_exportar:
            btn_exp = ctk.CTkButton(
                header_frame,
                text="📥 Ir para Exportação Excel",
                font=ctk.CTkFont(size=12, weight="bold"),
                height=38,
                corner_radius=8,
                fg_color=theme.ACCENT_GREEN,
                hover_color=theme.ACCENT_GREEN_HOVER,
                command=self.on_goto_exportar,
            )
            btn_exp.pack(side="right", padx=(8, 0))

        btn_senha = ctk.CTkButton(
            header_frame,
            text="🔐 Senha do Administrador",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=38,
            corner_radius=8,
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            command=self._abrir_modal_senha,
        )
        btn_senha.pack(side="right")

        # 2. Cards de Métricas Consolidadas (4 KPIs Executivos)
        kpi_grid = ctk.CTkFrame(self, fg_color="transparent")
        kpi_grid.pack(fill="x", padx=24, pady=(0, 14))

        # Card 1: Faturamento Total Bruto
        c1 = ctk.CTkFrame(kpi_grid, corner_radius=10, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        c1.pack(side="left", fill="both", expand=True, padx=(0, 4))
        ctk.CTkLabel(c1, text="FATURAMENTO TOTAL BRUTO", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(pady=(8, 2))
        self.lbl_fat_total = ctk.CTkLabel(c1, text="R$ 0,00", font=ctk.CTkFont(size=18, weight="bold"), text_color=theme.PRICE_COLOR)
        self.lbl_fat_total.pack(pady=(0, 8))

        # Card 2: Custo Total (CMV)
        c2 = ctk.CTkFrame(kpi_grid, corner_radius=10, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        c2.pack(side="left", fill="both", expand=True, padx=4)
        ctk.CTkLabel(c2, text="(-) CUSTO TOTAL (CMV)", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(pady=(8, 2))
        self.lbl_custo_total = ctk.CTkLabel(c2, text="R$ 0,00", font=ctk.CTkFont(size=18, weight="bold"), text_color=theme.TEXT_PRIMARY)
        self.lbl_custo_total.pack(pady=(0, 8))

        # Card 3: Lucro Total Líquido (Destaque Verde Esmeralda)
        c3 = ctk.CTkFrame(kpi_grid, corner_radius=10, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        c3.pack(side="left", fill="both", expand=True, padx=4)
        ctk.CTkLabel(c3, text="(=) LUCRO TOTAL LÍQUIDO", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(pady=(8, 2))
        self.lbl_lucro_total = ctk.CTkLabel(c3, text="R$ 0,00", font=ctk.CTkFont(size=18, weight="bold"), text_color=theme.STOCK_COLOR)
        self.lbl_lucro_total.pack(pady=(0, 8))

        # Card 4: Volume & Produto Campeão
        c4 = ctk.CTkFrame(kpi_grid, corner_radius=10, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        c4.pack(side="left", fill="both", expand=True, padx=(4, 0))
        ctk.CTkLabel(c4, text="VOLUME TOTAL / CAMPEÃO", font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.TEXT_SECONDARY).pack(pady=(8, 2))
        self.lbl_vol_total = ctk.CTkLabel(c4, text="0 itens", font=ctk.CTkFont(size=16, weight="bold"), text_color=theme.TEXT_PRIMARY)
        self.lbl_vol_total.pack(pady=(0, 1))
        self.lbl_campeao = ctk.CTkLabel(c4, text="Campeão: Nenhum", font=ctk.CTkFont(size=10), text_color=theme.TEXT_SECONDARY)
        self.lbl_campeao.pack(pady=(0, 6))

        # Faixa de Auditoria Criptográfica SHA-256
        self.strip_auditoria = ctk.CTkFrame(self, height=36, corner_radius=8, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        self.strip_auditoria.pack(fill="x", padx=24, pady=(0, 10))

        self.lbl_auditoria = ctk.CTkLabel(
            self.strip_auditoria,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SECONDARY,
        )
        self.lbl_auditoria.pack(side="left", padx=14, pady=6)

        # 3. Card da Tabela de Fechamento Consolidado
        table_card = ctk.CTkFrame(self, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        table_card.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        # Cabeçalho da Tabela (5 Colunas Limpas e Objetivas)
        header_grid = ctk.CTkFrame(table_card, height=38, fg_color=theme.INNER_CARD_BG, corner_radius=6, border_width=1, border_color=theme.BORDER_COLOR)
        header_grid.pack(fill="x", padx=16, pady=(14, 6))

        col_configs = [
            ("Nome do Produto", 0, "w"),
            ("Qtd Vendida", 110, "center"),
            ("Preço Venda Unit.", 130, "e"),
            ("Preço Custo Unit.", 130, "e"),
            ("Total Faturamento", 150, "e"),
        ]

        for nome_col, largura, alinhamento in col_configs:
            lbl = ctk.CTkLabel(
                header_grid,
                text=nome_col,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=theme.TEXT_SECONDARY,
            )
            if alinhamento == "w":
                lbl.pack(side="left", fill="x", expand=True, padx=8)
            else:
                lbl.configure(width=largura)
                lbl.pack(side="left", padx=4)

        # Scrollable Frame para os Itens Consolidados
        self.scroll_frame = ctk.CTkScrollableFrame(table_card, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        # Linha Totalizadora Fixa no Rodapé
        self.footer_total = ctk.CTkFrame(table_card, height=44, fg_color=theme.INNER_CARD_BG, corner_radius=6, border_width=1, border_color=theme.ACCENT_BLUE)
        self.footer_total.pack(fill="x", padx=16, pady=(0, 14))

        self.lbl_total_label = ctk.CTkLabel(
            self.footer_total,
            text="TOTAIS DE VENDAS DO DIA",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        self.lbl_total_label.pack(side="left", fill="x", expand=True, padx=8)

        self.lbl_total_qtd = ctk.CTkLabel(
            self.footer_total,
            text="0 un",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
            width=110,
        )
        self.lbl_total_qtd.pack(side="left", padx=4)

        ctk.CTkLabel(self.footer_total, text="-", font=ctk.CTkFont(size=12), text_color=theme.TEXT_MUTED, width=130).pack(side="left", padx=4)
        ctk.CTkLabel(self.footer_total, text="-", font=ctk.CTkFont(size=12), text_color=theme.TEXT_MUTED, width=130).pack(side="left", padx=4)

        self.lbl_total_vendas = ctk.CTkLabel(
            self.footer_total,
            text="R$ 0,00",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.PRICE_COLOR,
            width=150,
            anchor="e",
        )
        self.lbl_total_vendas.pack(side="left", padx=4)

    def recarregar_dados(self):
        """Atualiza os dados consolidados do dia."""
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        dados = db.obter_relatorio_consolidado_dia()

        if not dados:
            self.lbl_fat_total.configure(text="R$ 0,00")
            self.lbl_custo_total.configure(text="R$ 0,00")
            self.lbl_lucro_total.configure(text="R$ 0,00")
            self.lbl_vol_total.configure(text="0 itens")
            self.lbl_campeao.configure(text="Campeão: Nenhum")
            self.lbl_total_qtd.configure(text="0 un")
            self.lbl_total_vendas.configure(text="R$ 0,00")

            lbl_vazio = ctk.CTkLabel(
                self.scroll_frame,
                text="Nenhuma venda registrada na data de hoje para compor o fechamento.",
                font=ctk.CTkFont(size=12, slant="italic"),
                text_color=theme.TEXT_MUTED,
            )
            lbl_vazio.pack(pady=40)
            return

        total_fat = sum(item["total_arrecadado"] for item in dados)
        total_custo = sum(item.get("total_custo", 0.0) for item in dados)
        total_lucro = sum(item.get("lucro_total", 0.0) for item in dados)
        total_pecas = sum(item["quantidade_total"] for item in dados)
        campeao = max(dados, key=lambda x: x["quantidade_total"])

        margem = round((total_lucro / total_fat) * 100, 1) if total_fat > 0 else 0.0

        self.lbl_fat_total.configure(text=formatar_moeda(total_fat))
        self.lbl_custo_total.configure(text=formatar_moeda(total_custo))
        self.lbl_lucro_total.configure(text=f"{formatar_moeda(total_lucro)} ({margem}%)")
        self.lbl_vol_total.configure(text=f"{total_pecas} un")
        self.lbl_campeao.configure(text=f"Campeão: {campeao['produto_nome']} ({campeao['quantidade_total']}x)")

        self.lbl_total_qtd.configure(text=f"{total_pecas} un")
        self.lbl_total_vendas.configure(text=formatar_moeda(total_fat))

        for row in dados:
            linha = ctk.CTkFrame(self.scroll_frame, height=40, fg_color=theme.INNER_CARD_BG, corner_radius=6, border_width=1, border_color=theme.BORDER_COLOR)
            linha.pack(fill="x", pady=2)

            ctk.CTkLabel(linha, text=row["produto_nome"], font=ctk.CTkFont(size=12, weight="bold"), text_color=theme.TEXT_PRIMARY, anchor="w").pack(side="left", fill="x", expand=True, padx=8)
            ctk.CTkLabel(linha, text=f"{row['quantidade_total']} un", font=ctk.CTkFont(size=12), text_color=theme.TEXT_PRIMARY, width=110).pack(side="left", padx=4)
            ctk.CTkLabel(linha, text=formatar_moeda(row["preco_unitario"]), font=ctk.CTkFont(size=12), text_color=theme.PRICE_COLOR, width=130, anchor="e").pack(side="left", padx=4)
            ctk.CTkLabel(linha, text=formatar_moeda(row.get("preco_custo", 0.0)), font=ctk.CTkFont(size=12), text_color=theme.TEXT_SECONDARY, width=130, anchor="e").pack(side="left", padx=4)
            ctk.CTkLabel(linha, text=formatar_moeda(row["total_arrecadado"]), font=ctk.CTkFont(size=12, weight="bold"), text_color=theme.TEXT_PRIMARY, width=150, anchor="e").pack(side="left", padx=4)

        # Atualiza status da auditoria e integridade
        hoje_iso = datetime.now().strftime("%Y-%m-%d")
        audit = db.obter_fechamento_auditado(hoje_iso)
        if audit:
            hash_curto = audit["hash_sha256"][:24]
            data_fech = audit.get("data_hora_fechamento", "")
            self.lbl_auditoria.configure(
                text=f"🛡️ Fechamento Auditado e Selado (SHA-256: {hash_curto}...) | Gravado em: {data_fech}",
                text_color=theme.STOCK_COLOR[1],
            )
        else:
            self.lbl_auditoria.configure(
                text="ℹ️ Fechamento do dia em aberto. O selo SHA-256 e a proteção criptográfica são gravados ao exportar para Excel.",
                text_color=theme.TEXT_SECONDARY,
            )

    def _abrir_modal_senha(self):
        """Abre o gerenciador de senha do administrador."""
        AdminPasswordModal(self, on_success_callback=self.recarregar_dados)

