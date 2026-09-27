"""
Módulo de Visualização: Exportar Planilha Excel
Arquivo: views/export_excel_view.py

Tela dedicada exclusivamente à geração, visualização de status e download
do relatório diário de vendas em formato Excel (.xlsx).
"""

import os
import subprocess
from datetime import datetime
from typing import Optional
import customtkinter as ctk

import database as db
import reports
import theme
from views.admin_password_modal import AdminPasswordModal


def formatar_moeda(valor: float) -> str:
    """Formata valor numérico para padrão monetário brasileiro R$ 0,00."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class ExportExcelView(ctk.CTkFrame):
    """Tela dedicada à exportação e manipulação de arquivos Excel (.xlsx)."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.ultimo_arquivo_gerado: str = ""

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
            text="📥 Central de Exportação de Planilhas (Excel)",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        )
        lbl_titulo.pack(anchor="w")

        lbl_subtitulo = ctk.CTkLabel(
            col_tit,
            text="Gere arquivos .xlsx formatados profissionalmente com dados consolidados das vendas do dia.",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        )
        lbl_subtitulo.pack(anchor="w")

        self.btn_senha_admin = ctk.CTkButton(
            header_frame,
            text="🔐 Senha do Administrador",
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            command=self._abrir_modal_senha,
        )
        self.btn_senha_admin.pack(side="right")

        # 2. Card Principal de Exportação
        main_card = ctk.CTkFrame(self, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        main_card.pack(fill="x", padx=24, pady=(0, 16))

        inner_action = ctk.CTkFrame(main_card, fg_color="transparent")
        inner_action.pack(fill="x", padx=24, pady=20)

        # Ícone do Excel à esquerda
        excel_badge = ctk.CTkFrame(inner_action, width=64, height=64, corner_radius=12, fg_color="#107C41")
        excel_badge.pack_propagate(False)
        excel_badge.pack(side="left", padx=(0, 18))
        ctk.CTkLabel(excel_badge, text="📊", font=ctk.CTkFont(size=28)).pack(expand=True)

        # Informações da Exportação
        info_col = ctk.CTkFrame(inner_action, fg_color="transparent")
        info_col.pack(side="left", fill="x", expand=True)

        hoje_formatado = datetime.now().strftime("%d/%m/%Y")
        ctk.CTkLabel(
            info_col,
            text=f"Relatório Consolidado de Fechamento Diário ({hoje_formatado})",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            info_col,
            text="Agrupa todas as vendas do dia por produto com cabeçalhos estilizados, totais e moedas em R$.",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        # Botão de Ação Imediata
        self.btn_exportar = ctk.CTkButton(
            inner_action,
            text="📊 GERAR PLANILHA EXCEL AGORA",
            height=48,
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=theme.ACCENT_GREEN,
            hover_color=theme.ACCENT_GREEN_HOVER,
            command=self._gerar_planilha,
        )
        self.btn_exportar.pack(side="right")

        # Barra de Status de Proteção Criptográfica
        self.sec_strip = ctk.CTkFrame(main_card, fg_color=theme.INNER_CARD_BG, corner_radius=8, border_width=1, border_color=theme.BORDER_COLOR)
        self.sec_strip.pack(fill="x", padx=24, pady=(0, 10))

        self.lbl_sec_status = ctk.CTkLabel(
            self.sec_strip,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_PRIMARY,
        )
        self.lbl_sec_status.pack(side="left", padx=14, pady=6)

        self.btn_config_pwd = ctk.CTkButton(
            self.sec_strip,
            text="Configurar Senha",
            width=130,
            height=26,
            corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._abrir_modal_senha,
        )
        self.btn_config_pwd.pack(side="right", padx=10, pady=4)

        # Caixa de Status / Resultado da Exportação
        self.result_box = ctk.CTkFrame(main_card, fg_color=theme.INNER_CARD_BG, corner_radius=10, border_width=1, border_color=theme.BORDER_COLOR)
        self.result_box.pack(fill="x", padx=24, pady=(0, 18))

        self.lbl_status = ctk.CTkLabel(
            self.result_box,
            text="Nenhum arquivo gerado nesta sessão ainda. Clique no botão acima para exportar a planilha do dia.",
            font=ctk.CTkFont(size=12),
            text_color=theme.TEXT_SECONDARY,
            wraplength=600,
            justify="left",
        )
        self.lbl_status.pack(side="left", padx=16, pady=14)

        self.btn_abrir_pasta = ctk.CTkButton(
            self.result_box,
            text="Abrir Pasta",
            width=110,
            height=34,
            corner_radius=6,
            fg_color=theme.BTN_SECONDARY_BG,
            hover_color=theme.BTN_SECONDARY_HOVER,
            text_color=theme.BTN_SECONDARY_TEXT,
            command=self._abrir_pasta_destino,
            state="disabled",
        )
        self.btn_abrir_pasta.pack(side="right", padx=(6, 16), pady=12)

        self.btn_abrir_arquivo = ctk.CTkButton(
            self.result_box,
            text="Abrir Excel",
            width=110,
            height=34,
            corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=theme.ACCENT_BLUE,
            hover_color=theme.ACCENT_BLUE_HOVER,
            command=self._abrir_arquivo_excel,
            state="disabled",
        )
        self.btn_abrir_arquivo.pack(side="right", padx=(0, 6), pady=12)

        # 3. Card de Especificações e Pré-visualização da Planilha
        spec_card = ctk.CTkFrame(self, corner_radius=12, fg_color=theme.CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
        spec_card.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        ctk.CTkLabel(
            spec_card,
            text="📋 Estrutura da Planilha Gerada",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(16, 10))

        # Cards com os campos da planilha
        cols_grid = ctk.CTkFrame(spec_card, fg_color="transparent")
        cols_grid.pack(fill="x", padx=20, pady=(0, 14))

        campos_info = [
            ("Coluna A", "Nome do Produto", "Identificação cadastral da peça"),
            ("Coluna B", "Quantidade Total Vendida", "Contador de unidades faturadas"),
            ("Coluna C", "Preço de Venda Unitário", "Valor unitário de venda"),
            ("Coluna D", "Preço de Custo Unitário", "Custo unitário de aquisição"),
            ("Coluna E", "Valor Total de Faturamento", "Faturamento bruto por produto"),
        ]

        for col, titulo, desc in campos_info:
            c_box = ctk.CTkFrame(cols_grid, corner_radius=8, fg_color=theme.INNER_CARD_BG, border_width=1, border_color=theme.BORDER_COLOR)
            c_box.pack(side="left", fill="both", expand=True, padx=3)
            ctk.CTkLabel(c_box, text=col, font=ctk.CTkFont(size=10, weight="bold"), text_color=theme.PRICE_COLOR).pack(pady=(6, 2))
            ctk.CTkLabel(c_box, text=titulo, font=ctk.CTkFont(size=11, weight="bold"), text_color=theme.TEXT_PRIMARY).pack(pady=(0, 2))
            ctk.CTkLabel(c_box, text=desc, font=ctk.CTkFont(size=9), text_color=theme.TEXT_SECONDARY, wraplength=130).pack(pady=(0, 6))

        # Informações de armazenamento e compatibilidade
        storage_box = ctk.CTkFrame(spec_card, fg_color=theme.INNER_CARD_BG, corner_radius=8, border_width=1, border_color=theme.BORDER_COLOR)
        storage_box.pack(fill="x", padx=20, pady=(4, 16))

        padrao_nome = f"relatorio_vendas_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        pasta_destino = db.get_base_dir()

        texto_info = (
            f"• Nome do Arquivo: {padrao_nome}\n"
            f"• Pasta de Destino: {pasta_destino}\n"
            f"• Formato: Planilha do Microsoft Excel (.xlsx) compatível com Excel 2013+, Google Planilhas e LibreOffice\n"
            f"• Estrutura Limpa (5 Colunas): Mantém apenas as colunas essenciais sem dados redundantes.\n"
            f"• Linha em Verde no Rodapé: Apura o Lucro Total do dia já com o valor de custo abatido de cada item (com margem % apurada).\n"
            f"• Criptografia e Abertura: Exige a Senha do Administrador para abrir e visualizar os dados no Excel."
        )
        ctk.CTkLabel(
            storage_box,
            text=texto_info,
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_PRIMARY,
            justify="left",
        ).pack(anchor="w", padx=16, pady=12)

    def recarregar_dados(self):
        """Atualiza o estado da tela e a situação da proteção por senha."""
        self._atualizar_status_protecao()

    def _atualizar_status_protecao(self):
        """Atualiza os indicadores visuais de proteção de fechamentos."""
        if db.existe_senha_admin():
            self.lbl_sec_status.configure(
                text="🛡️ Proteção Ativa: Senha personalizada em vigor (Planilhas criptografadas - exige senha para abrir)",
                text_color=theme.STOCK_COLOR[1],
            )
            self.btn_config_pwd.configure(text="Alterar Senha")
        else:
            self.lbl_sec_status.configure(
                text="⚠️ Senha Padrão (Central@2026): Defina sua senha exclusiva de administrador para blindar a abertura das planilhas",
                text_color=theme.WARNING_COLOR[1],
            )
            self.btn_config_pwd.configure(text="Definir Senha")

    def _abrir_modal_senha(self):
        """Abre o modal para definir ou alterar a senha do administrador."""
        AdminPasswordModal(self, on_success_callback=self._atualizar_status_protecao)

    def _gerar_planilha(self):
        sucesso, msg, arquivo = reports.gerar_relatorio_diario_excel()
        if sucesso:
            self.ultimo_arquivo_gerado = arquivo
            nome_arquivo = os.path.basename(arquivo)
            tem_senha = db.existe_senha_admin()
            dica_senha = "sua Senha do Administrador personalizada" if tem_senha else "a Senha Padrão ('Central@2026' - altere no botão ao lado)"
            self.lbl_status.configure(
                text=f"✔ Planilha gerada e CRIPTOGRAFADA com sucesso!\n"
                     f"Arquivo: {nome_arquivo}\n"
                     f"🔒 Senha para Abrir: Ao abrir o arquivo no Excel, informe {dica_senha}.\n"
                     f"🛡️ Somente o dono com a senha poderá visualizar o conteúdo. Células travadas e autenticadas com SHA-256.",
                text_color=theme.STOCK_COLOR[1],
            )
            self.btn_abrir_arquivo.configure(state="normal")
            self.btn_abrir_pasta.configure(state="normal")
        else:
            self.lbl_status.configure(text=f"Aviso: {msg}", text_color=theme.WARNING_COLOR[1])

    def _abrir_arquivo_excel(self):
        if self.ultimo_arquivo_gerado and os.path.exists(self.ultimo_arquivo_gerado):
            try:
                os.startfile(self.ultimo_arquivo_gerado)
            except Exception as e:
                self.lbl_status.configure(text=f"Erro ao abrir arquivo: {str(e)}", text_color=theme.ACCENT_RED[1])

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
