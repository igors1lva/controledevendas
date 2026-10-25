"""
Módulo de Configuração de Edições do Software
Arquivo: edicao_config.py

Define as três edições comerciais independentes da aplicação:
1. NAO_FISCAL : Software de Gestão Comercial e Controle Interno (sem módulos fiscais SEFAZ).
2. FISCAL     : Software Emissor Fiscal Dedicado (NFC-e Modelo 65 via ACBr com contingência).
3. COMPLETO   : Edição Híbrida / Dual (permite alternar entre Não-Fiscal e Fiscal via senha administrativa).
"""

from typing import Optional

EDICAO_NAO_FISCAL = "NAO_FISCAL"
EDICAO_FISCAL = "FISCAL"
EDICAO_COMPLETA = "COMPLETO"

# Edição padrão global da instância em execução (definida no startup do app)
_EDICAO_ATUAL: str = EDICAO_COMPLETA


def definir_edicao(edicao: str) -> None:
    """Define a edição ativa para a sessão atual."""
    global _EDICAO_ATUAL
    ed_upper = edicao.strip().upper()
    if ed_upper in (EDICAO_NAO_FISCAL, EDICAO_FISCAL, EDICAO_COMPLETA):
        _EDICAO_ATUAL = ed_upper
    else:
        _EDICAO_ATUAL = EDICAO_COMPLETA


def obter_edicao() -> str:
    """Retorna o identificador da edição atualmente em execução."""
    return _EDICAO_ATUAL


def obter_nome_edicao(edicao: Optional[str] = None) -> str:
    """Retorna o nome amigável e comercial da edição informada ou da atual."""
    ed = edicao.upper() if edicao else _EDICAO_ATUAL
    if ed == EDICAO_NAO_FISCAL:
        return "Central de Vendas • Edição Controle Interno (Não-Fiscal)"
    elif ed == EDICAO_FISCAL:
        return "Central de Vendas • Edição Fiscal NFC-e (SEFAZ)"
    return "Central de Vendas • Edição Completa (Dual Fiscal / Não-Fiscal)"


def permite_modulo_fiscal(edicao: Optional[str] = None) -> bool:
    """
    Retorna True se a edição possui recursos fiscais (NFC-e, ACBr, SEFAZ).
    Na edição NAO_FISCAL, retorna False (esconde telas e atalhos fiscais).
    """
    ed = edicao.upper() if edicao else _EDICAO_ATUAL
    return ed in (EDICAO_FISCAL, EDICAO_COMPLETA)


def permite_alternancia_regime(edicao: Optional[str] = None) -> bool:
    """
    Retorna True se o usuário/administrador pode alternar entre Não-Fiscal e Fiscal.
    Apenas a edição COMPLETA permite alternância livre mediante senha administrativa.
    """
    ed = edicao.upper() if edicao else _EDICAO_ATUAL
    return ed == EDICAO_COMPLETA


def obter_modo_fixo(edicao: Optional[str] = None) -> Optional[str]:
    """
    Retorna o modo operacional fixo da edição ('NAO_FISCAL' ou 'FISCAL_NFCE'),
    ou None se a edição for COMPLETA (modo dinâmico armazenado no banco).
    """
    ed = edicao.upper() if edicao else _EDICAO_ATUAL
    if ed == EDICAO_NAO_FISCAL:
        return "NAO_FISCAL"
    elif ed == EDICAO_FISCAL:
        return "FISCAL_NFCE"
    return None
