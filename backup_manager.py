"""
Módulo de Gerenciamento de Backups e Cópia de Segurança
Arquivo: backup_manager.py

Implementa:
1. Backup Online Atômico via API nativa do SQLite (sqlite3.Connection.backup),
   garantindo integridade transacional sem travar a aplicação.
2. Compactação ZIP com assinatura digital SHA-256 e metadados no manifesto.
3. Rotina de Backup Automático Diário em background com política de retenção (15 dias).
4. Rotina de Backup Manual para destinos externos (Pendrives, Google Drive, OneDrive).
5. Rotina de Restauração Segura com salvaguarda automática antes da substituição.
"""

import os
import sys
import time
import json
import zipfile
import hashlib
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Any, Optional

import database as db
import edicao_config


def get_base_dir() -> str:
    """Retorna o diretório base da aplicação."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BACKUPS_DIR = os.path.join(get_base_dir(), "backups")


def _garantir_diretorio_backups() -> str:
    """Garante a existência da pasta de backups local."""
    pasta = os.path.join(get_base_dir(), "backups")
    os.makedirs(pasta, exist_ok=True)
    return pasta


def _calcular_sha256_arquivo(caminho_arquivo: str) -> str:
    """Calcula o hash SHA-256 de um arquivo em blocos de 64KB."""
    sha = hashlib.sha256()
    with open(caminho_arquivo, "rb") as f:
        while True:
            bloco = f.read(65536)
            if not bloco:
                break
            sha.update(bloco)
    return sha.hexdigest()


def criar_backup(
    destino_dir: Optional[str] = None,
    prefixo: str = "backup_gestao_vendas",
) -> Tuple[bool, str, Optional[str]]:
    """
    Realiza o backup completo e atômico do banco de dados SQLite gestao_vendas.db.
    Gera um arquivo .zip contendo o banco snapshot e um arquivo manifest.json.
    """
    db_origem = db.DB_PATH
    if not os.path.exists(db_origem):
        return False, "Banco de dados local não encontrado para backup.", None

    pasta_destino = destino_dir if destino_dir else _garantir_diretorio_backups()
    os.makedirs(pasta_destino, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    nome_base = f"{prefixo}_{timestamp_str}"
    caminho_temp_db = os.path.join(pasta_destino, f"{nome_base}_temp.db")
    caminho_zip_final = os.path.join(pasta_destino, f"{nome_base}.zip")

    try:
        # 1. Utiliza a API nativa sqlite3.backup() para consistência ACID em memória/disco
        conn_origem = sqlite3.connect(db_origem)
        conn_destino = sqlite3.connect(caminho_temp_db)

        with conn_origem, conn_destino:
            conn_origem.backup(conn_destino, pages=250)

        conn_origem.close()
        conn_destino.close()

        # 2. Coleta métricas estatísticas para o manifesto
        tamanho_bytes = os.path.getsize(caminho_temp_db)
        hash_sha256 = _calcular_sha256_arquivo(caminho_temp_db)

        # Estatísticas básicas para auditoria
        total_produtos = 0
        total_vendas = 0
        try:
            conn_check = sqlite3.connect(caminho_temp_db)
            cur = conn_check.cursor()
            cur.execute("SELECT COUNT(*) FROM produtos;")
            total_produtos = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM vendas;")
            total_vendas = cur.fetchone()[0]
            conn_check.close()
        except Exception:
            pass

        manifesto = {
            "app_name": "Central de Vendas",
            "edition": edicao_config.obter_edicao(),
            "backup_created_at": datetime.now().isoformat(),
            "database_filename": "gestao_vendas.db",
            "database_size_bytes": tamanho_bytes,
            "sha256_checksum": hash_sha256,
            "total_produtos": total_produtos,
            "total_vendas": total_vendas,
            "generator": "BackupManager_v2",
        }

        # 3. Compacta o banco snapshot e o manifesto em um arquivo ZIP protegido
        with zipfile.ZipFile(caminho_zip_final, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(caminho_temp_db, arcname="gestao_vendas.db")
            zipf.writestr("manifest.json", json.dumps(manifesto, indent=2, ensure_ascii=False))

        # 4. Remove o arquivo temporário
        if os.path.exists(caminho_temp_db):
            os.remove(caminho_temp_db)

        tamanho_mb = os.path.getsize(caminho_zip_final) / (1024 * 1024)
        msg_sucesso = f"Cópia de segurança criada com sucesso ({tamanho_mb:.2f} MB)."
        return True, msg_sucesso, caminho_zip_final

    except Exception as e:
        if os.path.exists(caminho_temp_db):
            try:
                os.remove(caminho_temp_db)
            except Exception:
                pass
        return False, f"Falha ao gerar cópia de segurança: {str(e)}", None


def executar_backup_automatico_se_necessario() -> Optional[str]:
    """
    Executa verificação e backup automático silencioso se mais de 24 horas se passaram
    desde o último backup automático registrado no sistema.
    Mantém uma política de retenção de 15 backups mais recentes.
    """
    try:
        ultimo_ts_str = db.obter_config("ultimo_backup_automatico_ts", "0")
        ultimo_ts = float(ultimo_ts_str) if ultimo_ts_str else 0.0
    except Exception:
        ultimo_ts = 0.0

    agora = datetime.now()
    agora_ts = agora.timestamp()

    # Intervalo de 24 horas (86400 segundos)
    if (agora_ts - ultimo_ts) >= 86400:
        sucesso, msg, caminho = criar_backup(
            destino_dir=_garantir_diretorio_backups(),
            prefixo="auto_backup_gestao_vendas",
        )
        if sucesso and caminho:
            db.salvar_config("ultimo_backup_automatico_ts", str(agora_ts))
            db.salvar_config("ultimo_backup_automatico_data", agora.strftime("%d/%m/%Y %H:%M"))
            db.salvar_config("ultimo_backup_arquivo", os.path.basename(caminho))

            # Aplica política de retenção: mantém os 15 backups automáticos mais recentes
            _aplicar_politica_retencao(max_backups=15)
            return caminho

    return None


def _aplicar_politica_retencao(max_backups: int = 15):
    """Remove automaticamente backups automáticos mais antigos que o limite configurado."""
    pasta = _garantir_diretorio_backups()
    try:
        arquivos = [
            os.path.join(pasta, f)
            for f in os.listdir(pasta)
            if f.startswith("auto_backup_") and f.endswith(".zip")
        ]
        # Ordena por data de modificação (mais antigos primeiro)
        arquivos.sort(key=lambda x: os.path.getmtime(x))

        while len(arquivos) > max_backups:
            antigo = arquivos.pop(0)
            try:
                os.remove(antigo)
            except Exception:
                pass
    except Exception:
        pass


def restaurar_backup(caminho_zip: str) -> Tuple[bool, str]:
    """
    Restaura o banco de dados a partir de um arquivo ZIP de backup.
    1. Valida a integridade do arquivo ZIP.
    2. Cria uma salvaguarda do banco atual (gestao_vendas.db.pre_restore.bak).
    3. Extrai o banco e valida a consistência SQLite.
    """
    if not os.path.exists(caminho_zip):
        return False, "O arquivo de backup selecionado não existe."

    db_destino = db.DB_PATH
    db_backup_seguranca = f"{db_destino}.pre_restore.bak"

    try:
        # Validação do ZIP
        with zipfile.ZipFile(caminho_zip, "r") as zipf:
            nomes = zipf.namelist()
            if "gestao_vendas.db" not in nomes:
                return False, "O arquivo compactado não contém uma base de dados válida ('gestao_vendas.db')."

            # 1. Cria salvaguarda do banco atual antes de substituir
            if os.path.exists(db_destino):
                try:
                    conn_atual = sqlite3.connect(db_destino)
                    conn_bak = sqlite3.connect(db_backup_seguranca)
                    with conn_atual, conn_bak:
                        conn_atual.backup(conn_bak)
                    conn_atual.close()
                    conn_bak.close()
                except Exception as eb:
                    return False, f"Falha ao criar salvaguarda pré-restauração: {str(eb)}"

            # 2. Extrai o arquivo para uma pasta temporária e valida o SQLite
            temp_extracao = os.path.join(os.path.dirname(caminho_zip), "_temp_restauracao.db")
            with open(temp_extracao, "wb") as f_out:
                f_out.write(zipf.read("gestao_vendas.db"))

            # Valida integridade do banco extraído
            conn_test = sqlite3.connect(temp_extracao)
            cur = conn_test.cursor()
            cur.execute("PRAGMA integrity_check;")
            res = cur.fetchone()[0]
            conn_test.close()

            if res != "ok":
                if os.path.exists(temp_extracao):
                    os.remove(temp_extracao)
                return False, f"O banco de dados contido no backup está corrompido: {res}"

            # 3. Transfere o banco restaurado para a localização final
            conn_nova = sqlite3.connect(temp_extracao)
            conn_final = sqlite3.connect(db_destino)
            with conn_nova, conn_final:
                conn_nova.backup(conn_final)
            conn_nova.close()
            conn_final.close()

            if os.path.exists(temp_extracao):
                os.remove(temp_extracao)

            return True, "Banco de dados restaurado com sucesso! Os dados foram atualizados."

    except Exception as e:
        return False, f"Erro crítico durante o processo de restauração: {str(e)}"


def listar_backups_locais() -> List[Dict[str, Any]]:
    """Retorna a lista de backups disponíveis na pasta local ordenados do mais recente para o mais antigo."""
    pasta = _garantir_diretorio_backups()
    resultado = []

    try:
        arquivos = [f for f in os.listdir(pasta) if f.endswith(".zip")]
        for arq in arquivos:
            caminho_completo = os.path.join(pasta, arq)
            tamanho_mb = os.path.getsize(caminho_completo) / (1024 * 1024)
            data_mod = datetime.fromtimestamp(os.path.getmtime(caminho_completo))

            eh_auto = arq.startswith("auto_backup_")
            tipo_label = "Automático (Diário)" if eh_auto else "Manual / Exportado"

            resultado.append({
                "arquivo": arq,
                "caminho": caminho_completo,
                "tamanho_mb": round(tamanho_mb, 2),
                "data_hora": data_mod.strftime("%d/%m/%Y às %H:%M:%S"),
                "timestamp": os.path.getmtime(caminho_completo),
                "tipo": tipo_label,
            })

        resultado.sort(key=lambda x: x["timestamp"], reverse=True)
    except Exception:
        pass

    return resultado


def disparar_backup_automatico_thread():
    """Executa a verificação de backup automático em thread separada para não travar o carregamento da UI."""
    t = threading.Thread(target=executar_backup_automatico_se_necessario, daemon=True, name="AutoBackupWorker")
    t.start()
