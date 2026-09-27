"""
fiscal/acbr_adapter.py
Driver de comunicação TCP Socket com o ACBrMonitorPLUS.

Permite envio e recebimento de comandos padronizados do Projeto ACBr para:
- Consulta de status de serviço da SEFAZ (NFE.StatusServico)
- Emissão síncrona/assíncrona de NFC-e (NFE.CriarEnviarNFe)
- Assinatura digital local de XML (NFE.AssinarNFe)
- Impressão de cupom DANFE NFC-e térmico EscPOS / Fortes (NFE.ImprimirDANFE)
"""

import socket
import re
import logging
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger("ACBrAdapter")


class ACBrAdapter:
    """Cliente Socket de integração de alto desempenho com o ACBrMonitorPLUS."""

    def __init__(self, host: str = "127.0.0.1", port: int = 3434, timeout: float = 4.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def executar_comando(self, comando: str, timeout: Optional[float] = None) -> Tuple[bool, str]:
        """
        Envia um comando para o ACBrMonitorPLUS via TCP Socket e processa a resposta.
        Padrão de finalização do protocolo ACBr: '\r\n.\r\n'
        """
        tempo_limite = timeout if timeout is not None else self.timeout
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(tempo_limite)
                s.connect((self.host, self.port))

                # Leitura do banner de boas-vindas do ACBr
                _ = s.recv(1024)

                # Envio do comando formatado
                cmd_formatado = f"{comando.strip()}\r\n.\r\n".encode("latin1", errors="replace")
                s.sendall(cmd_formatado)

                # Recepção contínua da resposta
                resposta_bytes = b""
                while True:
                    pedaco = s.recv(4096)
                    if not pedaco:
                        break
                    resposta_bytes += pedaco
                    if b"\r\n.\r\n" in resposta_bytes or resposta_bytes.endswith(b"\r\n"):
                        break

                texto = resposta_bytes.decode("latin1", errors="replace").strip()
                if texto.startswith("OK:"):
                    return True, texto[3:].strip()
                elif texto.startswith("ERRO:"):
                    return False, texto[5:].strip()
                return True, texto

        except (socket.timeout, TimeoutError):
            logger.warning(f"Timeout ({tempo_limite}s) atingido na comunicação com ACBr / SEFAZ.")
            return False, "TIMEOUT_SEFAZ: Tempo limite de comunicação com a SEFAZ excedido."
        except ConnectionRefusedError:
            logger.error("ACBrMonitorPLUS não está ativo ou porta 3434 inacessível.")
            return False, "CONEXAO_RECUSADA: ACBrMonitorPLUS não está em execução no computador."
        except Exception as e:
            logger.error(f"Erro inesperado no Socket ACBr: {e}")
            return False, f"FALHA_SOCKET: {str(e)}"

    def testar_comunicacao(self) -> Tuple[bool, str]:
        """Verifica se o ACBrMonitorPLUS responde localmente."""
        return self.executar_comando("ACBr.Restaurar", timeout=2.0)

    def consultar_status_servico(self) -> Tuple[bool, str, int]:
        """
        Consulta o status operacional do WebService da SEFAZ do estado configurado.
        Retorna: (sucesso, mensagem_ou_retorno, cStat)
        cStat 107 = Serviço em Operação.
        """
        ok, resp = self.executar_comando("NFE.StatusServico", timeout=4.0)
        if not ok:
            return False, resp, 0

        cstat = 0
        match_cstat = re.search(r"cStat=(\d+)", resp)
        if match_cstat:
            cstat = int(match_cstat.group(1))
        elif "107" in resp or "Serviço em Operação" in resp:
            cstat = 107

        return True, resp, cstat

    def criar_enviar_nfce(
        self,
        conteudo_ou_caminho_ini: str,
        lote: int = 1,
        imprimir: bool = False,
        sincrono: bool = True,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Envia a NFC-e para validação e autorização pela SEFAZ.
        Comando ACBr: NFE.CriarEnviarNFe(cIniOuPath, nLote, [bImprime], [bSincrono])
        """
        b_imp = "1" if imprimir else "0"
        b_sinc = "1" if sincrono else "0"
        cmd = f'NFE.CriarEnviarNFe("{conteudo_ou_caminho_ini}", {lote}, {b_imp}, {b_sinc})'

        ok, resp = self.executar_comando(cmd, timeout=timeout or self.timeout)

        resultado = {
            "sucesso": ok,
            "cStat": 0,
            "motivo": resp,
            "protocolo": "",
            "chave": "",
            "caminho_xml": "",
            "resposta_bruta": resp,
        }

        if not ok:
            return resultado

        # Extração de parâmetros fundamentais do retorno
        match_cstat = re.search(r"cStat=(\d+)", resp)
        if match_cstat:
            resultado["cStat"] = int(match_cstat.group(1))

        match_prot = re.search(r"nProt=(\d+)", resp)
        if match_prot:
            resultado["protocolo"] = match_prot.group(1)

        match_ch = re.search(r"chNFe=(\d{44})", resp)
        if match_ch:
            resultado["chave"] = match_ch.group(1)

        match_xml = re.search(r"Caminho=(.*?\.xml)", resp, re.IGNORECASE)
        if match_xml:
            resultado["caminho_xml"] = match_xml.group(1).strip()

        match_xmotivo = re.search(r"xMotivo=(.*?)(?:\r|\n|$)", resp)
        if match_xmotivo:
            resultado["motivo"] = match_xmotivo.group(1).strip()

        return resultado

    def imprimir_danfe(self, caminho_xml: str) -> Tuple[bool, str]:
        """Solicita a impressão da DANFE NFC-e na impressora térmica configurada no ACBr."""
        cmd = f'NFE.ImprimirDANFE("{caminho_xml}")'
        return self.executar_comando(cmd, timeout=5.0)

    def cancelar_nfce(self, chave_acesso: str, motivo: str, protocolo: str, cnpj: str) -> Dict[str, Any]:
        """Cancela uma NFC-e previamente autorizada dentro do prazo legal."""
        cmd = f'NFE.CancelarNFe("{chave_acesso}", "{motivo}", "{cnpj}", "{protocolo}")'
        ok, resp = self.executar_comando(cmd, timeout=5.0)
        return {"sucesso": ok, "resposta": resp}
