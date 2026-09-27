"""
fiscal/nfce_builder.py
Construtor canônico da NFC-e (modelo 65) e cálculo matemático da Chave de Acesso.

Em conformidade com o Manual de Orientação do Contribuinte (MOC) da SEFAZ,
Layout 4.00 e Padrão de Padrões Técnicos do DANFE NFC-e.
"""

from datetime import datetime
import re
from typing import Dict, Any, List, Tuple


def calcular_dv_chave(chave_43: str) -> int:
    """
    Calcula o Dígito Verificador (DV) Módulo 11 da Chave de Acesso de 43 dígitos.
    Pesos de 2 a 9 da direita para a esquerda.
    Se o resto for 0 ou 1, o DV é 0; caso contrário, é (11 - resto).
    """
    if len(chave_43) != 43 or not chave_43.isdigit():
        raise ValueError(f"A chave para cálculo do DV deve conter exatamente 43 dígitos numéricos (recebido: {len(chave_43)}).")

    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = 0
    p_idx = 0

    for digito in reversed(chave_43):
        soma += int(digito) * pesos[p_idx]
        p_idx = (p_idx + 1) % len(pesos)

    resto = soma % 11
    return 0 if resto in (0, 1) else (11 - resto)


def gerar_chave_acesso(
    uf_ibge: int,
    data_emissao: datetime,
    cnpj: str,
    modelo: int,
    serie: int,
    numero_nfe: int,
    tipo_emissao: int,
    codigo_numerico: int,
) -> Tuple[str, int]:
    """
    Constrói a Chave de Acesso única de 44 dígitos da NF-e / NFC-e.
    Formato:
      cUF (2) + AAMM (4) + CNPJ (14) + mod (2) + serie (3) + nNF (9) + tpEmis (1) + cNF (8) + cDV (1)
    Retorna: (chave_44_digitos, digito_verificador)
    """
    cnpj_limpo = re.sub(r"\D", "", cnpj).zfill(14)
    aamm = data_emissao.strftime("%y%m")

    chave_43 = (
        f"{uf_ibge:02d}"
        f"{aamm}"
        f"{cnpj_limpo}"
        f"{modelo:02d}"
        f"{serie:03d}"
        f"{numero_nfe:09d}"
        f"{tipo_emissao:01d}"
        f"{codigo_numerico:08d}"
    )

    dv = calcular_dv_chave(chave_43)
    return f"{chave_43}{dv}", dv


def montar_ini_nfce(
    config: Dict[str, Any],
    venda_id: int,
    itens: List[Dict[str, Any]],
    valor_total: float,
    tipo_emissao: int,           # 1 = Normal, 9 = Contingência Offline
    numero_nfce: int,
    serie: int,
    codigo_numerico: int,
    data_emissao: datetime,
    forma_pagamento: str = "01", # 01=Dinheiro, 03=Crédito, 04=Débito, 17=PIX
    troco: float = 0.0,
    valor_recebido: float = 0.0,
) -> Tuple[str, str]:
    """
    Gera o documento no formato padrão INI aceito pelo ACBrMonitorPLUS para a NFC-e (modelo 65).
    Retorna: (conteudo_ini_string, chave_acesso_44)
    """
    uf_ibge = int(config.get("ibge_uf") or config.get("fiscal_ibge_uf") or 35)
    cnpj = config.get("cnpj") or config.get("fiscal_cnpj") or ""
    ie = config.get("ie") or config.get("fiscal_ie") or ""
    razao = config.get("razao_social") or config.get("fiscal_razao_social") or "EMPRESA VAREJISTA LTDA"
    fantasia = config.get("nome_fantasia") or config.get("fiscal_nome_fantasia") or razao
    crt = config.get("crt") or config.get("fiscal_crt") or "1"
    ambiente = config.get("ambiente") or config.get("fiscal_ambiente") or "2"

    chave_acesso, _ = gerar_chave_acesso(
        uf_ibge=uf_ibge,
        data_emissao=data_emissao,
        cnpj=cnpj,
        modelo=65,
        serie=serie,
        numero_nfe=numero_nfce,
        tipo_emissao=tipo_emissao,
        codigo_numerico=codigo_numerico,
    )

    dh_formatada = data_emissao.strftime("%d/%m/%Y %H:%M:%S")

    ini = [
        "[NOTA_FISCAL]",
        "Versao=4.00",
        "",
        "[Identificacao]",
        "NaturezaOperacao=VENDA AO CONSUMIDOR",
        "Modelo=65",
        f"Serie={serie}",
        f"Codigo={codigo_numerico:08d}",
        f"Numero={numero_nfce}",
        f"Emissao={dh_formatada}",
        f"Saida={dh_formatada}",
        "Tipo=1",
        f"tpAmb={ambiente}",
        f"tpEmis={tipo_emissao}",
        "FinNFe=1",
        "indFinal=1",
        "indPres=1",
    ]

    # Regras e campos obrigatórios para Contingência Offline (tpEmis = 9)
    if tipo_emissao == 9:
        ini.append(f"dhCont={dh_formatada}")
        ini.append("xJust=Falha de comunicacao com a SEFAZ autorizadora")

    # Identificação do Emitente
    ini.extend([
        "",
        "[Emitente]",
        f"CNPJ={re.sub(r'\\D', '', cnpj)}",
        f"IE={re.sub(r'\\D', '', ie)}",
        f"RazaoSocial={razao}",
        f"Fantasia={fantasia}",
        f"CRT={crt}",
    ])

    # Destinatário (Consumidor Final não identificado no balcão por padrão)
    ini.extend([
        "",
        "[Destinatario]",
        "indIEDest=9",
    ])

    # Itens / Produtos da Venda
    total_produtos = 0.0
    for i, it in enumerate(itens, start=1):
        qtd = float(it.get("quantidade", 1))
        preco_unit = float(it.get("preco_unitario", 0.0))
        item_total = round(qtd * preco_unit, 2)
        total_produtos += item_total

        ncm = str(it.get("ncm") or "21069090").strip().replace(".", "")
        cest = str(it.get("cest") or "").strip().replace(".", "")
        cfop = str(it.get("cfop") or "5102").strip()
        origem = int(it.get("origem") or 0)
        csosn = str(it.get("csosn") or "102").strip()
        unidade = str(it.get("unidade") or "UN").strip()
        desc = str(it.get("produto_nome") or "PRODUTO").strip()

        ini.extend([
            "",
            f"[Produto{i:03d}]",
            f"Codigo={it.get('produto_id', i)}",
            f"Descricao={desc}",
            f"NCM={ncm}",
            f"CFOP={cfop}",
            f"Unidade={unidade}",
            f"Quantidade={qtd:.4f}",
            f"ValorUnitario={preco_unit:.4f}",
            f"ValorTotal={item_total:.2f}",
        ])

        if cest:
            ini.append(f"CEST={cest}")

        # Tributação do Item (Simples Nacional vs Regime Normal)
        if crt == "1":
            ini.extend([
                "",
                f"[ICMS{i:03d}]",
                f"CSOSN={csosn}",
                f"Origem={origem}",
            ])
        else:
            ini.extend([
                "",
                f"[ICMS{i:03d}]",
                "CST=00",
                f"Origem={origem}",
            ])

        # PIS e COFINS padrão monofásico/não tributado no Simples
        ini.extend([
            "",
            f"[PIS{i:03d}]",
            "CST=49",
            f"ValorBase={item_total:.2f}",
            "Aliquota=0.00",
            "Valor=0.00",
            "",
            f"[COFINS{i:03d}]",
            "CST=49",
            f"ValorBase={item_total:.2f}",
            "Aliquota=0.00",
            "Valor=0.00",
        ])

    # Totais da Nota Fiscal
    ini.extend([
        "",
        "[Total]",
        f"ValorProduto={total_produtos:.2f}",
        f"ValorNota={valor_total:.2f}",
        "ValorDesconto=0.00",
        "ValorOutrasDespesas=0.00",
    ])

    # Detalhamento de Pagamento
    v_pago = valor_recebido if valor_recebido > valor_total else valor_total
    ini.extend([
        "",
        "[Pagamento001]",
        f"FormaPagamento={forma_pagamento}",
        f"Valor={v_pago:.2f}",
    ])

    if troco > 0:
        ini.append(f"ValorTroco={troco:.2f}")

    # Informações Complementares e Alerta Obrigatório de Contingência
    ini.extend([
        "",
        "[DadosAdicionais]",
    ])
    if tipo_emissao == 9:
        ini.append("InfsAdic=EMITIDA EM CONTINGÊNCIA - Pendente de autorização. Documento emitido por ME ou EPP optante pelo Simples Nacional.")
    else:
        ini.append("InfsAdic=Documento emitido por ME ou EPP optante pelo Simples Nacional. Não gera direito a crédito fiscal de IPI.")

    return "\n".join(ini), chave_acesso
