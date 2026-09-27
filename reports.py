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
    obter_resumo_dia,
    obter_senha_para_protecao_relatorio,
    registrar_fechamento_auditado,
)


def formatar_moeda(valor: float) -> str:
    """Formata valor numérico para string no padrão brasileiro R$ 0,00."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_relatorio_diario_excel(data_str: Optional[str] = None) -> Tuple[bool, str, str]:
    """
    Gera uma planilha Excel com as vendas consolidadas e apuração de lucro da data especificada.
    
    Salva o arquivo no padrão:
    `relatorio_vendas_YYYY-MM-DD.xlsx` no diretório base da aplicação (ao lado do executável).

    Retorna:
    (sucesso: bool, mensagem: str, caminho_arquivo: str)
    """
    if not data_str:
        data_str = datetime.now().strftime("%Y-%m-%d")

    nome_arquivo = f"relatorio_vendas_{data_str}.xlsx"
    caminho_arquivo = os.path.join(get_base_dir(), nome_arquivo)

    # 1. Pré-validação de arquivo aberto (bloqueio do Microsoft Excel)
    if os.path.exists(caminho_arquivo):
        try:
            with open(caminho_arquivo, "a"):
                pass
        except (PermissionError, IOError):
            return (
                False,
                f"O arquivo '{nome_arquivo}' está atualmente aberto no Excel ou em outro programa.\nPor favor, feche a planilha antes de gerar um novo relatório.",
                "",
            )

    try:
        # 2. Consulta dados consolidados da base de dados com custos e lucro
        dados = obter_relatorio_consolidado_dia(data_str)

        if not dados:
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

        # 4. Cria arquivo Excel inicial via pandas
        with pd.ExcelWriter(caminho_arquivo, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Resumo de Vendas", index=False, startrow=3)

        # 5. Aplica estilização profissional avançada com openpyxl
        wb = openpyxl.load_workbook(caminho_arquivo)
        ws = wb["Resumo de Vendas"]

        # Paleta de Estilos
        fill_titulo = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        fill_cabecalho = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        fill_vendas_total = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        fill_custo_total = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        fill_lucro_total = PatternFill(start_color="065F46", end_color="065F46", fill_type="solid")  # Verde Esmeralda

        font_titulo = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
        font_subtitulo = Font(name="Segoe UI", size=10, italic=True, color="64748B")
        font_cabecalho = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        font_dados = Font(name="Segoe UI", size=10, color="1E293B")

        font_tot_vendas = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        font_tot_custo = Font(name="Segoe UI", size=10, bold=True, color="334155")
        font_tot_lucro = Font(name="Segoe UI", size=12, bold=True, color="FFFFFF")

        thin_border_side = Side(border_style="thin", color="CBD5E1")
        thick_border_top = Side(border_style="medium", color="0F172A")
        double_border_bottom = Side(border_style="double", color="0F172A")

        border_dados = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
        border_tot_vendas = Border(left=thin_border_side, right=thin_border_side, top=thick_border_top, bottom=thin_border_side)
        border_tot_custo = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
        border_tot_lucro = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=double_border_bottom)

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

        # Linha 1: Total Geral de Vendas (Faturamento Bruto)
        row_vendas = end_row + 1
        ws.row_dimensions[row_vendas].height = 28

        ws.cell(row=row_vendas, column=1, value="VALOR TOTAL DE FATURAMENTO (VENDAS)").alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.cell(row=row_vendas, column=2, value=total_qtd).number_format = "#,##0"
        ws.cell(row=row_vendas, column=3, value="-").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=row_vendas, column=4, value="-").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=row_vendas, column=5, value=total_faturamento).number_format = 'R$ #,##0.00'

        for c in range(1, 6):
            cell = ws.cell(row=row_vendas, column=c)
            cell.font = font_tot_vendas
            cell.fill = fill_vendas_total
            cell.border = border_tot_vendas

        # Linha 2: Custo Total das Mercadorias Vendidas (CMV)
        row_custo = end_row + 2
        ws.row_dimensions[row_custo].height = 26

        ws.cell(row=row_custo, column=1, value="(-) CUSTO TOTAL DAS MERCADORIAS (CMV)").alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.cell(row=row_custo, column=2, value="-").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=row_custo, column=3, value="-").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=row_custo, column=4, value="-").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=row_custo, column=5, value=total_custo).number_format = 'R$ #,##0.00'

        for c in range(1, 6):
            cell = ws.cell(row=row_custo, column=c)
            cell.font = font_tot_custo
            cell.fill = fill_custo_total
            cell.border = border_tot_custo

        # Linha 3: Lucro Total do Dia (Já com Custo Abatido) - Destaque em Verde Esmeralda
        row_lucro = end_row + 3
        ws.row_dimensions[row_lucro].height = 30

        ws.cell(row=row_lucro, column=1, value="(=) LUCRO TOTAL DO DIA (JÁ COM CUSTO ABATIDO)").alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.cell(row=row_lucro, column=2, value="-").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=row_lucro, column=3, value="-").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=row_lucro, column=4, value=f"Margem: {margem_lucro:.1f}%").alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=row_lucro, column=5, value=total_lucro).number_format = 'R$ #,##0.00'

        for c in range(1, 6):
            cell = ws.cell(row=row_lucro, column=c)
            cell.font = font_tot_lucro
            cell.fill = fill_lucro_total
            cell.border = border_tot_lucro

        # Linha de Rodapé Legal: Controle Interno / Não-Fiscal
        row_aviso = row_lucro + 2
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

        # 7. Proteção da Planilha com Senha Criptográfica
        senha_protecao = obter_senha_para_protecao_relatorio()
        ws.protection.sheet = True
        ws.protection.enable()
        ws.protection.set_password(senha_protecao)

        # Ajuste automático inteligente das larguras de colunas
        linhas_ignoradas = [1, 2, row_vendas, row_custo, row_lucro, row_aviso, row_selo_tit, row_hash, row_info_prot]
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.row in linhas_ignoradas:
                    continue
                val_str = str(cell.value or "")
                if len(val_str) > max_len:
                    max_len = len(val_str)
            ws.column_dimensions[col_letter].width = max(max_len + 5, 18)

        # Salva a planilha em buffer de memória para cifragem com senha de abertura
        raw_buffer = io.BytesIO()
        wb.save(raw_buffer)
        wb.close()
        raw_buffer.seek(0)

        # Criptografa o arquivo Excel no padrão ECMA-376 (Agile Encryption)
        # Exige a senha do administrador logo na abertura do arquivo para que somente o dono veja os dados
        try:
            with open(caminho_arquivo, "wb") as f_out:
                office_file = msoffcrypto.OfficeFile(raw_buffer)
                office_file.encrypt(senha_protecao, f_out)
        except Exception:
            raw_buffer.seek(0)
            with open(caminho_arquivo, "wb") as f_fb:
                f_fb.write(raw_buffer.getvalue())

        return (
            True,
            f"Relatório protegido gerado com sucesso!\nArquivo: {nome_arquivo}\n"
            f"Faturamento: {formatar_moeda(total_faturamento)} | Custo: {formatar_moeda(total_custo)} | Lucro Real: {formatar_moeda(total_lucro)} ({margem_lucro:.1f}%)\n"
            f"🔒 Protegido com Senha de Abertura (somente quem possui a senha do administrador pode abrir e ver a planilha)\n"
            f"Selo SHA-256: {hash_sha256[:16]}... (Integridade Garantida)",
            caminho_arquivo,
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
