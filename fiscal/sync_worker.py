"""
fiscal/sync_worker.py
Silent Background Sync Worker: Monitoramento e transmissão transparente de NFC-e em contingência.

Executa em thread daemon em segundo plano:
1. Realiza ping leve para verificar se a SEFAZ está operacional (cStat = 107).
2. Se online, localiza notas com status 'PENDENTE_ENVIO' emitidas em contingência.
3. Transmite os lotes pendentes via ACBr.
4. Ao autorizar (cStat = 100), atualiza o banco local com o protocolo e substitui o status.
5. Em caso de rejeição por erro cadastral/tributário, atualiza para 'REJEITADA'.
"""

import time
import threading
import logging
from typing import Callable, Optional, Dict, Any, List

import database as db
from .acbr_adapter import ACBrAdapter

logger = logging.getLogger("FiscalSyncWorker")


class FiscalSyncWorker:
    """Worker autônomo para sincronização de notas fiscais emitidas em contingência."""

    def __init__(self, intervalo_segundos: int = 120, on_status_updated: Optional[Callable] = None):
        self.intervalo = intervalo_segundos
        self.on_status_updated = on_status_updated
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._em_execucao = False

    def start(self):
        """Inicia a execução do worker em segundo plano."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="FiscalSyncWorkerThread", daemon=True)
        self._thread.start()
        logger.info("FiscalSyncWorker iniciado com sucesso.")

    def stop(self):
        """Para a thread de sincronização de forma suave."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("FiscalSyncWorker finalizado.")

    def sincronizar_agora(self) -> Dict[str, int]:
        """Dispara imediatamente um ciclo de sincronização síncrona."""
        return self._processar_pendencias()

    def _loop(self):
        while not self._stop_event.is_set():
            try:
                self._processar_pendencias()
            except Exception as e:
                logger.error(f"Erro no ciclo de sincronização fiscal: {e}")

            # Aguarda o intervalo ou interrupção do evento
            self._stop_event.wait(self.intervalo)

    def _processar_pendencias(self) -> Dict[str, int]:
        resultado = {"autorizadas": 0, "rejeitadas": 0, "pendentes": 0}

        # 1. Verifica se o sistema está em modo fiscal
        modo = db.obter_modo_emissao()
        if modo != "FISCAL_NFCE":
            return resultado

        # 2. Busca vendas pendentes de envio
        pendentes = db.obter_vendas_fiscais_pendentes()
        resultado["pendentes"] = len(pendentes)
        if not pendentes:
            return resultado

        # 3. Ping leve na SEFAZ para confirmar conectividade
        config = db.obter_configuracoes_fiscais()
        adapter = ACBrAdapter(
            host=config.get("acbr_host", "127.0.0.1"),
            port=config.get("acbr_porta", 3434),
            timeout=3.0,
        )

        ok_sefaz, _, cstat = adapter.consultar_status_servico()
        if not ok_sefaz or cstat != 107:
            logger.info("SEFAZ continua offline ou inacessível. Mantendo vendas em contingência para a próxima rodada.")
            return resultado

        # 4. Transmissão sequencial dos lotes pendentes
        for nf in pendentes:
            if self._stop_event.is_set():
                break

            venda_id = nf["venda_id"]
            caminho_xml_ini = nf.get("caminho_xml_assinado", "")

            if not caminho_xml_ini:
                continue

            try:
                resp = adapter.criar_enviar_nfce(
                    conteudo_ou_caminho_ini=caminho_xml_ini,
                    lote=venda_id,
                    imprimir=False,
                    sincrono=True,
                    timeout=5.0,
                )

                cstat_resp = resp.get("cStat", 0)

                # AUTORIZAÇÃO CONCLUÍDA
                if resp.get("sucesso") and cstat_resp == 100:
                    db.atualizar_status_fiscal(
                        venda_id=venda_id,
                        status="AUTORIZADA",
                        cstat=100,
                        motivo=resp.get("motivo", "Autorizado o uso da NF-e"),
                        protocolo=resp.get("protocolo", ""),
                        caminho_xml_protocolado=resp.get("caminho_xml", ""),
                    )
                    resultado["autorizadas"] += 1
                    logger.info(f"Venda #{venda_id} (NFC-e contingência) AUTORIZADA com sucesso!")

                # ERROS TEMPORÁRIOS DE SEFAZ (MANTÉM EM CONTINGÊNCIA)
                elif cstat_resp in (108, 109, 999) or "TIMEOUT" in resp.get("motivo", ""):
                    logger.warning(f"Instabilidade temporária da SEFAZ na venda #{venda_id}. Reagendando.")
                    continue

                # REJEIÇÃO TRIBUTÁRIA OU DEFINITIVA
                elif cstat_resp > 0:
                    db.atualizar_status_fiscal(
                        venda_id=venda_id,
                        status="REJEITADA",
                        cstat=cstat_resp,
                        motivo=resp.get("motivo", "Rejeição da SEFAZ"),
                    )
                    resultado["rejeitadas"] += 1
                    logger.error(f"Venda #{venda_id} REJEITADA pela SEFAZ: {cstat_resp} - {resp.get('motivo')}")

            except Exception as ex:
                logger.error(f"Exceção ao sincronizar venda #{venda_id}: {ex}")

        # Se houver atualizações e callback configurado, notifica a UI
        if (resultado["autorizadas"] > 0 or resultado["rejeitadas"] > 0) and self.on_status_updated:
            try:
                self.on_status_updated(resultado)
            except Exception:
                pass

        return resultado
