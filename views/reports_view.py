"""
Módulo de Visualização de Relatórios (Excel)
Arquivo: views/reports_view.py

Responsável pela interface de consolidação diária de vendas,
acionamento da exportação para planilha Excel (.xlsx) e abertura
direta do arquivo ou diretório de destino.
"""

import os
import sys
import subprocess
from datetime import datetime
import customtkinter as ctk

import database as db
import reports


def formatar_moeda(valor: float) -> str:
    """Formata valor numérico para padrão monetário brasileiro R$ 0,00."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class ReportsView(ctk.CTkFrame):
    """Painel do Módulo de Relatórios Diários."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.ultimo_arquivo_gerado: str = ""

        self._criar_layout()
        self.recarregar_dados()

    def _criar_layout(self):
        # 1. Cabeçalho
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(16, 12))

        lbl_titulo = ctk.CTkLabel(
            header_frame,
            text="📈 Relatórios e Exportação Excel",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F8FAFC",
        )
        lbl_titulo.pack(anchor="w")

        lbl_subtitulo = ctk.CTkLabel(
            header_frame,
            text="Gere relatórios consolidados em planilhas Excel (.xlsx) profissionais prontas para contabilidade e gestão.",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8",
        )
        lbl_subtitulo.pack(anchor="w")

        # 2. Painel de Ação e Cards de Métricas (Card Superior)
        top_card = ctk.CTkFrame(self, corner_radius=12, fg_color="#1E293B", border_width=1, border_color="#334155")
        top_card.pack(fill="x", padx=24, pady=(0, 16))

        action_frame = ctk.CTkFrame(top_card, fg_color="transparent")
        action_frame.pack(fill="x", padx=20, pady=16)

        # Informações da Data Atual
        info_date_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        info_date_frame.pack(side="left")

        hoje_formatado = datetime.now().strftime("%d/%m/%Y")
        ctk.CTkLabel(
            info_date_frame,
            text=f"📅 Período de Apuração: Hoje ({hoje_formatado})",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#F8FAFC",
        ).pack(anchor="w")

        ctk.CTkLabel(
            info_date_frame,
            text="Consolidação por produto com quantidade, preço unitário e total arrecadado.",
            font=ctk.CTkFont(size=11),
            text_color="#94A3B8",
        ).pack(anchor="w", pady=(2, 0))

        # Botão Principal de Exportação
        self.btn_exportar = ctk.CTkButton(
            action_frame,
            text="📊 GERAR RELATÓRIO DO DIA (EXCEL)",
            height=44,
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#10B981",
            hover_color="#059669",
            command=self._gerar_relatorio,
        )
        self.btn_exportar.pack(side="right")

        # Cards com Métricas Consolidadas do Dia
        metrics_grid = ctk.CTkFrame(top_card, fg_color="transparent")
        metrics_grid.pack(fill="x", padx=20, pady=(0, 16))

        # Card 1: Faturamento Geral
        card1 = ctk.CTkFrame(metrics_grid, corner_radius=8, fg_color="#0F172A", border_width=1, border_color="#334155")
        card1.pack(side="left", fill="both", expand=True, padx=(0, 8))
        ctk.CTkLabel(card1, text="FATURAMENTO TOTAL DO DIA", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8").pack(pady=(10, 2))
        self.lbl_fat_total = ctk.CTkLabel(card1, text="R$ 0,00", font=ctk.CTkFont(size=18, weight="bold"), text_color="#10B981")
        self.lbl_fat_total.pack(pady=(0, 10))

        # Card 2: Volume Total Vendido
        card2 = ctk.CTkFrame(metrics_grid, corner_radius=8, fg_color="#0F172A", border_width=1, border_color="#334155")
        card2.pack(side="left", fill="both", expand=True, padx=4)
        ctk.CTkLabel(card2, text="QUANTIDADE TOTAL VENDIDA", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8").pack(pady=(10, 2))
        self.lbl_vol_total = ctk.CTkLabel(card2, text="0 itens", font=ctk.CTkFont(size=18, weight="bold"), text_color="#38BDF8")
        self.lbl_vol_total.pack(pady=(0, 10))

        # Card 3: Produto Mais Vendido
        card3 = ctk.CTkFrame(metrics_grid, corner_radius=8, fg_color="#0F172A", border_width=1, border_color="#334155")
        card3.pack(side="left", fill="both", expand=True, padx=(8, 0))
        ctk.CTkLabel(card3, text="PRODUTO CAMPEÃO DE VENDAS", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8").pack(pady=(10, 2))
        self.lbl_campeao = ctk.CTkLabel(card3, text="Nenhum", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F8FAFC")
        self.lbl_campeao.pack(pady=(0, 10))

        # Status / Feedback da Geração
        self.status_box = ctk.CTkFrame(top_card, fg_color="#0F172A", corner_radius=8, border_width=1, border_color="#334155")
        self.status_box.pack(fill="x", padx=20, pady=(0, 14))

        self.lbl_status = ctk.CTkLabel(
            self.status_box,
            text="Pronto para gerar relatório. Clique no botão acima para exportar em formato .xlsx.",
            font=ctk.CTkFont(size=11),
            text_color="#94A3B8",
            wraplength=700,
        )
        self.lbl_status.pack(side="left", padx=14, pady=10)

        self.btn_abrir_arquivo = ctk.CTkButton(
            self.status_box,
            text="Abrir Excel",
            width=100,
            height=30,
            corner_radius=6,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self._abrir_arquivo_excel,
            state="disabled",
        )
        self.btn_abrir_arquivo.pack(side="right", padx=(6, 12), pady=8)

        self.btn_abrir_pasta = ctk.CTkButton(
            self.status_box,
            text="Abrir Pasta",
            width=100,
            height=30,
            corner_radius=6,
            fg_color="#334155",
            hover_color="#475569",
            command=self._abrir_pasta_destino,
            state="disabled",
        )
        self.btn_abrir_pasta.pack(side="right", padx=(0, 6), pady=8)

        # 3. Pré-visualização da Tabela Consolidada (Card Inferior)
        preview_card = ctk.CTkFrame(self, corner_radius=12, fg_color="#1E293B", border_width=1, border_color="#334155")
        preview_card.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        lbl_prev_title = ctk.CTkLabel(
            preview_card,
            text="📋 Pré-visualização dos Dados Consolidados do Dia",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#E2E8F0",
        )
        lbl_prev_title.pack(anchor="w", padx=20, pady=(14, 10))

        # Cabeçalho da Tabela
        header_grid = ctk.CTkFrame(preview_card, height=36, fg_color="#0F172A", corner_radius=6)
        header_grid.pack(fill="x", padx=16, pady=(0, 6))

        col_configs = [
            ("Nome do Produto", 300, "w"),
            ("Quantidade Total Vendida", 180, "center"),
            ("Valor Unitário (R$)", 160, "e"),
            ("Total Arrecadado (R$)", 180, "e"),
        ]

        for nome_col, largura, alinhamento in col_configs:
            lbl = ctk.CTkLabel(
                header_grid,
                text=nome_col,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#94A3B8",
                width=largura,
            )
            if alinhamento == "w":
                lbl.pack(side="left", fill="x", expand=True, padx=8)
            else:
                lbl.pack(side="left", padx=6)

        # Scrollable Frame para Linhas Consolidadas
        self.scroll_preview = ctk.CTkScrollableFrame(preview_card, fg_color="transparent")
        self.scroll_preview.pack(fill="both", expand=True, padx=16, pady=(0, 14))

    def recarregar_dados(self):
        """Atualiza a pré-visualização com base nas vendas do dia."""
        for w in self.scroll_preview.winfo_children():
            w.destroy()

        dados = db.obter_relatorio_consolidado_dia()

        if not dados:
            self.lbl_fat_total.configure(text="R$ 0,00")
            self.lbl_vol_total.configure(text="0 itens")
            self.lbl_campeao.configure(text="Nenhum")

            lbl_vazio = ctk.CTkLabel(
                self.scroll_preview,
                text="Nenhuma venda registrada na data de hoje para compor o relatório.",
                font=ctk.CTkFont(size=12, slant="italic"),
                text_color="#64748B",
            )
            lbl_vazio.pack(pady=40)
            return

        total_faturamento = sum(item["total_arrecadado"] for item in dados)
        total_pecas = sum(item["quantidade_total"] for item in dados)
        campeao = max(dados, key=lambda x: x["quantidade_total"])

        self.lbl_fat_total.configure(text=formatar_moeda(total_faturamento))
        self.lbl_vol_total.configure(text=f"{total_pecas} un")
        self.lbl_campeao.configure(text=f"{campeao['produto_nome']} ({campeao['quantidade_total']}x)")

        for row in dados:
            linha = ctk.CTkFrame(self.scroll_preview, height=38, fg_color="#182234", corner_radius=6)
            linha.pack(fill="x", pady=2)

            ctk.CTkLabel(linha, text=row["produto_nome"], font=ctk.CTkFont(size=12, weight="bold"), text_color="#F1F5F9", anchor="w", width=300).pack(side="left", fill="x", expand=True, padx=8)
            ctk.CTkLabel(linha, text=f"{row['quantidade_total']} un", font=ctk.CTkFont(size=12), text_color="#CBD5E1", width=180).pack(side="left", padx=6)
            ctk.CTkLabel(linha, text=formatar_moeda(row["preco_unitario"]), font=ctk.CTkFont(size=12), text_color="#38BDF8", width=160, anchor="e").pack(side="left", padx=6)
            ctk.CTkLabel(linha, text=formatar_moeda(row["total_arrecadado"]), font=ctk.CTkFont(size=12, weight="bold"), text_color="#10B981", width=180, anchor="e").pack(side="left", padx=6)

    def _gerar_relatorio(self):
        sucesso, msg, arquivo = reports.gerar_relatorio_diario_excel()
        if sucesso:
            self.ultimo_arquivo_gerado = arquivo
            nome_arquivo = os.path.basename(arquivo)
            self.lbl_status.configure(
                text=f"✔ Relatório gerado e CRIPTOGRAFADO!\nArquivo: {nome_arquivo}\n🔒 Exige a Senha do Administrador para abrir no Excel.",
                text_color="#10B981",
            )
            self.btn_abrir_arquivo.configure(state="normal")
            self.btn_abrir_pasta.configure(state="normal")
            self.recarregar_dados()
        else:
            self.lbl_status.configure(text=f"Aviso: {msg}", text_color="#F59E0B")

    def _abrir_arquivo_excel(self):
        if self.ultimo_arquivo_gerado and os.path.exists(self.ultimo_arquivo_gerado):
            try:
                os.startfile(self.ultimo_arquivo_gerado)
            except Exception as e:
                self.lbl_status.configure(text=f"Erro ao abrir arquivo: {str(e)}", text_color="#EF4444")

    def _abrir_pasta_destino(self):
        if self.ultimo_arquivo_gerado and os.path.exists(self.ultimo_arquivo_gerado):
            try:
                subprocess.Popen(f'explorer /select,"{os.path.abspath(self.ultimo_arquivo_gerado)}"')
            except Exception:
                pasta = os.path.dirname(os.path.abspath(self.ultimo_arquivo_gerado))
                os.startfile(pasta)
        else:
            pasta = db.get_base_dir()
            os.startfile(pasta)

    def disparar_exportacao(self):
        """Aciona diretamente a geração do relatório em Excel."""
        self._gerar_relatorio()
