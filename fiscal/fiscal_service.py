"""
fiscal/fiscal_service.py
Serviço orquestrador da emissão fiscal com arquitetura Offline-First.

Controla:
1. Respeito ao modo configurado pelo administrador: 'NAO_FISCAL' vs 'FISCAL_NFCE'.
2. Emissão síncrona Normal com timeout curto (4.0s).
3. Fallback instantâneo para Contingência Offline (tpEmis = 9) em caso de falha de conexão/SEFAZ.
4. Armazenamento e isolamento de arquivos em fiscal_storage/.
"""

import os
import random
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

import database as db
from .acbr_adapter import ACBrAdapter
from .nfce_builder import montar_ini_nfce

logger = logging.getLogger("FiscalService")


class FiscalService:
    """Fachada de operações fiscais do sistema PDV."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.storage_dir = os.path.join(base_dir, "fiscal_storage")
        else:
            self.storage_dir = os.path.join(db.get_base_dir(), "fiscal_storage")

        self._garantir_diretorios()
        self.config = db.obter_configuracoes_fiscais()
        self.adapter = ACBrAdapter(
            host=self.config.get("acbr_host", "127.0.0.1"),
            port=self.config.get("acbr_porta", 3434),
            timeout=4.0,
        )

    def _garantir_diretorios(self):
        """Cria as pastas locais organizadas para arquivamento dos documentos fiscais."""
        subpastas = [
            "xmls/autorizados",
            "xmls/contingencia",
            "xmls/cancelados",
            "temp",
            "logs",
        ]
        for sub in subpastas:
            caminho = os.path.join(self.storage_dir, sub.replace("/", os.sep))
            os.makedirs(caminho, exist_ok=True)

    def recarregar_configuracoes(self):
        """Atualiza os parâmetros da empresa e do ACBr em tempo de execução."""
        self.config = db.obter_configuracoes_fiscais()
        self.adapter.host = self.config.get("acbr_host", "127.0.0.1")
        self.adapter.port = self.config.get("acbr_porta", 3434)

    def testar_sefaz(self) -> Tuple[bool, str, int]:
        """Testa o status em tempo real dos servidores da SEFAZ."""
        self.recarregar_configuracoes()
        return self.adapter.consultar_status_servico()

    def emitir_venda_pdv(
        self,
        venda_id: int,
        itens: List[Dict[str, Any]],
        valor_total: float,
        forma_pagamento: str = "01",
        troco: float = 0.0,
        valor_recebido: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Executa a emissão fiscal de uma venda.
        Se o modo for NAO_FISCAL: não faz chamadas fiscais e retorna sucesso gerencial.
        Se o modo for FISCAL_NFCE: tenta envio normal online com fallback para contingência offline.
        """
        self.recarregar_configuracoes()
        modo = self.config.get("modo_emissao", "NAO_FISCAL")

        # -------------------------------------------------------------
        # MODO 1: NÃO FISCAL (Controle Interno - Sem Valor Fiscal)
        # -------------------------------------------------------------
        if modo != "FISCAL_NFCE":
            return {
                "sucesso": True,
                "modo": "NAO_FISCAL",
                "contingencia": False,
                "status": "CONCLUIDA",
                "chave": "",
                "numero_nfce": 0,
                "protocolo": "",
                "mensagem": "Venda concluída em Modo Não-Fiscal (Controle Interno).",
            }

        # -------------------------------------------------------------
        # MODO 2: FISCAL (NFC-e SEFAZ Modelo 65)
        # -------------------------------------------------------------
        cnpj = self.config.get("cnpj", "")
        if not cnpj or len(cnpj) < 14:
            return {
                "sucesso": False,
                "modo": "FISCAL_NFCE",
                "contingencia": False,
                "status": "ERRO_CONFIG",
                "chave": "",
                "numero_nfce": 0,
                "mensagem": "CNPJ da empresa não configurado no Módulo Fiscal. Configure nas preferências administrativas.",
            }

        serie = int(self.config.get("serie", 1))
        numero_nfce, _ = db.obter_proximo_numero_nfce(serie)
        codigo_numerico = random.randint(10000000, 99999999)
        agora = datetime.now()
        dh_str = agora.strftime("%Y-%m-%d %H:%M:%S")

        # 1. TENTATIVA ONLINE: MODO NORMAL (tpEmis = 1) com Timeout Curto (4s)
        try:
            ini_normal, chave_normal = montar_ini_nfce(
                config=self.config,
                venda_id=venda_id,
                itens=itens,
                valor_total=valor_total,
                tipo_emissao=1,
                numero_nfce=numero_nfce,
                serie=serie,
                codigo_numerico=codigo_numerico,
                data_emissao=agora,
                forma_pagamento=forma_pagamento,
                troco=troco,
                valor_recebido=valor_recebido,
            )

            # Salva arquivo INI temporário
            caminho_ini_temp = os.path.join(self.storage_dir, "temp", f"nfce_{venda_id}_normal.ini")
            with open(caminho_ini_temp, "w", encoding="latin1", errors="replace") as f:
                f.write(ini_normal)

            # Transmite para o ACBr/SEFAZ com timeout curto
            resp_envio = self.adapter.criar_enviar_nfce(
                conteudo_ou_caminho_ini=caminho_ini_temp,
                lote=venda_id,
                imprimir=True,
                sincrono=True,
                timeout=4.0,
            )

            # SEFAZ AUTORIZOU EM TEMPO REAL (cStat = 100)
            if resp_envio.get("sucesso") and resp_envio.get("cStat") == 100:
                chave_final = resp_envio.get("chave") or chave_normal
                caminho_xml = resp_envio.get("caminho_xml", "")

                db.gravar_venda_fiscal(
                    venda_id=venda_id,
                    modelo=65,
                    serie=serie,
                    numero_nfce=numero_nfce,
                    chave_acesso=chave_final,
                    tipo_emissao=1,
                    status_fiscal="AUTORIZADA",
                    dh_emissao=dh_str,
                    cstat=100,
                    motivo_status=resp_envio.get("motivo", "Autorizado o uso da NF-e"),
                    protocolo_autorizacao=resp_envio.get("protocolo", ""),
                    dh_autorizacao=dh_str,
                    caminho_xml_protocolado=caminho_xml,
                )

                return {
                    "sucesso": True,
                    "modo": "FISCAL_NFCE",
                    "contingencia": False,
                    "status": "AUTORIZADA",
                    "chave": chave_final,
                    "numero_nfce": numero_nfce,
                    "protocolo": resp_envio.get("protocolo", ""),
                    "mensagem": f"NFC-e nº {numero_nfce} AUTORIZADA com sucesso pela SEFAZ!",
                }

        except Exception as e:
            logger.warning(f"Falha na tentativa de envio normal online da NFC-e: {e}")

        # -------------------------------------------------------------
        # 2. CONTINGÊNCIA OFFLINE (tpEmis = 9): FAILOVER IMEDIATO
        # -------------------------------------------------------------
        logger.info(f"Ativando Contingência Offline para a Venda #{venda_id} (tpEmis=9)...")

        ini_cont, chave_cont = montar_ini_nfce(
            config=self.config,
            venda_id=venda_id,
            itens=itens,
            valor_total=valor_total,
            tipo_emissao=9,
            numero_nfce=numero_nfce,
            serie=serie,
            codigo_numerico=codigo_numerico,
            data_emissao=agora,
            forma_pagamento=forma_pagamento,
            troco=troco,
            valor_recebido=valor_recebido,
        )

        caminho_cont_ini = os.path.join(self.storage_dir, "xmls", "contingencia", f"{chave_cont}-nfe.ini")
        with open(caminho_cont_ini, "w", encoding="latin1", errors="replace") as f:
            f.write(ini_cont)

        # Grava venda fiscal no banco SQLite local com status PENDENTE_ENVIO
        db.gravar_venda_fiscal(
            venda_id=venda_id,
            modelo=65,
            serie=serie,
            numero_nfce=numero_nfce,
            chave_acesso=chave_cont,
            tipo_emissao=9,
            status_fiscal="PENDENTE_ENVIO",
            dh_emissao=dh_str,
            cstat=0,
            motivo_status="EMITIDA EM CONTINGÊNCIA OFFLINE (SEFAZ Indisponível)",
            caminho_xml_assinado=caminho_cont_ini,
            motivo_contingencia="Falha ou indisponibilidade na comunicação com a SEFAZ autorizadora",
        )

        # Solicita impressão do cupom com a tarja obrigatória de contingência
        try:
            self.adapter.imprimir_danfe(caminho_cont_ini)
        except Exception:
            pass

        return {
            "sucesso": True,
            "modo": "FISCAL_NFCE",
            "contingencia": True,
            "status": "PENDENTE_ENVIO",
            "chave": chave_cont,
            "numero_nfce": numero_nfce,
            "protocolo": "",
            "mensagem": f"NFC-e nº {numero_nfce} emitida em CONTINGÊNCIA OFFLINE. Cupom impresso. Sincronização em segundo plano ativada.",
        }
