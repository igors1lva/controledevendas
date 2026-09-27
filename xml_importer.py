"""
Módulo de Importação e Leitura de XML de NF-e (Modelos 55 e 65)
Arquivo: xml_importer.py

Lê e processa notas fiscais eletrônicas (NF-e / NFC-e) no formato XML padrão SEFAZ,
extraindo dados do emitente, produtos, quantidades e valores de custo unitário.
Utiliza estratégia de remoção de namespaces para compatibilidade universal (v3.10, v4.00+).
"""

import os
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple


def _remover_namespaces(raiz: ET.Element) -> None:
    """
    Remove recursivamente os prefixos de namespace XML (ex: {http://www.portalfiscal.inf.br/nfe})
    de todas as tags do documento, permitindo buscas diretas e limpas por tag.
    """
    for elemento in raiz.iter():
        if "}" in elemento.tag:
            elemento.tag = elemento.tag.split("}", 1)[1]


def _obter_texto(elemento: Optional[ET.Element], subtag: str, padrao: str = "") -> str:
    """Extrai com segurança o texto de uma subtag dentro de um elemento."""
    if elemento is None:
        return padrao
    filho = elemento.find(subtag)
    if filho is not None and filho.text:
        return filho.text.strip()
    return padrao


def _obter_float(elemento: Optional[ET.Element], subtag: str, padrao: float = 0.0) -> float:
    """Extrai com segurança um valor numérico de ponto flutuante de uma subtag."""
    txt = _obter_texto(elemento, subtag, "")
    try:
        return float(txt)
    except (ValueError, TypeError):
        return padrao


def parsear_xml_nfe(caminho_arquivo: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Realiza a leitura e validação do arquivo XML de NF-e / NFC-e.
    Retorna uma tupla: (sucesso: bool, mensagem: str, dados_nota: Optional[dict])
    """
    if not os.path.exists(caminho_arquivo):
        return False, f"Arquivo não encontrado: {caminho_arquivo}", None

    try:
        tree = ET.parse(caminho_arquivo)
        root = tree.getroot()
    except ET.ParseError as e:
        return False, f"Erro ao analisar o arquivo XML: formato inválido ou corrompido. Detalhes: {e}", None
    except Exception as e:
        return False, f"Falha na abertura do arquivo: {str(e)}", None

    # Remove namespaces para permitir pesquisa direta
    _remover_namespaces(root)

    # Localiza o nó infNFe (ou o nó raiz se for direto)
    inf_nfe = root.find(".//infNFe")
    if inf_nfe is None:
        # Tenta verificar se é um nó direto NFe
        inf_nfe = root.find(".//NFe")
        if inf_nfe is None:
            inf_nfe = root

    # Metadados de Identificação da Nota (<ide>)
    ide = inf_nfe.find(".//ide")
    num_nf = _obter_texto(ide, "nNF", "S/N")
    serie = _obter_texto(ide, "serie", "1")
    dh_emi = _obter_texto(ide, "dhEmi", "")
    if not dh_emi:
        dh_emi = _obter_texto(ide, "dEmi", "")

    # Dados do Fornecedor / Emitente (<emit>)
    emit = inf_nfe.find(".//emit")
    emitente_nome = _obter_texto(emit, "xNome", "Fornecedor Não Identificado")
    emitente_cnpj = _obter_texto(emit, "CNPJ", "")
    if not emitente_cnpj:
        emitente_cnpj = _obter_texto(emit, "CPF", "")

    # Total da Nota (<ICMSTot>)
    total_nfe = _obter_float(inf_nfe.find(".//ICMSTot"), "vNF", 0.0)

    # Detalhes dos Itens / Produtos (<det>)
    dets = inf_nfe.findall(".//det")
    if not dets:
        return False, "Nenhum item ou mercadoria (<det>) foi encontrado no XML da nota fiscal informada.", None

    itens_extraidos: List[Dict[str, Any]] = []

    for idx, det in enumerate(dets, start=1):
        prod = det.find("prod")
        if prod is None:
            continue

        c_prod = _obter_texto(prod, "cProd", "").strip()
        c_ean = _obter_texto(prod, "cEAN", "").strip()
        c_ean_trib = _obter_texto(prod, "cEANTrib", "").strip()
        x_prod = _obter_texto(prod, "xProd", f"Item #{idx}").strip()
        u_com = _obter_texto(prod, "uCom", "UN").strip()

        # Determinação inteligente do Código de Barras:
        # 1. cEAN (se for válido e não for "SEM GTIN")
        # 2. cEANTrib (se for válido e não for "SEM GTIN")
        # 3. cProd (código interno do fornecedor como contingência)
        codigo_barras = None
        if c_ean and c_ean.upper() != "SEM GTIN":
            codigo_barras = c_ean
        elif c_ean_trib and c_ean_trib.upper() != "SEM GTIN":
            codigo_barras = c_ean_trib
        elif c_prod:
            codigo_barras = c_prod

        q_com = _obter_float(prod, "qCom", 0.0)
        v_un_com = _obter_float(prod, "vUnCom", 0.0)
        v_prod = _obter_float(prod, "vProd", 0.0)

        # Arredonda quantidade para inteiro se for unidade inteira, ou arredonda para 2 casas
        qtd_inteira = int(round(q_com)) if abs(q_com - round(q_com)) < 0.001 else max(1, int(round(q_com)))

        # Sugestão padrão de preço de venda (50% de margem sobre o custo)
        preco_venda_sug = round(v_un_com * 1.5, 2)
        if preco_venda_sug <= 0:
            preco_venda_sug = round(v_un_com, 2) if v_un_com > 0 else 1.0

        itens_extraidos.append({
            "item_numero": idx,
            "codigo_barras": codigo_barras,
            "codigo_fornecedor": c_prod,
            "nome": x_prod,
            "unidade": u_com,
            "quantidade": qtd_inteira,
            "preco_custo": round(v_un_com, 2),
            "valor_total": round(v_prod, 2),
            "preco_venda_sugerido": preco_venda_sug,
        })

    if not itens_extraidos:
        return False, "Nenhum produto válido pôde ser extraído das tags <prod> da nota fiscal.", None

    dados_nota = {
        "arquivo": os.path.basename(caminho_arquivo),
        "numero_nf": num_nf,
        "serie": serie,
        "data_emissao": dh_emi,
        "emitente_nome": emitente_nome,
        "emitente_cnpj": emitente_cnpj,
        "valor_total": total_nfe,
        "total_itens": len(itens_extraidos),
        "itens": itens_extraidos,
    }

    return True, f"XML processado com sucesso: {len(itens_extraidos)} produto(s) identificado(s).", dados_nota
