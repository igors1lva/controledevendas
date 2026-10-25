"""
Módulo de Camada de Dados (SQLite)
Arquivo: database.py

Responsável pelo gerenciamento do banco de dados local SQLite (`gestao_vendas.db`),
execução de operações CRUD de produtos, transações atômicas de vendas (com baixa de estoque)
e consultas agregadas para geração de relatórios.
"""

import os
import sys
import re
import sqlite3
import hashlib
import secrets
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from contextlib import contextmanager
from cryptography.fernet import Fernet


def get_base_dir() -> str:
    """
    Retorna o diretório base correto para persistência,
    compatível tanto com a execução direta (.py) quanto com
    o executável empacotado pelo PyInstaller (.exe).
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DB_NAME = "gestao_vendas.db"
DB_PATH = os.path.join(get_base_dir(), DB_NAME)


@contextmanager
def get_connection():
    """
    Cria e retorna uma conexão com o banco SQLite.
    Habilita suporte a chaves estrangeiras e retorna linhas como dicionários.
    Garante o encerramento seguro e a liberação imediata de recursos ao fim do bloco with.
    """
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def init_db() -> None:
    """
    Inicializa as tabelas do banco de dados caso não existam.
    - produtos: Cadastro de itens, preços e estoque atual.
    - vendas: Registro detalhado das transações realizadas com timestamp.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Tabela de Produtos
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE COLLATE NOCASE,
                preco REAL NOT NULL CHECK(preco >= 0),
                estoque INTEGER NOT NULL CHECK(estoque >= 0),
                data_cadastro TEXT NOT NULL
            );
            """
        )

        # Tabela de Vendas
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS vendas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER NOT NULL,
                produto_nome TEXT NOT NULL,
                quantidade INTEGER NOT NULL CHECK(quantidade > 0),
                preco_unitario REAL NOT NULL CHECK(preco_unitario >= 0),
                valor_total REAL NOT NULL CHECK(valor_total >= 0),
                data_hora TEXT NOT NULL,
                status TEXT DEFAULT 'CONCLUIDA',
                FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE RESTRICT
            );
            """
        )

        # Índices para otimização de consultas e relatórios
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_vendas_data ON vendas (data_hora);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_produtos_nome ON produtos (nome);"
        )

        # Tabela de Configurações do Sistema (preferências, tema, etc.)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS configuracoes (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            );
            """
        )

        # Tabela de Auditoria e Integridade Digital de Fechamentos Diários
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS fechamentos_auditados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_referencia TEXT NOT NULL UNIQUE,
                data_hora_fechamento TEXT NOT NULL,
                total_faturamento REAL NOT NULL,
                total_itens INTEGER NOT NULL,
                total_vendas INTEGER NOT NULL,
                total_custo REAL DEFAULT 0.0,
                total_lucro REAL DEFAULT 0.0,
                hash_sha256 TEXT NOT NULL,
                status_auditoria TEXT DEFAULT 'AUTENTICO'
            );
            """
        )

        # Migração de colunas na tabela fechamentos_auditados
        cursor.execute("PRAGMA table_info(fechamentos_auditados);")
        colunas_fech = [row["name"] for row in cursor.fetchall()]
        if "total_custo" not in colunas_fech:
            cursor.execute("ALTER TABLE fechamentos_auditados ADD COLUMN total_custo REAL DEFAULT 0.0;")
        if "total_lucro" not in colunas_fech:
            cursor.execute("ALTER TABLE fechamentos_auditados ADD COLUMN total_lucro REAL DEFAULT 0.0;")

        # Migração incremental e segura de colunas na tabela produtos
        cursor.execute("PRAGMA table_info(produtos);")
        colunas_existentes = [row["name"] for row in cursor.fetchall()]

        if "codigo_barras" not in colunas_existentes:
            cursor.execute("ALTER TABLE produtos ADD COLUMN codigo_barras TEXT;")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_produtos_codigo_barras ON produtos (codigo_barras);")

        if "preco_custo" not in colunas_existentes:
            cursor.execute("ALTER TABLE produtos ADD COLUMN preco_custo REAL DEFAULT 0.0;")

        # Campos tributários para emissão de NFC-e (modelo 65)
        colunas_fiscais = {
            "ncm": "TEXT DEFAULT '21069090'",
            "cest": "TEXT DEFAULT ''",
            "cfop": "TEXT DEFAULT '5102'",
            "origem": "INTEGER DEFAULT 0",
            "csosn": "TEXT DEFAULT '102'",
            "cst_pis": "TEXT DEFAULT '49'",
            "cst_cofins": "TEXT DEFAULT '49'",
            "unidade": "TEXT DEFAULT 'UN'",
        }
        for col, col_def in colunas_fiscais.items():
            if col not in colunas_existentes:
                cursor.execute(f"ALTER TABLE produtos ADD COLUMN {col} {col_def};")

        # Migração incremental e segura de colunas na tabela vendas
        cursor.execute("PRAGMA table_info(vendas);")
        colunas_vendas = [row["name"] for row in cursor.fetchall()]

        if "status" not in colunas_vendas:
            cursor.execute("ALTER TABLE vendas ADD COLUMN status TEXT DEFAULT 'CONCLUIDA';")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vendas_status ON vendas (status);")

        if "forma_pagamento" not in colunas_vendas:
            cursor.execute("ALTER TABLE vendas ADD COLUMN forma_pagamento TEXT DEFAULT 'DINHEIRO';")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vendas_forma_pagamento ON vendas (forma_pagamento);")

        if "cpf_cliente" not in colunas_vendas:
            cursor.execute("ALTER TABLE vendas ADD COLUMN cpf_cliente TEXT DEFAULT '';")

        # Tabela de Histórico de Fechamentos de Caixa (Gera registro a cada fechamento no PDV)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS fechamentos_caixa (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TEXT NOT NULL,
                data_referencia TEXT NOT NULL,
                total_vendas INTEGER NOT NULL,
                total_itens INTEGER NOT NULL,
                total_faturamento REAL NOT NULL,
                total_custo REAL DEFAULT 0.0,
                total_lucro REAL DEFAULT 0.0,
                caminho_excel TEXT,
                hash_sha256 TEXT
            );
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fc_data ON fechamentos_caixa (data_referencia);")

        # Tabela de Registro Fiscal da Venda (NFC-e / Contingência Offline)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS vendas_fiscais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venda_id INTEGER NOT NULL UNIQUE,
                modelo INTEGER DEFAULT 65,
                serie INTEGER NOT NULL DEFAULT 1,
                numero_nfce INTEGER NOT NULL,
                chave_acesso TEXT NOT NULL UNIQUE,
                tipo_emissao INTEGER NOT NULL, -- 1 = Normal, 9 = Contingência Offline
                status_fiscal TEXT NOT NULL,   -- 'PENDENTE_ENVIO', 'AUTORIZADA', 'REJEITADA', 'CANCELADA'
                dh_emissao TEXT NOT NULL,
                cstat INTEGER DEFAULT 0,
                motivo_status TEXT,
                protocolo_autorizacao TEXT,
                dh_autorizacao TEXT,
                caminho_xml_assinado TEXT,
                caminho_xml_protocolado TEXT,
                qr_code_url TEXT,
                tentativas_sincronizacao INTEGER DEFAULT 0,
                ultima_tentativa TEXT,
                motivo_contingencia TEXT,
                cpf_destinatario TEXT DEFAULT '',
                FOREIGN KEY (venda_id) REFERENCES vendas (id) ON DELETE RESTRICT
            );
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vf_status ON vendas_fiscais (status_fiscal);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vf_chave ON vendas_fiscais (chave_acesso);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vf_venda ON vendas_fiscais (venda_id);")

        cursor.execute("PRAGMA table_info(vendas_fiscais);")
        colunas_vf = [row["name"] for row in cursor.fetchall()]
        if "cpf_destinatario" not in colunas_vf:
            cursor.execute("ALTER TABLE vendas_fiscais ADD COLUMN cpf_destinatario TEXT DEFAULT '';")

        conn.commit()


# ============================================================================
# CONFIGURAÇÕES DO SISTEMA (TEMA / PREFERÊNCIAS)
# ============================================================================

def obter_config(chave: str, padrao: str = "") -> str:
    """Retorna o valor de uma configuração armazenada no banco ou o valor padrão."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT valor FROM configuracoes WHERE chave = ?;", (chave,))
            row = cursor.fetchone()
            return row["valor"] if row else padrao
    except Exception:
        return padrao


def salvar_config(chave: str, valor: str) -> None:
    """Salva ou atualiza uma configuração no banco SQLite."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO configuracoes (chave, valor)
                VALUES (?, ?)
                ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor;
                """,
                (chave, str(valor)),
            )
            conn.commit()
    except Exception:
        pass


# ============================================================================
# OPERAÇÕES DE PRODUTOS (INVENTÁRIO)
# ============================================================================

def adicionar_produto(
    nome: str,
    preco: float,
    estoque: int,
    codigo_barras: Optional[str] = None,
    preco_custo: float = 0.0,
) -> Tuple[bool, str]:
    """
    Cadastra um novo produto no inventário.
    Valida unicidade do nome e código de barras, e valores positivos.
    """
    nome_limpo = nome.strip()
    cod_limpo = codigo_barras.strip() if codigo_barras and codigo_barras.strip() else None

    if not nome_limpo:
        return False, "O nome do produto não pode ficar em branco."
    if preco <= 0:
        return False, "O preço de venda unitário deve ser maior que zero."
    if estoque < 0:
        return False, "A quantidade de estoque não pode ser negativa."
    if preco_custo < 0:
        return False, "O preço de custo não pode ser negativo."

    data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Valida duplicidade de código de barras se informado
            if cod_limpo:
                cursor.execute("SELECT id, nome FROM produtos WHERE codigo_barras = ?;", (cod_limpo,))
                existente = cursor.fetchone()
                if existente:
                    return False, f"O código de barras '{cod_limpo}' já pertence ao produto '{existente['nome']}'."

            cursor.execute(
                """
                INSERT INTO produtos (nome, preco, estoque, data_cadastro, codigo_barras, preco_custo)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (nome_limpo, preco, estoque, data_atual, cod_limpo, preco_custo),
            )
            conn.commit()
            return True, f"Produto '{nome_limpo}' cadastrado com sucesso!"
    except sqlite3.IntegrityError:
        return False, f"Já existe um produto cadastrado com o nome '{nome_limpo}'."
    except Exception as e:
        return False, f"Erro ao cadastrar produto: {str(e)}"


def atualizar_produto(
    produto_id: int,
    nome: str,
    preco: float,
    estoque: int,
    codigo_barras: Optional[str] = None,
    preco_custo: float = 0.0,
) -> Tuple[bool, str]:
    """
    Atualiza as informações de um produto existente (nome, preço, estoque, código de barras e custo).
    """
    nome_limpo = nome.strip()
    cod_limpo = codigo_barras.strip() if codigo_barras and codigo_barras.strip() else None

    if not nome_limpo:
        return False, "O nome do produto não pode ficar em branco."
    if preco <= 0:
        return False, "O preço unitário deve ser maior que zero."
    if estoque < 0:
        return False, "A quantidade de estoque não pode ser negativa."
    if preco_custo < 0:
        return False, "O preço de custo não pode ser negativo."

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Valida duplicidade de código de barras se informado em outro produto
            if cod_limpo:
                cursor.execute(
                    "SELECT id, nome FROM produtos WHERE codigo_barras = ? AND id != ?;",
                    (cod_limpo, produto_id),
                )
                existente = cursor.fetchone()
                if existente:
                    return False, f"O código de barras '{cod_limpo}' já pertence ao produto '{existente['nome']}'."

            cursor.execute(
                """
                UPDATE produtos
                SET nome = ?, preco = ?, estoque = ?, codigo_barras = ?, preco_custo = ?
                WHERE id = ?;
                """,
                (nome_limpo, preco, estoque, cod_limpo, preco_custo, produto_id),
            )
            if cursor.rowcount == 0:
                return False, "Produto não encontrado."
            conn.commit()
            return True, "Produto atualizado com sucesso!"
    except sqlite3.IntegrityError:
        return False, f"Já existe outro produto com o nome '{nome_limpo}'."
    except Exception as e:
        return False, f"Erro ao atualizar produto: {str(e)}"


def excluir_produto(produto_id: int) -> Tuple[bool, str]:
    """
    Exclui um produto do inventário.
    Caso o produto já tenha vendas registradas, a exclusão física é prevenida
    para preservar o histórico contábil (ou tratada de acordo com regras de integridade).
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            # Verifica se há vendas vinculadas a este produto
            cursor.execute("SELECT COUNT(*) AS total FROM vendas WHERE produto_id = ?", (produto_id,))
            total_vendas = cursor.fetchone()["total"]

            if total_vendas > 0:
                return False, (
                    "Este produto possui histórico de vendas registradas. "
                    "Para manter a integridade contábil, altere o estoque para 0 em vez de excluí-lo."
                )

            cursor.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))
            if cursor.rowcount == 0:
                return False, "Produto não encontrado."
            conn.commit()
            return True, "Produto excluído com sucesso!"
    except Exception as e:
        return False, f"Erro ao excluir produto: {str(e)}"


def listar_produtos(termo_busca: str = "") -> List[Dict[str, Any]]:
    """
    Retorna a lista de produtos cadastrados, opcionalmente filtrada por termo de busca
    no nome ou no código de barras. Suporta correspondência exata, múltiplos tokens e busca por palavras-chave.
    Para tokens curtos (<= 2 caracteres, ex: 'D', 'M', '1'), aplica limite de palavra para evitar
    falsos positivos em palavras como 'produto' ou 'demonstrativo'.
    """
    termo_limpo = re.sub(r"[^\w\s]", " ", termo_busca or "").strip()
    tokens = [t for t in termo_limpo.split() if t]

    with get_connection() as conn:
        cursor = conn.cursor()
        if not tokens:
            cursor.execute(
                """
                SELECT id, nome, preco, preco_custo, estoque, codigo_barras, data_cadastro
                FROM produtos
                ORDER BY nome ASC;
                """
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        # 1. Se contém múltiplos termos, tenta correspondência contígua da frase completa primeiro
        if len(tokens) > 1:
            frase_like = f"%{termo_limpo}%"
            cursor.execute(
                """
                SELECT id, nome, preco, preco_custo, estoque, codigo_barras, data_cadastro
                FROM produtos
                WHERE nome LIKE ? OR (codigo_barras IS NOT NULL AND codigo_barras LIKE ?)
                ORDER BY nome ASC;
                """,
                (frase_like, frase_like),
            )
            rows_frase = cursor.fetchall()
            if rows_frase:
                return [dict(row) for row in rows_frase]

        # 2. Correspondência inteligente por tokens
        clausulas = []
        parametros = []
        for t in tokens:
            if len(t) <= 2:
                clausula_t = """(
                    nome = ? OR 
                    nome LIKE ? || ' %' OR 
                    nome LIKE '% ' || ? || ' %' OR 
                    nome LIKE '% ' || ? OR 
                    (codigo_barras IS NOT NULL AND (codigo_barras = ? OR codigo_barras LIKE ? || ' %' OR codigo_barras LIKE '% ' || ?))
                )"""
                clausulas.append(clausula_t)
                parametros.extend([t, t, t, t, t, t, t])
            else:
                clausulas.append("(nome LIKE ? OR (codigo_barras IS NOT NULL AND codigo_barras LIKE ?))")
                parametros.extend([f"%{t}%", f"%{t}%"])

        sql = f"""
            SELECT id, nome, preco, preco_custo, estoque, codigo_barras, data_cadastro
            FROM produtos
            WHERE {" AND ".join(clausulas)}
            ORDER BY nome ASC;
        """
        cursor.execute(sql, parametros)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def obter_produto_por_id(produto_id: int) -> Optional[Dict[str, Any]]:
    """
    Busca e retorna um produto específico pelo ID com todos os campos.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, nome, preco, preco_custo, estoque, codigo_barras, data_cadastro
            FROM produtos
            WHERE id = ?;
            """,
            (produto_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


# Alias de compatibilidade
obter_produtos = listar_produtos


def obter_produto_por_codigo_barras(codigo_barras: str) -> Optional[Dict[str, Any]]:
    """
    Busca um produto exatamente pelo código de barras.
    Utilizado por leitores ópticos USB no PDV e na tela de cadastro rápido.
    """
    cod = codigo_barras.strip()
    if not cod:
        return None
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, nome, preco, preco_custo, estoque, codigo_barras, data_cadastro
            FROM produtos
            WHERE codigo_barras = ?;
            """,
            (cod,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def obter_produtos_disponiveis() -> List[Dict[str, Any]]:
    """
    Retorna apenas os produtos que possuem estoque maior que zero,
    utilizados na seleção de produtos do PDV.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, nome, preco, preco_custo, estoque, codigo_barras
            FROM produtos
            WHERE estoque > 0
            ORDER BY nome ASC;
            """
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def repor_ou_cadastrar_produto_xml(
    codigo_barras: Optional[str],
    nome: str,
    qtd: int,
    preco_custo: float,
    preco_venda_sugerido: Optional[float] = None,
) -> Tuple[bool, str, str]:
    """
    Processa item lido do XML da NF-e:
    - Se encontrar produto com o mesmo código de barras (ou nome exato se sem código),
      soma a quantidade ao estoque e atualiza o preço de custo.
    - Se for novo, cadastra o item com preço de venda calculado ou sugerido.
    Retorna: (sucesso, mensagem, acao_tomada: "REPOSICAO" | "NOVO")
    """
    cod = codigo_barras.strip() if codigo_barras and codigo_barras.strip() else None
    nome_limpo = nome.strip()

    if not nome_limpo:
        return False, "Nome do produto inválido no XML.", ""

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            prod_existente = None

            if cod:
                cursor.execute("SELECT * FROM produtos WHERE codigo_barras = ?;", (cod,))
                prod_existente = cursor.fetchone()

            if not prod_existente:
                cursor.execute("SELECT * FROM produtos WHERE LOWER(nome) = LOWER(?);", (nome_limpo,))
                prod_existente = cursor.fetchone()

            if prod_existente:
                novo_estoque = prod_existente["estoque"] + max(qtd, 0)
                novo_custo = preco_custo if preco_custo > 0 else (prod_existente["preco_custo"] if "preco_custo" in prod_existente.keys() else 0.0)
                novo_venda = preco_venda_sugerido if preco_venda_sugerido and preco_venda_sugerido > 0 else prod_existente["preco"]
                cod_final = cod if cod else (prod_existente["codigo_barras"] if "codigo_barras" in prod_existente.keys() else None)

                cursor.execute(
                    """
                    UPDATE produtos
                    SET estoque = ?, preco_custo = ?, preco = ?, codigo_barras = ?
                    WHERE id = ?;
                    """,
                    (novo_estoque, novo_custo, novo_venda, cod_final, prod_existente["id"]),
                )
                conn.commit()
                return True, f"Estoque de '{nome_limpo}' atualizado (+{qtd} un). Total: {novo_estoque} un.", "REPOSICAO"
            else:
                # Produto novo: calcular preço de venda padrão se não fornecido
                preco_venda = preco_venda_sugerido if preco_venda_sugerido and preco_venda_sugerido > 0 else round(preco_custo * 1.5, 2)
                if preco_venda <= 0:
                    preco_venda = 1.0  # fallback mínimo
                data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                cursor.execute(
                    """
                    INSERT INTO produtos (nome, preco, estoque, data_cadastro, codigo_barras, preco_custo)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (nome_limpo, preco_venda, max(qtd, 0), data_atual, cod, preco_custo),
                )
                conn.commit()
                return True, f"Novo produto '{nome_limpo}' cadastrado com sucesso!", "NOVO"
    except Exception as e:
        return False, f"Erro ao processar item do XML: {str(e)}", ""


# ============================================================================
# OPERAÇÕES DE VENDAS (PDV)
# ============================================================================

def registrar_venda(
    produto_id: int,
    quantidade: int,
    forma_pagamento: str = "DINHEIRO",
    cpf_cliente: str = "",
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Realiza uma transação atômica de venda:
    1. Verifica se o produto existe e tem estoque suficiente.
    2. Abate a quantidade vendida do estoque do produto.
    3. Registra a venda com data, hora, forma de pagamento e CPF do cliente (opcional).
    4. Confirma tudo via COMMIT seguro ou ROLLBACK em caso de falha.
    """
    if quantidade <= 0:
        return False, "A quantidade vendida deve ser no mínimo 1 unidade.", None

    forma_pgto_limpa = forma_pagamento.strip().upper() if forma_pagamento else "DINHEIRO"
    cpf_limpo = cpf_cliente.strip() if cpf_cliente else ""

    with get_connection() as conn:
        try:
            cursor = conn.cursor()
            # Inicia transação imediata para garantir exclusividade de escrita
            cursor.execute("BEGIN IMMEDIATE;")

            # Obtém o produto e verifica estoque
            cursor.execute("SELECT id, nome, preco, estoque FROM produtos WHERE id = ?", (produto_id,))
            produto = cursor.fetchone()

            if not produto:
                conn.rollback()
                return False, "Produto não encontrado.", None

            estoque_atual = produto["estoque"]
            preco_unitario = produto["preco"]
            produto_nome = produto["nome"]

            if estoque_atual <= 0:
                conn.rollback()
                return False, f"O produto '{produto_nome}' está esgotado (estoque 0).", None

            if quantidade > estoque_atual:
                conn.rollback()
                return (
                    False,
                    f"Estoque insuficiente para '{produto_nome}'. Disponível: {estoque_atual} un, Solicitado: {quantidade} un.",
                    None,
                )

            # 1. Abater do estoque
            novo_estoque = estoque_atual - quantidade
            cursor.execute(
                "UPDATE produtos SET estoque = ? WHERE id = ?",
                (novo_estoque, produto_id),
            )

            # 2. Registrar a transação de venda
            valor_total = round(preco_unitario * quantidade, 2)
            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute(
                """
                INSERT INTO vendas (produto_id, produto_nome, quantidade, preco_unitario, valor_total, data_hora, status, forma_pagamento, cpf_cliente)
                VALUES (?, ?, ?, ?, ?, ?, 'CONCLUIDA', ?, ?);
                """,
                (produto_id, produto_nome, quantidade, preco_unitario, valor_total, agora, forma_pgto_limpa, cpf_limpo),
            )
            venda_id = cursor.lastrowid

            conn.commit()

            info_venda = {
                "venda_id": venda_id,
                "produto_id": produto_id,
                "produto_nome": produto_nome,
                "quantidade": quantidade,
                "preco_unitario": preco_unitario,
                "valor_total": valor_total,
                "data_hora": agora,
                "status": "CONCLUIDA",
                "forma_pagamento": forma_pgto_limpa,
                "cpf_cliente": cpf_limpo,
                "estoque_restante": novo_estoque,
            }

            return True, f"Venda realizada com sucesso! ({quantidade}x {produto_nome})", info_venda

        except Exception as e:
            conn.rollback()
            return False, f"Falha ao registrar venda: {str(e)}", None


def registrar_venda_carrinho(
    itens: List[Dict[str, Any]],
    forma_pagamento: str = "DINHEIRO",
    cpf_cliente: str = "",
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Realiza uma transação atômica de venda para múltiplos itens acumulados no carrinho:
    1. Valida se o carrinho possui ao menos 1 item com quantidade válida.
    2. Sob transação BEGIN IMMEDIATE, valida a existência e estoque de CADA produto.
    3. Abate atomicamente a quantidade vendida de cada produto.
    4. Registra cada item na tabela de vendas com a mesma data/hora, forma de pagamento e CPF do cliente.
    5. Confirma tudo via COMMIT seguro ou ROLLBACK completo em caso de inconsistência.
    """
    if not itens:
        return False, "O carrinho de compras está vazio.", None

    forma_pgto_limpa = forma_pagamento.strip().upper() if forma_pagamento else "DINHEIRO"
    cpf_limpo = cpf_cliente.strip() if cpf_cliente else ""

    with get_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")

            produtos_validados = []
            for item in itens:
                p_id = int(item["produto_id"])
                qtd = int(item["quantidade"])
                if qtd <= 0:
                    conn.rollback()
                    return False, f"A quantidade para o produto ID {p_id} deve ser de no mínimo 1 unidade.", None

                cursor.execute("SELECT id, nome, preco, estoque FROM produtos WHERE id = ?", (p_id,))
                p = cursor.fetchone()
                if not p:
                    conn.rollback()
                    return False, f"Produto ID {p_id} não encontrado no catálogo.", None

                if p["estoque"] < qtd:
                    conn.rollback()
                    return (
                        False,
                        f"Estoque insuficiente para '{p['nome']}'. Disponível: {p['estoque']} un, Solicitado: {qtd} un.",
                        None,
                    )

                produtos_validados.append({
                    "produto_id": p["id"],
                    "produto_nome": p["nome"],
                    "quantidade": qtd,
                    "preco_unitario": p["preco"],
                    "valor_total": round(p["preco"] * qtd, 2),
                    "estoque_anterior": p["estoque"],
                    "estoque_restante": p["estoque"] - qtd,
                })

            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            vendas_ids = []
            valor_total_geral = 0.0

            for pv in produtos_validados:
                # 1. Abate do estoque
                cursor.execute(
                    "UPDATE produtos SET estoque = ? WHERE id = ?",
                    (pv["estoque_restante"], pv["produto_id"]),
                )

                # 2. Insere registro de venda
                cursor.execute(
                    """
                    INSERT INTO vendas (produto_id, produto_nome, quantidade, preco_unitario, valor_total, data_hora, status, forma_pagamento, cpf_cliente)
                    VALUES (?, ?, ?, ?, ?, ?, 'CONCLUIDA', ?, ?);
                    """,
                    (pv["produto_id"], pv["produto_nome"], pv["quantidade"], pv["preco_unitario"], pv["valor_total"], agora, forma_pgto_limpa, cpf_limpo),
                )
                vendas_ids.append(cursor.lastrowid)
                valor_total_geral += pv["valor_total"]

            conn.commit()

            info_carrinho = {
                "vendas_ids": vendas_ids,
                "itens": produtos_validados,
                "total_itens": sum(pv["quantidade"] for pv in produtos_validados),
                "total_produtos_distintos": len(produtos_validados),
                "valor_total": round(valor_total_geral, 2),
                "data_hora": agora,
                "status": "CONCLUIDA",
                "forma_pagamento": forma_pgto_limpa,
                "cpf_cliente": cpf_limpo,
            }

            resumo_msg = f"{len(produtos_validados)} produto(s), total {info_carrinho['total_itens']} un"
            return True, f"Venda do carrinho realizada com sucesso! ({resumo_msg})", info_carrinho

        except Exception as e:
            conn.rollback()
            return False, f"Falha ao registrar venda do carrinho: {str(e)}", None


def cancelar_venda(venda_id: int) -> Tuple[bool, str]:
    """
    Cancela uma venda previamente realizada:
    1. Localiza a venda e verifica se já não está com status 'CANCELADA'.
    2. Devolve as unidades vendidas de volta ao estoque do produto.
    3. Atualiza o status da transação para 'CANCELADA'.
    4. Garante consistência e integridade atômica via transação SQLite.
    """
    with get_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE;")

            cursor.execute(
                "SELECT id, produto_id, produto_nome, quantidade, status FROM vendas WHERE id = ?;",
                (venda_id,),
            )
            venda = cursor.fetchone()

            if not venda:
                conn.rollback()
                return False, f"Venda #{venda_id} não encontrada no sistema."

            status_atual = venda["status"] if ("status" in venda.keys() and venda["status"]) else "CONCLUIDA"
            if status_atual == "CANCELADA":
                conn.rollback()
                return False, f"A venda #{venda_id} já foi cancelada anteriormente."

            produto_id = venda["produto_id"]
            quantidade = venda["quantidade"]
            produto_nome = venda["produto_nome"]

            # 1. Repor estoque do produto
            cursor.execute(
                "UPDATE produtos SET estoque = estoque + ? WHERE id = ?;",
                (quantidade, produto_id),
            )

            # 2. Marcar a venda como CANCELADA
            cursor.execute(
                "UPDATE vendas SET status = 'CANCELADA' WHERE id = ?;",
                (venda_id,),
            )

            conn.commit()
            return True, f"Venda #{venda_id} cancelada com sucesso! {quantidade} un de '{produto_nome}' foram repostas no estoque."

        except Exception as e:
            conn.rollback()
            return False, f"Erro ao cancelar venda #{venda_id}: {str(e)}"


def obter_vendas_recentes_do_dia(limite: int = 500) -> List[Dict[str, Any]]:
    """
    Retorna as transações de venda realizadas na data de hoje,
    ordenadas da mais recente para a mais antiga, incluindo status de cancelamento.
    """
    hoje = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, produto_id, produto_nome, quantidade, preco_unitario, valor_total, data_hora,
                   COALESCE(status, 'CONCLUIDA') AS status
            FROM vendas
            WHERE substr(data_hora, 1, 10) = ?
            ORDER BY id DESC
            LIMIT ?;
            """,
            (hoje, limite),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def buscar_vendas(termo_busca: str = "", limite: int = 500) -> List[Dict[str, Any]]:
    """
    Busca transações de vendas no histórico com suporte a múltiplos termos (nome do produto, ID, data, status).
    Se termo_busca for vazio:
    - Retorna as vendas de hoje;
    - Se hoje não houver vendas, retorna as últimas vendas registradas do sistema para que a tela não fique vazia.
    Suporta correspondência exata por frase (ex: 'Modelo D') e limites de palavra para tokens curtos (evita falso positivo).
    """
    termo_limpo = re.sub(r"[^\w\s\-:]", " ", termo_busca or "").strip()
    tokens = [t for t in termo_limpo.split() if t]

    hoje = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        cursor = conn.cursor()
        if not tokens:
            cursor.execute(
                """
                SELECT id, produto_id, produto_nome, quantidade, preco_unitario, valor_total, data_hora,
                       COALESCE(status, 'CONCLUIDA') AS status
                FROM vendas
                WHERE substr(data_hora, 1, 10) = ?
                ORDER BY id DESC
                LIMIT ?;
                """,
                (hoje, limite),
            )
            rows = cursor.fetchall()
            if rows:
                return [dict(row) for row in rows]

            cursor.execute(
                """
                SELECT id, produto_id, produto_nome, quantidade, preco_unitario, valor_total, data_hora,
                       COALESCE(status, 'CONCLUIDA') AS status
                FROM vendas
                ORDER BY id DESC
                LIMIT ?;
                """,
                (limite,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        # 1. Correspondência de frase contígua se múltiplos termos
        if len(tokens) > 1:
            frase_like = f"%{termo_limpo}%"
            cursor.execute(
                """
                SELECT id, produto_id, produto_nome, quantidade, preco_unitario, valor_total, data_hora,
                       COALESCE(status, 'CONCLUIDA') AS status
                FROM vendas
                WHERE produto_nome LIKE ? OR data_hora LIKE ? OR COALESCE(status, '') LIKE ?
                ORDER BY id DESC
                LIMIT ?;
                """,
                (frase_like, frase_like, frase_like, limite),
            )
            rows_frase = cursor.fetchall()
            if rows_frase:
                return [dict(row) for row in rows_frase]

        # 2. Correspondência inteligente por tokens
        clausulas = []
        parametros = []
        for t in tokens:
            if len(t) <= 2:
                clausulas.append(
                    """(
                        produto_nome = ? OR 
                        produto_nome LIKE ? || ' %' OR 
                        produto_nome LIKE '% ' || ? || ' %' OR 
                        produto_nome LIKE '% ' || ? OR 
                        CAST(id AS TEXT) = ? OR 
                        data_hora LIKE ? OR 
                        COALESCE(status, '') = ?
                    )"""
                )
                parametros.extend([t, t, t, t, t, f"%{t}%", t])
            else:
                clausulas.append(
                    """(
                        produto_nome LIKE ? OR 
                        CAST(id AS TEXT) LIKE ? OR 
                        data_hora LIKE ? OR 
                        COALESCE(status, '') LIKE ?
                    )"""
                )
                parametros.extend([f"%{t}%", f"%{t}%", f"%{t}%", f"%{t}%"])

        sql = f"""
            SELECT id, produto_id, produto_nome, quantidade, preco_unitario, valor_total, data_hora,
                   COALESCE(status, 'CONCLUIDA') AS status
            FROM vendas
            WHERE {" AND ".join(clausulas)}
            ORDER BY id DESC
            LIMIT ?;
        """
        parametros.append(limite)
        cursor.execute(sql, parametros)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def obter_resumo_dia(data_str: Optional[str] = None) -> Dict[str, Any]:
    """
    Retorna métricas consolidadas do dia: total faturado, itens vendidos e número de transações.
    Desconsidera vendas com status 'CANCELADA'.
    """
    if not data_str:
        data_str = datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                COALESCE(SUM(v.valor_total), 0.0) AS total_faturamento,
                COALESCE(SUM(v.quantidade), 0) AS total_itens,
                COUNT(v.id) AS total_vendas,
                COALESCE(SUM(v.quantidade * COALESCE(p.preco_custo, 0.0)), 0.0) AS total_custo,
                COALESCE(SUM(v.valor_total - (v.quantidade * COALESCE(p.preco_custo, 0.0))), 0.0) AS total_lucro
            FROM vendas v
            LEFT JOIN produtos p ON v.produto_id = p.id
            WHERE substr(v.data_hora, 1, 10) = ?
              AND (v.status IS NULL OR v.status != 'CANCELADA');
            """,
            (data_str,),
        )
        row = cursor.fetchone()
        return {
            "data": data_str,
            "total_faturamento": float(row["total_faturamento"]),
            "total_itens": int(row["total_itens"]),
            "total_vendas": int(row["total_vendas"]),
            "total_custo": float(row["total_custo"]),
            "total_lucro": float(row["total_lucro"]),
        }


# ============================================================================
# CONSULTAS PARA RELATÓRIOS CONSOLIDADOS
# ============================================================================

def obter_relatorio_consolidado_dia(data_str: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retorna as vendas agrupadas por produto para a data informada (padrão: hoje),
    incluindo preço de custo, custo total e lucro apurado (venda - custo).
    Desconsidera vendas canceladas para manter a acurácia fiscal e contábil.
    Campos retornados:
    - produto_nome
    - quantidade_total
    - preco_unitario (preço médio de venda)
    - preco_custo (preço de custo cadastrado)
    - total_arrecadado (faturamento bruto do produto)
    - total_custo (custo das mercadorias vendidas)
    - lucro_total (lucro real: faturamento - custo)
    """
    if not data_str:
        data_str = datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                v.produto_nome,
                SUM(v.quantidade) AS quantidade_total,
                ROUND(SUM(v.valor_total) / SUM(v.quantidade), 2) AS preco_unitario,
                COALESCE(p.preco_custo, 0.0) AS preco_custo,
                ROUND(SUM(v.valor_total), 2) AS total_arrecadado,
                ROUND(SUM(v.quantidade) * COALESCE(p.preco_custo, 0.0), 2) AS total_custo,
                ROUND(SUM(v.valor_total) - (SUM(v.quantidade) * COALESCE(p.preco_custo, 0.0)), 2) AS lucro_total
            FROM vendas v
            LEFT JOIN produtos p ON v.produto_id = p.id
            WHERE substr(v.data_hora, 1, 10) = ?
              AND (v.status IS NULL OR v.status != 'CANCELADA')
            GROUP BY v.produto_id, v.produto_nome
            ORDER BY total_arrecadado DESC, v.produto_nome ASC;
            """,
            (data_str,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def obter_vendas_canceladas_dia(data_str: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retorna todas as vendas canceladas/estornadas na data informada (padrão: hoje),
    com identificador, produto, quantidade, valores e forma de pagamento original.
    Permite demonstrar e auditar os cancelamentos no relatório Excel oficial.
    """
    if not data_str:
        data_str = datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                v.id,
                v.produto_id,
                v.produto_nome,
                v.quantidade,
                v.preco_unitario,
                v.valor_total,
                v.data_hora,
                v.forma_pagamento,
                COALESCE(v.cpf_cliente, '') AS cpf_cliente,
                COALESCE(p.preco_custo, 0.0) AS preco_custo,
                ROUND(v.quantidade * COALESCE(p.preco_custo, 0.0), 2) AS custo_total
            FROM vendas v
            LEFT JOIN produtos p ON v.produto_id = p.id
            WHERE substr(v.data_hora, 1, 10) = ?
              AND v.status = 'CANCELADA'
            ORDER BY v.id DESC;
            """,
            (data_str,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def obter_resumo_caixa_detalhado(data_str: Optional[str] = None) -> Dict[str, Any]:
    """
    Retorna métricas operacionais completas do caixa para fechamento de turno/dia:
    - Faturamento bruto, custo CMV, lucro apurado e margem %
    - Contagem de transações e itens comercializados
    - Desdobramento financeiro por método de pagamento (Dinheiro, Pix, Cartão, etc.)
    """
    if not data_str:
        data_str = datetime.now().strftime("%Y-%m-%d")

    resumo_base = obter_resumo_dia(data_str)
    faturamento = resumo_base["total_faturamento"]
    lucro = resumo_base["total_lucro"]
    vendas_count = resumo_base["total_vendas"]

    margem = round((lucro / faturamento * 100), 1) if faturamento > 0 else 0.0
    ticket_medio = round(faturamento / vendas_count, 2) if vendas_count > 0 else 0.0

    formas_dict = {
        "DINHEIRO": 0.0,
        "PIX": 0.0,
        "CARTAO_DEBITO": 0.0,
        "CARTAO_CREDITO": 0.0,
        "VALE_ALIMENTACAO": 0.0,
        "OUTROS": 0.0,
    }

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                COALESCE(UPPER(forma_pagamento), 'DINHEIRO') AS forma,
                COALESCE(SUM(valor_total), 0.0) AS total,
                COUNT(id) AS qtd
            FROM vendas
            WHERE substr(data_hora, 1, 10) = ?
              AND (status IS NULL OR status != 'CANCELADA')
            GROUP BY COALESCE(UPPER(forma_pagamento), 'DINHEIRO');
            """,
            (data_str,),
        )
        for row in cursor.fetchall():
            forma = row["forma"]
            tot = float(row["total"])
            if forma in formas_dict:
                formas_dict[forma] += tot
            else:
                formas_dict["OUTROS"] += tot

        # Busca último fechamento do dia se houver
        cursor.execute(
            """
            SELECT id, data_hora, total_faturamento, caminho_excel 
            FROM fechamentos_caixa 
            WHERE data_referencia = ? 
            ORDER BY id DESC LIMIT 1;
            """,
            (data_str,),
        )
        ult_fech = cursor.fetchone()
        ultimo_fechamento_info = dict(ult_fech) if ult_fech else None

    return {
        "data": data_str,
        "total_faturamento": faturamento,
        "total_custo": resumo_base["total_custo"],
        "total_lucro": lucro,
        "margem_lucro": margem,
        "ticket_medio": ticket_medio,
        "total_vendas": vendas_count,
        "total_itens": resumo_base["total_itens"],
        "formas_pagamento": formas_dict,
        "ultimo_fechamento": ultimo_fechamento_info,
    }


def registrar_fechamento_caixa(
    caminho_excel: str = "",
    hash_sha256: str = "",
    data_referencia: Optional[str] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Registra um evento oficial de fechamento de caixa na base de dados SQLite.
    Garante rastreabilidade histórica e integridade com o relatório Excel gerado.
    """
    if not data_referencia:
        data_referencia = datetime.now().strftime("%Y-%m-%d")

    resumo = obter_resumo_dia(data_referencia)
    agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO fechamentos_caixa (
                data_hora, data_referencia, total_vendas, total_itens,
                total_faturamento, total_custo, total_lucro, caminho_excel, hash_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                agora_iso,
                data_referencia,
                resumo["total_vendas"],
                resumo["total_itens"],
                resumo["total_faturamento"],
                resumo["total_custo"],
                resumo["total_lucro"],
                caminho_excel,
                hash_sha256,
            ),
        )
        fechamento_id = cursor.lastrowid
        conn.commit()

    info_retorno = {
        "id": fechamento_id,
        "data_hora": agora_iso,
        "data_referencia": data_referencia,
        "total_faturamento": resumo["total_faturamento"],
        "total_vendas": resumo["total_vendas"],
        "total_itens": resumo["total_itens"],
        "total_lucro": resumo["total_lucro"],
        "caminho_excel": caminho_excel,
        "hash_sha256": hash_sha256,
    }

    return True, f"Fechamento de caixa #{fechamento_id} registrado com sucesso!", info_retorno


def obter_metricas_dashboard(periodo: str = "hoje") -> Dict[str, Any]:
    """
    Gera as estatísticas consolidadas e séries temporais para o Dashboard In-App Analytics.
    Periodos suportados:
    - 'hoje': Vendas de hoje
    - '7d': Últimos 7 dias
    - '30d': Últimos 30 dias
    - 'mes': Mês corrente
    - 'todos': Histórico completo
    """
    agora = datetime.now()
    hoje_iso = agora.strftime("%Y-%m-%d")
    mes_iso = agora.strftime("%Y-%m")

    if periodo == "hoje":
        clausula_where = "substr(v.data_hora, 1, 10) = ?"
        params = (hoje_iso,)
        titulo_periodo = f"Hoje ({agora.strftime('%d/%m/%Y')})"
    elif periodo == "7d":
        data_ini = (agora - timedelta(days=6)).strftime("%Y-%m-%d")
        clausula_where = "substr(v.data_hora, 1, 10) >= ?"
        params = (data_ini,)
        titulo_periodo = f"Últimos 7 Dias (desde {datetime.strptime(data_ini, '%Y-%m-%d').strftime('%d/%m')})"
    elif periodo == "30d":
        data_ini = (agora - timedelta(days=29)).strftime("%Y-%m-%d")
        clausula_where = "substr(v.data_hora, 1, 10) >= ?"
        params = (data_ini,)
        titulo_periodo = f"Últimos 30 Dias (desde {datetime.strptime(data_ini, '%Y-%m-%d').strftime('%d/%m')})"
    elif periodo == "mes":
        clausula_where = "substr(v.data_hora, 1, 7) = ?"
        params = (mes_iso,)
        titulo_periodo = f"Mês de {agora.strftime('%B/%Y').capitalize()}"
    else:  # todos
        clausula_where = "1=1"
        params = ()
        titulo_periodo = "Todo o Período Histórico"

    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Totais Gerais do Período (Vendas Ativas Concluídas)
        sql_totais = f"""
            SELECT 
                COALESCE(SUM(v.valor_total), 0.0) AS total_faturamento,
                COALESCE(SUM(v.quantidade), 0) AS total_itens,
                COUNT(v.id) AS total_vendas,
                COALESCE(SUM(v.quantidade * COALESCE(p.preco_custo, 0.0)), 0.0) AS total_custo,
                COALESCE(SUM(v.valor_total - (v.quantidade * COALESCE(p.preco_custo, 0.0))), 0.0) AS total_lucro
            FROM vendas v
            LEFT JOIN produtos p ON v.produto_id = p.id
            WHERE {clausula_where}
              AND (v.status IS NULL OR v.status != 'CANCELADA');
        """
        cursor.execute(sql_totais, params)
        row_tot = cursor.fetchone()

        fat = float(row_tot["total_faturamento"])
        custo = float(row_tot["total_custo"])
        lucro = float(row_tot["total_lucro"])
        vendas_n = int(row_tot["total_vendas"])
        itens_n = int(row_tot["total_itens"])
        margem = round((lucro / fat * 100), 1) if fat > 0 else 0.0
        ticket = round(fat / vendas_n, 2) if vendas_n > 0 else 0.0

        # 1.1 Totais de Estornos / Vendas Canceladas no Período
        sql_canceladas = f"""
            SELECT 
                COALESCE(SUM(v.valor_total), 0.0) AS total_cancelado,
                COUNT(v.id) AS total_canceladas,
                COALESCE(SUM(v.quantidade), 0) AS itens_cancelados
            FROM vendas v
            WHERE {clausula_where}
              AND v.status = 'CANCELADA';
        """
        cursor.execute(sql_canceladas, params)
        row_canc = cursor.fetchone()
        tot_cancelado = float(row_canc["total_cancelado"])
        qtd_canceladas = int(row_canc["total_canceladas"])
        itens_cancelados = int(row_canc["itens_cancelados"])
        fat_bruto = round(fat + tot_cancelado, 2)

        # 2. Série Diária (Evolução das Vendas por Dia)
        sql_diario = f"""
            SELECT 
                substr(v.data_hora, 1, 10) AS dia,
                COALESCE(SUM(v.valor_total), 0.0) AS total_dia,
                COUNT(v.id) AS qtd_vendas
            FROM vendas v
            WHERE {clausula_where}
              AND (v.status IS NULL OR v.status != 'CANCELADA')
            GROUP BY substr(v.data_hora, 1, 10)
            ORDER BY dia ASC;
        """
        cursor.execute(sql_diario, params)
        rows_diario = cursor.fetchall()
        vendas_diarias = []
        for r in rows_diario:
            dia_raw = r["dia"]
            try:
                dia_fmt = datetime.strptime(dia_raw, "%Y-%m-%d").strftime("%d/%m")
            except Exception:
                dia_fmt = dia_raw
            vendas_diarias.append({
                "dia_iso": dia_raw,
                "dia_fmt": dia_fmt,
                "faturamento": float(r["total_dia"]),
                "vendas": int(r["qtd_vendas"]),
            })

        # 3. Formas de Pagamento
        sql_formas = f"""
            SELECT 
                COALESCE(UPPER(v.forma_pagamento), 'DINHEIRO') AS forma,
                COALESCE(SUM(v.valor_total), 0.0) AS total,
                COUNT(v.id) AS qtd
            FROM vendas v
            WHERE {clausula_where}
              AND (v.status IS NULL OR v.status != 'CANCELADA')
            GROUP BY COALESCE(UPPER(v.forma_pagamento), 'DINHEIRO')
            ORDER BY total DESC;
        """
        cursor.execute(sql_formas, params)
        formas_lista = []
        for rf in cursor.fetchall():
            tot_f = float(rf["total"])
            pct = round((tot_f / fat * 100), 1) if fat > 0 else 0.0
            formas_lista.append({
                "forma": rf["forma"],
                "total": tot_f,
                "qtd": int(rf["qtd"]),
                "percentual": pct,
            })

        # 4. Top Produtos Mais Vendidos (Curva ABC)
        sql_top = f"""
            SELECT 
                v.produto_nome,
                SUM(v.quantidade) AS qtd_total,
                SUM(v.valor_total) AS total_arrecadado,
                COALESCE(SUM(v.quantidade * COALESCE(p.preco_custo, 0.0)), 0.0) AS custo_total,
                COALESCE(SUM(v.valor_total - (v.quantidade * COALESCE(p.preco_custo, 0.0))), 0.0) AS lucro_total
            FROM vendas v
            LEFT JOIN produtos p ON v.produto_id = p.id
            WHERE {clausula_where}
              AND (v.status IS NULL OR v.status != 'CANCELADA')
            GROUP BY v.produto_id, v.produto_nome
            ORDER BY total_arrecadado DESC
            LIMIT 10;
        """
        cursor.execute(sql_top, params)
        top_produtos = []
        for rp in cursor.fetchall():
            tot_p = float(rp["total_arrecadado"])
            lucro_p = float(rp["lucro_total"])
            margem_p = round((lucro_p / tot_p * 100), 1) if tot_p > 0 else 0.0
            top_produtos.append({
                "nome": rp["produto_nome"],
                "quantidade": int(rp["qtd_total"]),
                "faturamento": tot_p,
                "custo": float(rp["custo_total"]),
                "lucro": lucro_p,
                "margem": margem_p,
            })

        # 5. Faixas de Horário (Manhã, Tarde, Noite)
        sql_horarios = f"""
            SELECT 
                CAST(substr(v.data_hora, 12, 2) AS INTEGER) AS hora,
                v.valor_total
            FROM vendas v
            WHERE {clausula_where}
              AND (v.status IS NULL OR v.status != 'CANCELADA');
        """
        cursor.execute(sql_horarios, params)
        faixas = {"manha": 0.0, "tarde": 0.0, "noite": 0.0}
        for rh in cursor.fetchall():
            h = rh["hora"] if rh["hora"] is not None else 12
            val = float(rh["valor_total"])
            if 6 <= h < 12:
                faixas["manha"] += val
            elif 12 <= h < 18:
                faixas["tarde"] += val
            else:
                faixas["noite"] += val

        # 6. Log de Transações do Período (Vendas Ativas e Estornos/Canceladas)
        sql_logs = f"""
            SELECT 
                v.id,
                v.produto_id,
                v.produto_nome,
                v.quantidade,
                v.preco_unitario,
                v.valor_total,
                v.data_hora,
                COALESCE(v.forma_pagamento, 'DINHEIRO') AS forma_pagamento,
                COALESCE(v.status, 'CONCLUIDA') AS status
            FROM vendas v
            WHERE {clausula_where}
            ORDER BY v.id DESC
            LIMIT 100;
        """
        cursor.execute(sql_logs, params)
        logs_transacoes = []
        for rlg in cursor.fetchall():
            logs_transacoes.append({
                "id": int(rlg["id"]),
                "produto_id": rlg["produto_id"],
                "produto_nome": rlg["produto_nome"],
                "quantidade": int(rlg["quantidade"]),
                "preco_unitario": float(rlg["preco_unitario"]),
                "valor_total": float(rlg["valor_total"]),
                "data_hora": rlg["data_hora"],
                "forma_pagamento": rlg["forma_pagamento"],
                "status": rlg["status"],
            })

    return {
        "periodo": periodo,
        "titulo_periodo": titulo_periodo,
        "total_faturamento": fat,
        "total_faturamento_bruto": fat_bruto,
        "total_cancelado": tot_cancelado,
        "total_canceladas": qtd_canceladas,
        "itens_cancelados": itens_cancelados,
        "total_custo": custo,
        "total_lucro": lucro,
        "margem_lucro": margem,
        "total_vendas": vendas_n,
        "total_itens": itens_n,
        "ticket_medio": ticket,
        "vendas_diarias": vendas_diarias,
        "formas_pagamento": formas_lista,
        "top_produtos": top_produtos,
        "faixas_horario": faixas,
        "logs_transacoes": logs_transacoes,
    }


# ============================================================================
# GERENCIAMENTO DE SENHA DO ADMINISTRADOR E AUDITORIA CRIPTOGRÁFICA
# ============================================================================

def _obter_chave_cifracao_interna() -> bytes:
    """
    Retorna uma chave Fernet derivada e exclusiva desta instalação para
    cifrar localmente a senha de desproteção do Excel.
    """
    salt_hex = obter_config("system_crypto_salt", "")
    if not salt_hex:
        salt_hex = secrets.token_hex(16)
        salvar_config("system_crypto_salt", salt_hex)

    derivada = hashlib.pbkdf2_hmac(
        "sha256",
        b"CENTRAL_DE_VENDAS_EXCEL_PROT_KEY_V1",
        bytes.fromhex(salt_hex),
        50000,
    )
    return base64.urlsafe_b64encode(derivada)


def existe_senha_admin() -> bool:
    """Retorna True se o administrador/proprietário já definiu sua senha."""
    hash_salvo = obter_config("admin_pwd_hash", "")
    return bool(hash_salvo and len(hash_salvo) >= 32)


def verificar_senha_admin(senha: str) -> bool:
    """
    Valida a senha digitada contra o hash PBKDF2 HMAC-SHA256 armazenado.
    Utiliza comparação de tempo constante para evitar ataques de timing.
    """
    hash_salvo = obter_config("admin_pwd_hash", "")
    salt_hex = obter_config("admin_pwd_salt", "")
    if not hash_salvo or not salt_hex:
        return False

    try:
        hash_calculado = hashlib.pbkdf2_hmac(
            "sha256",
            senha.encode("utf-8"),
            bytes.fromhex(salt_hex),
            100000,
        ).hex()
        return secrets.compare_digest(hash_salvo, hash_calculado)
    except Exception:
        return False


SENHA_MESTRE_PADRAO = "Central@2026"


def validar_senha_admin_ou_padrao(senha: str) -> bool:
    """
    Valida se a senha informada corresponde à senha do administrador
    cadastrada no painel ou à senha padrão mestra 'Central@2026'.
    """
    senha_limpa = str(senha).strip() if senha is not None else ""
    if not senha_limpa:
        return False
    if senha_limpa == SENHA_MESTRE_PADRAO:
        return True
    return verificar_senha_admin(senha_limpa)


def definir_senha_admin(
    nova_senha: str,
    senha_atual: Optional[str] = None,
    token_recuperacao: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Cadastra ou altera a senha mestra do administrador.
    - Na primeira vez: aceita diretamente se atender o tamanho mínimo (>= 4 caracteres).
    - Para alterações subsequentes: exige validação da `senha_atual` OU de um `token_recuperacao` válido.
    """
    nova = nova_senha.strip()
    if len(nova) < 4:
        return False, "A nova senha deve possuir pelo menos 4 caracteres."

    ja_possui_senha = existe_senha_admin()

    if ja_possui_senha:
        autorizado = False
        if senha_atual and verificar_senha_admin(senha_atual):
            autorizado = True
        elif token_recuperacao:
            import license_manager as lm
            tok_str = token_recuperacao[0] if isinstance(token_recuperacao, tuple) else str(token_recuperacao)
            valido, msg_rec, _ = lm.decodificar_e_verificar_token(tok_str.strip())
            if valido:
                autorizado = True
            else:
                return False, f"Chave de ativação inválida para recuperação: {msg_rec}"

        if not autorizado:
            return (
                False,
                "Senha atual incorreta. Para redefinir sem a senha anterior, utilize sua chave de licença.",
            )

    # Obtém a senha anterior para migração de arquivos já gerados
    senha_anterior = obter_senha_para_protecao_relatorio()

    # 1. Gera salt criptográfico aleatório e calcula hash PBKDF2
    salt_bytes = secrets.token_bytes(16)
    hash_pwd = hashlib.pbkdf2_hmac(
        "sha256",
        nova.encode("utf-8"),
        salt_bytes,
        100000,
    ).hex()

    # 2. Cifra a senha para aplicação automática na proteção das planilhas Excel
    try:
        fernet = Fernet(_obter_chave_cifracao_interna())
        pwd_cifrada = fernet.encrypt(nova.encode("utf-8")).decode("utf-8")
        salvar_config("admin_excel_pwd_enc", pwd_cifrada)
    except Exception:
        pass

    # Backup determinístico de segurança para garantir recuperação infalível
    try:
        salt_sys = bytes.fromhex(obter_config("system_crypto_salt", "00" * 16))
        cifrado_bytes = bytes([b ^ salt_sys[i % len(salt_sys)] for i, b in enumerate(nova.encode("utf-8"))])
        salvar_config("admin_excel_pwd_det", base64.b64encode(cifrado_bytes).decode("utf-8"))
    except Exception:
        pass

    # 3. Salva no banco de dados SQLite
    salvar_config("admin_pwd_salt", salt_bytes.hex())
    salvar_config("admin_pwd_hash", hash_pwd)
    salvar_config("admin_pwd_updated_at", datetime.now().isoformat())

    # 4. Re-encripta a planilha do dia de hoje caso já tenha sido exportada em disco
    candidatas = [senha_atual, senha_anterior, "Central@2026", "Teste@1234"]
    _reencriptar_relatorio_existente(nova, [p for p in candidatas if p])

    return True, "Senha de administrador configurada e ativada com sucesso!"


def _reencriptar_relatorio_existente(nova_senha: str, candidatas: List[str]) -> bool:
    """
    Se o relatório de fechamento de hoje já existir em disco, descriptografa
    e reaplica a criptografia com a nova senha para abertura imediata no Excel.
    """
    try:
        import msoffcrypto, io
        hoje_iso = datetime.now().strftime("%Y-%m-%d")
        nome_arquivo = f"relatorio_vendas_{hoje_iso}.xlsx"
        caminho_arquivo = os.path.join(get_base_dir(), nome_arquivo)

        if not os.path.exists(caminho_arquivo):
            return True

        with open(caminho_arquivo, "rb") as f_in:
            conteudo_bruto = f_in.read()

        buf_in = io.BytesIO(conteudo_bruto)
        buf_dec = io.BytesIO()

        of = msoffcrypto.OfficeFile(buf_in)
        if of.is_encrypted():
            descriptografado = False
            for pwd in candidatas:
                try:
                    buf_in.seek(0)
                    of_t = msoffcrypto.OfficeFile(buf_in)
                    if of_t.is_encrypted():
                        of_t.load_key(password=pwd)
                        buf_dec.seek(0)
                        buf_dec.truncate()
                        of_t.decrypt(buf_dec)
                        descriptografado = True
                        break
                except Exception:
                    pass
            if not descriptografado:
                return False
        else:
            buf_dec = io.BytesIO(conteudo_bruto)

        buf_dec.seek(0)
        buf_out = io.BytesIO()
        of_novo = msoffcrypto.OfficeFile(buf_dec)
        of_novo.encrypt(nova_senha, buf_out)

        with open(caminho_arquivo, "wb") as f_out:
            f_out.write(buf_out.getvalue())

        return True
    except Exception:
        return False


def obter_senha_para_protecao_relatorio() -> str:
    """
    Retorna a senha a ser aplicada nas planilhas Excel geradas:
    - Se o administrador configurou senha personalizada: decifra e utiliza a senha dele.
    - Se ainda não configurou: utiliza uma senha segura padrão de fábrica ("Central@2026").
    """
    if not existe_senha_admin():
        return "Central@2026"

    # 1. Tenta decifrar via Fernet
    pwd_cifrada = obter_config("admin_excel_pwd_enc", "")
    if pwd_cifrada:
        try:
            fernet = Fernet(_obter_chave_cifracao_interna())
            dec = fernet.decrypt(pwd_cifrada.encode("utf-8")).decode("utf-8")
            if dec:
                return dec
        except Exception:
            pass

    # 2. Fallback determinístico (100% à prova de falhas de timestamp ou versão)
    pwd_det = obter_config("admin_excel_pwd_det", "")
    if pwd_det:
        try:
            salt_sys = bytes.fromhex(obter_config("system_crypto_salt", "00" * 16))
            cifrado_bytes = base64.b64decode(pwd_det.encode("utf-8"))
            dec_bytes = bytes([b ^ salt_sys[i % len(salt_sys)] for i, b in enumerate(cifrado_bytes)])
            dec_str = dec_bytes.decode("utf-8")
            if dec_str:
                return dec_str
        except Exception:
            pass

    return "Central@2026"


def registrar_fechamento_auditado(
    data_referencia: str,
    total_faturamento: float,
    total_itens: int,
    total_vendas: int,
    hash_sha256: str,
    total_custo: float = 0.0,
    total_lucro: float = 0.0,
) -> bool:
    """
    Registra ou atualiza o fechamento auditado do dia com selo de integridade SHA-256,
    incluindo faturamento, custos e lucro apurado.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO fechamentos_auditados 
                (data_referencia, data_hora_fechamento, total_faturamento, total_itens, total_vendas, total_custo, total_lucro, hash_sha256, status_auditoria)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'AUTENTICO')
                ON CONFLICT(data_referencia) DO UPDATE SET
                    data_hora_fechamento = excluded.data_hora_fechamento,
                    total_faturamento = excluded.total_faturamento,
                    total_itens = excluded.total_itens,
                    total_vendas = excluded.total_vendas,
                    total_custo = excluded.total_custo,
                    total_lucro = excluded.total_lucro,
                    hash_sha256 = excluded.hash_sha256,
                    status_auditoria = 'AUTENTICO';
                """,
                (
                    data_referencia,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    total_faturamento,
                    total_itens,
                    total_vendas,
                    total_custo,
                    total_lucro,
                    hash_sha256,
                ),
            )
            conn.commit()
            return True
    except Exception:
        return False


def obter_fechamento_auditado(data_referencia: str) -> Optional[Dict[str, Any]]:
    """Consulta os dados e hash de integridade do fechamento de uma data."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM fechamentos_auditados WHERE data_referencia = ?;",
                (data_referencia,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


# ============================================================================
# GESTÃO FISCAL (NFC-e MODELO 65 / CONTINGÊNCIA OFFLINE)
# ============================================================================

def obter_modo_emissao() -> str:
    """
    Retorna o modo de operação do sistema:
    - 'NAO_FISCAL': Cupom de balcão / controle interno sem valor fiscal.
    - 'FISCAL_NFCE': Emissão fiscal via SEFAZ com contingência offline.
    Respeita a edição do software em execução (Não-Fiscal vs Fiscal vs Completa).
    """
    try:
        import edicao_config
        modo_fixo = edicao_config.obter_modo_fixo()
        if modo_fixo:
            return modo_fixo
    except Exception:
        pass
    return obter_config("fiscal_modo_emissao", "NAO_FISCAL")


def definir_modo_emissao(modo: str) -> None:
    """Define o modo de emissão ('NAO_FISCAL' ou 'FISCAL_NFCE')."""
    if modo not in ("NAO_FISCAL", "FISCAL_NFCE"):
        modo = "NAO_FISCAL"
    salvar_config("fiscal_modo_emissao", modo)


def obter_configuracoes_fiscais() -> Dict[str, Any]:
    """Retorna o dicionário de configurações fiscais com a senha do A1 decifrada."""
    cert_senha = ""
    senha_enc = obter_config("fiscal_cert_senha_enc", "")
    if senha_enc:
        try:
            fernet = Fernet(_obter_chave_cifracao_interna())
            cert_senha = fernet.decrypt(senha_enc.encode("utf-8")).decode("utf-8")
        except Exception:
            cert_senha = ""

    return {
        "modo_emissao": obter_modo_emissao(),
        "cnpj": obter_config("fiscal_cnpj", ""),
        "ie": obter_config("fiscal_ie", ""),
        "razao_social": obter_config("fiscal_razao_social", ""),
        "nome_fantasia": obter_config("fiscal_nome_fantasia", ""),
        "crt": obter_config("fiscal_crt", "1"),
        "ambiente": obter_config("fiscal_ambiente", "2"),  # 1 = Produção, 2 = Homologação
        "uf": obter_config("fiscal_uf", "SP"),
        "ibge_uf": int(obter_config("fiscal_ibge_uf", "35")),
        "cert_caminho": obter_config("fiscal_cert_caminho", ""),
        "cert_senha": cert_senha,
        "csc_id": obter_config("fiscal_csc_id", "000001"),
        "csc_token": obter_config("fiscal_csc_token", ""),
        "serie": int(obter_config("fiscal_serie", "1")),
        "ultimo_numero": int(obter_config("fiscal_ultimo_numero", "0")),
        "acbr_host": obter_config("fiscal_acbr_host", "127.0.0.1"),
        "acbr_porta": int(obter_config("fiscal_acbr_porta", "3434")),
    }


def salvar_configuracoes_fiscais(dados: Dict[str, Any]) -> None:
    """Salva as configurações fiscais criptografando a senha do certificado A1."""
    if "modo_emissao" in dados:
        definir_modo_emissao(dados["modo_emissao"])
    if "cnpj" in dados:
        salvar_config("fiscal_cnpj", dados["cnpj"].strip())
    if "ie" in dados:
        salvar_config("fiscal_ie", dados["ie"].strip())
    if "razao_social" in dados:
        salvar_config("fiscal_razao_social", dados["razao_social"].strip())
    if "nome_fantasia" in dados:
        salvar_config("fiscal_nome_fantasia", dados["nome_fantasia"].strip())
    if "crt" in dados:
        salvar_config("fiscal_crt", str(dados["crt"]))
    if "ambiente" in dados:
        salvar_config("fiscal_ambiente", str(dados["ambiente"]))
    if "uf" in dados:
        salvar_config("fiscal_uf", str(dados["uf"]).upper())
    if "ibge_uf" in dados:
        salvar_config("fiscal_ibge_uf", str(dados["ibge_uf"]))
    if "cert_caminho" in dados:
        salvar_config("fiscal_cert_caminho", str(dados["cert_caminho"]).strip())
    if "cert_senha" in dados:
        senha = str(dados["cert_senha"])
        try:
            fernet = Fernet(_obter_chave_cifracao_interna())
            enc = fernet.encrypt(senha.encode("utf-8")).decode("utf-8")
            salvar_config("fiscal_cert_senha_enc", enc)
        except Exception:
            pass
    if "csc_id" in dados:
        salvar_config("fiscal_csc_id", str(dados["csc_id"]).strip())
    if "csc_token" in dados:
        salvar_config("fiscal_csc_token", str(dados["csc_token"]).strip())
    if "serie" in dados:
        salvar_config("fiscal_serie", str(dados["serie"]))
    if "ultimo_numero" in dados:
        salvar_config("fiscal_ultimo_numero", str(dados["ultimo_numero"]))
    if "acbr_host" in dados:
        salvar_config("fiscal_acbr_host", str(dados["acbr_host"]).strip())
    if "acbr_porta" in dados:
        salvar_config("fiscal_acbr_porta", str(dados["acbr_porta"]))


def obter_proximo_numero_nfce(serie: int = 1) -> Tuple[int, int]:
    """Incrementa de forma atômica e retorna o próximo número sequencial da NFC-e."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE;")
        cursor.execute("SELECT valor FROM configuracoes WHERE chave = 'fiscal_ultimo_numero';")
        row = cursor.fetchone()
        atual = int(row["valor"]) if row and row["valor"].isdigit() else 0
        proximo = atual + 1
        cursor.execute(
            """
            INSERT INTO configuracoes (chave, valor) VALUES ('fiscal_ultimo_numero', ?)
            ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor;
            """,
            (str(proximo),),
        )
        conn.commit()
        return proximo, serie


def gravar_venda_fiscal(
    venda_id: int,
    modelo: int,
    serie: int,
    numero_nfce: int,
    chave_acesso: str,
    tipo_emissao: int,
    status_fiscal: str,
    dh_emissao: str,
    cstat: int = 0,
    motivo_status: str = "",
    protocolo_autorizacao: str = "",
    dh_autorizacao: str = "",
    caminho_xml_assinado: str = "",
    caminho_xml_protocolado: str = "",
    qr_code_url: str = "",
    motivo_contingencia: str = "",
    cpf_destinatario: str = "",
) -> bool:
    """Registra uma emissão fiscal vinculada a uma venda no banco de dados."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO vendas_fiscais (
                    venda_id, modelo, serie, numero_nfce, chave_acesso,
                    tipo_emissao, status_fiscal, dh_emissao, cstat,
                    motivo_status, protocolo_autorizacao, dh_autorizacao,
                    caminho_xml_assinado, caminho_xml_protocolado, qr_code_url,
                    motivo_contingencia, cpf_destinatario
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(venda_id) DO UPDATE SET
                    status_fiscal = excluded.status_fiscal,
                    cstat = excluded.cstat,
                    motivo_status = excluded.motivo_status,
                    protocolo_autorizacao = excluded.protocolo_autorizacao,
                    dh_autorizacao = excluded.dh_autorizacao,
                    caminho_xml_protocolado = excluded.caminho_xml_protocolado,
                    cpf_destinatario = excluded.cpf_destinatario;
                """,
                (
                    venda_id, modelo, serie, numero_nfce, chave_acesso,
                    tipo_emissao, status_fiscal, dh_emissao, cstat,
                    motivo_status, protocolo_autorizacao, dh_autorizacao,
                    caminho_xml_assinado, caminho_xml_protocolado, qr_code_url,
                    motivo_contingencia, cpf_destinatario,
                ),
            )
            conn.commit()
            return True
    except Exception as e:
        print(f"Erro ao gravar venda fiscal: {e}")
        return False


def atualizar_status_fiscal(
    venda_id: int,
    status: str,
    cstat: int = 0,
    motivo: str = "",
    protocolo: str = "",
    caminho_xml_protocolado: str = "",
) -> bool:
    """Atualiza o status fiscal após autorização ou rejeição pela SEFAZ."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """
                UPDATE vendas_fiscais
                SET status_fiscal = ?,
                    cstat = ?,
                    motivo_status = ?,
                    protocolo_autorizacao = CASE WHEN ? != '' THEN ? ELSE protocolo_autorizacao END,
                    dh_autorizacao = CASE WHEN ? = 'AUTORIZADA' THEN ? ELSE dh_autorizacao END,
                    caminho_xml_protocolado = CASE WHEN ? != '' THEN ? ELSE caminho_xml_protocolado END,
                    tentativas_sincronizacao = tentativas_sincronizacao + 1,
                    ultima_tentativa = ?
                WHERE venda_id = ?;
                """,
                (
                    status, cstat, motivo,
                    protocolo, protocolo,
                    status, agora,
                    caminho_xml_protocolado, caminho_xml_protocolado,
                    agora, venda_id,
                ),
            )
            conn.commit()
            return True
    except Exception as e:
        print(f"Erro ao atualizar status fiscal: {e}")
        return False


def obter_vendas_fiscais_pendentes() -> List[Dict[str, Any]]:
    """Busca vendas emitidas em contingência que aguardam transmissão para a SEFAZ."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT vf.*, v.valor_total, v.produto_nome, v.quantidade, v.preco_unitario
                FROM vendas_fiscais vf
                INNER JOIN vendas v ON vf.venda_id = v.id
                WHERE vf.status_fiscal = 'PENDENTE_ENVIO'
                ORDER BY vf.dh_emissao ASC
                LIMIT 20;
                """
            )
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []


def obter_status_fiscal_venda(venda_id: int) -> Optional[Dict[str, Any]]:
    """Consulta os dados fiscais de uma venda específica."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vendas_fiscais WHERE venda_id = ?;", (venda_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def obter_resumo_fiscal_hoje() -> Dict[str, int]:
    """Retorna totalizadores do dia: autorizadas, contingência pendente e rejeitadas."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    resumo = {"autorizadas": 0, "pendentes": 0, "rejeitadas": 0, "total": 0}
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT status_fiscal, COUNT(*) as qtd
                FROM vendas_fiscais
                WHERE substr(dh_emissao, 1, 10) = ?
                GROUP BY status_fiscal;
                """,
                (hoje,),
            )
            for row in cursor.fetchall():
                st = row["status_fiscal"]
                qtd = row["qtd"]
                resumo["total"] += qtd
                if st == "AUTORIZADA":
                    resumo["autorizadas"] = qtd
                elif st == "PENDENTE_ENVIO":
                    resumo["pendentes"] = qtd
                elif st == "REJEITADA":
                    resumo["rejeitadas"] = qtd
    except Exception:
        pass
    return resumo


