"""
Módulo de Relatórios e Exportação Excel
Arquivo: reports.py

Responsável pela consolidação e exportação dos dados de vendas diárias
para planilhas Excel (.xlsx) utilizando as bibliotecas pandas e openpyxl,
com layout visual refinado, cabeçalhos estilizados, formatação monetária (R$),
demonstração de preço de venda, custo das mercadorias, apuração de lucro líquido
apartado do faturamento total, selo de integridade digital SHA-256 e proteção por senha.
"""

import os
import sys
import subprocess
import io
import hashlib
from datetime import datetime
from typing import Tuple, Optional
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import msoffcrypto

from database import (
    get_base_dir,
    obter_relatorio_consolidado_dia,
    obter_vendas_canceladas_dia,
    obter_resumo_dia,
    obter_senha_para_protecao_relatorio,
    registrar_fechamento_auditado,
)


def formatar_moeda(valor: float) -> str:
    """Formata valor numérico para string no padrão brasileiro R$ 0,00."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_relatorio_diario_excel(
    data_str: Optional[str] = None,
    sufixo_fechamento: Optional[str] = None,
    eh_fechamento_caixa: bool = False,
) -> Tuple[bool, str, str]:
    """
    Gera uma planilha Excel com as vendas consolidadas e apuração de lucro da data especificada.
    
    Salva o arquivo no padrão:
    - Se fechamento de caixa: `relatorio_vendas_YYYY-MM-DD_fechamento_HHMMSS.xlsx` (arquivo único por fechamento)
    - Se relatório padrão: `relatorio_vendas_YYYY-MM-DD.xlsx`
    
    Retorna:
    (sucesso: bool, mensagem: str, caminho_arquivo: str)
    """
    if not data_str:
        data_str = datetime.now().strftime("%Y-%m-%d")

    if eh_fechamento_caixa and not sufixo_fechamento:
        sufixo_fechamento = datetime.now().strftime("fechamento_%H%M%S")

    if sufixo_fechamento:
        nome_arquivo = f"relatorio_vendas_{data_str}_{sufixo_fechamento}.xlsx"
    else:
        nome_arquivo = f"relatorio_vendas_{data_str}.xlsx"

    caminho_arquivo = os.path.join(get_base_dir(), nome_arquivo)
    caminho_padrao = os.path.join(get_base_dir(), f"relatorio_vendas_{data_str}.xlsx")

    # 1. Pré-validação de arquivo aberto (bloqueio do Microsoft Excel)
    if os.path.exists(caminho_arquivo):
        try:
            with open(caminho_arquivo, "a"):
                pass
        except (PermissionError, IOError):
            return (
                False,
                f"O arquivo '{nome_arquivo}' está atualmente aberto no Excel ou em outro programa.\nPor favor, feche a planilha antes de continuar.",
                "",
            )

    if sufixo_fechamento and os.path.exists(caminho_padrao):
        try:
            with open(caminho_padrao, "a"):
                pass
        except (PermissionError, IOError):
            return (
                False,
                f"A planilha consolidada 'relatorio_vendas_{data_str}.xlsx' está aberta no Excel.\nPor favor, feche a planilha antes de realizar o fechamento do caixa.",
                "",
            )

    try:
        # 2. Consulta dados consolidados da base de dados com custos e lucro
        dados = obter_relatorio_consolidado_dia(data_str)
        canceladas = obter_vendas_canceladas_dia(data_str)

        if not dados:
            if eh_fechamento_caixa or canceladas:
                # Permite fechamento auditado ou exibição de cancelamentos mesmo sem vendas ativas
                dados = [
                    {
                        "produto_nome": "NENHUMA VENDA ATIVA (OU TODAS FORAM CANCELADAS)" if canceladas else "NENHUMA VENDA REGISTRADA NESTE TURNO",
                        "quantidade_total": 0,
                        "preco_unitario": 0.0,
                        "preco_custo": 0.0,
                        "total_arrecadado": 0.0,
                        "total_custo": 0.0,
                        "lucro_total": 0.0,
                    }
                ]
            else:
                return (
                    False,
                    f"Não foram encontradas vendas registradas para o dia {data_str}.",
                    "",
                )

        # 3. Constrói DataFrame pandas com as 5 colunas essenciais
        df = pd.DataFrame(dados)
        colunas_ordenadas = [
            "produto_nome",
            "quantidade_total",
            "preco_unitario",
            "preco_custo",
            "total_arrecadado",
        ]
        df = df[colunas_ordenadas]
        df = df.rename(
            columns={
                "produto_nome": "Nome do Produto",
                "quantidade_total": "Quantidade Total Vendida",
                "preco_unitario": "Preço de Venda Unitário (R$)",
                "preco_custo": "Preço de Custo Unitário (R$)",
                "total_arrecadado": "Valor Total de Faturamento (R$)",
            }
        )

        # 4. Cria arquivo Excel inicial via pandas em memória
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Resumo de Vendas", index=False, startrow=3)
        excel_buffer.seek(0)

        # 5. Aplica estilização profissional avançada com openpyxl
        wb = openpyxl.load_workbook(excel_buffer)
        ws = wb["Resumo de Vendas"]

        # Paleta de Estilos
        fill_titulo = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        fill_cabecalho = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        fill_vendas_total = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        fill_custo_total = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        fill_lucro_total = PatternFill(start_color="065F46", end_color="065F46", fill_type="solid")  # Verde Esmeralda
        fill_cancelado_total = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
        fill_cancelado_head = PatternFill(start_color="991B1B", end_color="991B1B", fill_type="solid")
        fill_cancelado_subhead = PatternFill(start_color="7F1D1D", end_color="7F1D1D", fill_type="solid")
        fill_cancelado_row = PatternFill(start_color="FFF1F2", end_color="FFF1F2", fill_type="solid")

        font_titulo = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
        font_subtitulo = Font(name="Segoe UI", size=10, italic=True, color="64748B")
        font_cabecalho = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        font_dados = Font(name="Segoe UI", size=10, color="1E293B")

        font_tot_vendas = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        font_tot_custo = Font(name="Segoe UI", size=10, bold=True, color="334155")
        font_tot_lucro = Font(name="Segoe UI", size=12, bold=True, color="FFFFFF")
        font_cancelado_tot = Font(name="Segoe UI", size=10, bold=True, color="991B1B")
        font_cancelado_head = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        font_cancelado_dados = Font(name="Segoe UI", size=9, color="7F1D1D")

        thin_border_side = Side(border_style="thin", color="CBD5E1")
        thick_border_top = Side(border_style="medium", color="0F172A")
        double_border_bottom = Side(border_style="double", color="0F172A")

        border_dados = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
        border_tot_vendas = Border(left=thin_border_side, right=thin_border_side, top=thick_border_top, bottom=thin_border_side)
        border_tot_custo = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
        border_tot_lucro = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=double_border_bottom)
        border_cancelado = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

        # Título superior
        ws.merge_cells("A1:E1")
        cell_titulo = ws["A1"]
        data_formatada = datetime.strptime(data_str, "%Y-%m-%d").strftime("%d/%m/%Y")
        cell_titulo.value = f"RELATÓRIO DIÁRIO DE VENDAS E APURAÇÃO DE LUCRO - {data_formatada}"
        cell_titulo.font = font_titulo
        cell_titulo.fill = fill_titulo
        cell_titulo.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 36

        # Subtítulo com timestamp de geração
        ws.merge_cells("A2:E2")
        cell_sub = ws["A2"]
        cell_sub.value = f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')} | Central de Vendas"
        cell_sub.font = font_subtitulo
        cell_sub.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[2].height = 20

        # Cabeçalho da tabela (linha 4 - 5 colunas limpas)
        ws.row_dimensions[4].height = 28
        for col_idx in range(1, 6):
            cell = ws.cell(row=4, column=col_idx)
            cell.font = font_cabecalho
            cell.fill = fill_cabecalho
            cell.border = border_dados
            if col_idx == 1:
                cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
            elif col_idx == 2:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="right", vertical="center")

        # Linhas de dados
        start_row = 5
        num_linhas = len(dados)
        end_row = start_row + num_linhas - 1

        total_qtd = 0
        total_faturamento = 0.0
        total_custo = 0.0
        total_lucro = 0.0

        for idx, row in enumerate(dados, start=start_row):
            ws.row_dimensions[idx].height = 22
            
            # 1. Nome do Produto
            c1 = ws.cell(row=idx, column=1)
            c1.font = font_dados
            c1.border = border_dados
            c1.alignment = Alignment(horizontal="left", vertical="center", indent=1)

            # 2. Quantidade Total Vendida
            c2 = ws.cell(row=idx, column=2)
            c2.font = font_dados
            c2.border = border_dados
            c2.alignment = Alignment(horizontal="center", vertical="center")
            c2.number_format = "#,##0"
            total_qtd += row["quantidade_total"]

            # 3. Preço Unitário de Venda (R$)
            c3 = ws.cell(row=idx, column=3)
            c3.font = font_dados
            c3.border = border_dados
            c3.alignment = Alignment(horizontal="right", vertical="center")
            c3.number_format = 'R$ #,##0.00'

            # 4. Preço de Custo Unitário (R$)
            c4 = ws.cell(row=idx, column=4)
            c4.font = font_dados
            c4.border = border_dados
            c4.alignment = Alignment(horizontal="right", vertical="center")
            c4.number_format = 'R$ #,##0.00'

            # 5. Valor Total de Faturamento (R$)
            c5 = ws.cell(row=idx, column=5)
            c5.font = font_dados
            c5.border = border_dados
            c5.alignment = Alignment(horizontal="right", vertical="center")
            c5.number_format = 'R$ #,##0.00'
            total_faturamento += row["total_arrecadado"]

            total_custo += row.get("total_custo", 0.0)
            total_lucro += row.get("lucro_total", 0.0)

        total_faturamento = round(total_faturamento, 2)
        total_custo = round(total_custo, 2)
        total_lucro = round(total_faturamento - total_custo, 2)
        margem_lucro = round((total_lucro / total_faturamento) * 100, 1) if total_faturamento > 0 else 0.0

        # ====================================================================
        # LINHAS TOTAIS: APURAÇÃO SEPARADA DE FATURAMENTO, CUSTO E LUCRO
        # ====================================================================

        total_cancelado_valor = round(sum(c["valor_total"] for c in canceladas), 2) if canceladas else 0.0
        total_cancelado_qtd = sum(c["quantidade"] for c in canceladas) if canceladas else 0

        # ====================================================================
        # LINHAS TOTAIS: APURAÇÃO SEPARADA DE FATURAMENTO, ESTORNOS, CUSTO E LUCRO
        # ====================================================================

        current_row = end_row + 1

        # Linha 1: Total Geral de Vendas (Faturamento Concluído)
        ws.row_dimensions[current_row].height = 28
        ws.cell(row=current_row, column=1, value="VALOR TOTAL DE FATURAMENTO (VENDAS CONCLUÍDAS)").alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.cell(row=current_row, column=2, value=total_qtd).number_format = "#,##0"
        ws.cell(row=current_row, column=3, value="-").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=current_row, column=4, value="-").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=current_row, column=5, value=total_faturamento).number_format = 'R$ #,##0.00'

        for c in range(1, 6):
            cell = ws.cell(row=current_row, column=c)
            cell.font = font_tot_vendas
            cell.fill = fill_vendas_total
            cell.border = border_tot_vendas
        current_row += 1

        # Linha 2 (se houver vendas canceladas): Estorno / Cancelamentos
        if canceladas:
            ws.row_dimensions[current_row].height = 26
            ws.cell(row=current_row, column=1, value="(-) VENDAS CANCELADAS / ESTORNADAS NO DIA").alignment = Alignment(horizontal="left", vertical="center", indent=1)
            ws.cell(row=current_row, column=2, value=f"{total_cancelado_qtd} estornada(s)").alignment = Alignment(horizontal="center", vertical="center")
            ws.cell(row=current_row, column=3, value="-").alignment = Alignment(horizontal="center", vertical="center")
            ws.cell(row=current_row, column=4, value="-").alignment = Alignment(horizontal="center", vertical="center")
            ws.cell(row=current_row, column=5, value=total_cancelado_valor).number_format = 'R$ #,##0.00'

            for c in range(1, 6):
                cell = ws.cell(row=current_row, column=c)
                cell.font = font_cancelado_tot
                cell.fill = fill_cancelado_total
                cell.border = border_cancelado
            current_row += 1

        # Linha 3: Custo Total das Mercadorias Vendidas (CMV)
        ws.row_dimensions[current_row].height = 26
        ws.cell(row=current_row, column=1, value="(-) CUSTO TOTAL DAS MERCADORIAS (CMV EFETIVO)").alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.cell(row=current_row, column=2, value="-").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=current_row, column=3, value="-").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=current_row, column=4, value="-").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=current_row, column=5, value=total_custo).number_format = 'R$ #,##0.00'

        for c in range(1, 6):
            cell = ws.cell(row=current_row, column=c)
            cell.font = font_tot_custo
            cell.fill = fill_custo_total
            cell.border = border_tot_custo
        current_row += 1

        # Linha 4: Lucro Total do Dia (Já com Custo Abatido) - Destaque em Verde Esmeralda
        ws.row_dimensions[current_row].height = 30
        ws.cell(row=current_row, column=1, value="(=) LUCRO TOTAL DO DIA (JÁ COM CUSTO ABATIDO)").alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.cell(row=current_row, column=2, value="-").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=current_row, column=3, value="-").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=current_row, column=4, value=f"Margem: {margem_lucro:.1f}%").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=current_row, column=5, value=total_lucro).number_format = 'R$ #,##0.00'

        for c in range(1, 6):
            cell = ws.cell(row=current_row, column=c)
            cell.font = font_tot_lucro
            cell.fill = fill_lucro_total
            cell.border = border_tot_lucro
        current_row += 1

        # ====================================================================
        # SEÇÃO DETALHADA: VENDAS CANCELADAS / ESTORNADAS NO DIA
        # ====================================================================
        if canceladas:
            current_row += 1  # Espaçamento
            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=5)
            c_canc_head = ws.cell(row=current_row, column=1)
            c_canc_head.value = f"⚠️ AUDITORIA: DEMONSTRATIVO DE VENDAS CANCELADAS / ESTORNADAS NO DIA ({len(canceladas)} OPERAÇÕES)"
            c_canc_head.font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
            c_canc_head.fill = fill_cancelado_head
            c_canc_head.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[current_row].height = 28
            current_row += 1

            titulos_canc = [
                "Venda ID / Horário",
                "Produto Cancelado",
                "Qtd Estornada",
                "Forma Pagto / Consumidor",
                "Valor Estornado (R$)",
            ]
            ws.row_dimensions[current_row].height = 24
            for idx_col, tit in enumerate(titulos_canc, start=1):
                cell = ws.cell(row=current_row, column=idx_col, value=tit)
                cell.font = font_cancelado_head
                cell.fill = fill_cancelado_subhead
                cell.border = border_cancelado
                cell.alignment = Alignment(horizontal="center" if idx_col != 2 else "left", vertical="center")
            current_row += 1

            for c_item in canceladas:
                ws.row_dimensions[current_row].height = 22
                horario = c_item["data_hora"][11:19] if len(c_item.get("data_hora", "")) >= 19 else ""
                id_txt = f"Venda #{c_item['id']} ({horario})"
                cpf_txt_c = f"CPF: {c_item['cpf_cliente']}" if c_item.get("cpf_cliente") else "Sem CPF"
                pgto_txt = f"{c_item.get('forma_pagamento', 'DINHEIRO')} • {cpf_txt_c}"

                c1 = ws.cell(row=current_row, column=1, value=id_txt)
                c2 = ws.cell(row=current_row, column=2, value=c_item["produto_nome"])
                c3 = ws.cell(row=current_row, column=3, value=c_item["quantidade"])
                c4 = ws.cell(row=current_row, column=4, value=pgto_txt)
                c5 = ws.cell(row=current_row, column=5, value=c_item["valor_total"])

                c1.alignment = Alignment(horizontal="center", vertical="center")
                c2.alignment = Alignment(horizontal="left", vertical="center", indent=1)
                c3.alignment = Alignment(horizontal="center", vertical="center")
                c4.alignment = Alignment(horizontal="center", vertical="center")
                c5.alignment = Alignment(horizontal="right", vertical="center")

                c3.number_format = "#,##0"
                c5.number_format = 'R$ #,##0.00'

                for col_i in range(1, 6):
                    cell_i = ws.cell(row=current_row, column=col_i)
                    cell_i.font = font_cancelado_dados
                    cell_i.fill = fill_cancelado_row
                    cell_i.border = border_cancelado

                current_row += 1

            # Linha totalizadora de estornos
            ws.row_dimensions[current_row].height = 24
            ws.cell(row=current_row, column=1, value="TOTAL GERAL DE VALORES ESTORNADOS NO DIA").alignment = Alignment(horizontal="left", vertical="center", indent=1)
            ws.cell(row=current_row, column=2, value=f"{len(canceladas)} operação(ões)").alignment = Alignment(horizontal="center", vertical="center")
            ws.cell(row=current_row, column=3, value=total_cancelado_qtd).number_format = "#,##0"
            ws.cell(row=current_row, column=4, value="-").alignment = Alignment(horizontal="center", vertical="center")
            ws.cell(row=current_row, column=5, value=total_cancelado_valor).number_format = 'R$ #,##0.00'

            for col_i in range(1, 6):
                cell_i = ws.cell(row=current_row, column=col_i)
                cell_i.font = font_cancelado_tot
                cell_i.fill = fill_cancelado_total
                cell_i.border = border_cancelado
            current_row += 1

        # Linha de Rodapé Legal: Controle Interno / Não-Fiscal
        row_aviso = current_row + 1
        ws.merge_cells(start_row=row_aviso, start_column=1, end_row=row_aviso, end_column=5)
        c_aviso = ws.cell(row=row_aviso, column=1)
        c_aviso.value = "Relatório Gerencial Interno - Documento sem validade fiscal."
        c_aviso.font = Font(name="Segoe UI", size=9, italic=True, color="64748B")
        c_aviso.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[row_aviso].height = 20

        # 6. Cálculo do Selo de Integridade e Auditoria Digital (SHA-256)
        resumo_dia = obter_resumo_dia(data_str)
        total_vendas_count = resumo_dia.get("total_vendas", 0)

        payload_auditoria = (
            f"CENTRAL_DE_VENDAS:{data_str}:FAT={total_faturamento:.2f}:CUSTO={total_custo:.2f}:LUCRO={total_lucro:.2f}:QTD={total_qtd}:VENDAS={total_vendas_count}:"
            + ";".join(
                f"{d['produto_nome']}:{d['quantidade_total']}:{d['preco_unitario']:.2f}:{d['preco_custo']:.2f}:{d['total_arrecadado']:.2f}"
                for d in dados
            )
        )
        hash_sha256 = hashlib.sha256(payload_auditoria.encode("utf-8")).hexdigest()

        # Registra no banco de dados SQLite para auditoria
        registrar_fechamento_auditado(
            data_referencia=data_str,
            total_faturamento=total_faturamento,
            total_itens=total_qtd,
            total_vendas=total_vendas_count,
            hash_sha256=hash_sha256,
            total_custo=total_custo,
            total_lucro=total_lucro,
        )

        # Bloco Visual do Selo de Integridade no Excel
        row_selo_tit = row_aviso + 2
        ws.merge_cells(start_row=row_selo_tit, start_column=1, end_row=row_selo_tit, end_column=5)
        c_selo_tit = ws.cell(row=row_selo_tit, column=1)
        c_selo_tit.value = "🔒 SELO DE INTEGRIDADE E AUDITORIA DIGITAL (SHA-256)"
        c_selo_tit.font = Font(name="Segoe UI", size=9, bold=True, color="0F172A")
        c_selo_tit.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        c_selo_tit.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[row_selo_tit].height = 22

        row_hash = row_selo_tit + 1
        ws.merge_cells(start_row=row_hash, start_column=1, end_row=row_hash, end_column=5)
        c_hash = ws.cell(row=row_hash, column=1)
        c_hash.value = f"Hash de Autenticidade: {hash_sha256}"
        c_hash.font = Font(name="Consolas", size=9, bold=True, color="334155")
        c_hash.fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        c_hash.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[row_hash].height = 20

        row_info_prot = row_hash + 1
        ws.merge_cells(start_row=row_info_prot, start_column=1, end_row=row_info_prot, end_column=5)
        c_prot = ws.cell(row=row_info_prot, column=1)
        c_prot.value = "Planilha protegida com senha de abertura. Valores certificados no banco de dados da Central de Vendas."
        c_prot.font = Font(name="Segoe UI", size=8, italic=True, color="64748B")
        c_prot.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[row_info_prot].height = 18
        ws.row_dimensions[row_info_prot].height = 18

        # 7. Proteção da Planilha e Estrutura com Senha do Administrador
        senha_protecao = obter_senha_para_protecao_relatorio()
        ws.protection.sheet = True
        ws.protection.enable()
        ws.protection.set_password(senha_protecao)
        wb.security.lockStructure = True
        wb.security.set_workbook_password(senha_protecao)

        # Ajuste automático inteligente das larguras de colunas
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                # Considera apenas o cabeçalho e os itens vendidos para definir a largura ideal
                if cell.row < 3 or cell.row > max(3, end_row):
                    continue
                val_str = str(cell.value or "")
                if len(val_str) > max_len:
                    max_len = len(val_str)
            ws.column_dimensions[col_letter].width = max(max_len + 5, 20)

        # Salva o conteúdo do workbook em buffer binário
        raw_buffer = io.BytesIO()
        wb.save(raw_buffer)
        wb.close()
        raw_bytes = raw_buffer.getvalue()

        # Se for fechamento de caixa, atualiza e criptografa primeiro a planilha consolidada padrão do dia
        if sufixo_fechamento:
            buf_in2 = io.BytesIO(raw_bytes)
            of2 = msoffcrypto.OfficeFile(buf_in2)
            with open(caminho_padrao, "wb") as f_out2:
                of2.encrypt(senha_protecao, f_out2)

        # Criptografa o arquivo de fechamento/relatório com a senha administrativa via msoffcrypto
        buf_in1 = io.BytesIO(raw_bytes)
        of1 = msoffcrypto.OfficeFile(buf_in1)
        with open(caminho_arquivo, "wb") as f_out:
            of1.encrypt(senha_protecao, f_out)

        msg_cifra = "🔒 Protegido com Senha Administrativa (exigida na abertura no Excel e auditada por SHA-256)"

        # Se for fechamento de caixa, registra oficialmente no banco de dados SQLite
        if eh_fechamento_caixa:
            try:
                from database import registrar_fechamento_caixa
                registrar_fechamento_caixa(
                    caminho_excel=caminho_arquivo,
                    hash_sha256=hash_sha256,
                    data_referencia=data_str,
                )
            except Exception as e_reg:
                print(f"Aviso ao registrar fechamento no banco: {e_reg}")

        if eh_fechamento_caixa:
            prefixo_msg = (
                f"🔒 Caixa Fechado e Planilha Atualizada!\n"
                f"Planilha Diária Atualizada: relatorio_vendas_{data_str}.xlsx\n"
                f"Cópia Auditada: {nome_arquivo}"
            )
            caminho_retorno = caminho_arquivo
        else:
            prefixo_msg = f"Relatório gerado com sucesso!\nArquivo: {nome_arquivo}"
            caminho_retorno = caminho_arquivo

        return (
            True,
            f"{prefixo_msg}\n"
            f"Faturamento: {formatar_moeda(total_faturamento)} | Custo: {formatar_moeda(total_custo)} | Lucro Real: {formatar_moeda(total_lucro)} ({margem_lucro:.1f}%)\n"
            f"{msg_cifra}\n"
            f"Selo SHA-256: {hash_sha256[:16]}... (Integridade Garantida)",
            caminho_retorno,
        )

    except PermissionError:
        return (
            False,
            f"Permissão negada ao salvar '{nome_arquivo}'. Feche o arquivo no Excel antes de continuar.",
            "",
        )
    except Exception as e:
        return (
            False,
            f"Falha ao gerar relatório Excel: {str(e)}",
            "",
        )


def obter_ultimo_relatorio_excel_gerado() -> Optional[str]:
    """
    Localiza o arquivo Excel (.xlsx) mais recente gerado pelo sistema, seja via
    exportação manual ("GERAR PLANILHA EXCEL AGORA") ou via rotina de "Fechar Caixa".
    Analisa os arquivos em disco e no histórico do banco, retornando o caminho do
    arquivo com timestamp de modificação mais recente.
    """
    candidatos = set()
    base = get_base_dir()

    # 1. Arquivos na pasta do sistema (diretório base)
    try:
        if os.path.exists(base):
            for f in os.listdir(base):
                if f.endswith(".xlsx") and not f.startswith("~$") and (
                    f.startswith("relatorio_vendas_")
                    or f.startswith("fechamento_")
                    or "vendas" in f.lower()
                    or "fechamento" in f.lower()
                ):
                    caminho = os.path.join(base, f)
                    if os.path.isfile(caminho):
                        candidatos.add(os.path.abspath(caminho))
    except Exception:
        pass

    # 2. Arquivos registrados na tabela fechamentos_caixa (mais recentes primeiro)
    try:
        from database import get_connection
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT caminho_excel FROM fechamentos_caixa WHERE caminho_excel IS NOT NULL AND caminho_excel != '' ORDER BY id DESC;"
            )
            for row in cursor.fetchall():
                caminho = row["caminho_excel"]
                if caminho and os.path.isfile(caminho):
                    candidatos.add(os.path.abspath(caminho))
    except Exception:
        pass

    lista_existentes = [c for c in candidatos if os.path.exists(c)]
    if not lista_existentes:
        return None

    # Ordena pelo mtime mais recente. Se empatar, o arquivo específico do fechamento tem precedência.
    lista_existentes.sort(
        key=lambda x: (
            os.path.getmtime(x),
            1 if "_fechamento_" in os.path.basename(x) else 0,
        ),
        reverse=True,
    )
    return lista_existentes[0]


def abrir_arquivo_planilha(caminho: Optional[str] = None) -> Tuple[bool, str]:
    """
    Abre o arquivo Excel com máxima compatibilidade e resiliência no ambiente Windows.
    Garante suporte nativo a Microsoft Excel, LibreOffice Calc, WPS e Google Sheets.
    Mantém a proteção por senha administrativa ativa para abertura confidencial.
    """
    if not caminho:
        caminho = obter_ultimo_relatorio_excel_gerado()

    if not caminho or not os.path.exists(caminho):
        return False, "Nenhuma planilha Excel encontrada no computador para abrir."

    abs_path = os.path.normpath(os.path.abspath(caminho))

    # 1. Limpeza preventiva de processos órfãos e arquivos de lock do LibreOffice/Excel
    try:
        cmd_clean = 'Get-Process soffice.bin -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -eq 0 } | Stop-Process -Force'
        subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", cmd_clean], capture_output=True, timeout=2)
    except Exception:
        pass

    try:
        for lk in [
            os.path.expandvars(r"%APPDATA%\LibreOffice\4\.lock"),
            os.path.expandvars(r"%APPDATA%\LibreOffice\4\user\.lock"),
            os.path.join(os.path.dirname(abs_path), f".~lock.{os.path.basename(abs_path)}#"),
        ]:
            if os.path.exists(lk):
                try:
                    os.remove(lk)
                except Exception:
                    pass
    except Exception:
        pass

    # 2. Tentativa nativa do Windows (os.startfile)
    try:
        os.startfile(abs_path)
        return True, f"Planilha aberta: {os.path.basename(abs_path)}"
    except Exception:
        pass

    # 4. Tentativa direta com executáveis conhecidos instalados
    candidatos_executaveis = [
        r"C:\Program Files\LibreOffice\program\scalc.exe",
        r"C:\Program Files (x86)\LibreOffice\program\scalc.exe",
        r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
        r"C:\Program Files (x86)\Microsoft Office\root\Office16\EXCEL.EXE",
    ]
    for exe in candidatos_executaveis:
        if os.path.exists(exe):
            try:
                subprocess.Popen([exe, abs_path])
                return True, f"Planilha aberta: {os.path.basename(abs_path)}"
            except Exception:
                pass

    # 5. Tentativa via cmd.exe /c start "" "<caminho>" (associação do shell do Windows)
    try:
        cmd = f'cmd /c start "" "{abs_path}"'
        subprocess.Popen(cmd, shell=True)
        return True, f"Planilha iniciada: {os.path.basename(abs_path)}"
    except Exception:
        pass

    # 6. Fallback: Se não houver programa de planilha configurado,
    # abre a pasta de destino com o arquivo selecionado no Windows Explorer
    try:
        subprocess.Popen(f'explorer /select,"{abs_path}"')
        return True, f"Pasta aberta com o arquivo selecionado: {os.path.basename(abs_path)}"
    except Exception:
        # 7. Fallback final: abre apenas a pasta
        try:
            pasta = os.path.dirname(abs_path)
            os.startfile(pasta)
            return True, f"Pasta aberta: {pasta}"
        except Exception as e_final:
            return False, f"Falha ao abrir planilha: {e_final}"

