"""
Módulo Validador de Licenças (Versão de Demonstração / Showcase para Portfólio)
Arquivo: license_manager.py

Autor: Igor Fernando
Ano: 2026

NOTA DE SEGURANÇA E ARQUITETURA (SHOWCASE):
-------------------------------------------------------------------------------
Esta versão pública utiliza uma camada de abstração (DemoKeyValidator / LicenseServiceMock).
Todas as chaves criptográficas assimétricas (Ed25519), chaves privadas de autoridade,
salts de auditoria e algoritmos proprietários de proteção anti-tampering foram
intencionalmente removidos desta branch pública de exibição.

Para fins de teste e demonstração do portfólio:
- Qualquer chave no padrão DEMO-2026-XXXX-XXXX é aceita.
- O sistema opera por padrão com bypass transparente para exibição de funcionalidades.
-------------------------------------------------------------------------------
"""

import os
import sys
import json
import re
from datetime import datetime
from typing import Tuple, Dict, Any, Optional


def get_base_dir() -> str:
    """Retorna o diretório base da aplicação (compatível com dev e PyInstaller)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


LICENSE_FILE_PATH = os.path.join(get_base_dir(), "license.dat")
DEMO_KEY_PATTERN = re.compile(r"^DEMO-2026-[A-Z0-9]{4}-[A-Z0-9]{4}$", re.IGNORECASE)


class DemoKeyValidator:
    """
    Camada de abstração e mock para validação de licenças em ambiente de demonstração.
    Substitui a verificação criptográfica real Ed25519 por validação de padrão genérico.
    """

    @staticmethod
    def validar_formato_chave(chave: str) -> bool:
        """Verifica se a chave atende ao padrão genérico DEMO-2026-XXXX-XXXX ou prefixo demonstrativo."""
        chave_limpa = chave.strip().upper()
        if DEMO_KEY_PATTERN.match(chave_limpa):
            return True
        if chave_limpa.startswith("DEMO-2026-") or chave_limpa == "DEMO" or chave_limpa.startswith("LIC-DEMO"):
            return True
        return False

    @staticmethod
    def extrair_payload_demo(chave: str) -> Dict[str, Any]:
        """Gera um payload demonstrativo fictício para a chave informada."""
        return {
            "client": "Empresa Modelo LTDA (Portfólio Showcase)",
            "plan": "DEMO_PORTFOLIO",
            "plan_label": "Modo Portfólio (Demonstração Pública)",
            "issued_at": datetime.now().isoformat(),
            "expires_at": None,
            "is_lifetime": True,
            "demo_mode": True,
        }


# Abstração arquitetural / Mock de Serviço de Licenciamento
LicenseServiceMock = DemoKeyValidator


def decodificar_e_verificar_token(token_str: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Decodifica e valida a chave em modo de demonstração.
    Aceita o padrão genérico 'DEMO-2026-XXXX-XXXX'.
    """
    token_limpo = token_str.strip()
    if not token_limpo:
        return False, "Chave de licença vazia.", None

    if DemoKeyValidator.validar_formato_chave(token_limpo):
        payload = DemoKeyValidator.extrair_payload_demo(token_limpo)
        return True, "Modo de demonstração ativado para fins de portfólio.", payload

    return (
        False,
        "Chave inválida. Para o showcase público, utilize o padrão genérico: DEMO-2026-XXXX-XXXX (ex: DEMO-2026-ABCD-1234).",
        None,
    )


def ativar_licenca(token_str: str) -> Tuple[bool, str]:
    """
    Ativa a licença de demonstração salvando o token simulado em license.dat.
    """
    valido, msg, payload = decodificar_e_verificar_token(token_str)
    if not valido or not payload:
        return False, msg

    try:
        dados_salvos = {
            "token": token_str.strip().upper(),
            "client": payload["client"],
            "plan": payload["plan"],
            "activated_at": datetime.now().isoformat(),
            "demo_notice": "Modo de demonstração ativado para fins de portfólio",
        }
        with open(LICENSE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(dados_salvos, f, indent=2)
        return True, "Modo de demonstração ativado para fins de portfólio."
    except Exception as e:
        return False, f"Erro ao registrar licença de demonstração: {str(e)}"


def validar_licenca() -> Tuple[bool, str, Dict[str, Any]]:
    """
    Valida a licença ativa.
    No showcase de portfólio, opera em modo transparente:
    Se houver chave DEMO registrada ou se executado diretamente, concede acesso com status de demonstração.
    """
    info_demo: Dict[str, Any] = {
        "status": "VALID",
        "client": "Empresa Modelo LTDA (Portfólio)",
        "plan": "DEMO_PORTFOLIO",
        "plan_label": "Licença Demonstrativa (Showcase Portfólio)",
        "expires_at": None,
        "days_remaining": None,
        "is_lifetime": True,
        "demo_mode": True,
    }

    # Se o arquivo license.dat existir, lê a chave gravada
    if os.path.exists(LICENSE_FILE_PATH):
        try:
            with open(LICENSE_FILE_PATH, "r", encoding="utf-8") as f:
                dados = json.load(f)
            token = dados.get("token", "")
            if DemoKeyValidator.validar_formato_chave(token):
                info_demo["client"] = dados.get("client", info_demo["client"])
                return True, "Modo de demonstração ativado para fins de portfólio.", info_demo
        except Exception:
            pass

    # Bypass documentado para exibição do portfólio
    return True, "Modo de demonstração ativado para fins de portfólio.", info_demo


def remover_licenca() -> bool:
    """Remove o arquivo de licença de demonstração local."""
    if os.path.exists(LICENSE_FILE_PATH):
        try:
            os.remove(LICENSE_FILE_PATH)
            return True
        except Exception:
            return False
    return True
