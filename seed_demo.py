"""
Script de Inicialização e População Demonstrativa (Seed Demo)
Arquivo: seed_demo.py

Autor: Igor Fernando
Ano: 2026
Finalidade: Popula o banco local SQLite com dados fictícios para fins de teste e portfólio.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import database as db

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SQL_FILE = os.path.join(PROJECT_ROOT, "seed.demo.sql")


def run_seed():
    print("[*] Inicializando banco de dados...")
    db.init_db()

    if not os.path.exists(SQL_FILE):
        print(f"[ERRO] Arquivo SQL nao encontrado: {SQL_FILE}")
        return

    print("[*] Aplicando dados demonstrativos de seed.demo.sql...")
    with open(SQL_FILE, "r", encoding="utf-8") as f:
        sql_content = f.read()

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.executescript(sql_content)
        conn.commit()

    print("[OK] Banco de dados populado com sucesso com produtos e configuracoes modelo!")
    print("[OK] Pronto para execucao: python app.py")


if __name__ == "__main__":
    run_seed()
