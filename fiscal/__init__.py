"""
Módulo de Integração Fiscal e Emissão de NFC-e (Modelo 65)
Ecossistema ACBr & Arquitetura Offline-First
"""

from .acbr_adapter import ACBrAdapter
from .nfce_builder import gerar_chave_acesso, calcular_dv_chave, montar_ini_nfce
from .fiscal_service import FiscalService
from .sync_worker import FiscalSyncWorker

__all__ = [
    "ACBrAdapter",
    "gerar_chave_acesso",
    "calcular_dv_chave",
    "montar_ini_nfce",
    "FiscalService",
    "FiscalSyncWorker",
]
